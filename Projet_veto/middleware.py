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


# Liste blanche des origines externes réellement chargées par l'application —
# vérifiée exhaustivement dans tout le dépôt (templates + static/js/*.js) :
# jsdelivr (Bootstrap, bootstrap-icons, FullCalendar), jQuery, DataTables et
# Google Fonts (+ fonts.gstatic.com, qui héberge les fichiers de police
# eux-mêmes derrière la feuille de style Google Fonts). N'ajouter un nouveau
# domaine ici que si une ressource du projet le charge réellement.
_CSP_ORIGINES_JS = "https://cdn.jsdelivr.net https://code.jquery.com https://cdn.datatables.net"
_CSP_ORIGINES_CSS = "https://cdn.jsdelivr.net https://cdn.datatables.net https://fonts.googleapis.com"
# data: pour les polices d'icônes (Bootstrap Icons/FullCalendar embarquent un
# fallback de police encodé en base64 directement dans leur CSS).
_CSP_ORIGINES_FONTS = "https://cdn.jsdelivr.net https://fonts.gstatic.com data:"

CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    f"script-src 'self' 'unsafe-inline' {_CSP_ORIGINES_JS}",
    f"style-src 'self' 'unsafe-inline' {_CSP_ORIGINES_CSS}",
    f"font-src 'self' {_CSP_ORIGINES_FONTS}",
    # data: pour la courbe de poids (PNG généré par matplotlib, encodé en
    # base64 directement dans l'attribut src — cf. animaux/views.py).
    "img-src 'self' data: https://cdn.datatables.net",
    # DataTables charge sa traduction française en AJAX depuis ce CDN (cf.
    # `language: {url: 'https://cdn.datatables.net/plug-ins/.../fr-FR.json'}`
    # dans animaux/factures/documents/consultations liste.html).
    "connect-src 'self' https://cdn.datatables.net",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


class ContentSecurityPolicyMiddleware:
    """Limite les origines dont le navigateur accepte de charger un script,
    une feuille de style, une police ou une image — se déclenche si un script
    tiers malveillant tentait de se charger (ex. mineur de cryptomonnaie
    injecté via une dépendance ou un CDN compromis) ou si une page tentait de
    s'afficher dans une iframe étrangère (`frame-ancestors 'none'`, en plus
    de XFrameOptionsMiddleware).

    `'unsafe-inline'` reste nécessaire pour script-src/style-src : l'appli
    utilise de nombreux <script> et style="" inline (cf. animaux/form.html,
    consultations/calendrier.html...) qu'il faudrait extraire en fichiers
    externes pour s'en passer — hors marge de cette protection ponctuelle.
    La CSP reste malgré tout utile : elle bloque toujours le chargement d'un
    script/style/police/image externe qui ne viendrait pas d'une des origines
    listées ci-dessus."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = CONTENT_SECURITY_POLICY
        return response
