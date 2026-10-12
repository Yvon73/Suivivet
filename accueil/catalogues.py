"""Devenir des entrées de catalogue d'un compte que l'on supprime.

Les catalogues rattachés à leur compte créateur (consultations.Veterinaire,
vaccins.Vaccin, vaccins.Traitement, factures.Designation,
documents.TypeDocument — cf. accueil.utils.filtre_catalogue) sont partagés
avec le foyer : un autre compte peut donc avoir un suivi, une ligne de
facture, un document ou une consultation qui pointe vers l'entrée d'un compte
supprimé depuis. Une simple cascade supprimerait l'entrée et laisserait ces
objets sans vaccin / désignation / type (clés en SET_NULL), ou refuserait la
suppression du compte (Consultation.veterinaire, en RESTRICT). Vider le compte
de l'entrée (SET_NULL) est exclu : une entrée sans compte est une entrée de
référence, visible de tous les comptes de l'installation.

D'où REATTRIBUER_OU_SUPPRIMER, à utiliser comme `on_delete` du champ
`utilisateur` de ces catalogues.

Pourquoi un `on_delete` et pas un signal `pre_delete` sur le compte : Django
dresse la liste de tout ce qu'il va supprimer (et lève ProtectedError) *avant*
d'émettre le moindre `pre_delete` ; une entrée réattribuée dans ce signal
serait supprimée quand même, par sa clé primaire. Le `on_delete` intervient,
lui, pendant ce recensement. Il n'écrit rien : il inscrit des mises à jour
différées (`Collector.add_field_update`, comme SET_NULL), appliquées dans la
transaction de la suppression — la page de confirmation de l'administration,
qui ne fait que simuler la suppression, ne modifie donc rien.
"""
from collections import Counter

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import CASCADE, Count, UniqueConstraint

# Pour chaque catalogue : les modèles qui référencent ses entrées, sous la
# forme (modèle, clé vers le catalogue, chemin vers le compte auquel
# appartient l'objet référent). À compléter pour toute nouvelle clé étrangère
# vers l'un de ces catalogues.
REFERENTS = {
    'consultations.veterinaire': (('consultations.Consultation', 'veterinaire', 'animal__utilisateur'),),
    'vaccins.vaccin': (('vaccins.SuiviVaccinTraitement', 'vaccin', 'animal__utilisateur'),),
    'vaccins.traitement': (('vaccins.SuiviVaccinTraitement', 'traitement', 'animal__utilisateur'),),
    'factures.designation': (('factures.LigneFacture', 'designation', 'facture__utilisateur'),),
    'documents.typedocument': (('documents.Document', 'type_document', 'animal__utilisateur'),),
}


def _referents(modele):
    return [
        (apps.get_model(nom), cle, chemin)
        for nom, cle, chemin in REFERENTS.get(modele._meta.label_lower, ())
    ]


def _utilisations(entree, comptes_supprimes, using):
    """Pour chaque modèle référent, les objets des comptes *conservés* qui
    pointent vers `entree` : liste de (modèle, clé, chemin, QuerySet)."""
    return [
        (
            modele, cle, chemin,
            modele._base_manager.using(using).filter(**{cle: entree}).exclude(
                **{f'{chemin}__in': comptes_supprimes}
            ),
        )
        for modele, cle, chemin in _referents(type(entree))
    ]


def _repreneur(utilisations, using):
    """Clé du compte qui reprend l'entrée : celui qui l'utilise le plus, le
    plus ancien à égalité ; None si aucun compte conservé ne l'utilise."""
    decompte = Counter()
    for _modele, _cle, chemin, objets in utilisations:
        for compte, nombre in objets.order_by().values_list(chemin).annotate(nombre=Count('pk')):
            decompte[compte] += nombre
    if not decompte:
        return None
    maximum = max(decompte.values())
    candidats = [compte for compte, nombre in decompte.items() if nombre == maximum]
    if len(candidats) == 1:
        return candidats[0]
    return (
        get_user_model()._base_manager.using(using).filter(pk__in=candidats)
        .order_by('date_joined', 'pk').values_list('pk', flat=True).first()
    )


def _contraintes_par_compte(modele, field):
    """Contraintes d'unicité de `modele` qui portent sur le compte
    (Designation : (utilisateur, nom))."""
    return [
        contrainte for contrainte in modele._meta.constraints
        if isinstance(contrainte, UniqueConstraint) and contrainte.condition is None
        and field.name in contrainte.fields
    ]


def _cles_d_unicite(entree, field, repreneur):
    """Ce qui identifie `entree` chez `repreneur` au regard de chacune de
    ces contraintes : une clé par contrainte."""
    return [
        (
            type(entree), contrainte.name, repreneur,
            tuple(getattr(entree, nom) for nom in contrainte.fields if nom != field.name),
        )
        for contrainte in _contraintes_par_compte(type(entree), field)
    ]


def _homonyme(entree, field, repreneur, using, deja_reattribuees):
    """Entrée qu'une contrainte d'unicité portant sur le compte interdirait
    de doubler en réattribuant `entree` à `repreneur` ; None s'il n'y a pas
    de conflit. C'est soit une entrée que `repreneur` possède déjà, soit une
    entrée que cette même suppression lui a déjà réattribuée
    (`deja_reattribuees` — plusieurs comptes supprimés à la fois, chacun
    avec une désignation du même nom reprise par le même compte)."""
    modele = type(entree)
    for contrainte in _contraintes_par_compte(modele, field):
        criteres = {nom: getattr(entree, nom) for nom in contrainte.fields if nom != field.name}
        criteres[field.attname] = repreneur
        homonyme = modele._base_manager.using(using).filter(**criteres).exclude(pk=entree.pk).first()
        if homonyme is not None:
            return homonyme
    for cle in _cles_d_unicite(entree, field, repreneur):
        if cle in deja_reattribuees:
            return deja_reattribuees[cle]
    return None


def REATTRIBUER_OU_SUPPRIMER(collector, field, sub_objs, using):
    """`on_delete` du champ `utilisateur` d'un catalogue rattaché à son compte
    créateur (cf. le haut de ce module). À la suppression du compte :

    - une entrée encore utilisée par un objet d'un *autre* compte est
      réattribuée à ce compte (le plus gros utilisateur s'ils sont plusieurs,
      le plus ancien à égalité — tous sont membres ou anciens membres du même
      foyer) ;
    - si ce compte possède déjà une entrée du même nom — ou vient d'en
      recevoir une d'un autre compte supprimé en même temps — et que
      l'unicité par compte interdit d'en avoir deux (Designation), les objets
      conservés sont repointés vers celle-là et l'entrée du compte supprimé
      disparaît ;
    - une entrée que seuls les objets du compte supprimé utilisent (ou que
      personne n'utilise) est supprimée avec lui, comme avec CASCADE.
    """
    entrees = list(sub_objs)
    # Comptes en cours de suppression : ceux déjà recensés par le collecteur
    # (suppression de plusieurs comptes à la fois) et les propriétaires des
    # entrées reçues.
    comptes_supprimes = {compte.pk for compte in collector.data.get(get_user_model(), ())}
    comptes_supprimes.update(getattr(entree, field.attname) for entree in entrees)

    # Réattributions déjà inscrites par cette suppression, mémorisées sur le
    # collecteur : Django peut appeler ce `on_delete` en plusieurs fois (par
    # lots d'entrées) au cours d'un même recensement.
    deja_reattribuees = collector.__dict__.setdefault('_catalogues_reattribues', {})

    a_supprimer = []
    a_repointer = []
    # Par clé : à nom égal, l'entrée conservée est la plus ancienne.
    for entree in sorted(entrees, key=lambda entree: entree.pk):
        utilisations = _utilisations(entree, comptes_supprimes, using)
        repreneur = _repreneur(utilisations, using)
        if repreneur is None:
            a_supprimer.append(entree)
            continue
        homonyme = _homonyme(entree, field, repreneur, using, deja_reattribuees)
        if homonyme is None:
            collector.add_field_update(field, repreneur, [entree])
            for cle in _cles_d_unicite(entree, field, repreneur):
                deja_reattribuees[cle] = entree
        else:
            a_supprimer.append(entree)
            a_repointer.append((homonyme, utilisations))

    if a_supprimer:
        CASCADE(collector, field, a_supprimer, using)
    # Inscrit *après* la cascade ci-dessus, et c'est voulu : elle a prévu de
    # vider (SET_NULL) la clé de tous les objets qui pointent vers une entrée
    # supprimée. Django applique les mises à jour différées dans l'ordre où
    # leur couple (champ, valeur) a été inscrit pour la première fois : le
    # repointage passe donc après ce vidage et l'emporte.
    for homonyme, utilisations in a_repointer:
        for modele, cle, _chemin, objets in utilisations:
            objets = list(objets)
            if objets:
                collector.add_field_update(modele._meta.get_field(cle), homonyme.pk, objets)
