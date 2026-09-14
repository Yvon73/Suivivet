import django.db.models.deletion
from django.db import migrations, models

ESPECES = [
    ('CHIEN', 'Chien'),
    ('CHAT', 'Chat'),
    ('RONGEUR', 'Rongeur'),
    ('OISEAU', 'Oiseau'),
    ('AUTRE', 'Autre'),
]

ROBES = [
    ('NOIR', 'Noir'),
    ('BLANC', 'Blanc'),
    ('GRIS', 'Gris'),
    ('ROUX', 'Roux'),
    ('BRUN', 'Brun'),
    ('TIGRE', 'Tigré'),
    ('AUTRE', 'Autre'),
]

RACES_PAR_ESPECE = {
    'CHIEN': [
        "Labrador Retriever", "Golden Retriever", "Berger Allemand", "Berger Australien",
        "Berger Belge Malinois", "Border Collie", "Bouledogue Français", "Bouledogue Anglais",
        "Carlin", "Caniche", "Cocker Spaniel Anglais", "Beagle", "Basset Hound", "Teckel",
        "Chihuahua", "Yorkshire Terrier", "Shih Tzu", "Jack Russell Terrier",
        "Staffordshire Bull Terrier", "American Staffordshire Terrier", "Rottweiler",
        "Doberman", "Boxer", "Dogue de Bordeaux", "Cane Corso", "Akita Inu", "Shiba Inu",
        "Husky Sibérien", "Malamute d'Alaska", "Samoyède", "Braque de Weimar",
        "Épagneul Breton", "Setter Anglais", "Setter Irlandais", "Pointer Anglais",
        "Cavalier King Charles", "Bichon Frisé", "Bichon Maltais", "Spitz Nain (Poméranien)",
        "Whippet", "Greyhound", "Terre-Neuve", "Saint-Bernard", "Bull Terrier",
        "West Highland White Terrier", "Schnauzer", "Colley", "Berger des Shetland",
        "Chow-Chow", "Dalmatien", "Bouvier Bernois", "Leonberg", "Berger Blanc Suisse",
        "Lévrier Afghan", "Griffon Bruxellois", "Fox Terrier", "Pinscher Nain",
        "Croisé / Bâtard",
    ],
    'CHAT': [
        "Européen (chat de gouttière)", "Persan", "Maine Coon", "Siamois",
        "British Shorthair", "British Longhair", "Ragdoll", "Sacré de Birmanie",
        "Sphynx", "Bengal", "Abyssin", "Somali", "Chartreux", "Norvégien", "Sibérien",
        "Angora Turc", "Devon Rex", "Cornish Rex", "Scottish Fold", "Scottish Straight",
        "Bleu Russe", "Burmese", "Tonkinois", "Oriental", "Savannah", "Manx",
        "American Shorthair", "Exotic Shorthair", "Nebelung", "Ocicat", "Singapura",
        "Balinais", "Korat", "Chausie", "Croisé / Gouttière",
    ],
    'RONGEUR': [
        "Hamster Doré (Syrien)", "Hamster Nain Russe", "Hamster Roborovski",
        "Hamster Chinois", "Cochon d'Inde (Cavia)", "Rat Domestique", "Souris Domestique",
        "Gerbille", "Chinchilla", "Octodon (Dègue du Chili)", "Lapin Bélier",
        "Lapin Nain", "Lapin Angora", "Lapin Rex", "Autre rongeur",
    ],
    'OISEAU': [
        "Perruche Ondulée", "Perruche Calopsitte", "Perruche Catherine (à collier)",
        "Inséparable (Agapornis)", "Canari", "Diamant Mandarin",
        "Perroquet Gris du Gabon", "Ara", "Amazone", "Cacatoès", "Conure", "Pigeon",
        "Tourterelle", "Autre oiseau",
    ],
    'AUTRE': [
        "Furet", "Tortue terrestre", "Tortue aquatique", "Serpent", "Lézard / Reptile",
        "Poisson d'aquarium", "Cheval / Poney", "Autre",
    ],
}


def seed_referentiels(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Robe = apps.get_model('animaux', 'Robe')
    Race = apps.get_model('animaux', 'Race')

    especes_par_code = {}
    for code, nom in ESPECES:
        espece, _ = Espece.objects.get_or_create(code=code, defaults={'nom': nom})
        especes_par_code[code] = espece

    for code, nom in ROBES:
        Robe.objects.get_or_create(code=code, defaults={'nom': nom})

    for code, races in RACES_PAR_ESPECE.items():
        espece = especes_par_code[code]
        for nom_race in races:
            Race.objects.get_or_create(espece=espece, nom=nom_race)


def supprimer_referentiels(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Robe = apps.get_model('animaux', 'Robe')
    Robe.objects.filter(code__in=[c for c, _ in ROBES]).delete()
    Espece.objects.filter(code__in=[c for c, _ in ESPECES]).delete()  # cascade sur Race


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0002_alter_animal_proprietaire'),
    ]

    operations = [
        migrations.CreateModel(
            name='Espece',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='Code')),
                ('nom', models.CharField(max_length=50, verbose_name="Nom de l'espèce")),
            ],
            options={
                'verbose_name': 'Espèce',
                'verbose_name_plural': 'Espèces',
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='Robe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='Code')),
                ('nom', models.CharField(max_length=50, verbose_name='Nom de la robe')),
            ],
            options={
                'verbose_name': 'Robe',
                'verbose_name_plural': 'Robes',
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='Race',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='Nom de la race')),
                ('espece', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='races', to='animaux.espece', verbose_name='Espèce')),
            ],
            options={
                'verbose_name': 'Race',
                'verbose_name_plural': 'Races',
                'ordering': ['espece__nom', 'nom'],
            },
        ),
        migrations.AddConstraint(
            model_name='race',
            constraint=models.UniqueConstraint(fields=('espece', 'nom'), name='race_unique_par_espece'),
        ),
        migrations.RunPython(seed_referentiels, supprimer_referentiels),
    ]
