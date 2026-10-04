# Intègre le catalogue static/data/races_chats2.json (races de chats :
# comportement, dangerosité notée de 1 à 5, certificat de détention, note)
# dans les champs ajoutés par la migration 0039.
#
# Structure du fichier : {"categories": {<clé>: [{nom, comportement,
# dangerosite, certificat_detention, note}, ...]}, "legendes": {...}}.
#
# Particularités du fichier, traitées ici :
#   - de nombreux noms commencent par une espace (« " Chausie" ») : retirée ;
#   - beaucoup de races y figurent plusieurs fois (la seconde fois avec un
#     texte abrégé) : seule la première occurrence, la plus complète, compte ;
#   - quelques races déjà cataloguées (migration 0015) y portent un autre nom
#     (« Turc d'Angora » / « Angora Turc »...) : ALIAS évite de créer un
#     doublon, la race existante est complétée sous son nom actuel ;
#   - les clés de « categories » ne sont pas reprises dans Race.categorie :
#     « poils_courts_classiques » y regroupe indistinctement 134 entrées,
#     dont les hybrides et félins sauvages.
#
# Le niveau de dangerosité existant (celui qui pilote la couleur) est
# conservé : il est déduit de la note 1-5 (1 à 3 -> AUCUNE, 4 -> MODEREE,
# 5 -> ELEVEE, cf. Race.niveau_depuis_echelle) et n'est jamais abaissé par
# rapport à la valeur déjà en base (migration 0017 ou réglage manuel).
import json
from pathlib import Path

from django.conf import settings
from django.db import migrations

FICHIER = Path(settings.BASE_DIR) / 'static' / 'data' / 'races_chats2.json'

# Nom dans le fichier -> nom de la race déjà en base (si elle existe).
ALIAS = {
    "Turc d'Angora": 'Angora Turc',
    'Siberian': 'Sibérien',
    'Turkish Van': 'Turc de Van',
    'Don Sphynx': 'Donskoy',
    'Donskoy (Don Sphynx)': 'Donskoy',
    'Balinese': 'Balinais',
    'Burma (Burmese)': 'Burmese',
    'Bobtail Japonais': 'Japanese Bobtail',
    'Minuet (Napoleon)': 'Napoleon',
}

ORDRE_NIVEAUX = ['NON_RENSEIGNE', 'AUCUNE', 'MODEREE', 'ELEVEE']


def _niveau_depuis_echelle(echelle):
    # Copie de Race.niveau_depuis_echelle : les modèles historiques d'une
    # migration n'exposent pas les méthodes du modèle.
    if echelle >= 5:
        return 'ELEVEE'
    if echelle == 4:
        return 'MODEREE'
    return 'AUCUNE'


def importer_races_chats2(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Race = apps.get_model('animaux', 'Race')

    chat = Espece.objects.filter(code='CHAT').first()
    if chat is None:
        return

    with open(FICHIER, encoding='utf-8') as f:
        categories = json.load(f)['categories']

    races_par_nom = {race.nom.lower(): race for race in Race.objects.filter(espece=chat)}
    deja_traitees = set()

    for entrees in categories.values():
        for entree in entrees:
            nom = (entree.get('nom') or '').strip()
            if not nom:
                continue
            alias = ALIAS.get(nom)
            if alias and alias.lower() in races_par_nom:
                nom = alias
            cle = nom.lower()
            if cle in deja_traitees:
                continue
            deja_traitees.add(cle)

            race = races_par_nom.get(cle)
            if race is None:
                race = Race(espece=chat, nom=nom)
                races_par_nom[cle] = race

            echelle = entree.get('dangerosite')
            if echelle in (1, 2, 3, 4, 5):
                race.echelle_dangerosite = echelle
                niveau = _niveau_depuis_echelle(echelle)
                if ORDRE_NIVEAUX.index(niveau) > ORDRE_NIVEAUX.index(race.niveau_dangerosite):
                    race.niveau_dangerosite = niveau
            if isinstance(entree.get('certificat_detention'), bool):
                race.certificat_detention = entree['certificat_detention']
            race.comportement = (entree.get('comportement') or '').strip()
            race.note = (entree.get('note') or '').strip()[:255]
            race.save()


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0039_race_catalogue_chats2'),
    ]

    operations = [
        # Sans retour arrière propre : on ne peut pas distinguer a posteriori
        # les races créées ici de celles ajoutées depuis à la main. Annuler la
        # migration 0039 supprime de toute façon les colonnes remplies ici.
        migrations.RunPython(importer_races_chats2, migrations.RunPython.noop),
    ]
