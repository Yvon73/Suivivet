# Supprime l'ancien champ Animal.proprietaire (EmailField), renomme le champ
# temporaire proprietaire_fk en proprietaire (cf. migrations 0030 et 0031),
# puis referme la contrainte NOT NULL désormais garantie par la migration de
# données 0031.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0031_migrer_proprietaires'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='animal',
            name='proprietaire',
        ),
        migrations.RenameField(
            model_name='animal',
            old_name='proprietaire_fk',
            new_name='proprietaire',
        ),
        migrations.AlterField(
            model_name='animal',
            name='proprietaire',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='animaux', to='animaux.proprietaire', verbose_name='Propriétaire',
            ),
        ),
    ]
