# Reprend les champs identification/organisme/organisme_autre de chaque
# Animal existant vers une ligne AnimalIdentification (cf. migration 0025),
# avant leur suppression du modèle Animal (migration 0027).
from django.db import migrations


def migrer_vers_animalidentification(apps, schema_editor):
    Animal = apps.get_model('animaux', 'Animal')
    AnimalIdentification = apps.get_model('animaux', 'AnimalIdentification')

    for animal in Animal.objects.all():
        if animal.identification or animal.organisme_id or animal.organisme_autre:
            AnimalIdentification.objects.create(
                animal=animal,
                organisme_id=animal.organisme_id,
                organisme_autre=animal.organisme_autre,
                identification=animal.identification,
            )


def revenir_vers_animal(apps, schema_editor):
    Animal = apps.get_model('animaux', 'Animal')
    AnimalIdentification = apps.get_model('animaux', 'AnimalIdentification')

    for animal in Animal.objects.all():
        premiere = animal.identifications.order_by('id').first()
        if premiere:
            animal.identification = premiere.identification
            animal.organisme_id = premiere.organisme_id
            animal.organisme_autre = premiere.organisme_autre
            animal.save(update_fields=['identification', 'organisme', 'organisme_autre'])
    AnimalIdentification.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0025_animalidentification'),
    ]

    operations = [
        migrations.RunPython(migrer_vers_animalidentification, revenir_vers_animal),
    ]
