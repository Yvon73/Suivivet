# Supprime de Animal les champs identification/organisme/organisme_autre,
# désormais portés par AnimalIdentification (cf. migrations 0025 et 0026 pour
# la création de la table et la reprise des données existantes).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0026_migrer_identifications'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='animal',
            name='identification',
        ),
        migrations.RemoveField(
            model_name='animal',
            name='organisme',
        ),
        migrations.RemoveField(
            model_name='animal',
            name='organisme_autre',
        ),
    ]
