from django.contrib.auth import get_user_model


def resoudre_utilisateur(email):
    """Retrouve le compte utilisateur Django correspondant à un email de
    propriétaire/vétérinaire (pour lui créer une notification in-app), ou
    None si personne ne correspond, ou si plusieurs comptes partagent cet
    email (email non unique sur le modèle User) — dans les deux cas, pas de
    notification plutôt qu'une exception.

    Centralise une recherche auparavant dupliquée (et pas toujours protégée
    contre le cas « plusieurs comptes ») dans consultations/models.py,
    consultations/signals.py, documents/models.py et factures/models.py.
    """
    if not email:
        return None
    User = get_user_model()
    try:
        return User.objects.get(email=email)
    except (User.DoesNotExist, User.MultipleObjectsReturned):
        return None
