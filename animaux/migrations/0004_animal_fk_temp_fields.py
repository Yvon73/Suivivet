import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0003_espece_robe_race'),
    ]

    operations = [
        migrations.AddField(
            model_name='animal',
            name='espece_fk',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='animaux_tmp', to='animaux.espece'),
        ),
        migrations.AddField(
            model_name='animal',
            name='robe_fk',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='animaux_tmp', to='animaux.robe'),
        ),
        migrations.AddField(
            model_name='animal',
            name='race_fk',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='animaux_tmp', to='animaux.race'),
        ),
    ]
