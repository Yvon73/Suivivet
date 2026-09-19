from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, TemplateView

from Projet_veto import throttling
from .forms import PremierUtilisateurForm
from .models import PreferenceAccessibilite


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
    ouverte à tout visiteur, sans validation de l'Admin. Chaque compte a ses
    propres animaux/consultations/factures/documents, invisibles des autres
    comptes (cf. Animal.utilisateur et les querysets filtrés dans les vues des
    apps animaux/vaccins/consultations/factures/documents) — un nouveau
    compte auto-créé n'obtient donc jamais accès aux données de quelqu'un
    d'autre, juste son propre espace vide au départ."""

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
    elif champ in ('contraste_eleve', 'police_lisible', 'reduire_animations', 'palette_daltonisme'):
        setattr(prefs, champ, valeur == '1')
    else:
        return JsonResponse({'success': False, 'erreur': 'champ inconnu'}, status=400)

    prefs.save()
    return JsonResponse({'success': True})
