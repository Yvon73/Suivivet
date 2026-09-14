# Crée la table AnimalIdentification : un animal peut être enregistré
# auprès de plusieurs organismes (ex. puce + LOF, inscription dans
# plusieurs registres), chaque couple identification/organisme devient donc
# une ligne à part plutôt qu'un champ unique sur Animal (cf. migrations
# 0026 pour la reprise des données existantes et 0027 pour la suppression
# des anciens champs sur Animal).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0024_espece_equide'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnimalIdentification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('organisme_autre', models.CharField(blank=True, help_text="Nom de l'organisme si absent de la liste ci-dessus.", max_length=200, verbose_name='Autre organisme (si non listé)')),
                ('identification', models.CharField(blank=True, help_text='Numéro de puce électronique ou tatouage, optionnel', max_length=50, null=True, unique=True, verbose_name='Identification (puce/numéro)')),
                ('animal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='identifications', to='animaux.animal')),
                ('organisme', models.ForeignKey(blank=True, help_text="Registre officiel auquel l'animal est inscrit (LOF, LOOF, SIRE...).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='identifications', to='animaux.organisme', verbose_name="Organisme d'inscription")),
            ],
            options={
                'verbose_name': 'Identification',
                'verbose_name_plural': 'Identifications',
                'ordering': ['id'],
            },
        ),
    ]
