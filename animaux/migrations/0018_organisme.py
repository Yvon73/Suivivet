# Crée le modèle Organisme (registres/fédérations officiels auxquels un
# animal peut être inscrit), catalogué depuis
# static/data/organismes_officiel.json (import : migration 0019). Remplace à
# terme la case à cocher « Inscrit au LOF » (migration 0021), trop
# spécifique aux chiens.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0017_classification_dangerosite_globale'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organisme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom complet')),
                ('nom_court', models.CharField(help_text='Ex. LOF, LOOF, SIRE, CITES...', max_length=30, verbose_name='Nom court')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('site_web', models.URLField(blank=True, verbose_name='Site web')),
                ('espece', models.CharField(choices=[('CHIEN', 'Chien'), ('CHAT', 'Chat'), ('CHEVAL', 'Cheval'), ('RONGEUR', 'Rongeur'), ('OISEAU', 'Oiseau'), ('REPTILE', 'Reptile / Amphibien'), ('POISSON', 'Poisson'), ('ABEILLE', 'Abeille'), ('PIGEON', 'Pigeon'), ('AUTRE', 'Autre')], max_length=20, verbose_name='Espèce concernée')),
                ('pays', models.CharField(blank=True, max_length=100, verbose_name='Pays')),
                ('est_officiel', models.BooleanField(default=True, verbose_name='Organisme officiel')),
            ],
            options={
                'verbose_name': 'Organisme / Fédération',
                'verbose_name_plural': 'Organismes / Fédérations',
                'ordering': ['espece', 'nom_court'],
                'constraints': [models.UniqueConstraint(fields=('espece', 'nom_court'), name='organisme_unique_par_espece')],
            },
        ),
    ]
