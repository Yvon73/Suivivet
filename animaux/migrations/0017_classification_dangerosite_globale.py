# Étend l'évaluation de dangerosité (indicateur interne de précaution à la
# manipulation, PAS une catégorisation légale — cf. migration 0008) à
# l'ensemble du catalogue, toutes espèces confondues, plutôt qu'aux seuls
# chiens du catalogue d'origine. Sans cela, le bandeau de dangerosité de la
# fiche animal (qui ne s'affiche que si niveau_dangerosite != NON_RENSEIGNE)
# reste invisible pour la quasi-totalité des races importées (migration 0015).
#
# Méthode, par ordre de priorité :
#   1. Chiens : mêmes listes qu'en migration 0008/l'essai précédent (races
#      molossoïdes/de combat -> ÉLEVÉE, races de garde/protection -> MODÉRÉE),
#      complétées ici avec les variantes d'orthographe du catalogue JSON.
#   2. Quelques races d'autres espèces pour lesquelles le catalogue JSON
#      lui-même signale un risque (ex. le champ imbriqué "venin.dangerosite"
#      du Mygale Rose) ou dont le risque de manipulation est bien documenté
#      (morsure des grands psittacidés, constriction d'un python, félin
#      hybride Savannah) -> MODÉRÉE.
#   3. Toutes les autres races encore à NON_RENSEIGNE (toutes espèces) :
#      AUCUNE dangerosité particulière connue par défaut — comme pour le
#      catalogue d'origine, jamais laissées à NON_RENSEIGNE quand elles sont
#      cataloguées, cet indicateur restant modifiable à tout moment (admin,
#      ou fiche race) sans jamais toucher aux autres données de l'animal.
from django.db import migrations

ELEVEE_CHIENS = [
    'American Staffordshire Terrier', 'Cane Corso', 'Dogue de Bordeaux', 'Rottweiler',
    'Staffordshire Bull Terrier', 'Bull Terrier', 'Akita Inu', 'Doberman', 'Dobermann',
    'American Pit Bull Terrier', 'Bulldog Américain', 'Boerboel',
    'Cão de Fila de São Miguel', 'Dogue Argentin', 'Dogue Espagnol',
    'Mâtin Espagnol', 'Fila Brasileiro', 'Mâtin de Naples', 'Tosa Inu', 'Bullmastiff',
]

MODEREE_CHIENS = [
    'Berger Allemand', 'Berger Belge Malinois', 'Berger Blanc Suisse', 'Boxer', 'Chow-Chow',
    'Berger Belge (Malinois)', 'Berger Belge (Groenendael)', 'Berger Belge (Laekenois)',
    'Berger Belge (Tervueren)', 'Chow Chow', 'Dogue Allemand', 'Dogue du Tibet',
    'Russian Black Terrier', 'American Akita',
]

# (espece_code, [noms]) -> MODÉRÉE, pour les espèces autres que Chien.
MODEREE_AUTRES_ESPECES = [
    ('CHAT', ['Savannah', 'Savannah Mi-Long']),  # hybride serval, instincts marqués
    ('ARACHNIDE', ['Mygale Rose']),  # venin listé "Faible" dans le catalogue NAC
    ('REPTILE', ['Python Royal']),  # constricteur, risque à la manipulation
    ('OISEAU', ['Ara', 'Cacatoès', 'Perroquet Gris du Gabon']),  # morsure puissante
]


def peupler_dangerosite(apps, schema_editor):
    Race = apps.get_model('animaux', 'Race')

    Race.objects.filter(espece__code='CHIEN', nom__in=ELEVEE_CHIENS).update(
        niveau_dangerosite='ELEVEE'
    )
    Race.objects.filter(espece__code='CHIEN', nom__in=MODEREE_CHIENS).update(
        niveau_dangerosite='MODEREE'
    )
    for espece_code, noms in MODEREE_AUTRES_ESPECES:
        Race.objects.filter(espece__code=espece_code, nom__in=noms).update(
            niveau_dangerosite='MODEREE'
        )

    # Défaut : sans dangerosité particulière connue, pour toutes les races
    # encore à NON_RENSEIGNE (toutes espèces, y compris les chiens non listés
    # ci-dessus).
    Race.objects.filter(niveau_dangerosite='NON_RENSEIGNE').update(
        niveau_dangerosite='AUCUNE'
    )


def revenir_en_arriere(apps, schema_editor):
    # Réversible seulement pour les races listées explicitement ci-dessus :
    # impossible de distinguer a posteriori, parmi les races passées à AUCUNE
    # par défaut, celles qui l'étaient déjà avant cette migration de celles
    # modifiées depuis manuellement (admin).
    Race = apps.get_model('animaux', 'Race')
    Race.objects.filter(
        espece__code='CHIEN', nom__in=ELEVEE_CHIENS + MODEREE_CHIENS
    ).update(niveau_dangerosite='NON_RENSEIGNE')
    for espece_code, noms in MODEREE_AUTRES_ESPECES:
        Race.objects.filter(espece__code=espece_code, nom__in=noms).update(
            niveau_dangerosite='NON_RENSEIGNE'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0016_supprimer_races_chiens_sans_informations'),
    ]

    operations = [
        migrations.RunPython(peupler_dangerosite, revenir_en_arriere),
    ]
