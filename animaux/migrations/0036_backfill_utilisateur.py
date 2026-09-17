from django.db import migrations


def backfill_utilisateur(apps, schema_editor):
    """Rattache les Animal/Proprietaire deja en base (crees avant l'isolation
    des donnees par compte) au premier superutilisateur existant — c'est
    l'unique compte administrateur au moment ou cette fonctionnalite a ete
    introduite, cf. accueil.PremierUtilisateurCreateView."""
    User = apps.get_model('auth', 'User')
    Animal = apps.get_model('animaux', 'Animal')
    Proprietaire = apps.get_model('animaux', 'Proprietaire')

    premier_superuser = User.objects.filter(is_superuser=True).order_by('date_joined').first()
    if not premier_superuser:
        return

    Animal.objects.filter(utilisateur__isnull=True).update(utilisateur=premier_superuser)
    Proprietaire.objects.filter(utilisateur__isnull=True).update(utilisateur=premier_superuser)


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0035_animal_utilisateur_proprietaire_utilisateur_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_utilisateur, migrations.RunPython.noop),
    ]
