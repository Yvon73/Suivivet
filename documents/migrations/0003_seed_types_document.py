from django.db import migrations

TYPES_PAR_DEFAUT = [
    "Analyse de sang",
    "Analyse biologique",
    "Radio",
    "Echographie",
]


def creer_types_par_defaut(apps, schema_editor):
    TypeDocument = apps.get_model('documents', 'TypeDocument')
    for nom in TYPES_PAR_DEFAUT:
        TypeDocument.objects.get_or_create(nom__iexact=nom, defaults={'nom': nom})


def supprimer_types_par_defaut(apps, schema_editor):
    TypeDocument = apps.get_model('documents', 'TypeDocument')
    TypeDocument.objects.filter(nom__in=TYPES_PAR_DEFAUT).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_alter_document_fichier'),
    ]

    operations = [
        migrations.RunPython(creer_types_par_defaut, supprimer_types_par_defaut),
    ]
