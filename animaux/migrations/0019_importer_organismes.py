# Importe le catalogue d'organismes/fédérations officiels depuis
# static/data/organismes_officiel.json.
#
# Ce fichier n'est PAS du JSON strict : guillemets simples, True/False à la
# Python, séparateurs de section "=== NOM ===" et lignes de commentaire "#".
# Chaque entrée d'organisme reste en revanche un littéral Python valide (dict
# à un seul niveau) : on les extrait un par un par une regex non gourmande
# sur les accolades, puis on les évalue avec ast.literal_eval plutôt que
# json.loads — ça gère nativement guillemets simples et True/False, et ça
# ignore de fait tout le texte de section autour (qui ne matche pas le motif
# "{...}").
import ast
import re
from pathlib import Path

from django.conf import settings
from django.db import migrations

CHEMIN_FICHIER = Path(settings.BASE_DIR) / 'static' / 'data' / 'organismes_officiel.json'


def _charger_organismes():
    texte = CHEMIN_FICHIER.read_text(encoding='utf-8')
    organismes = []
    for bloc in re.findall(r'\{[^{}]*\}', texte):
        try:
            valeur = ast.literal_eval(bloc)
        except (SyntaxError, ValueError):
            continue
        if isinstance(valeur, dict) and 'nom_court' in valeur:
            organismes.append(valeur)
    return organismes


def importer_organismes(apps, schema_editor):
    Organisme = apps.get_model('animaux', 'Organisme')
    for donnees in _charger_organismes():
        Organisme.objects.get_or_create(
            espece=donnees['espece'],
            nom_court=donnees['nom_court'],
            defaults={
                'nom': donnees.get('nom', ''),
                'description': donnees.get('description', ''),
                'site_web': donnees.get('site_web', ''),
                'pays': donnees.get('pays', ''),
                'est_officiel': donnees.get('est_officiel', True),
            },
        )


def retirer_organismes(apps, schema_editor):
    Organisme = apps.get_model('animaux', 'Organisme')
    noms_courts = {donnees['nom_court'] for donnees in _charger_organismes()}
    Organisme.objects.filter(nom_court__in=noms_courts).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0018_organisme'),
    ]

    operations = [
        migrations.RunPython(importer_organismes, retirer_organismes),
    ]
