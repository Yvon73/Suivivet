from django.db import migrations

# Catégories génériques de traitements/médicaments vétérinaires courants (chien,
# chat, et autres espèces le cas échéant), classées par forme d'administration.
# Noms génériques (pas de marques commerciales) pour rester valables quel que
# soit le produit effectivement prescrit par le vétérinaire.
TRAITEMENTS_PAR_DEFAUT = [
    # Antiparasitaires internes (vermifuges)
    ("Vermifuge (comprimé)", "Chien/chat - traitement des vers ronds et plats, rappel tous les 3 mois en moyenne."),
    ("Vermifuge (solution buvable)", "Adapté aux chiots/chatons et petits animaux ne pouvant avaler de comprimé."),
    # Antiparasitaires externes
    ("Antiparasitaire externe (pipette spot-on)", "Chien/chat/lapin - contre puces et tiques, application cutanée mensuelle."),
    ("Antiparasitaire externe (comprimé)", "Chien/chat - traitement oral contre les puces."),
    ("Collier antiparasitaire", "Chien/chat - protection longue durée (plusieurs mois) contre puces et tiques."),
    ("Shampooing antiparasitaire", "Chien/chat - en cas de forte infestation par puces/tiques."),
    ("Spray antiparasitaire", "Application sur le pelage ou l'environnement (panier, coussins) contre puces/tiques."),
    # Dermatologie
    ("Crème/pommade dermatologique", "Cicatrisante ou anti-inflammatoire locale, plaies et irritations cutanées."),
    ("Crème antifongique", "Traitement local des mycoses cutanées (teigne, dermatophytose)."),
    ("Collyre (gouttes oculaires)", "Traitement des conjonctivites et irritations oculaires."),
    ("Gouttes auriculaires", "Traitement des otites externes."),
    # Médicaments généraux
    ("Antibiotique (comprimé)", "Traitement des infections bactériennes, sur prescription vétérinaire."),
    ("Anti-inflammatoire (comprimé)", "Anti-inflammatoire non stéroïdien (AINS), douleurs et inflammations."),
    ("Complément alimentaire / cure vitaminée", "Comprimé ou pâte, soutien nutritionnel ponctuel (articulations, pelage, convalescence)."),
]


def creer_traitements_par_defaut(apps, schema_editor):
    Traitement = apps.get_model('vaccins', 'Traitement')
    for nom, description in TRAITEMENTS_PAR_DEFAUT:
        Traitement.objects.get_or_create(nom__iexact=nom, defaults={'nom': nom, 'description': description})


def supprimer_traitements_par_defaut(apps, schema_editor):
    Traitement = apps.get_model('vaccins', 'Traitement')
    noms = [nom for nom, _ in TRAITEMENTS_PAR_DEFAUT]
    Traitement.objects.filter(nom__in=noms).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vaccins', '0003_seed_vaccins_nac'),
    ]

    operations = [
        migrations.RunPython(creer_traitements_par_defaut, supprimer_traitements_par_defaut),
    ]
