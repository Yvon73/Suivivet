# Supprime l'ancien champ Consultation.veterinaire (CharField), renomme le
# champ temporaire veterinaire_fk en veterinaire (cf. migrations 0003 et
# 0004), puis referme la contrainte NOT NULL désormais garantie par la
# migration de données 0004.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0004_migrer_veterinaires'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='consultation',
            name='veterinaire',
        ),
        migrations.RenameField(
            model_name='consultation',
            old_name='veterinaire_fk',
            new_name='veterinaire',
        ),
        migrations.AlterField(
            model_name='consultation',
            name='veterinaire',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='consultations', to='consultations.veterinaire', verbose_name='Vétérinaire',
            ),
        ),
    ]
