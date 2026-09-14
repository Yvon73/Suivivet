from django.db import migrations

# Nouveaux vaccins réellement disponibles en France pour d'autres espèces (NAC).
# Il n'existe pas de vaccin avec AMM en France pour les rongeurs de compagnie
# (hamsters, rats, souris, cochons d'Inde) : aucune entrée n'est donc ajoutée
# pour ces espèces.
NOUVEAUX_VACCINS = [
    ("Myxomatose", "Lapin - transmise par puces/moustiques, souvent mortelle. Rappel annuel."),
    ("Maladie hémorragique virale du lapin (VHD)", "Lapin - calicivirus très résistant dans l'environnement, mortalité élevée. Rappel annuel."),
    ("Paramyxovirose aviaire (maladie de Newcastle)", "Oiseaux (notamment pigeons) - maladie virale grave et très contagieuse."),
]

# Descriptions mises à jour pour préciser que ces vaccins s'appliquent aussi aux furets.
DESCRIPTIONS_MISES_A_JOUR = {
    "Rage": (
        "Vaccin antirabique, obligatoire pour les voyages et certains chiens catégorisés. "
        "Utilisable aussi chez le furet (AMM Rabisin), rappel annuel pour cette espèce.",
        "Vaccin antirabique, obligatoire pour les voyages et certains chiens catégorisés.",
    ),
    "Maladie de Carré": (
        "Chien et furet (CDV) - fièvre, troubles respiratoires, digestifs et nerveux, très souvent mortelle chez le furet.",
        "Chien (CDV) - fièvre, troubles respiratoires, digestifs et nerveux.",
    ),
}


def ajouter_vaccins_nac(apps, schema_editor):
    Vaccin = apps.get_model('vaccins', 'Vaccin')
    for nom, description in NOUVEAUX_VACCINS:
        Vaccin.objects.get_or_create(nom__iexact=nom, defaults={'nom': nom, 'description': description})

    for nom, (nouvelle_description, _) in DESCRIPTIONS_MISES_A_JOUR.items():
        Vaccin.objects.filter(nom__iexact=nom).update(description=nouvelle_description)


def retirer_vaccins_nac(apps, schema_editor):
    Vaccin = apps.get_model('vaccins', 'Vaccin')
    noms = [nom for nom, _ in NOUVEAUX_VACCINS]
    Vaccin.objects.filter(nom__in=noms).delete()

    for nom, (_, ancienne_description) in DESCRIPTIONS_MISES_A_JOUR.items():
        Vaccin.objects.filter(nom__iexact=nom).update(description=ancienne_description)


class Migration(migrations.Migration):

    dependencies = [
        ('vaccins', '0002_seed_vaccins'),
    ]

    operations = [
        migrations.RunPython(ajouter_vaccins_nac, retirer_vaccins_nac),
    ]
