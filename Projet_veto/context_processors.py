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
    """Classes CSS (cf. static/css/style.css) correspondant aux préférences
    d'accessibilité enregistrées pour le compte connecté (cf.
    accueil.models.PreferenceAccessibilite) — posées directement sur <html>
    par templates/base.html, pour qu'elles s'appliquent dès la connexion, sur
    n'importe quel navigateur, sans dépendre du localStorage du panneau
    accessibilité (qui reste le seul mécanisme pour un visiteur non connecté,
    cf. accueil/templates/accueil/*.html et registration/login.html)."""
    if not request.user.is_authenticated:
        return {'classes_accessibilite_utilisateur': ''}
    # Import différé : accueil dépend d'animaux (via ses vues), pas l'inverse,
    # mais un import en tête de module ici créerait un couplage inutile entre
    # ce module de configuration globale et une app applicative précise.
    from accueil.models import PreferenceAccessibilite
    prefs = PreferenceAccessibilite.objects.filter(utilisateur=request.user).first()
    return {'classes_accessibilite_utilisateur': prefs.classes_css() if prefs else ''}