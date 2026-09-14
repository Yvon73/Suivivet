# Reporte les animaux marqués lof=True vers le nouveau champ
# organisme/organisme_autre (migration 0020) : vers l'organisme LOF (chiens)
# ou LOOF (chats) — les deux seuls organismes qu'une case "LOF" générique
# pouvait raisonnablement désigner selon l'espèce — puis, pour les autres
# espèces (où LOF n'a pas de sens réel), conserve l'information en saisie
# libre plutôt que de la perdre. Le champ lof lui-même n'est supprimé qu'à
# la migration 0022 (séparée : PostgreSQL refuse d'altérer la table
# animaux_animal, encore soumise aux triggers de la mise à jour ci-dessous,
# dans la même transaction).
from django.db import migrations


def migrer_lof_vers_organisme(apps, schema_editor):
    Animal = apps.get_model('animaux', 'Animal')
    Organisme = apps.get_model('animaux', 'Organisme')

    lof = Organisme.objects.filter(espece='CHIEN', nom_court='LOF').first()
    loof = Organisme.objects.filter(espece='CHAT', nom_court='LOOF').first()

    for animal in Animal.objects.filter(lof=True).select_related('espece'):
        code_espece = animal.espece.code
        if code_espece == 'CHIEN' and lof:
            animal.organisme = lof
        elif code_espece == 'CHAT' and loof:
            animal.organisme = loof
        else:
            animal.organisme_autre = 'LOF'
        animal.save(update_fields=['organisme', 'organisme_autre'])


def revenir_en_arriere(apps, schema_editor):
    # À ce stade de la remontée, la migration 0022 (RemoveField lof) a déjà
    # été annulée (le champ existe de nouveau) : on peut donc restaurer
    # lof=True pour les animaux migrés vers LOF/LOOF/« LOF » en saisie libre.
    Animal = apps.get_model('animaux', 'Animal')
    Animal.objects.filter(organisme__espece='CHIEN', organisme__nom_court='LOF').update(lof=True)
    Animal.objects.filter(organisme__espece='CHAT', organisme__nom_court='LOOF').update(lof=True)
    Animal.objects.filter(organisme_autre='LOF').update(lof=True)


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0020_animal_organisme_fields'),
    ]

    operations = [
        migrations.RunPython(migrer_lof_vers_organisme, revenir_en_arriere),
    ]
