import logging
from urllib.parse import urldefrag

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, TemplateView

from Projet_veto import throttling
from Projet_veto.emailing import envoyer_email
from . import accessibilite
from .forms import InvitationFoyerForm, PremierUtilisateurForm
from .models import Foyer, InvitationFoyer, MembreFoyer, PreferenceAccessibilite

logger = logging.getLogger(__name__)


def robots_txt(request):
    """Interdit le crawl à tout robot respectueux de robots.txt : outil
    personnel non destiné à être indexé ou aspiré (cf. NoIndexMiddleware,
    qui couvre en plus les robots qui ne lisent que les en-têtes HTTP)."""
    contenu = "User-agent: *\nDisallow: /\n"
    return HttpResponse(contenu, content_type='text/plain')


class AccueilView(TemplateView):
    """Page d'accueil publique de l'application : présentation, accès pour
    les utilisateurs existants (connexion), création du tout premier compte
    tant qu'aucun utilisateur n'existe encore, informations légales et
    déclaration d'accessibilité."""

    template_name = 'accueil/accueil.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['premier_lancement'] = not get_user_model().objects.exists()
        context['formulaire_connexion'] = AuthenticationForm()
        context['editeur'] = {
            'nom': settings.EDITEUR_NOM,
            'adresse': settings.EDITEUR_ADRESSE,
            'email': settings.EDITEUR_EMAIL,
            'telephone': settings.EDITEUR_TELEPHONE,
        }
        context['hebergeur'] = {
            'nom': settings.HEBERGEUR_NOM,
            'adresse': settings.HEBERGEUR_ADRESSE,
        }
        return context


class PreferencesVisiteurMixin:
    """Pour les vues de création de compte : reprend les réglages que le
    visiteur a déjà faits dans le panneau accessibilité avant d'avoir un
    compte (cookie, cf. accueil/accessibilite.py), au lieu de les lui faire
    perdre à la connexion — les cases du formulaire en sont précochées (il
    peut toujours les décocher), et « Très grand » est conservé."""

    def get_initial(self):
        initial = super().get_initial()
        preferences = accessibilite.lire(self.request)
        initial.update({champ: preferences[champ] for champ in accessibilite.CHAMPS_BOOLEENS})
        initial['texte_agrandi'] = preferences['taille_texte'] != PreferenceAccessibilite.Taille.NORMAL
        return initial

    def enregistrer_preferences(self, form):
        """À appeler avant login() : une fois connecté, accessibilite.lire()
        ne regarde plus le cookie du visiteur."""
        form.creer_preferences_accessibilite(
            self.object, taille_visiteur=accessibilite.lire(self.request)['taille_texte'],
        )


class PremierUtilisateurCreateView(PreferencesVisiteurMixin, CreateView):
    """Création du tout premier compte de l'application, depuis la page
    d'accueil (cf. AccueilView) — un raccourci à `createsuperuser` en ligne
    de commande pour un premier lancement. Volontairement bloquée dès qu'un
    compte existe déjà : sans ce garde-fou, ce serait une création de compte
    ouverte à n'importe quel visiteur non connecté."""

    form_class = PremierUtilisateurForm
    template_name = 'accueil/premier_compte.html'
    success_url = reverse_lazy('animaux:animal_list')

    def dispatch(self, request, *args, **kwargs):
        if get_user_model().objects.exists():
            messages.warning(
                request,
                "Un compte existe déjà sur cette installation : connecte-toi plutôt depuis la page d'accueil.",
            )
            return redirect('accueil:accueil')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        reponse = super().form_valid(form)
        # Premier compte de l'installation : administrateur de plein droit
        # (accès à /admin/ compris), pour pouvoir ensuite créer les comptes
        # suivants et gérer les catalogues sans repasser par le shell.
        self.object.is_staff = True
        self.object.is_superuser = True
        self.object.save(update_fields=['is_staff', 'is_superuser'])
        self.enregistrer_preferences(form)
        login(self.request, self.object)
        messages.success(self.request, f"Bienvenue {self.object.username}, ton compte administrateur a été créé.")
        return reponse


class InscriptionCreateView(PreferencesVisiteurMixin, CreateView):
    """Création d'un compte utilisateur « classique » (par opposition au tout
    premier compte, administrateur — cf. PremierUtilisateurCreateView) :
    ouverte à tout visiteur, sans validation de l'Admin. Par défaut, chaque
    compte a ses propres animaux/consultations/factures/documents, invisibles
    des autres comptes (cf. Animal.utilisateur et les querysets filtrés dans
    les vues des apps animaux/vaccins/consultations/factures/documents, tous
    élargis via accueil.utils.comptes_accessibles) — un nouveau compte
    auto-créé n'obtient donc jamais accès aux données de quelqu'un d'autre,
    juste son propre espace vide au départ, sauf s'il accepte ensuite une
    invitation à rejoindre un foyer partagé (cf. accueil.models.Foyer)."""

    form_class = PremierUtilisateurForm
    template_name = 'accueil/inscription.html'
    success_url = reverse_lazy('animaux:animal_list')

    def post(self, request, *args, **kwargs):
        # Limite à 3 tentatives (réussies ou non) par adresse — 15 min la 1ère
        # fois, 1h en cas de récidive, définitivement à partir de la 3e (cf.
        # Projet_veto.throttling) — pas de remise à zéro sur succès,
        # contrairement à la connexion : un compte créé n'indique pas ici
        # qu'il ne s'agit pas d'un robot.
        if throttling.est_bloque('inscription', request):
            messages.error(request, throttling.message_blocage('inscription', request))
            return redirect('accueil:inscription')
        throttling.enregistrer_tentative('inscription', request)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        reponse = super().form_valid(form)
        self.enregistrer_preferences(form)
        login(self.request, self.object)
        messages.success(self.request, f"Bienvenue {self.object.username}, ton compte a été créé.")
        return reponse


@require_POST
def mettre_a_jour_preferences_accessibilite(request):
    """Enregistre l'état du panneau accessibilité (cf.
    templates/partials/panneau_accessibilite.html), envoyé en entier à chaque
    changement d'un de ses réglages, puis renvoie vers la page d'où il vient :
    c'est en la réaffichant que le serveur applique les nouveaux réglages (cf.
    Projet_veto.context_processors). Ouvert aux visiteurs non connectés, dont
    les réglages vont dans un cookie (cf. accueil/accessibilite.py) : rien
    d'autre que leurs propres préférences d'affichage n'y est modifiable."""
    preferences = accessibilite.depuis_formulaire(request.POST)

    # Page à réafficher : celle où se trouve le visiteur (htmx la transmet), à
    # défaut celle où le panneau a été rendu. Jamais une adresse externe.
    suite = request.headers.get('HX-Current-URL') or request.POST.get('suite', '')
    suite = urldefrag(suite).url
    if not url_has_allowed_host_and_scheme(suite, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        suite = reverse('accueil:accueil')

    if request.headers.get('HX-Request'):
        reponse = HttpResponse(status=204)
        reponse['HX-Redirect'] = suite
    else:
        reponse = redirect(suite)
    accessibilite.enregistrer(request, reponse, preferences)
    return reponse


def _foyer_ou_creation(utilisateur):
    """Foyer du compte connecté, créé à la volée (avec ce compte comme membre
    fondateur, `invite_par=None`) s'il n'en a pas encore — la toute première
    invitation envoyée par un compte solo fait ainsi automatiquement de lui
    le fondateur de son foyer."""
    try:
        return utilisateur.membre_foyer.foyer
    except MembreFoyer.DoesNotExist:
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=utilisateur, foyer=foyer, invite_par=None)
        return foyer


class PartageCompteView(LoginRequiredMixin, TemplateView):
    """Page de gestion du partage de compte (« foyer ») : membres actuels,
    invitations envoyées/reçues en attente, formulaire d'invitation."""

    template_name = 'accueil/partage_compte.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        utilisateur = self.request.user
        membre = MembreFoyer.objects.filter(utilisateur=utilisateur).select_related('foyer', 'invite_par').first()
        context['membre_foyer'] = membre
        # Seul le fondateur du foyer voit les boutons « Retirer ».
        fondateur = membre.foyer.membre_fondateur() if membre else None
        context['membre_fondateur'] = fondateur
        context['est_fondateur'] = bool(membre and fondateur and fondateur.pk == membre.pk)
        if membre:
            context['autres_membres'] = (
                MembreFoyer.objects.filter(foyer=membre.foyer)
                .exclude(utilisateur=utilisateur)
                .select_related('utilisateur', 'invite_par')
            )
        else:
            context['autres_membres'] = MembreFoyer.objects.none()
        context['invitations_envoyees'] = InvitationFoyer.objects.filter(
            invite_par=utilisateur, statut=InvitationFoyer.Statut.EN_ATTENTE,
        )
        # Par compte invité (résolu à l'envoi), jamais par email : celui-ci
        # n'est pas vérifié, un autre compte pourrait déclarer le même.
        context['invitations_recues'] = InvitationFoyer.objects.filter(
            invite=utilisateur, statut=InvitationFoyer.Statut.EN_ATTENTE,
        ).select_related('invite_par')
        context['formulaire_invitation'] = InvitationFoyerForm(utilisateur=utilisateur)
        return context


@login_required
@require_POST
def envoyer_invitation_foyer(request):
    """Envoie une invitation à partager le compte connecté avec un autre
    compte existant (cf. InvitationFoyerForm) — crée le foyer du compte
    connecté à la volée s'il n'en a pas encore (membre fondateur)."""
    form = InvitationFoyerForm(request.POST, utilisateur=request.user)
    if not form.is_valid():
        for erreurs in form.errors.values():
            for erreur in erreurs:
                messages.error(request, erreur)
        return redirect('accueil:partage_compte')

    foyer = _foyer_ou_creation(request.user)
    InvitationFoyer.objects.create(
        foyer=foyer, invite_par=request.user, email_invite=form.cleaned_data['email'], invite=form.invite,
    )

    # Pas de lien GET direct vers l'acceptation/le refus (actions en POST,
    # protégées CSRF) : le lien mène à la page de gestion du partage, où
    # l'invitation apparaît avec ses deux boutons une fois connecté.
    lien = request.build_absolute_uri(reverse('accueil:partage_compte'))
    # Notification dans l'application d'abord : l'invité est ainsi prévenu
    # même si l'email ne part pas.
    from notifications.models import Notification
    Notification.objects.create(
        utilisateur=form.invite,
        type='INVITATION_FOYER',
        titre="Invitation à partager un compte",
        message=f"{request.user.username} t'invite à partager l'accès à son compte.",
        lien=lien,
    )

    try:
        envoyer_email(
            'invitation_foyer',
            {'nom_invitant': request.user.username, 'lien': lien},
            "Invitation à partager un compte - Suivi Vétérinaire",
            [form.cleaned_data['email']],
        )
    except Exception:
        # Serveur SMTP injoignable, destinataire refusé... : l'invitation est
        # déjà enregistrée et reste acceptable, pas de page d'erreur.
        logger.exception("Échec de l'envoi de l'email d'invitation de foyer")
        messages.warning(
            request,
            "Invitation enregistrée, mais l'email n'a pas pu être envoyé : "
            "la personne la verra en se connectant.",
        )
        return redirect('accueil:partage_compte')

    messages.success(request, f"Invitation envoyée à {form.cleaned_data['email']}.")
    return redirect('accueil:partage_compte')


def _invitation_pour_repondre(request, token):
    """Invitation en attente adressée au compte connecté — identifié par la
    clé `invite` posée à l'envoi, pas par son email (ni vérifié ni unique :
    un compte créé avec l'adresse de l'invité pouvait répondre à sa place)."""
    return get_object_or_404(
        InvitationFoyer, token=token, statut=InvitationFoyer.Statut.EN_ATTENTE, invite=request.user,
    )


def _annuler_invitations_de(membre):
    """Annule les invitations encore en attente envoyées par un membre qui
    sort du foyer : elles ne doivent plus pouvoir faire entrer quelqu'un dans
    un foyer que leur auteur a quitté."""
    InvitationFoyer.objects.filter(
        foyer=membre.foyer, invite_par=membre.utilisateur, statut=InvitationFoyer.Statut.EN_ATTENTE,
    ).update(statut=InvitationFoyer.Statut.ANNULEE, date_reponse=timezone.now())


@login_required
@require_POST
def accepter_invitation_foyer(request, token):
    invitation = _invitation_pour_repondre(request, token)
    # Garde-fou : l'auteur de l'invitation doit toujours être membre du foyer
    # (quitter_foyer/retirer_membre_foyer annulent déjà ses invitations).
    if not MembreFoyer.objects.filter(utilisateur=invitation.invite_par, foyer=invitation.foyer).exists():
        invitation.statut = InvitationFoyer.Statut.ANNULEE
        invitation.date_reponse = timezone.now()
        invitation.save(update_fields=['statut', 'date_reponse'])
        messages.error(request, "Cette invitation n'est plus valable : son auteur ne fait plus partie du foyer.")
        return redirect('accueil:partage_compte')
    try:
        with transaction.atomic():
            # Le savepoint créé par atomic() permet à IntegrityError d'être
            # rattrapée proprement (sous PostgreSQL, une erreur non isolée
            # dans un savepoint avorte toute la transaction en cours — gênant
            # notamment sous TestCase, qui enveloppe chaque test dans une
            # transaction).
            # Un foyer où l'on est seul (créé par une invitation envoyée
            # puis restée sans suite) ne partage rien : on le supprime pour
            # rejoindre celui-ci — la cascade emporte ses invitations encore
            # en attente, qui mèneraient sinon à un foyer vide.
            solo = MembreFoyer.objects.filter(utilisateur=request.user).first()
            if (
                solo and solo.foyer_id != invitation.foyer_id
                and not MembreFoyer.objects.filter(foyer=solo.foyer_id).exclude(pk=solo.pk).exists()
            ):
                Foyer.objects.filter(pk=solo.foyer_id).delete()
            MembreFoyer.objects.create(
                utilisateur=request.user, foyer=invitation.foyer, invite_par=invitation.invite_par,
            )
    except IntegrityError:
        messages.error(request, "Tu appartiens déjà à un foyer : quitte-le avant d'en rejoindre un autre.")
        return redirect('accueil:partage_compte')
    invitation.statut = InvitationFoyer.Statut.ACCEPTEE
    invitation.date_reponse = timezone.now()
    invitation.save(update_fields=['statut', 'date_reponse'])
    messages.success(request, f"Tu partages désormais le compte de {invitation.invite_par.username}.")
    return redirect('accueil:partage_compte')


@login_required
@require_POST
def refuser_invitation_foyer(request, token):
    invitation = _invitation_pour_repondre(request, token)
    invitation.statut = InvitationFoyer.Statut.REFUSEE
    invitation.date_reponse = timezone.now()
    invitation.save(update_fields=['statut', 'date_reponse'])
    messages.info(request, "Invitation refusée.")
    return redirect('accueil:partage_compte')


@login_required
@require_POST
def annuler_invitation_foyer(request, pk):
    """Annule une invitation encore en attente — réservé à celui qui l'a
    envoyée (cf. InvitationFoyer.invite_par)."""
    invitation = get_object_or_404(
        InvitationFoyer, pk=pk, invite_par=request.user, statut=InvitationFoyer.Statut.EN_ATTENTE,
    )
    invitation.statut = InvitationFoyer.Statut.ANNULEE
    invitation.date_reponse = timezone.now()
    invitation.save(update_fields=['statut', 'date_reponse'])
    messages.info(request, "Invitation annulée.")
    return redirect('accueil:partage_compte')


@login_required
@require_POST
def retirer_membre_foyer(request, pk):
    """Retire un membre du foyer — réservé au fondateur du foyer (cf.
    Foyer.membre_fondateur), qu'il ait lui-même invité ce membre ou non :
    avoir invité quelqu'un ne donne aucun droit de le retirer. Le fondateur
    ne peut être retiré par personne (lui seul retire, et pas lui-même par
    cette action) ; il peut seulement quitter le foyer (cf. quitter_foyer),
    le plus ancien membre restant devenant alors fondateur."""
    moi = get_object_or_404(MembreFoyer.objects.select_related('foyer'), utilisateur=request.user)
    # Dans le foyer du compte connecté seulement — jamais un membre d'un
    # autre foyer, même en devinant sa clé.
    membre = get_object_or_404(MembreFoyer, pk=pk, foyer=moi.foyer)
    if membre.pk == moi.pk or not moi.est_fondateur():
        raise Http404
    nom = membre.utilisateur.username
    _annuler_invitations_de(membre)
    membre.delete()
    messages.info(request, f"{nom} a été retiré du foyer.")
    return redirect('accueil:partage_compte')


@login_required
@require_POST
def quitter_foyer(request):
    """Un membre peut toujours se retirer lui-même du foyer, à tout moment,
    sans condition (contrairement à retirer_membre_foyer) — fondateur
    compris : le plus ancien membre restant devient alors fondateur, sans
    rien à faire ici (cf. Foyer.membre_fondateur)."""
    membre = get_object_or_404(MembreFoyer, utilisateur=request.user)
    _annuler_invitations_de(membre)
    membre.delete()
    messages.info(request, "Tu as quitté le foyer partagé.")
    return redirect('accueil:partage_compte')
