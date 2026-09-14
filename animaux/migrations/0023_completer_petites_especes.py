# Complète le catalogue de races des espèces qui en comptaient moins de 25
# (hors Chien et Chat, volontairement non retouchées) : Batracien, Iguane,
# Arachnide, Insecte, Gastéropode, Poisson, Reptile, Lapin, Oiseau. Rongeur
# comptait déjà 31 races et n'est pas concerné. « Autre » (espèce fourre-tout,
# cf. migration de suppression des entrées « Autre » des formulaires) n'est
# volontairement pas peuplée : il ne s'agit pas d'une catégorie biologique
# réelle dont on pourrait énumérer des races.
#
# Pour chaque espèce, la liste couvre un maximum d'espèces/variétés
# réellement admises en captivité (NAC, aquariophilie, terrariophilie...) ;
# certaines espèces (Iguane, Gastéropode...) ont un nombre naturellement
# limité de variétés couramment détenues et n'atteignent donc pas 25 malgré
# une liste aussi complète que raisonnablement possible.
#
# La dangerosité (indicateur interne de précaution à la manipulation, cf.
# migration 0008/0017) est systématiquement renseignée (jamais laissée à
# NON_RENSEIGNE) : AUCUNE par défaut, MODEREE/ELEVEE pour les espèces
# venimeuses ou à la morsure documentée comme puissante.
from django.db import migrations

# (nom, description, origine, espérance de vie, dangerosité)
RACES_PAR_ESPECE = {
    'BATRACIEN': [
        ("Grenouille Pacman", "Grosse grenouille cornue au tempérament vorace, guette ses proies immobile.", "Amérique du Sud", "6-10 ans", "AUCUNE"),
        ("Grenouille cornue du Chaco", "Proche de la Pacman, gueule très large et appétit tout aussi vorace.", "Argentine, Paraguay", "6-10 ans", "AUCUNE"),
        ("Grenouille tomate", "Grenouille rouge vif de Madagascar, sécrète un mucus irritant si stressée.", "Madagascar", "6-8 ans", "AUCUNE"),
        ("Dendrobate azuré", "Petite grenouille bleu vif ; les toxines cutanées restent présentes même en captivité.", "Amérique du Sud", "10-15 ans", "MODEREE"),
        ("Dendrobate tinctorius", "Grenouille dendrobate très colorée, parmi les plus grandes du genre.", "Guyane, Brésil", "10-15 ans", "MODEREE"),
        ("Dendrobate leucomelas", "Grenouille jaune et noire, une des dendrobates les plus rustiques en élevage.", "Venezuela, Guyana", "10-15 ans", "MODEREE"),
        ("Grenouille arboricole aux yeux rouges", "Grenouille emblématique d'Amérique centrale, yeux rouges et flancs bleus.", "Amérique centrale", "5 ans", "AUCUNE"),
        ("Xénope du Cap", "Grenouille aquatique sans langue ni oreilles externes, entièrement aquatique.", "Afrique australe", "15 ans", "AUCUNE"),
        ("Xénope nain africain", "Petit xénope entièrement aquatique, très sociable en groupe.", "Afrique centrale", "5-8 ans", "AUCUNE"),
        ("Triton ventre de feu oriental", "Triton aquatique au ventre orangé, apprécié pour sa robustesse.", "Chine", "10-15 ans", "AUCUNE"),
        ("Triton ventre de feu japonais", "Proche du triton oriental, ventre orange tacheté de noir.", "Japon", "15-20 ans", "AUCUNE"),
        ("Salamandre tigrée", "Grande salamandre terrestre nord-américaine, très rustique.", "Amérique du Nord", "12-15 ans", "AUCUNE"),
        ("Crapaud commun", "Crapaud européen classique, peau granuleuse et mœurs nocturnes.", "Europe", "10-12 ans", "AUCUNE"),
        ("Rainette verte", "Petite grenouille arboricole verte, ventouses aux doigts.", "Europe", "5-10 ans", "AUCUNE"),
        ("Grenouille taureau africaine", "Très grande grenouille vorace et territoriale, morsure possible.", "Afrique subsaharienne", "20-25 ans", "MODEREE"),
    ],
    'IGUANE': [
        ("Iguane rhinocéros", "Grand iguane des Caraïbes portant des cornes nasales proéminentes.", "Hispaniola", "15-20 ans", "AUCUNE"),
        ("Iguane bleu de Grand Cayman", "Iguane bleuté très rare, programme de conservation actif.", "Îles Caïmans", "25-30 ans", "AUCUNE"),
        ("Iguane du désert", "Petit iguane rapide adapté aux climats arides nord-américains.", "Amérique du Nord", "7-10 ans", "AUCUNE"),
        ("Iguane à queue épineuse noir", "Iguane robuste et véloce, longue queue annelée d'épines.", "Amérique centrale", "15 ans", "AUCUNE"),
        ("Iguane terrestre des Galápagos", "Grand iguane jaunâtre endémique des Galápagos.", "Îles Galápagos", "50-60 ans", "AUCUNE"),
        ("Iguane des Fidji à bandes", "Iguane vert rayé de bleu, endémique du Pacifique Sud.", "Fidji", "15-20 ans", "AUCUNE"),
        ("Iguane cornu des Fidji", "Iguane vert à écaille frontale en forme de corne.", "Fidji", "15-20 ans", "AUCUNE"),
        ("Iguane du désert de Sonora", "Variante d'iguane du désert adaptée aux zones rocailleuses arides.", "Amérique du Nord", "8 ans", "AUCUNE"),
    ],
    'ARACHNIDE': [
        ("Mygale à genoux roses", "Mygale terrestre docile, une des plus courantes en élevage débutant.", "Argentine, Paraguay", "20-25 ans (femelle)", "MODEREE"),
        ("Mygale Curly Hair", "Mygale robuste au poil ondulé brun, très rustique.", "Amérique centrale", "15-20 ans (femelle)", "MODEREE"),
        ("Mygale Goliath", "La plus grande mygale du monde, poils urticants abondants.", "Amazonie", "15-25 ans (femelle)", "MODEREE"),
        ("Mygale bleu cobalt", "Mygale fouisseuse au bleu électrique, vive et nerveuse.", "Asie du Sud-Est", "10-12 ans (femelle)", "MODEREE"),
        ("Mygale à pattes rouges du Mexique", "Mygale emblématique noire aux articulations rouge orangé.", "Mexique", "25-30 ans (femelle)", "MODEREE"),
        ("Mygale royale des Indes", "Mygale arboricole ornementée, très rapide.", "Inde", "12 ans (femelle)", "MODEREE"),
        ("Mygale Pinktoe", "Mygale arboricole aux extrémités de pattes roses, tempérament calme.", "Amérique du Sud", "10-12 ans (femelle)", "MODEREE"),
        ("Mygale géante du Brésil", "Grande mygale terrestre à croissance rapide.", "Brésil", "10-15 ans (femelle)", "MODEREE"),
        ("Mygale à chélicères bleus", "Mygale fouisseuse asiatique aux chélicères bleu métallique.", "Asie du Sud-Est", "12-15 ans (femelle)", "MODEREE"),
        ("Mygale à trompe", "Petite mygale arboricole au céphalothorax allongé en trompe.", "Amérique du Sud", "8-10 ans (femelle)", "MODEREE"),
        ("Scorpion empereur", "Grand scorpion noir au venin peu dangereux, très populaire en élevage.", "Afrique de l'Ouest", "6-8 ans", "MODEREE"),
        ("Scorpion à queue épaisse", "Scorpion au venin médicalement significatif, manipulation déconseillée.", "Afrique du Nord", "5-8 ans", "ELEVEE"),
        ("Scorpion arc-en-ciel du désert", "Grand scorpion nord-américain fouisseur, venin peu dangereux.", "Amérique du Nord", "6-10 ans", "MODEREE"),
        ("Scorpion forestier asiatique", "Scorpion forestier de grande taille, relativement calme.", "Asie du Sud-Est", "5-8 ans", "MODEREE"),
    ],
    'INSECTE': [
        ("Phasme géant de Malaisie", "Un des plus grands phasmes du monde, femelles très imposantes.", "Malaisie", "1-2 ans", "AUCUNE"),
        ("Phasme feuille", "Mimétisme parfait avec une feuille, y compris les nervures.", "Asie du Sud-Est", "6-12 mois", "AUCUNE"),
        ("Mante religieuse européenne", "Mante commune en Europe, prédatrice à l'affût.", "Europe", "6-12 mois", "AUCUNE"),
        ("Mante orchidée", "Mante rose mimant une fleur d'orchidée pour attirer ses proies.", "Asie du Sud-Est", "6-8 mois", "AUCUNE"),
        ("Blatte de Madagascar siffleuse", "Grande blatte incapable de voler, émet un sifflement caractéristique.", "Madagascar", "2-5 ans", "AUCUNE"),
        ("Blatte à damier argentin", "Blatte non grimpante très utilisée comme proie vivante et NAC.", "Amérique du Sud", "1-2 ans", "AUCUNE"),
        ("Scarabée rhinocéros européen", "Grand coléoptère à corne unique, larves détritivores.", "Europe", "1 an (adulte quelques mois)", "AUCUNE"),
        ("Scarabée Hercule", "Un des plus grands coléoptères du monde, corne impressionnante chez le mâle.", "Amérique centrale et du Sud", "1 an (adulte quelques mois)", "AUCUNE"),
        ("Grillon domestique", "Grillon d'élevage courant, utilisé aussi comme proie vivante.", "Origine cosmopolite", "2-3 mois", "AUCUNE"),
        ("Fourmi noire des jardins", "Espèce de fourmilière la plus répandue en myrmécologie amateur.", "Europe", "Reine : plusieurs années", "AUCUNE"),
    ],
    'GASTEROPODE': [
        ("Petit-gris", "Escargot comestible européen, le plus commun des jardins.", "Europe", "5-7 ans", "AUCUNE"),
        ("Escargot de Bourgogne", "Grand escargot européen, symbole de la gastronomie française.", "Europe", "8-10 ans", "AUCUNE"),
        ("Achatina fulica", "Escargot terrestre géant très répandu en élevage, croissance rapide.", "Afrique de l'Est", "5-7 ans", "AUCUNE"),
        ("Achatina achatina", "Le plus grand escargot terrestre du monde, coquille très allongée.", "Afrique de l'Ouest", "10 ans", "AUCUNE"),
        ("Archachatina marginata", "Gros escargot ouest-africain à la coquille brun foncé strié.", "Afrique de l'Ouest", "8-10 ans", "AUCUNE"),
        ("Limace léopard", "Grande limace tachetée, prédatrice occasionnelle d'autres limaces.", "Europe", "2-3 ans", "AUCUNE"),
    ],
    'POISSON': [
        ("Guppy", "Petit poisson vivipare très coloré, se reproduit facilement en aquarium.", "Amérique du Sud", "2-3 ans", "AUCUNE"),
        ("Betta / Combattant du Siam", "Poisson aux nageoires amples, mâles territoriaux à isoler entre eux.", "Asie du Sud-Est", "2-4 ans", "AUCUNE"),
        ("Néon bleu", "Petit poisson grégaire à la bande bleu électrique, classique du bac communautaire.", "Amazonie", "3-5 ans", "AUCUNE"),
        ("Molly", "Poisson vivipare robuste, apprécie une eau légèrement saumâtre.", "Amérique centrale", "3-5 ans", "AUCUNE"),
        ("Platy", "Petit poisson vivipare coloré, très facile pour les débutants.", "Amérique centrale", "3-5 ans", "AUCUNE"),
        ("Porte-épée (Xipho)", "Poisson vivipare dont le mâle porte un prolongement caudal en épée.", "Amérique centrale", "3-5 ans", "AUCUNE"),
        ("Scalaire", "Cichlidé plat aux longues nageoires, forme des couples stables.", "Amazonie", "10 ans", "AUCUNE"),
        ("Discus", "Cichlidé exigeant à la silhouette discoïde, réputé difficile en eau de qualité.", "Amazonie", "10-15 ans", "AUCUNE"),
        ("Corydoras", "Petit poisson-chat de fond grégaire, nettoie le substrat.", "Amérique du Sud", "5-10 ans", "AUCUNE"),
        ("Plecostomus", "Poisson-chat ventouse algivore, peut atteindre une taille imposante.", "Amérique du Sud", "10-15 ans", "AUCUNE"),
        ("Gourami perlé", "Labyrinthidé calme aux reflets nacrés, respire l'air atmosphérique.", "Asie du Sud-Est", "4-5 ans", "AUCUNE"),
        ("Danio zébré", "Petit poisson rayé très actif et grégaire, modèle scientifique courant.", "Asie du Sud", "2-3 ans", "AUCUNE"),
        ("Barbus de Sumatra", "Poisson grégaire rayé, à maintenir en groupe pour limiter le mordillage.", "Indonésie", "5-6 ans", "AUCUNE"),
        ("Poisson-ange empereur", "Grand poisson marin aux rayures bleu et jaune, change de robe en grandissant.", "Indo-Pacifique", "15-20 ans", "AUCUNE"),
        ("Poisson-chirurgien bleu (Tang)", "Poisson marin bleu vif à la nageoire caudale jaune, rendu célèbre au cinéma.", "Indo-Pacifique", "8-20 ans", "AUCUNE"),
        ("Hippocampe", "Poisson marin à nage verticale, mâle porteur des œufs.", "Zones tempérées et tropicales", "1-5 ans", "AUCUNE"),
        ("Poisson-papillon", "Poisson marin récifal aux motifs vifs, souvent en couple.", "Indo-Pacifique", "5-7 ans", "AUCUNE"),
        ("Requin-chabot à pois", "Petit requin de fond marin, adapté aux grands bacs récifaux.", "Indo-Pacifique", "20-25 ans", "AUCUNE"),
    ],
    'REPTILE': [
        ("Pogona / Dragon barbu", "Agame australien placide, très populaire comme premier reptile.", "Australie", "10-15 ans", "AUCUNE"),
        ("Gecko à crête", "Gecko arboricole sans paupières, queue parfois caduque.", "Nouvelle-Calédonie", "15-20 ans", "AUCUNE"),
        ("Serpent des blés (Corn snake)", "Couleuvre nord-américaine placide, référence pour les débutants.", "Amérique du Nord", "15-20 ans", "AUCUNE"),
        ("Boa constrictor", "Grand constricteur robuste, tempérament généralement calme en élevage.", "Amérique du Sud", "20-30 ans", "MODEREE"),
        ("Python molure", "Grand python asiatique pouvant dépasser 5 mètres.", "Asie du Sud", "20-25 ans", "MODEREE"),
        ("Tortue de Floride", "Tortue aquatique très répandue, espèce envahissante hors captivité.", "Amérique du Nord", "20-30 ans", "AUCUNE"),
        ("Tortue russe des steppes", "Petite tortue terrestre rustique d'Asie centrale.", "Asie centrale", "40-50 ans", "AUCUNE"),
        ("Tortue sillonnée", "Troisième plus grande tortue terrestre au monde, croissance très rapide.", "Afrique subsaharienne", "50-80 ans", "AUCUNE"),
        ("Varan des savanes", "Grand lézard robuste au fouet caudal puissant, morsure possible.", "Afrique subsaharienne", "10-15 ans", "MODEREE"),
        ("Caméléon panthère", "Caméléon très coloré de Madagascar, territorial et solitaire.", "Madagascar", "5-7 ans", "AUCUNE"),
        ("Caméléon casqué du Yémen", "Caméléon à la crête crânienne proéminente, un des plus robustes en élevage.", "Péninsule arabique", "5-8 ans", "AUCUNE"),
        ("Anole vert", "Petit lézard arboricole nord-américain au fanon rouge.", "Amérique du Nord", "4-8 ans", "AUCUNE"),
        ("Gecko Tokay", "Grand gecko vif et territorial, morsure franche s'il se sent menacé.", "Asie du Sud-Est", "10 ans", "MODEREE"),
        ("Uromastyx / Fouette-queue", "Lézard herbivore désertique à la queue épineuse défensive.", "Afrique du Nord, Moyen-Orient", "15-20 ans", "AUCUNE"),
        ("Serpent-roi (Kingsnake)", "Couleuvre nord-américaine robuste, parfois ophiophage entre congénères.", "Amérique du Nord", "15-20 ans", "AUCUNE"),
        ("Python réticulé", "Un des plus longs serpents du monde, nécessite une expérience confirmée.", "Asie du Sud-Est", "20-25 ans", "ELEVEE"),
        ("Tégu argentin", "Grand lézard intelligent et vif, morsure possible s'il est mal manipulé.", "Amérique du Sud", "15-20 ans", "MODEREE"),
    ],
    'LAPIN': [
        ("Bélier Français", "Grand lapin bélier robuste, tête massive et oreilles tombantes.", "France", "8-10 ans", "AUCUNE"),
        ("Bélier Anglais", "Bélier aux oreilles extrêmement longues, entretien attentif requis.", "Royaume-Uni", "7-10 ans", "AUCUNE"),
        ("Néerlandais (Dutch)", "Petit lapin bicolore à la marque caractéristique en ceinture.", "Pays-Bas", "7-10 ans", "AUCUNE"),
        ("Papillon Anglais (English Spot)", "Lapin blanc tacheté de couleur, silhouette longiligne.", "Royaume-Uni", "7-9 ans", "AUCUNE"),
        ("Himalayen", "Petit lapin blanc aux extrémités colorées, façon chat siamois.", "Asie/Europe (origine incertaine)", "7-10 ans", "AUCUNE"),
        ("Polonais", "Un des plus petits lapins de race, format compact et docile.", "Royaume-Uni", "7-10 ans", "AUCUNE"),
        ("Californien", "Lapin de chair et d'exposition blanc aux extrémités foncées.", "États-Unis", "7-8 ans", "AUCUNE"),
        ("Chinchilla de Vienne", "Lapin au pelage gris imitant celui du chinchilla.", "France", "7-10 ans", "AUCUNE"),
        ("Rex Satin", "Variété Rex au poil particulièrement brillant et soyeux.", "États-Unis", "7-9 ans", "AUCUNE"),
        ("Fauve de Bourgogne", "Grand lapin roux uniforme, race française ancienne.", "France", "8-10 ans", "AUCUNE"),
        ("Argenté de Champagne", "Lapin gris argenté, une des plus anciennes races françaises.", "France", "8-10 ans", "AUCUNE"),
        ("Blanc de Bouscat", "Grand lapin blanc aux yeux bleus, race française.", "France", "7-9 ans", "AUCUNE"),
        ("Papillon Géant Français", "Grand lapin blanc tacheté, silhouette imposante.", "France", "7-9 ans", "AUCUNE"),
        ("Hotot", "Lapin blanc aux yeux cerclés de noir, dit « eyeliner ».", "France", "7-10 ans", "AUCUNE"),
        ("Jersey Wooly", "Petit lapin à la fourrure longue et dense, format nain.", "États-Unis", "7-10 ans", "AUCUNE"),
        ("Lionhead (Tête de Lion)", "Petit lapin à la crinière de poils longs autour de la tête.", "Belgique", "7-9 ans", "AUCUNE"),
        ("Mini Rex", "Version naine du Rex, pelage court et dense caractéristique.", "États-Unis", "7-9 ans", "AUCUNE"),
        ("Harlequin (Arlequin)", "Lapin au pelage bicolore réparti en damier asymétrique.", "France", "7-9 ans", "AUCUNE"),
        ("Havane", "Petit lapin brun chocolat uniforme, une des plus anciennes races.", "Pays-Bas", "7-9 ans", "AUCUNE"),
    ],
    'OISEAU': [
        ("Perruche omnicolore (Rainbow Lorikeet)", "Loriquet aux couleurs très vives, se nourrit surtout de nectar.", "Australie", "20-25 ans", "AUCUNE"),
        ("Conure Soleil", "Conure jaune et orange vif très expressive et sociable.", "Amérique du Sud", "20-30 ans", "AUCUNE"),
        ("Conure à tête noire (Nanday)", "Conure verte à la tête noire, très joueuse.", "Amérique du Sud", "25-30 ans", "AUCUNE"),
        ("Youyou du Sénégal", "Perroquet africain de taille moyenne, calme et attachant.", "Afrique de l'Ouest", "25-30 ans", "AUCUNE"),
        ("Eclectus", "Perroquet au fort dimorphisme sexuel (mâle vert, femelle rouge et bleu).", "Océanie", "30-50 ans", "AUCUNE"),
        ("Toucan toco", "Grand oiseau tropical au bec démesuré, frugivore.", "Amérique du Sud", "15-20 ans", "AUCUNE"),
        ("Faisan doré", "Faisan d'ornement au plumage flamboyant, souvent en volière.", "Chine", "6-8 ans", "AUCUNE"),
        ("Paon bleu", "Grand oiseau d'ornement, le mâle déploie une traîne spectaculaire.", "Asie du Sud", "20-25 ans", "AUCUNE"),
        ("Diamant de Gould", "Petit oiseau grégaire aux couleurs très vives, élevage en volière.", "Australie", "5-8 ans", "AUCUNE"),
        ("Moineau du Japon", "Petit passereau domestique docile, facile à élever.", "Origine domestique (Asie)", "8-10 ans", "AUCUNE"),
    ],
}


def peupler_races(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Race = apps.get_model('animaux', 'Race')

    for code, races in RACES_PAR_ESPECE.items():
        espece = Espece.objects.filter(code=code).first()
        if not espece:
            continue
        for nom, description, origine, esperance_vie, dangerosite in races:
            Race.objects.get_or_create(
                espece=espece, nom=nom,
                defaults={
                    'description': description,
                    'origine': origine,
                    'esperance_vie': esperance_vie,
                    'niveau_dangerosite': dangerosite,
                },
            )


def retirer_races(apps, schema_editor):
    Espece = apps.get_model('animaux', 'Espece')
    Race = apps.get_model('animaux', 'Race')

    for code, races in RACES_PAR_ESPECE.items():
        espece = Espece.objects.filter(code=code).first()
        if not espece:
            continue
        noms = [nom for nom, *_ in races]
        # Ne supprime que les races non utilisées par un animal (sécurité :
        # la contrainte PROTECT l'empêcherait de toute façon).
        Race.objects.filter(espece=espece, nom__in=noms, animaux__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('animaux', '0022_remove_animal_lof'),
    ]

    operations = [
        migrations.RunPython(peupler_races, retirer_races),
    ]
