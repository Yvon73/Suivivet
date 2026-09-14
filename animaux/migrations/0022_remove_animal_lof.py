# Supprime le champ lof, devenu inutile après le report de son contenu vers
# organisme/organisme_autre (migration 0021). Séparée de 0021 : PostgreSQL
# refuse d'altérer une table déjà modifiée par des données dans la même
# transaction ("il reste des événements sur les triggers").
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0021_migrer_lof_vers_organisme'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='animal',
            name='lof',
        ),
    ]
