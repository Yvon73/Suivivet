from django.db import migrations

NOUVELLES_ESPECES = [
    ('REPTILE', 'Reptile'),
    ('ARACHNIDE', 'Arachnide'),
    ('BATRACIEN', 'Batracien'),
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
        ('animaux', '0010_alter_animal_identification_and_more'),
    ]

    operations = [
        migrations.RunPython(ajouter_especes, retirer_especes),
    ]
