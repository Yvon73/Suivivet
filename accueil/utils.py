from django.contrib.auth import get_user_model

from .models import MembreFoyer


def comptes_accessibles(utilisateur):
    """Comptes dont les données sont visibles par `utilisateur` : lui-même,
    plus les autres membres de son foyer partagé le cas échéant (cf.
    accueil.models.Foyer/MembreFoyer) — sans jamais fusionner les comptes :
    chaque donnée reste rattachée à son créateur d'origine, seule la
    visibilité est élargie.

    Seul point d'entrée à utiliser pour élargir un filtre `utilisateur=...`
    existant en `utilisateur__in=comptes_accessibles(...)` (ou
    `animal__utilisateur__in=...`) dans les vues des apps métier (animaux,
    vaccins, consultations, factures, documents) — jamais de requête ad hoc,
    pour ne pas risquer d'élargir par erreur à tous les comptes de
    l'installation.
    """
    User = get_user_model()
    try:
        foyer = utilisateur.membre_foyer.foyer
    except MembreFoyer.DoesNotExist:
        return User.objects.filter(pk=utilisateur.pk)
    return User.objects.filter(membre_foyer__foyer=foyer)
