# Intègre le catalogue de races fourni dans static/data/ (races_chiens.json,
# races_chats.json, races_rongeurs.json, races_nac.json) : complète la fiche
# détaillée (cf. migration 0013) de chaque race déjà cataloguée (0003/0011) et
# crée les races manquantes, y compris pour les nouvelles espèces ajoutées par
# la migration 0014 (Lapin, Poisson, Insecte, Gastéropode).
#
# Les fichiers contiennent des commentaires `// ...` en début de ligne (JSON5),
# retirés avant analyse JSON standard.
#
# Correspondance espèce du JSON -> code Espece en base :
#   races_chiens.json  : "Chien"                              -> CHIEN
#   races_chats.json   : "Chat"                                -> CHAT
#   races_rongeurs.json: "Rongeur"                              -> RONGEUR
#                        "Lapin"                                -> LAPIN
#   races_nac.json      (classé par "categorie", plus précis que le
#                        champ "espece" du fichier) :
#                        "Rongeur"                              -> RONGEUR
#                        "Lagomorphe"                           -> LAPIN
#                        "Carnivore", "Insectivore"             -> AUTRE
#                        "Psittacidé", "Passereau", "Gallinacé" -> OISEAU
#                        "Serpent", "Lézard", "Tortue terrestre"-> REPTILE
#                        "Amphibien"                            -> BATRACIEN
#                        "Poisson d’eau douce"/"...de mer"      -> POISSON
#                        "Araignée"                             -> ARACHNIDE
#                        "Gastéropode"                          -> GASTEROPODE
#                        "Insecte"                               -> INSECTE
#
# Certains noms de races apparaissent dans plusieurs fichiers (ex. "Hamster
# Doré (Syrien)" dans races_rongeurs.json et races_nac.json) : la contrainte
# d'unicité (espece, nom) fait qu'ils désignent la même ligne, complétée au fur
# et à mesure sans jamais écraser une valeur déjà renseignée par un fichier
# précédent.
import json
from pathlib import Path

from django.conf import settings
from django.db import migrations

DOSSIER_DONNEES = Path(settings.BASE_DIR) / 'static' / 'data'

MAPPING_ESPECE_RONGEURS = {
    'Rongeur': 'RONGEUR',
    'Lapin': 'LAPIN',
}

MAPPING_CATEGORIE_NAC = {
    'Rongeur': 'RONGEUR',
    'Lagomorphe': 'LAPIN',
    'Carnivore': 'AUTRE',
    'Insectivore': 'AUTRE',
    'Psittacidé': 'OISEAU',
    'Passereau': 'OISEAU',
    'Gallinacé': 'OISEAU',
    'Serpent': 'REPTILE',
    'Lézard': 'REPTILE',
    'Tortue terrestre': 'REPTILE',
    'Amphibien': 'BATRACIEN',
    'Poisson d’eau douce': 'POISSON',
    'Poisson d’eau de mer': 'POISSON',
    'Araignée': 'ARACHNIDE',
    'Gastéropode': 'GASTEROPODE',
    'Insecte': 'INSECTE',
}

# Champs directement représentés par une colonne du modèle Race (cf. 0013).
CHAMPS_DIRECTS = {
    'origine', 'taille_min', 'taille_max', 'poids_min', 'poids_max',
    'esperance_vie', 'description', 'groupe_fci', 'categorie', 'sous_categorie',
    'nom_scientifique', 'niveau_soin', 'legislation_france', 'prix_moyen',
}
# Champs qui servent uniquement à identifier/router l'entrée, pas à décrire la race.
CHAMPS_IDENTIFIANTS = {'nom', 'espece'}


def _retirer_commentaires(texte):
    return '\n'.join(
        ligne for ligne in texte.split('\n')
        if not ligne.strip().startswith('//')
    )


def _charger_json(nom_fichier):
    chemin = DOSSIER_DONNEES / nom_fichier
    with open(chemin, encoding='utf-8') as f:
        return json.loads(_retirer_commentaires(f.read()))


def _fusionner(race, donnees):
    """Applique les champs de `donnees` sur `race` sans jamais écraser une
    valeur déjà renseignée (par un fichier traité précédemment) : permet de
    fusionner plusieurs sources sur une même race. Renvoie True si l'objet a
    été modifié (donc à sauvegarder)."""
    modifie = False
    for champ in CHAMPS_DIRECTS:
        valeur = donnees.get(champ)
        if valeur not in (None, '') and getattr(race, champ) in (None, ''):
            setattr(race, champ, valeur)
            modifie = True

    extra = {
        cle: val for cle, val in donnees.items()
        if cle not in CHAMPS_DIRECTS and cle not in CHAMPS_IDENTIFIANTS
        and val not in (None, '', [], {})
    }
    if extra:
        infos = dict(race.infos_complementaires or {})
        for cle, val in extra.items():
            if cle not in infos:
                infos[cle] = val
        if infos != (race.infos_complementaires or {}):
            race.infos_complementaires = infos
            modifie = True

    return modifie


def importer_catalogue(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Race = apps.get_model('animaux', 'Race')

    especes_par_code = {e.code: e for e in Espece.objects.all()}

    def importer_entree(code_espece, donnees):
        espece = especes_par_code.get(code_espece)
        nom = donnees.get('nom')
        if espece is None or not nom:
            return
        race, _ = Race.objects.get_or_create(espece=espece, nom=nom)
        if _fusionner(race, donnees):
            race.save()

    for entree in _charger_json('races_chiens.json')['races']:
        importer_entree('CHIEN', entree)

    for entree in _charger_json('races_chats.json')['races']:
        importer_entree('CHAT', entree)

    for entree in _charger_json('races_rongeurs.json')['races']:
        code = MAPPING_ESPECE_RONGEURS.get(entree.get('espece'))
        if code:
            importer_entree(code, entree)

    for entree in _charger_json('races_nac.json')['nac']:
        code = MAPPING_CATEGORIE_NAC.get(entree.get('categorie'))
        if code:
            importer_entree(code, entree)


def retirer_catalogue(apps, schema_editor):
    Race = apps.get_model('animaux', 'Race')

    # Les races des espèces créées par la migration 0014 n'existaient pas
    # avant cet import : elles peuvent être supprimées sans risque.
    Race.objects.filter(
        espece__code__in=['LAPIN', 'POISSON', 'INSECTE', 'GASTEROPODE']
    ).delete()

    # Pour les races déjà cataloguées avant cette migration (0003/0011), on ne
    # peut pas distinguer a posteriori les valeurs issues du catalogue de
    # celles saisies entre-temps par un utilisateur : on se contente donc de
    # vider les champs détaillés ajoutés par la migration 0013, sans jamais
    # supprimer la race elle-même.
    champs_texte = [
        'origine', 'esperance_vie', 'description', 'groupe_fci', 'categorie',
        'sous_categorie', 'nom_scientifique', 'niveau_soin',
        'legislation_france', 'prix_moyen',
    ]
    valeurs = {champ: '' for champ in champs_texte}
    valeurs.update({
        'taille_min': None, 'taille_max': None,
        'poids_min': None, 'poids_max': None,
        'infos_complementaires': None,
    })
    Race.objects.update(**valeurs)


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0014_seed_especes_catalogue'),
    ]

    operations = [
        migrations.RunPython(importer_catalogue, retirer_catalogue),
    ]
