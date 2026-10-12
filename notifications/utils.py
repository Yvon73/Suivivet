from django.contrib.auth import get_user_model


def resoudre_utilisateur(email, parmi=None):
    """Retrouve le compte utilisateur Django correspondant à un email de
    propriétaire/vétérinaire (pour lui créer une notification in-app), ou
    None si personne ne correspond, ou si plusieurs comptes partagent cet
    email (email non unique sur le modèle User) — dans les deux cas, pas de
    notification plutôt qu'une exception.

    Centralise une recherche auparavant dupliquée (et pas toujours protégée
    contre le cas « plusieurs comptes ») dans consultations/models.py,
    consultations/signals.py, documents/models.py et factures/models.py.

    `parmi` (queryset de comptes) restreint la recherche : l'email d'une
    fiche propriétaire est une saisie libre, il peut être celui d'un compte
    sans aucun lien avec l'auteur de la donnée. Les appels métier passent
    donc `comptes_accessibles(...)` du compte concerné, pour ne notifier
    qu'un compte qui voit réellement cette donnée.
    """
    if not email:
        return None
    User = get_user_model()
    comptes = User.objects.all() if parmi is None else parmi
    try:
        return comptes.get(email__iexact=email)
    except (User.DoesNotExist, User.MultipleObjectsReturned):
        return None
