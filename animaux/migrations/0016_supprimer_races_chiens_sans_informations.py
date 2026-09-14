# Supprime les races de chiens qui n'ont pas la fiche détaillée du catalogue
# (migration 0013/0015 : ni origine, taille, poids, espérance de vie,
# description, groupe FCI...) — que leur dangerosité (migration 0008) soit
# renseignée ou non. Ce sont des races du catalogue d'origine (migration
# 0003) dont le nom ne correspond à aucune entrée exacte de
# static/data/races_chiens.json (écart d'orthographe ou de graphie : ex.
# « Doberman » / « Dobermann », « Chow-Chow » / « Chow Chow », « Berger
# Belge Malinois » / « Berger Belge (Malinois) »), ou une entrée sans
# équivalent dans le nouveau catalogue (« Berger », « Croisé / Bâtard »...).
#
# Une race utilisée par au moins un animal est systématiquement conservée
# (de toute façon protégée par la contrainte PROTECT sur Animal.race).
from django.db import migrations


def supprimer_races_chiens_sans_informations(apps, schema_editor):
    Race = apps.get_model('animaux', 'Race')
    Race.objects.filter(
        espece__code='CHIEN',
        origine='', taille_min__isnull=True, taille_max__isnull=True,
        poids_min__isnull=True, poids_max__isnull=True,
        esperance_vie='', description='', groupe_fci='',
        categorie='', sous_categorie='', nom_scientifique='',
        niveau_soin='', legislation_france='', prix_moyen='',
        infos_complementaires__isnull=True,
        animaux__isnull=True,
    ).delete()


def restaurer_races_chiens_sans_informations(apps, schema_editor):
    # Non réversible : ces races ne portaient qu'un nom, une espèce et
    # éventuellement une dangerosité — rien à recréer de façon fiable.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0015_importer_catalogue_races'),
    ]

    operations = [
        migrations.RunPython(supprimer_races_chiens_sans_informations, restaurer_races_chiens_sans_informations),
    ]
