from django.db import migrations


def backfill_utilisateur(apps, schema_editor):
    """Rattache les Facture deja en base (creees avant l'isolation des
    donnees par compte) au compte proprietaire de leur animal quand il y en a
    un, sinon au premier superutilisateur existant (facture partagee sans
    animal renseigne)."""
    User = apps.get_model('auth', 'User')
    Facture = apps.get_model('factures', 'Facture')

    premier_superuser = User.objects.filter(is_superuser=True).order_by('date_joined').first()

    for facture in Facture.objects.filter(utilisateur__isnull=True).select_related('animal'):
        if facture.animal_id and facture.animal.utilisateur_id:
            facture.utilisateur_id = facture.animal.utilisateur_id
            facture.save(update_fields=['utilisateur'])
        elif premier_superuser:
            facture.utilisateur = premier_superuser
            facture.save(update_fields=['utilisateur'])


class Migration(migrations.Migration):

    dependencies = [
        ('factures', '0005_facture_utilisateur'),
        ('animaux', '0036_backfill_utilisateur'),
    ]

    operations = [
        migrations.RunPython(backfill_utilisateur, migrations.RunPython.noop),
    ]
