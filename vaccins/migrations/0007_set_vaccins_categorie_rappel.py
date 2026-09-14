from django.db import migrations

# (nom du vaccin, catégorie, intervalle de rappel)
# Sources : recommandations WSAVA/ANMV et réglementation française (voir aussi
# les descriptions du catalogue créées dans 0002/0003_seed_vaccins*).
INFOS_VACCINS = [
    ("Rage", "OBLIGATOIRE", "Annuel à tous les 3 ans selon le vaccin (obligatoire pour voyages, chiens catégorisés, furets voyageurs)"),
    ("Maladie de Carré", "ESSENTIEL", "Tous les 3 ans après la primovaccination"),
    ("Hépatite de Rubarth", "ESSENTIEL", "Tous les 3 ans après la primovaccination"),
    ("Parvovirose", "ESSENTIEL", "Tous les 3 ans après la primovaccination"),
    ("Leptospirose", "ESSENTIEL", "Annuel"),
    ("Toux du chenil", "RECOMMANDE", "Annuel (si vie en collectivité)"),
    ("Piroplasmose", "RECOMMANDE", "Annuel"),
    ("Leishmaniose", "RECOMMANDE", "Annuel (zones à risque)"),
    ("Maladie de Lyme (Borréliose)", "RECOMMANDE", "Annuel"),
    ("Typhus (Panleucopénie féline)", "ESSENTIEL", "Tous les 3 ans après la primovaccination"),
    ("Coryza", "ESSENTIEL", "Annuel"),
    ("Leucose féline (FeLV)", "RECOMMANDE", "Annuel (si accès à l'extérieur)"),
    ("Chlamydiose féline", "RECOMMANDE", "Annuel (si vie en collectivité)"),
    ("Myxomatose", "RECOMMANDE", "Annuel"),
    ("Maladie hémorragique virale du lapin (VHD)", "RECOMMANDE", "Annuel"),
    ("Paramyxovirose aviaire (maladie de Newcastle)", "RECOMMANDE", "Annuel"),
]


def definir_categorie_et_rappel(apps, schema_editor):
    Vaccin = apps.get_model('vaccins', 'Vaccin')
    for nom, categorie, rappel in INFOS_VACCINS:
        Vaccin.objects.filter(nom__iexact=nom).update(categorie=categorie, rappel_interval=rappel)


def revenir_en_arriere(apps, schema_editor):
    Vaccin = apps.get_model('vaccins', 'Vaccin')
    noms = [nom for nom, _, _ in INFOS_VACCINS]
    Vaccin.objects.filter(nom__in=noms).update(categorie='RECOMMANDE', rappel_interval='')


class Migration(migrations.Migration):

    dependencies = [
        ('vaccins', '0006_vaccin_rappel_max_length'),
    ]

    operations = [
        migrations.RunPython(definir_categorie_et_rappel, revenir_en_arriere),
    ]
