# Reprend l'ancien champ Animal.proprietaire (un simple email) vers une fiche
# Proprietaire (migration 0029), en dédupliquant par email : deux animaux
# partageant le même email de propriétaire pointent désormais vers la même
# fiche. Le nom est dérivé de la partie locale de l'email (ex.
# « jean.dupont@... » -> « Jean Dupont ») à défaut de mieux : à compléter
# ensuite via la fiche propriétaire (migration 0032 pour la suppression de
# l'ancien champ).
from django.db import migrations


def deriver_nom(email):
    partie_locale = email.split('@', 1)[0]
    mots = [mot for mot in partie_locale.replace('_', '.').replace('+', '.').split('.') if mot]
    return ' '.join(mot.capitalize() for mot in mots) or email


def migrer_vers_proprietaire(apps, schema_editor):
    Animal = apps.get_model('animaux', 'Animal')
    Proprietaire = apps.get_model('animaux', 'Proprietaire')

    proprietaires_par_email = {}
    for animal in Animal.objects.all():
        email = (animal.proprietaire or '').strip()
        cle = email.lower()
        proprietaire = proprietaires_par_email.get(cle)
        if proprietaire is None:
            proprietaire = Proprietaire.objects.filter(email__iexact=email).first() if email else None
        if proprietaire is None:
            proprietaire = Proprietaire.objects.create(nom=deriver_nom(email) if email else 'Inconnu', email=email)
        proprietaires_par_email[cle] = proprietaire
        animal.proprietaire_fk = proprietaire
        animal.save(update_fields=['proprietaire_fk'])


def revenir_vers_email(apps, schema_editor):
    Animal = apps.get_model('animaux', 'Animal')
    for animal in Animal.objects.all():
        if animal.proprietaire_fk_id:
            animal.proprietaire = animal.proprietaire_fk.email
            animal.save(update_fields=['proprietaire'])


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0030_animal_proprietaire_fk'),
    ]

    operations = [
        migrations.RunPython(migrer_vers_proprietaire, revenir_vers_email),
    ]
