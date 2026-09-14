from django.db import migrations

# Vaccins courants utilisés en France pour chiens et chats (valences essentielles
# et optionnelles usuelles), d'après les recommandations vétérinaires (WSAVA/ANMV).
VACCINS_PAR_DEFAUT = [
    ("Rage", "Vaccin antirabique, obligatoire pour les voyages et certains chiens catégorisés."),
    ("Maladie de Carré", "Chien (CDV) - fièvre, troubles respiratoires, digestifs et nerveux."),
    ("Hépatite de Rubarth", "Chien (CAV-1/CAV-2) - atteinte grave du foie."),
    ("Parvovirose", "Chien (CPV-2) - gastro-entérite hémorragique, très contagieuse."),
    ("Leptospirose", "Chien - transmise par l'urine des rongeurs, zoonose, rappel annuel."),
    ("Toux du chenil", "Chien (Bordetella/Parainfluenza) - recommandé en collectivité."),
    ("Piroplasmose", "Chien (Babésiose) - transmise par les tiques."),
    ("Leishmaniose", "Chien - transmise par le phlébotome, zones à risque (sud de la France)."),
    ("Maladie de Lyme (Borréliose)", "Chien - transmise par les tiques."),
    ("Typhus (Panleucopénie féline)", "Chat - gastro-entérite sévère, très contagieuse."),
    ("Coryza", "Chat (Herpèsvirus/Calicivirus) - troubles respiratoires et oculaires."),
    ("Leucose féline (FeLV)", "Chat - recommandé pour les chats ayant accès à l'extérieur."),
    ("Chlamydiose féline", "Chat - conjonctivite, recommandé en collectivité."),
]


def creer_vaccins_par_defaut(apps, schema_editor):
    Vaccin = apps.get_model('vaccins', 'Vaccin')
    for nom, description in VACCINS_PAR_DEFAUT:
        Vaccin.objects.get_or_create(nom__iexact=nom, defaults={'nom': nom, 'description': description})


def supprimer_vaccins_par_defaut(apps, schema_editor):
    Vaccin = apps.get_model('vaccins', 'Vaccin')
    noms = [nom for nom, _ in VACCINS_PAR_DEFAUT]
    Vaccin.objects.filter(nom__in=noms).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vaccins', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(creer_vaccins_par_defaut, supprimer_vaccins_par_defaut),
    ]
