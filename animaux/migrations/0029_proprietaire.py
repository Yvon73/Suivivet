# Crée la table Proprietaire (fiche complète : nom, prénom, adresse,
# téléphone, email, actif) en préparation du remplacement du champ
# Animal.proprietaire (jusqu'ici un simple EmailField) par une clé étrangère
# vers ce catalogue partagé (cf. migrations 0030 à 0032).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0027_remove_animal_identification_organisme'),
    ]

    operations = [
        migrations.CreateModel(
            name='Proprietaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='Nom')),
                ('prenom', models.CharField(blank=True, max_length=100, verbose_name='Prénom')),
                ('adresse', models.CharField(blank=True, max_length=255, verbose_name='Adresse')),
                ('telephone', models.CharField(blank=True, max_length=20, verbose_name='Téléphone')),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('actif', models.BooleanField(default=True, help_text="Décoché lors d'une « suppression » : la fiche reste en base (les animaux déjà enregistrés continuent de l'afficher) mais n'est plus proposée pour de nouvelles saisies, ni affichée sur la fiche animal en PDF.", verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Propriétaire',
                'verbose_name_plural': 'Propriétaires',
                'ordering': ['nom', 'prenom'],
            },
        ),
    ]
