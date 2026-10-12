from notifications.models import Notification


def notifications_context(request):
    if request.user.is_authenticated:
        return {
            'notifications_non_lues': Notification.objects.filter(
                utilisateur=request.user,
                lue=False
            ).count()
        }
    return {'notifications_non_lues': 0}


def preferences_accessibilite_context(request):
    """Préférences d'accessibilité en vigueur (cf. accueil/accessibilite.py :
    celles du compte connecté, sinon celles du cookie du visiteur), sous la
    forme des classes CSS (cf. static/css/style.css) que les gabarits posent
    directement sur <html> — elles s'appliquent donc dès le premier rendu, sans
    aucun script. `preferences_accessibilite` donne en plus l'état de chaque
    réglage, pour cocher les cases du panneau accessibilité.

    Le mode sombre n'est pas une classe mais l'attribut `data-bs-theme="dark"`
    (thème sombre natif de Bootstrap 5.3), d'où la variable séparée."""
    # Import différé : accueil dépend d'animaux (via ses vues), pas l'inverse,
    # mais un import en tête de module ici créerait un couplage inutile entre
    # ce module de configuration globale et une app applicative précise.
    from accueil import accessibilite
    if not hasattr(request, 'user'):
        preferences = accessibilite.par_defaut()
    else:
        preferences = accessibilite.lire(request)
    return {
        'preferences_accessibilite': preferences,
        'classes_accessibilite_utilisateur': accessibilite.classes_css(preferences),
        'mode_sombre_utilisateur': preferences['mode_sombre'],
    }
