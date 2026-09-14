import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0005_populate_animal_fk_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='animal',
            name='espece',
        ),
        migrations.RemoveField(
            model_name='animal',
            name='robe',
        ),
        migrations.RemoveField(
            model_name='animal',
            name='race',
        ),
        migrations.RenameField(
            model_name='animal',
            old_name='espece_fk',
            new_name='espece',
        ),
        migrations.RenameField(
            model_name='animal',
            old_name='robe_fk',
            new_name='robe',
        ),
        migrations.RenameField(
            model_name='animal',
            old_name='race_fk',
            new_name='race',
        ),
        migrations.AlterField(
            model_name='animal',
            name='espece',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='animaux', to='animaux.espece', verbose_name='Espèce'),
        ),
        migrations.AlterField(
            model_name='animal',
            name='robe',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='animaux', to='animaux.robe', verbose_name='Robe (couleur)'),
        ),
        migrations.AlterField(
            model_name='animal',
            name='race',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='animaux', to='animaux.race', verbose_name='Race'),
        ),
    ]
