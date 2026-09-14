from django.db import migrations


def populer_fk(apps, schema_editor):
    Animal = apps.get_model('animaux', 'Animal')
    Espece = apps.get_model('animaux', 'Espece')
    Robe = apps.get_model('animaux', 'Robe')
    Race = apps.get_model('animaux', 'Race')

    espece_autre, _ = Espece.objects.get_or_create(code='AUTRE', defaults={'nom': 'Autre'})
    robe_autre, _ = Robe.objects.get_or_create(code='AUTRE', defaults={'nom': 'Autre'})

    for animal in Animal.objects.all():
        espece_obj = Espece.objects.filter(code=animal.espece).first() or espece_autre
        robe_obj = Robe.objects.filter(code=animal.robe).first() or robe_autre

        nom_race = (animal.race or '').strip() or 'Autre'
        race_obj = Race.objects.filter(espece=espece_obj, nom__iexact=nom_race).first()
        if race_obj is None:
            race_obj = Race.objects.create(espece=espece_obj, nom=nom_race)

        animal.espece_fk = espece_obj
        animal.robe_fk = robe_obj
        animal.race_fk = race_obj
        animal.save(update_fields=['espece_fk', 'robe_fk', 'race_fk'])


def revenir_en_arriere(apps, schema_editor):
    # Rien à faire : les anciens champs texte n'ont pas été modifiés par cette migration.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0004_animal_fk_temp_fields'),
    ]

    operations = [
        migrations.RunPython(populer_fk, revenir_en_arriere),
    ]
