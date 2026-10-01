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
# Bootstrap Icons, FullCalendar, DataTables + sa traduction fr-FR.json,
# jQuery, Tom Select, police Atkinson Hyperlegible) sont hébergées dans
# static/vendor/ (cf. son README.md) plutôt que chargées depuis un CDN. Si
# une ressource externe devient un jour indispensable, ajouter son domaine
# à la seule directive concernée plutôt que d'élargir default-src.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    # data: pour la police d'icônes de FullCalendar, embarquée en base64
    # directement dans static/vendor/fullcalendar/main.min.css.
    "font-src 'self' data:",
    # data: pour la courbe de poids (PNG généré par matplotlib, encodé en
    # base64 directement dans l'attribut src — cf. animaux/views.py) et pour
    # les petites icônes SVG inline de Bootstrap/Tom Select (flèches de
    # <select>, cases à cocher...).
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

    `'unsafe-inline'` reste nécessaire pour script-src/style-src : l'appli
    utilise de nombreux <script> et style="" inline (cf. animaux/form.html,
    consultations/calendrier.html...) qu'il faudrait extraire en fichiers
    externes pour s'en passer — hors marge de cette protection ponctuelle.
    La CSP reste malgré tout utile : elle bloque toujours le chargement d'un
    script/style/police/image qui ne serait pas servi par l'application
    elle-même."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = CONTENT_SECURITY_POLICY
        return response
