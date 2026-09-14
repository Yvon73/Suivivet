# Ajoute l'espèce Équidé (code EQUIDE) et son catalogue de races : chevaux,
# poneys et ânes — un maximum de chaque race réellement reconnue, répartis
# via le champ `categorie` de Race pour un regroupement cohérent avec le
# reste du catalogue (cf. AnimalForm._libelle_categorie_race).
#
# Note : le catalogue d'organismes officiels (migration 0019,
# static/data/organismes_officiel.json) référence déjà des organismes
# d'espèce "CHEVAL" (SIRE, IFCE, FFE, FEI, Jockey Club) — Organisme.espece
# reste un simple code indépendant du référentiel Espece de cette migration,
# aucune modification n'est nécessaire de ce côté.
from django.db import migrations

ESPECE_EQUIDE = ('EQUIDE', 'Équidé')

# (nom, description, origine, catégorie, espérance de vie)
RACES_EQUIDE = [
    # --- Chevaux -----------------------------------------------------------
    ("Pur-sang Anglais", "Cheval de course par excellence, réputé pour sa vitesse et son endurance.", "Royaume-Uni", "Cheval", "25-30 ans"),
    ("Arabe", "Une des plus anciennes races, endurance remarquable et tête fine caractéristique.", "Péninsule arabique", "Cheval", "25-30 ans"),
    ("Selle Français", "Cheval de sport polyvalent, référence en saut d'obstacles et concours complet.", "France", "Cheval", "25-30 ans"),
    ("Anglo-Arabe", "Croisement Pur-sang/Arabe, alliant vitesse et élégance.", "France", "Cheval", "25-30 ans"),
    ("Frison", "Cheval noir à la crinière abondante, allures relevées et spectaculaires.", "Pays-Bas", "Cheval", "16-20 ans"),
    ("Lipizzan", "Cheval de dressage classique, célèbre à l'École espagnole de Vienne.", "Autriche, Slovénie", "Cheval", "25-30 ans"),
    ("Andalou (PRE)", "Cheval ibérique élégant, très utilisé en dressage et travail à pied.", "Espagne", "Cheval", "25-30 ans"),
    ("Lusitanien", "Proche de l'Andalou, réputé pour sa maniabilité en tauromachie équestre.", "Portugal", "Cheval", "25-30 ans"),
    ("Quarter Horse", "Cheval de western très rapide sur de courtes distances, polyvalent au travail du bétail.", "États-Unis", "Cheval", "25-30 ans"),
    ("Appaloosa", "Cheval à la robe tachetée caractéristique, historiquement lié aux Nez-Percés.", "États-Unis", "Cheval", "25-30 ans"),
    ("Morgan", "Petit cheval de selle et d'attelage, une des premières races américaines.", "États-Unis", "Cheval", "25-30 ans"),
    ("Trakehner", "Cheval de sport allemand léger, sang chaud très recherché en dressage.", "Allemagne", "Cheval", "25-30 ans"),
    ("Hanovrien", "Grand cheval de sport allemand, très présent en compétition internationale.", "Allemagne", "Cheval", "25-30 ans"),
    ("Holsteiner", "Une des plus anciennes races de sang chaud allemandes, excellent sauteur.", "Allemagne", "Cheval", "25-30 ans"),
    ("Camargue", "Cheval semi-sauvage blanc du sud de la France, rustique et endurant.", "France", "Cheval", "25-30 ans"),
    ("Percheron", "Grand cheval de trait puissant, robe grise ou noire.", "France", "Cheval", "25-30 ans"),
    ("Ardennais", "Cheval de trait trapu et massif, parmi les plus anciennes races de trait.", "France, Belgique", "Cheval", "25-30 ans"),
    ("Comtois", "Cheval de trait rustique du Jura, historiquement utilisé en montagne.", "France", "Cheval", "25-30 ans"),
    ("Breton", "Cheval de trait polyvalent, aussi utilisé en boucherie et attelage.", "France", "Cheval", "20-25 ans"),
    ("Boulonnais", "Cheval de trait élégant surnommé « le pur-sang des chevaux de trait ».", "France", "Cheval", "20-25 ans"),
    ("Shire", "Un des plus grands chevaux de trait du monde, fanons abondants aux membres.", "Royaume-Uni", "Cheval", "20-25 ans"),
    ("Mustang", "Cheval sauvage américain descendant de chevaux espagnols échappés.", "États-Unis", "Cheval", "25-30 ans"),
    ("Akhal-Teke", "Cheval au poil métallique caractéristique, réputé pour son endurance désertique.", "Turkménistan", "Cheval", "25-30 ans"),
    ("Criollo", "Cheval rustique sud-américain, très endurant sur de longues distances.", "Amérique du Sud", "Cheval", "25-30 ans"),
    ("Konik Polski", "Petit cheval rustique proche du tarpan, souvent utilisé en éco-pâturage.", "Pologne", "Cheval", "25-30 ans"),

    # --- Poneys --------------------------------------------------------------
    ("Shetland", "Le plus petit poney britannique, très robuste malgré sa taille.", "Écosse", "Poney", "25-30 ans"),
    ("Welsh", "Poney polyvalent décliné en plusieurs sections de taille, allures relevées.", "Pays de Galles", "Poney", "25-30 ans"),
    ("Connemara", "Poney irlandais athlétique, bon sauteur malgré son gabarit.", "Irlande", "Poney", "25-30 ans"),
    ("New Forest", "Poney britannique docile, adapté aussi bien aux enfants qu'aux adultes légers.", "Angleterre", "Poney", "25-30 ans"),
    ("Dartmoor", "Petit poney rustique du sud de l'Angleterre, tempérament calme.", "Angleterre", "Poney", "25-30 ans"),
    ("Exmoor", "Un des poneys britanniques les plus anciens et rustiques, quasi sauvage.", "Angleterre", "Poney", "25-30 ans"),
    ("Highland", "Robuste poney écossais utilisé historiquement pour le bât en montagne.", "Écosse", "Poney", "25-30 ans"),
    ("Fjord", "Poney norvégien à la robe isabelle et à la crinière bicolore tondue en brosse.", "Norvège", "Poney", "25-30 ans"),
    ("Islandais", "Poney à cinq allures dont le tölt, très rustique face au climat froid.", "Islande", "Poney", "25-40 ans"),
    ("Landais", "Poney français léger et véloce, proche de l'Arabe dans ses origines.", "France", "Poney", "25-30 ans"),

    # --- Ânes ----------------------------------------------------------------
    ("Baudet du Poitou", "Grand âne au poil long et frisé (guenilles), race française emblématique.", "France", "Âne", "25-35 ans"),
    ("Âne Normand", "Âne rustique de robe grise, historiquement utilisé comme animal de trait.", "France", "Âne", "25-35 ans"),
    ("Âne des Pyrénées", "Âne de montagne robuste, bien adapté aux terrains escarpés.", "France", "Âne", "25-35 ans"),
    ("Âne de Provence", "Petit âne rustique du sud de la France, robe grise ou bai.", "France", "Âne", "25-35 ans"),
    ("Grand Noir du Berry", "Grand âne à la robe noire uniforme, race française rare.", "France", "Âne", "25-35 ans"),
    ("Âne du Cotentin", "Âne normand robuste à la croix de Saint-André marquée.", "France", "Âne", "25-35 ans"),
    ("Âne miniature américain", "Petit âne de compagnie très docile, prisé comme animal familier.", "États-Unis", "Âne", "25-35 ans"),
    ("Âne commun", "Race d'âne généraliste sans standard particulier, très répandue.", "Origine cosmopolite", "Âne", "25-35 ans"),
]


def creer_espece_et_races(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Race = apps.get_model('animaux', 'Race')

    code, nom = ESPECE_EQUIDE
    espece, _ = Espece.objects.get_or_create(code=code, defaults={'nom': nom})

    for nom_race, description, origine, categorie, esperance_vie in RACES_EQUIDE:
        Race.objects.get_or_create(
            espece=espece, nom=nom_race,
            defaults={
                'description': description,
                'origine': origine,
                'categorie': categorie,
                'esperance_vie': esperance_vie,
                'niveau_dangerosite': 'AUCUNE',
            },
        )


def supprimer_espece_et_races(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    code, _nom = ESPECE_EQUIDE
    espece = Espece.objects.filter(code=code).first()
    if not espece:
        return
    # Race.espece a un ON DELETE PROTECT : supprimer d'abord les races non
    # utilisées par un animal, puis l'espèce elle-même si elle n'en a plus
    # (une race encore rattachée à un animal empêcherait la suppression, ce
    # qui est le comportement souhaité).
    espece.races.filter(animaux__isnull=True).delete()
    if not espece.races.exists():
        espece.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0023_completer_petites_especes'),
    ]

    operations = [
        migrations.RunPython(creer_espece_et_races, supprimer_espece_et_races),
    ]
