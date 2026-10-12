"""Reprise des catalogues jusque-là communs à tous les comptes
(consultations.Veterinaire, vaccins.Vaccin, vaccins.Traitement,
factures.Designation, documents.TypeDocument) : chaque entrée reçoit un compte
créateur (`utilisateur`, ajouté nullable par les migrations
`*_utilisateur_catalogue` de ces apps), d'après les objets qui l'utilisent.

- Entrée de référence, créée par une migration « seed » du projet (vaccins,
  traitements, types de document) : laissée sans compte, qu'elle soit
  utilisée ou non. `utilisateur` vide = entrée proposée à tous les comptes.
- Entrée utilisée par les objets d'un seul foyer (ou d'un seul compte sans
  foyer) : rattachée au compte de ce foyer qui l'utilise le plus (le plus
  ancien à égalité).
- Entrée utilisée par plusieurs foyers : une copie par foyer, à l'identique,
  et les objets de chaque foyer repointés vers la copie du leur. Le foyer
  dont le compte retenu est le plus ancien garde la ligne d'origine.
- Entrée utilisée par personne : rattachée au plus ancien superutilisateur,
  à défaut au plus ancien compte. Rien n'est jamais supprimé.

Cette migration vit dans `accueil` parce que la notion de foyer y est
définie ; elle ne lit que des modèles historiques (`apps.get_model`). Sans
effet sur une base vide. Le retour arrière ne fait rien : les champs
`utilisateur` sont retirés par les migrations de schéma des apps concernées
(les copies créées pour les entrées multi-foyers, elles, restent).
"""
from importlib import import_module

from django.db import migrations

# (app, modèle du catalogue, app, modèle qui le référence, clé étrangère,
#  chemin de ce modèle vers son compte, noms des entrées de référence)
CATALOGUES = (
    ('consultations', 'Veterinaire', 'consultations', 'Consultation', 'veterinaire', 'animal__utilisateur_id', None),
    ('vaccins', 'Vaccin', 'vaccins', 'SuiviVaccinTraitement', 'vaccin', 'animal__utilisateur_id', 'vaccins'),
    ('vaccins', 'Traitement', 'vaccins', 'SuiviVaccinTraitement', 'traitement', 'animal__utilisateur_id', 'traitements'),
    ('factures', 'Designation', 'factures', 'LigneFacture', 'designation', 'facture__utilisateur_id', None),
    ('documents', 'TypeDocument', 'documents', 'Document', 'type_document', 'animal__utilisateur_id', 'types_document'),
)


def noms_de_reference():
    """Noms (en minuscules) des entrées créées par les migrations « seed » du
    projet, relus dans ces migrations mêmes — historique figé, pas du code
    applicatif."""
    def noms(module, constante):
        entrees = getattr(import_module(module), constante)
        return {(entree if isinstance(entree, str) else entree[0]).lower() for entree in entrees}

    return {
        'vaccins': (
            noms('vaccins.migrations.0002_seed_vaccins', 'VACCINS_PAR_DEFAUT')
            | noms('vaccins.migrations.0003_seed_vaccins_nac', 'NOUVEAUX_VACCINS')
        ),
        'traitements': (
            noms('vaccins.migrations.0004_seed_traitements', 'TRAITEMENTS_PAR_DEFAUT')
            # vaccins.0012_seed_anti_inflammatoire_solution_buvable (nom en dur).
            | {"anti-inflammatoire (solution buvable)"}
        ),
        'types_document': noms('documents.migrations.0003_seed_types_document', 'TYPES_PAR_DEFAUT'),
    }


def rattacher_catalogues(apps, schema_editor=None):
    """Renvoie un bilan par catalogue : {'Vaccin': {'reference': n,
    'rattachees': n, 'dupliquees': n, 'copies': n, 'inutilisees': n}, ...}."""
    User = apps.get_model('auth', 'User')
    MembreFoyer = apps.get_model('accueil', 'MembreFoyer')

    # Ancienneté des comptes : rang 0 pour le plus ancien.
    comptes = list(User.objects.order_by('date_joined', 'pk').values_list('pk', 'is_superuser'))
    rang = {pk: position for position, (pk, _) in enumerate(comptes)}
    superutilisateurs = [pk for pk, superutilisateur in comptes if superutilisateur]
    compte_par_defaut = (superutilisateurs or [pk for pk, _ in comptes] or [None])[0]
    foyer_du_compte = dict(MembreFoyer.objects.values_list('utilisateur_id', 'foyer_id'))

    def groupe(compte_id):
        """Foyer du compte, ou le compte lui-même s'il n'en a pas."""
        foyer_id = foyer_du_compte.get(compte_id)
        return ('foyer', foyer_id) if foyer_id else ('compte', compte_id)

    reference = noms_de_reference()
    bilan = {}

    for app, nom_modele, app_ref, nom_modele_ref, cle, chemin_compte, cle_reference in CATALOGUES:
        Catalogue = apps.get_model(app, nom_modele)
        Referent = apps.get_model(app_ref, nom_modele_ref)
        noms_reference = reference.get(cle_reference, set())
        compteurs = bilan[nom_modele] = {
            'reference': 0, 'rattachees': 0, 'dupliquees': 0, 'copies': 0, 'inutilisees': 0,
        }

        # Les seules entrées sans compte : relancer la reprise ne refait rien.
        for entree in Catalogue.objects.filter(utilisateur__isnull=True).order_by('pk'):
            if (entree.nom or '').strip().lower() in noms_reference:
                compteurs['reference'] += 1
                continue

            # Objets qui utilisent l'entrée, regroupés par foyer :
            # {groupe: {compte: [clés des objets]}}.
            usages = {}
            for pk, compte_id in Referent.objects.filter(**{cle: entree.pk}).values_list('pk', chemin_compte):
                if compte_id is not None:
                    usages.setdefault(groupe(compte_id), {}).setdefault(compte_id, []).append(pk)

            if not usages:
                if compte_par_defaut is None:
                    raise RuntimeError(
                        f"Reprise des catalogues impossible : {nom_modele} #{entree.pk} « {entree.nom} » "
                        "n'est utilisé par personne et la base ne contient aucun compte auquel le "
                        "rattacher. Crée un compte (createsuperuser) puis relance la migration."
                    )
                entree.utilisateur_id = compte_par_defaut
                entree.save(update_fields=['utilisateur'])
                compteurs['inutilisees'] += 1
                continue

            # Par foyer : le compte qui utilise le plus l'entrée, le plus
            # ancien à égalité — puis les foyers du plus ancien compte retenu
            # au plus récent (le premier garde la ligne d'origine).
            attributions = []
            for objets_par_compte in usages.values():
                compte_retenu = min(
                    objets_par_compte, key=lambda compte_id: (-len(objets_par_compte[compte_id]), rang[compte_id]),
                )
                objets = [pk for liste in objets_par_compte.values() for pk in liste]
                attributions.append((rang[compte_retenu], compte_retenu, objets))
            attributions.sort()

            entree.utilisateur_id = attributions[0][1]
            entree.save(update_fields=['utilisateur'])
            if len(attributions) == 1:
                compteurs['rattachees'] += 1
                continue

            compteurs['dupliquees'] += 1
            valeurs = {
                champ.attname: getattr(entree, champ.attname)
                for champ in Catalogue._meta.concrete_fields
                if not champ.primary_key and champ.name != 'utilisateur'
            }
            for _, compte_retenu, objets in attributions[1:]:
                copie = Catalogue.objects.create(utilisateur_id=compte_retenu, **valeurs)
                Referent.objects.filter(pk__in=objets).update(**{cle: copie.pk})
                compteurs['copies'] += 1

    return bilan


class Migration(migrations.Migration):

    dependencies = [
        ('accueil', '0006_alter_membrefoyer_invite_par'),
        ('animaux', '0043_proprietaire_email_unique_parmi_les_actifs'),
        ('consultations', '0008_utilisateur_catalogue'),
        ('vaccins', '0013_utilisateur_catalogue'),
        ('factures', '0009_utilisateur_catalogue'),
        ('documents', '0004_utilisateur_catalogue'),
    ]

    operations = [
        migrations.RunPython(rattacher_catalogues, migrations.RunPython.noop),
    ]
