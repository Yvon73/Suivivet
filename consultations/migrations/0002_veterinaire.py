# Crée la table Veterinaire (fiche complète : nom, prénom, adresse,
# téléphone, email, actif) en préparation du remplacement du champ
# Consultation.veterinaire (jusqu'ici un simple nom en texte libre) par une
# clé étrangère vers ce catalogue partagé (cf. migrations 0003 à 0005).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Veterinaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='Nom')),
                ('prenom', models.CharField(blank=True, max_length=100, verbose_name='Prénom')),
                ('adresse', models.CharField(blank=True, max_length=255, verbose_name='Adresse')),
                ('telephone', models.CharField(blank=True, max_length=20, verbose_name='Téléphone')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('actif', models.BooleanField(default=True, help_text="Décoché lors d'une « suppression » : la fiche reste en base (les consultations déjà enregistrées continuent de l'afficher) mais n'est plus proposée pour de nouvelles saisies, ni affichée sur la fiche animal en PDF.", verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Vétérinaire',
                'verbose_name_plural': 'Vétérinaires',
                'ordering': ['nom', 'prenom'],
            },
        ),
    ]
