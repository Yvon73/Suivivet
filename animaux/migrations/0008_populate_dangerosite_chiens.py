# Renseigne un degré de dangerosité par défaut pour les races de chiens déjà
# cataloguées (migration 0003). Il s'agit d'un indicateur interne de précaution
# à la manipulation propre au cabinet, pas d'une catégorisation légale : il
# reste modifiable à tout moment (admin, ou fiche race) sans jamais toucher
# aux autres données de l'animal.
from django.db import migrations

DANGEROSITE_ELEVEE = [
    "American Staffordshire Terrier", "Cane Corso", "Dogue de Bordeaux", "Rottweiler",
    "Staffordshire Bull Terrier", "Bull Terrier", "Akita Inu", "Doberman",
]

DANGEROSITE_MODEREE = [
    "Berger Allemand", "Berger Belge Malinois", "Berger Blanc Suisse", "Boxer", "Chow-Chow",
]

# Toutes les autres races de chiens du catalogue de la migration 0003 sont
# considérées sans dangerosité particulière connue.
DANGEROSITE_AUCUNE = [
    "Labrador Retriever", "Golden Retriever", "Berger Australien", "Border Collie",
    "Bouledogue Français", "Bouledogue Anglais", "Carlin", "Caniche",
    "Cocker Spaniel Anglais", "Beagle", "Basset Hound", "Teckel", "Chihuahua",
    "Yorkshire Terrier", "Shih Tzu", "Jack Russell Terrier",
    "Husky Sibérien", "Malamute d'Alaska", "Samoyède", "Braque de Weimar",
    "Épagneul Breton", "Setter Anglais", "Setter Irlandais", "Pointer Anglais",
    "Cavalier King Charles", "Bichon Frisé", "Bichon Maltais",
    "Spitz Nain (Poméranien)", "Whippet", "Greyhound", "Terre-Neuve",
    "Saint-Bernard", "West Highland White Terrier", "Schnauzer", "Colley",
    "Berger des Shetland", "Dalmatien", "Bouvier Bernois", "Leonberg",
    "Lévrier Afghan", "Griffon Bruxellois", "Fox Terrier", "Pinscher Nain",
    "Croisé / Bâtard", "Shiba Inu",
]


def _appliquer(niveaux_par_nom, apps, valeur):
    Race = apps.get_model('animaux', 'Race')
    Race.objects.filter(espece__code='CHIEN', nom__in=niveaux_par_nom).update(niveau_dangerosite=valeur)


def peupler_dangerosite(apps, schema_editor):
    _appliquer(DANGEROSITE_ELEVEE, apps, 'ELEVEE')
    _appliquer(DANGEROSITE_MODEREE, apps, 'MODEREE')
    _appliquer(DANGEROSITE_AUCUNE, apps, 'AUCUNE')


def revenir_en_arriere(apps, schema_editor):
    Race = apps.get_model('animaux', 'Race')
    Race.objects.filter(espece__code='CHIEN').update(niveau_dangerosite='NON_RENSEIGNE')


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0007_race_niveau_dangerosite'),
    ]

    operations = [
        migrations.RunPython(peupler_dangerosite, revenir_en_arriere),
    ]
