# 1. Intègre trois catalogues de static/data/, de même structure que
#    races_chats2.json (migration 0040) avec en plus « duree_vie_moyenne » et,
#    pour les reptiles, « famille » :
#      insectes.json   -> espèce INSECTE
#      arachnides.json -> espèce ARACHNIDE
#      reptiles.json   -> espèce REPTILE, sauf sa catégorie « amphibians »
#                         -> espèce BATRACIEN
#    La clé de catégorie du fichier donne Race.categorie (cf. CATALOGUES), la
#    famille donne Race.sous_categorie, la durée de vie Race.esperance_vie.
#
#    Les noms du fichier sont de la forme « Nom (Autre nom) » (nom courant et
#    nom scientifique, dans un ordre qui dépend du fichier). Une race déjà en
#    base dont le nom correspond au nom complet ou à l'une de ses deux parties
#    (« Boa Constrictor (Boa imperator) » / « Boa constrictor ») est complétée
#    sous son nom actuel plutôt que doublonnée ; ses champs descriptifs déjà
#    renseignés (catégorie, espérance de vie...) ne sont pas écrasés.
#
# 2. Passe la dangerosité sur une seule échelle à 5 niveaux
#    (Race.echelle_dangerosite), avant la suppression de l'ancien champ à 3
#    niveaux niveau_dangerosite (migration 0042). Les races sans note 1-5
#    reprennent leur ancien niveau, au libellé équivalent :
#      AUCUNE -> 1 (Nul), MODEREE -> 3 (Moyenne), ELEVEE -> 4 (Élevé),
#      NON_RENSEIGNE -> vide.
import json
import re
from pathlib import Path

from django.conf import settings
from django.db import migrations

DOSSIER_DONNEES = Path(settings.BASE_DIR) / 'static' / 'data'

# fichier -> {clé de catégorie: (code espèce, Race.categorie)}
CATALOGUES = {
    'insectes.json': {
        'coleoperes': ('INSECTE', 'Coléoptère'),
        'phasmodes_phasmatodea': ('INSECTE', 'Phasme'),
        'orthopteres': ('INSECTE', 'Orthoptère'),
        'hymenopteres': ('INSECTE', 'Hyménoptère'),
        'lepidopteres_and_other': ('INSECTE', 'Lépidoptère et autres'),
    },
    'arachnides.json': {
        'scorpions': ('ARACHNIDE', 'Scorpion'),
        'mygales_araneae': ('ARACHNIDE', 'Mygale'),
        'solifugae_and_other': ('ARACHNIDE', 'Solifuge et autres'),
    },
    'reptiles.json': {
        'squamates_lizards': ('REPTILE', 'Lézard'),
        'squamates_snakes': ('REPTILE', 'Serpent'),
        'testudines_tortoises_and_turtles': ('REPTILE', 'Tortue'),
        'crocodilians': ('REPTILE', 'Crocodilien'),
        'amphibians': ('BATRACIEN', 'Amphibien'),
    },
}

# Seul reptiles.json écrit « Nom courant (Nom scientifique) » ; les deux
# autres font l'inverse, ou mélangent : on n'en déduit rien.
FICHIERS_NOM_SCIENTIFIQUE_ENTRE_PARENTHESES = {'reptiles.json'}

# Nom du fichier contenant des caractères cyrilliques (introuvable à la
# saisie dans le menu des races).
CORRECTIONS_NOMS = {
    'Scinque Triкольор (Tiliqua scincoides)': 'Scinque Tricolore (Tiliqua scincoides)',
}

ANCIEN_NIVEAU_VERS_ECHELLE = {'AUCUNE': 1, 'MODEREE': 3, 'ELEVEE': 4}
ECHELLE_VERS_ANCIEN_NIVEAU = {1: 'AUCUNE', 2: 'AUCUNE', 3: 'MODEREE', 4: 'ELEVEE', 5: 'ELEVEE'}


def _normaliser(nom):
    return nom.replace('’', "'").strip().lower()


def _parties(nom):
    """(hors parenthèses, entre parenthèses) de « Nom (Autre nom) »."""
    correspondance = re.match(r'^(.*?)\s*\((.*)\)\s*$', nom)
    if not correspondance:
        return nom, ''
    return correspondance.group(1).strip(), correspondance.group(2).strip()


def _importer_catalogues(Espece, Race):
    especes_par_code = {espece.code: espece for espece in Espece.objects.all()}
    races_par_espece = {}

    for fichier, categories_connues in CATALOGUES.items():
        with open(DOSSIER_DONNEES / fichier, encoding='utf-8') as f:
            categories = json.load(f)['categories']

        for cle_categorie, entrees in categories.items():
            if cle_categorie not in categories_connues:
                continue
            code_espece, categorie = categories_connues[cle_categorie]
            espece = especes_par_code.get(code_espece)
            if espece is None:
                continue
            if code_espece not in races_par_espece:
                races_par_espece[code_espece] = {
                    _normaliser(race.nom): race for race in Race.objects.filter(espece=espece)
                }
            races_par_nom = races_par_espece[code_espece]

            for entree in entrees:
                nom = (entree.get('nom') or '').strip()
                if not nom:
                    continue
                nom = CORRECTIONS_NOMS.get(nom, nom)
                hors_parentheses, entre_parentheses = _parties(nom)

                race = None
                for candidat in (nom, hors_parentheses, entre_parentheses):
                    if candidat and _normaliser(candidat) in races_par_nom:
                        race = races_par_nom[_normaliser(candidat)]
                        break
                if race is None:
                    race = Race(espece=espece, nom=nom)
                    races_par_nom[_normaliser(nom)] = race

                echelle = entree.get('dangerosite')
                if echelle in (1, 2, 3, 4, 5):
                    race.echelle_dangerosite = echelle
                if isinstance(entree.get('certificat_detention'), bool):
                    race.certificat_detention = entree['certificat_detention']
                race.comportement = (entree.get('comportement') or '').strip()
                race.note = (entree.get('note') or '').strip()[:255]

                # Champs descriptifs : jamais écrasés s'ils sont déjà renseignés.
                complements = {
                    'categorie': categorie,
                    'sous_categorie': (entree.get('famille') or '').strip(),
                    'esperance_vie': (entree.get('duree_vie_moyenne') or '').strip()[:50],
                }
                if fichier in FICHIERS_NOM_SCIENTIFIQUE_ENTRE_PARENTHESES:
                    complements['nom_scientifique'] = entre_parentheses
                for champ, valeur in complements.items():
                    if valeur and not getattr(race, champ):
                        setattr(race, champ, valeur)
                race.save()


def importer_et_convertir(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Race = apps.get_model('animaux', 'Race')

    _importer_catalogues(Espece, Race)

    for ancien_niveau, echelle in ANCIEN_NIVEAU_VERS_ECHELLE.items():
        Race.objects.filter(
            echelle_dangerosite__isnull=True, niveau_dangerosite=ancien_niveau,
        ).update(echelle_dangerosite=echelle)


def retablir_ancien_niveau(apps, schema_editor):
    # Rétablit seulement l'ancien champ à 3 niveaux (recréé à NON_RENSEIGNE
    # par l'annulation de 0042) ; les races importées restent en base, faute
    # de pouvoir les distinguer de celles ajoutées depuis à la main.
    Race = apps.get_model('animaux', 'Race')
    for echelle, ancien_niveau in ECHELLE_VERS_ANCIEN_NIVEAU.items():
        Race.objects.filter(echelle_dangerosite=echelle).update(niveau_dangerosite=ancien_niveau)


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0040_importer_races_chats2'),
    ]

    operations = [
        migrations.RunPython(importer_et_convertir, retablir_ancien_niveau),
    ]
