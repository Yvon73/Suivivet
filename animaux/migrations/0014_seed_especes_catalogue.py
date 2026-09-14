# Ajoute les espèces référencées par le catalogue de races (static/data/races_*.json,
# cf. migration 0015) qui n'ont pas d'équivalent exact parmi les espèces existantes
# (CHIEN, CHAT, RONGEUR, OISEAU, AUTRE, REPTILE, ARACHNIDE, BATRACIEN — cf. migrations
# 0003 et 0011).
from django.db import migrations

NOUVELLES_ESPECES = [
    ('LAPIN', 'Lapin'),
    ('POISSON', 'Poisson'),
    ('INSECTE', 'Insecte'),
    ('GASTEROPODE', 'Gastéropode'),
]


def ajouter_especes(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    for code, nom in NOUVELLES_ESPECES:
        Espece.objects.get_or_create(code=code, defaults={'nom': nom})


def retirer_especes(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Espece.objects.filter(code__in=[code for code, _ in NOUVELLES_ESPECES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0013_race_fiche_detaillee'),
    ]

    operations = [
        migrations.RunPython(ajouter_especes, retirer_especes),
    ]
