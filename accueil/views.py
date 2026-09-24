from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, TemplateView

from Projet_veto import throttling
from Projet_veto.emailing import envoyer_email
from .forms import InvitationFoyerForm, PremierUtilisateurForm
from .models import Foyer, InvitationFoyer, MembreFoyer, PreferenceAccessibilite


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


class PremierUtilisateurCreateView(CreateView):
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
        form.creer_preferences_accessibilite(self.object)
        login(self.request, self.object)
        messages.success(self.request, f"Bienvenue {self.object.username}, ton compte administrateur a été créé.")
        return reponse


class InscriptionCreateView(CreateView):
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
        form.creer_preferences_accessibilite(self.object)
        login(self.request, self.object)
        messages.success(self.request, f"Bienvenue {self.object.username}, ton compte a été créé.")
        return reponse


@login_required
@require_POST
def mettre_a_jour_preferences_accessibilite(request):
    """Enregistre un réglage du panneau accessibilité (cf.
    templates/partials/panneau_accessibilite.html et static/js/accessibilite.js)
    pour le compte connecté, afin qu'il soit réappliqué à chaque connexion —
    sur n'importe quel navigateur — plutôt que mémorisé uniquement dans le
    navigateur courant (cf. PreferenceAccessibilite.classes_css(), utilisée
    au rendu de chaque page par Projet_veto.context_processors)."""
    prefs, _ = PreferenceAccessibilite.objects.get_or_create(utilisateur=request.user)

    champ = request.POST.get('champ')
    valeur = request.POST.get('valeur')

    if champ == 'taille_texte':
        if valeur not in PreferenceAccessibilite.Taille.values:
            return JsonResponse({'success': False, 'erreur': 'valeur invalide'}, status=400)
        prefs.taille_texte = valeur
    elif champ in ('contraste_eleve', 'police_lisible', 'reduire_animations', 'palette_daltonisme', 'mode_sombre'):
        setattr(prefs, champ, valeur == '1')
    else:
        return JsonResponse({'success': False, 'erreur': 'champ inconnu'}, status=400)

    prefs.save()
    return JsonResponse({'success': True})


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
        context['invitations_recues'] = (
            InvitationFoyer.objects.filter(
                email_invite__iexact=utilisateur.email, statut=InvitationFoyer.Statut.EN_ATTENTE,
            )
            if utilisateur.email else InvitationFoyer.objects.none()
        )
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
    invitation = InvitationFoyer.objects.create(
        foyer=foyer, invite_par=request.user, email_invite=form.cleaned_data['email'],
    )

    # Pas de lien GET direct vers l'acceptation/le refus (actions en POST,
    # protégées CSRF) : le lien mène à la page de gestion du partage, où
    # l'invitation apparaît avec ses deux boutons une fois connecté.
    lien = request.build_absolute_uri(reverse('accueil:partage_compte'))
    envoyer_email(
        'invitation_foyer',
        {'nom_invitant': request.user.username, 'lien': lien},
        "Invitation à partager un compte - Suivi Vétérinaire",
        [form.cleaned_data['email']],
    )

    from notifications.models import Notification
    Notification.objects.create(
        utilisateur=form.invite,
        type='INVITATION_FOYER',
        titre="Invitation à partager un compte",
        message=f"{request.user.username} t'invite à partager l'accès à son compte.",
        lien=lien,
    )

    messages.success(request, f"Invitation envoyée à {form.cleaned_data['email']}.")
    return redirect('accueil:partage_compte')


def _invitation_pour_repondre(request, token):
    invitation = get_object_or_404(InvitationFoyer, token=token, statut=InvitationFoyer.Statut.EN_ATTENTE)
    if not request.user.email or invitation.email_invite.lower() != request.user.email.lower():
        raise Http404
    return invitation


@login_required
@require_POST
def accepter_invitation_foyer(request, token):
    invitation = _invitation_pour_repondre(request, token)
    try:
        with transaction.atomic():
            # Le savepoint créé par atomic() permet à IntegrityError d'être
            # rattrapée proprement (sous PostgreSQL, une erreur non isolée
            # dans un savepoint avorte toute la transaction en cours — gênant
            # notamment sous TestCase, qui enveloppe chaque test dans une
            # transaction).
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
    """Retire un membre du foyer — réservé à celui qui l'a invité (cf.
    MembreFoyer.invite_par) ; le membre fondateur (invite_par=None) ne peut
    être retiré par personne, seulement se retirer lui-même (cf.
    quitter_foyer)."""
    membre = get_object_or_404(MembreFoyer, pk=pk, invite_par=request.user)
    nom = membre.utilisateur.username
    membre.delete()
    messages.info(request, f"{nom} a été retiré du foyer.")
    return redirect('accueil:partage_compte')


@login_required
@require_POST
def quitter_foyer(request):
    """Un membre peut toujours se retirer lui-même du foyer, à tout moment,
    sans condition (contrairement à retirer_membre_foyer)."""
    membre = get_object_or_404(MembreFoyer, utilisateur=request.user)
    membre.delete()
    messages.info(request, "Tu as quitté le foyer partagé.")
    return redirect('accueil:partage_compte')
