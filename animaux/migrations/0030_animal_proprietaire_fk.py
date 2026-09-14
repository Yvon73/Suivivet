# Ajoute un champ temporaire proprietaire_fk (FK vers Proprietaire) en
# parallèle de l'ancien champ proprietaire (EmailField), le temps de migrer
# les données existantes (migration 0031) puis de basculer définitivement
# dessus (migration 0032).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0029_proprietaire'),
    ]

    operations = [
        migrations.AddField(
            model_name='animal',
            name='proprietaire_fk',
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='animaux', to='animaux.proprietaire', verbose_name='Propriétaire',
            ),
        ),
    ]
