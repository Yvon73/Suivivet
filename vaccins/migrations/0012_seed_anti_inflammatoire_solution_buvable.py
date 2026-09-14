from django.db import migrations


def ajouter_traitement(apps, schema_editor):
    Traitement = apps.get_model('vaccins', 'Traitement')
    Traitement.objects.get_or_create(
        nom__iexact="Anti-inflammatoire (solution buvable)",
        defaults={
            'nom': "Anti-inflammatoire (solution buvable)",
            'description': "Anti-inflammatoire non stéroïdien (AINS) en solution buvable, douleurs et inflammations.",
            'classe': 'SOLUTION_BUVABLE',
        },
    )


def retirer_traitement(apps, schema_editor):
    Traitement = apps.get_model('vaccins', 'Traitement')
    Traitement.objects.filter(nom__iexact="Anti-inflammatoire (solution buvable)").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vaccins', '0011_remove_suivivaccintraitement_dose_comprimes_and_more'),
    ]

    operations = [
        migrations.RunPython(ajouter_traitement, retirer_traitement),
    ]
