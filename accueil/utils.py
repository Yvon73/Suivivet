from django.contrib.auth import get_user_model
from django.db.models import Q

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



def filtre_catalogue(utilisateur, reference=False, garder=None):
    """Filtre (objet Q) des entrées d'un catalogue rattaché à son compte
    créateur (champ `utilisateur` : consultations.Veterinaire, vaccins.Vaccin,
    vaccins.Traitement, factures.Designation, documents.TypeDocument) visibles
    par `utilisateur` : les siennes et celles des autres membres de son foyer
    (cf. comptes_accessibles) — jamais celles d'un autre compte.

    `reference=True` pour les catalogues livrés avec des entrées de référence
    (Vaccin, Traitement, TypeDocument : `utilisateur` vide, créées par les
    migrations du projet) : elles restent proposées à tous les comptes.

    `garder` : clé de l'entrée déjà référencée par l'objet en cours de
    modification. Elle reste proposée même si elle est sortie du filtre
    (entrée d'un ancien membre du foyer, par exemple), sinon l'enregistrement
    viderait ou refuserait silencieusement la valeur en place.
    """
    filtre = Q(utilisateur__in=comptes_accessibles(utilisateur))
    if reference:
        filtre |= Q(utilisateur__isnull=True)
    if garder:
        filtre |= Q(pk=garder)
    return filtre
