# Ajoute un champ temporaire veterinaire_fk (FK vers Veterinaire) en
# parallèle de l'ancien champ veterinaire (CharField), le temps de migrer les
# données existantes (migration 0004) puis de basculer définitivement dessus
# (migration 0005).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0002_veterinaire'),
    ]

    operations = [
        migrations.AddField(
            model_name='consultation',
            name='veterinaire_fk',
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='consultations', to='consultations.veterinaire', verbose_name='Vétérinaire',
            ),
        ),
    ]
