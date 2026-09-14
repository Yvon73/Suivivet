from django.db import migrations

# (nom du traitement, classe) — classement du catalogue par défaut créé dans
# 0004_seed_traitements par forme d'administration (galénique).
CLASSES_TRAITEMENTS = [
    ("Vermifuge (comprimé)", "COMPRIME"),
    ("Vermifuge (solution buvable)", "SOLUTION_BUVABLE"),
    ("Antiparasitaire externe (pipette spot-on)", "PIPETTE"),
    ("Antiparasitaire externe (comprimé)", "COMPRIME"),
    ("Collier antiparasitaire", "COLLIER"),
    ("Shampooing antiparasitaire", "SHAMPOOING"),
    ("Spray antiparasitaire", "SPRAY"),
    ("Crème/pommade dermatologique", "CREME"),
    ("Crème antifongique", "CREME"),
    ("Collyre (gouttes oculaires)", "COLLYRE"),
    ("Gouttes auriculaires", "GOUTTES_AURICULAIRES"),
    ("Antibiotique (comprimé)", "COMPRIME"),
    ("Anti-inflammatoire (comprimé)", "COMPRIME"),
    ("Complément alimentaire / cure vitaminée", "COMPRIME"),
]


def definir_classe(apps, schema_editor):
    Traitement = apps.get_model('vaccins', 'Traitement')
    for nom, classe in CLASSES_TRAITEMENTS:
        Traitement.objects.filter(nom__iexact=nom).update(classe=classe)


def revenir_en_arriere(apps, schema_editor):
    Traitement = apps.get_model('vaccins', 'Traitement')
    noms = [nom for nom, _ in CLASSES_TRAITEMENTS]
    Traitement.objects.filter(nom__in=noms).update(classe='AUTRE')


class Migration(migrations.Migration):

    dependencies = [
        ('vaccins', '0009_alter_traitement_options_traitement_classe'),
    ]

    operations = [
        migrations.RunPython(definir_classe, revenir_en_arriere),
    ]
