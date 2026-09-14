# Ajoute les champs organisme/organisme_autre à Animal, en préparation du
# remplacement de la case à cocher « lof » (migration 0021).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0019_importer_organismes'),
    ]

    operations = [
        migrations.AddField(
            model_name='animal',
            name='organisme_autre',
            field=models.CharField(blank=True, default='', help_text="Nom de l'organisme si absent de la liste ci-dessus.", max_length=200, verbose_name='Autre organisme (si non listé)'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='animal',
            name='organisme',
            field=models.ForeignKey(blank=True, help_text="Registre officiel auquel l'animal est inscrit (LOF, LOOF, SIRE...).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='animaux', to='animaux.organisme', verbose_name="Organisme d'inscription"),
        ),
    ]
