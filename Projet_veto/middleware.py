from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.utils.http import url_has_allowed_host_and_scheme


class NoIndexMiddleware:
    """Ajoute l'en-tête `X-Robots-Tag` à toutes les réponses : l'application
    est un outil personnel de suivi vétérinaire, pas un site destiné à être
    indexé par les moteurs de recherche ou aspiré par des robots d'IA — en
    plus de `robots.txt` (respecté seulement par les robots qui le veulent
    bien), cet en-tête est lu directement par Google/Bing sur chaque page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive, nosnippet'
        return response


# Aucune origine externe : toutes les bibliothèques front-end (Bootstrap,
# Bootstrap Icons, htmx, police Atkinson Hyperlegible) sont hébergées dans
# static/vendor/ (cf. son README.md) plutôt que chargées depuis un CDN. Si
# une ressource externe devient un jour indispensable, ajouter son domaine
# à la seule directive concernée plutôt que d'élargir default-src.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self' data:",
    # data: pour la courbe de poids (PNG généré par matplotlib, encodé en
    # base64 directement dans l'attribut src — cf. animaux/views.py), l'aperçu
    # de la photo d'un animal avant enregistrement (cf. animaux/formulaire.py)
    # et les petites icônes SVG inline de Bootstrap (flèches de <select>,
    # cases à cocher...).
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


class ContentSecurityPolicyMiddleware:
    """Limite les origines dont le navigateur accepte de charger un script,
    une feuille de style, une police ou une image — se déclenche si un script
    tiers malveillant tentait de se charger (ex. mineur de cryptomonnaie
    injecté via une dépendance compromise) ou si une page tentait de
    s'afficher dans une iframe étrangère (`frame-ancestors 'none'`, en plus
    de XFrameOptionsMiddleware).

    `'unsafe-inline'` reste nécessaire pour style-src : l'appli utilise des
    attributs style="" et htmx insère sa petite feuille de style. Pour
    script-src en revanche, plus aucun gabarit de l'application ne contient de
    script ni de gestionnaire d'événement inline (toute l'interactivité passe
    par htmx, cf. CLAUDE.md) : `'unsafe-inline'` n'y est gardé que par
    prudence, et pourra être retiré une fois le comportement vérifié dans un
    navigateur sur l'ensemble des pages (admin Django comprise). Il n'y a pas
    de `'unsafe-eval'` : htmx est configuré avec `allowEval: false`."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = CONTENT_SECURITY_POLICY
        return response


class ConnexionRequiseHtmxMiddleware:
    """Session expirée (ou déconnexion dans un autre onglet) pendant une
    requête htmx : `login_required`/`LoginRequiredMixin` répondent par une
    redirection vers la page de connexion, que le navigateur suit de lui-même
    — htmx recevait alors la page de connexion entière en 200 et l'insérait
    dans la zone visée (ajout rapide, ventilation), ou vidait la zone quand
    `hx-select` n'y trouvait rien (listes, calendrier).

    Pour une requête portant `HX-Request`, cette redirection est remplacée par
    une réponse 204 avec l'en-tête `HX-Redirect` : htmx fait alors une vraie
    navigation, pleine page, vers la connexion. Le `next` n'est pas celui de
    la redirection d'origine (souvent un point d'entrée réservé au POST, qui
    donnerait une erreur 405 après connexion) mais la page où se trouve
    l'utilisateur, transmise par htmx dans `HX-Current-URL` — jamais une
    adresse externe."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.headers.get('HX-Request') or response.status_code not in (301, 302):
            return response
        utilisateur = getattr(request, 'user', None)
        if utilisateur is not None and utilisateur.is_authenticated:
            return response
        connexion = resolve_url(settings.LOGIN_URL)
        if urlsplit(response.get('Location', '')).path != connexion:
            return response

        suite = resolve_url(settings.LOGIN_REDIRECT_URL)
        courante = request.headers.get('HX-Current-URL', '')
        if courante and url_has_allowed_host_and_scheme(
            courante, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
        ):
            morceaux = urlsplit(courante)
            # Depuis la page de connexion elle-même, `next` n'aurait aucun sens.
            if morceaux.path and morceaux.path != connexion:
                suite = morceaux.path + (f'?{morceaux.query}' if morceaux.query else '')

        reponse = HttpResponse(status=204)
        reponse['HX-Redirect'] = redirect_to_login(suite, connexion).url
        return reponse
