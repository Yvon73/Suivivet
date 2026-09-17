from django.conf import settings
from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator
from datetime import date


class Espece(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=50, verbose_name="Nom de l'espèce")

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Espèce"
        verbose_name_plural = "Espèces"
        ordering = ['nom']


class Robe(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=50, verbose_name="Nom de la robe")

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Robe"
        verbose_name_plural = "Robes"
        ordering = ['nom']


class Race(models.Model):
    class NiveauDangerosite(models.TextChoices):
        NON_RENSEIGNE = 'NON_RENSEIGNE', 'Non renseigné'
        AUCUNE = 'AUCUNE', 'Aucune'
        MODEREE = 'MODEREE', 'Modérée'
        ELEVEE = 'ELEVEE', 'Élevée'

    espece = models.ForeignKey(Espece, on_delete=models.PROTECT, related_name='races', verbose_name="Espèce")
    nom = models.CharField(max_length=100, verbose_name="Nom de la race")
    niveau_dangerosite = models.CharField(
        max_length=20,
        choices=NiveauDangerosite.choices,
        default=NiveauDangerosite.NON_RENSEIGNE,
        verbose_name="Degré de dangerosité",
        help_text=(
            "Ne constitue pas une catégorisation légale."
        ),
    )

    # Fiche descriptive de la race, alimentée par le catalogue JSON
    # (static/data/races_*.json). Tous ces champs sont facultatifs : une race
    # créée à la main (via le formulaire animal, cf. AnimalForm) n'a
    # au départ qu'un nom et une espèce.
    origine = models.CharField(max_length=150, blank=True, verbose_name="Origine")
    taille_min = models.FloatField(null=True, blank=True, verbose_name="Taille minimale (cm)")
    taille_max = models.FloatField(null=True, blank=True, verbose_name="Taille maximale (cm)")
    poids_min = models.FloatField(null=True, blank=True, verbose_name="Poids minimal (kg)")
    poids_max = models.FloatField(null=True, blank=True, verbose_name="Poids maximal (kg)")
    esperance_vie = models.CharField(max_length=50, blank=True, verbose_name="Espérance de vie")
    description = models.TextField(blank=True, verbose_name="Description")
    groupe_fci = models.CharField(max_length=150, blank=True, verbose_name="Groupe FCI",
                                   help_text="Classification de la Fédération Cynologique Internationale (chiens).")
    categorie = models.CharField(max_length=100, blank=True, verbose_name="Catégorie",
                                  help_text="Ex. type de poil pour les chats, famille pour les NAC.")
    sous_categorie = models.CharField(max_length=100, blank=True, verbose_name="Sous-catégorie")
    nom_scientifique = models.CharField(max_length=150, blank=True, verbose_name="Nom scientifique")
    niveau_soin = models.CharField(max_length=50, blank=True, verbose_name="Niveau de soin requis")
    legislation_france = models.CharField(max_length=150, blank=True, verbose_name="Législation (France)")
    prix_moyen = models.CharField(max_length=50, blank=True, verbose_name="Prix moyen constaté")
    infos_complementaires = models.JSONField(
        null=True, blank=True,
        verbose_name="Informations complémentaires",
        help_text=(
            "Données additionnelles issues du catalogue (alimentation, habitat, "
            "comportement, santé, etc.), propres à certaines espèces."
        ),
    )

    # Libellés lisibles des clés « libres » que l'on peut trouver dans
    # infos_complémentaires (cf. migration 0015) : les clés absentes de ce
    # dictionnaire sont affichées telles quelles (underscores remplacés par
    # des espaces), ce qui garde l'affichage robuste à une clé imprévue.
    _LABELS_INFOS_COMPLEMENTAIRES = {
        'alimentation': 'Alimentation',
        'habitat': 'Habitat',
        'comportement': 'Comportement',
        'sante': 'Santé',
        'histoire': 'Histoire',
        'tempérament': 'Tempérament',
        'particularites': 'Particularités',
        'soins_pelage': 'Soins du pelage',
        'type_pelage': 'Type de pelage',
        'couleur_pelage': 'Couleur de robe',
        'niveau_energie': "Niveau d'énergie",
        'facilite_education': "Facilité d'éducation",
        'besoin_exercice': "Besoin d'exercice",
        'utilisation': 'Utilisation',
        'sante_particuliere': 'Santé particulière',
        'conseils': 'Conseils',
        'popularite': 'Popularité',
    }

    def __str__(self):
        return self.nom

    def classe_bootstrap_dangerosite(self):
        return {
            self.NiveauDangerosite.NON_RENSEIGNE: 'secondary',
            self.NiveauDangerosite.AUCUNE: 'success',
            self.NiveauDangerosite.MODEREE: 'warning',
            self.NiveauDangerosite.ELEVEE: 'danger',
        }.get(self.niveau_dangerosite, 'secondary')

    def taille_affichee(self):
        return self._fourchette(self.taille_min, self.taille_max, 'cm')

    def poids_affiche(self):
        return self._fourchette(self.poids_min, self.poids_max, 'kg')

    @staticmethod
    def _fourchette(minimum, maximum, unite):
        def _fmt(v):
            return f"{v:g}"
        if minimum and maximum:
            return f"{_fmt(minimum)} - {_fmt(maximum)} {unite}"
        if minimum or maximum:
            return f"{_fmt(minimum or maximum)} {unite}"
        return ''

    def a_une_fiche_detaillee(self):
        return bool(
            self.origine or self.description or self.esperance_vie
            or self.taille_min or self.taille_max or self.poids_min or self.poids_max
            or self.groupe_fci or self.categorie or self.sous_categorie
            or self.nom_scientifique or self.niveau_soin or self.legislation_france
            or self.prix_moyen or self.infos_complementaires
        )

    def infos_complementaires_lisibles(self):
        resultat = []
        for cle, valeur in (self.infos_complementaires or {}).items():
            label = self._LABELS_INFOS_COMPLEMENTAIRES.get(cle, cle.replace('_', ' ').capitalize())
            resultat.append({'label': label, 'lignes': self._aplanir_valeur(valeur)})
        return resultat

    @staticmethod
    def _aplanir_valeur(valeur, prefixe=''):
        if isinstance(valeur, dict):
            lignes = []
            for sous_cle, sous_valeur in valeur.items():
                sous_label = f"{prefixe}{sous_cle.replace('_', ' ').capitalize()}"
                if isinstance(sous_valeur, dict):
                    lignes.extend(Race._aplanir_valeur(sous_valeur, prefixe=f"{sous_label} – "))
                else:
                    if isinstance(sous_valeur, list):
                        sous_valeur = ', '.join(str(v) for v in sous_valeur)
                    lignes.append(f"{sous_label} : {sous_valeur}")
            return lignes
        if isinstance(valeur, list):
            return [str(v) for v in valeur]
        return [str(valeur)]

    def donnees_json(self):
        """Représentation compacte de la fiche de race, utilisée pour peupler
        le panneau d'aperçu en JavaScript du formulaire animal (cf. form.html)
        sans dupliquer cette liste de champs côté template."""
        return {
            'id': self.pk,
            'nom': self.nom,
            'espece_id': self.espece_id,
            'niveau_dangerosite': self.niveau_dangerosite,
            'niveau_dangerosite_display': self.get_niveau_dangerosite_display(),
            'classe_dangerosite': self.classe_bootstrap_dangerosite(),
            'origine': self.origine,
            'taille': self.taille_affichee(),
            'poids': self.poids_affiche(),
            'esperance_vie': self.esperance_vie,
            'groupe_fci': self.groupe_fci,
            'categorie': self.categorie,
            'sous_categorie': self.sous_categorie,
            'nom_scientifique': self.nom_scientifique,
            'niveau_soin': self.niveau_soin,
            'legislation_france': self.legislation_france,
            'prix_moyen': self.prix_moyen,
            'description': self.description,
        }

    class Meta:
        verbose_name = "Race"
        verbose_name_plural = "Races"
        ordering = ['espece__nom', 'nom']
        constraints = [
            models.UniqueConstraint(fields=['espece', 'nom'], name='race_unique_par_espece')
        ]


class Organisme(models.Model):
    """Organisme/fédération officiel(le) auquel un animal peut être inscrit
    (registre de race, fédération sportive...), catalogué depuis
    static/data/organismes_officiel.json (cf. migration 0019). Remplace
    l'ancienne case à cocher « Inscrit au LOF » (trop spécifique : LOF ne
    concerne que les chiens), par une liste couvrant plusieurs espèces."""

    class Espece(models.TextChoices):
        # Valeur (à gauche) = code stocké en base (utilisé notamment par le
        # catalogue importé depuis static/data/organismes_officiel.json,
        # migration 0019) ; libellé (à droite) = texte affiché. Un membre
        # défini avec une seule valeur (ex. `CHIEN = 'Chien'`) stocke
        # cette valeur telle quelle, différente du code 'CHIEN' déjà en
        # base — d'où l'écriture explicite (code, libellé) ci-dessous.
        CHIEN = 'CHIEN', 'Chien'
        CHAT = 'CHAT', 'Chat'
        CHEVAL = 'CHEVAL', 'Cheval'
        RONGEUR = 'RONGEUR', 'Rongeur'
        OISEAU = 'OISEAU', 'Oiseau'
        REPTILE = 'REPTILE', 'Reptile / Amphibien'
        POISSON = 'POISSON', 'Poisson'
        ABEILLE = 'ABEILLE', 'Abeille'
        PIGEON = 'PIGEON', 'Pigeon'
        AUTRE = 'AUTRE', 'Autre'

    nom = models.CharField(max_length=200, verbose_name="Nom complet")
    nom_court = models.CharField(max_length=30, verbose_name="Nom court",
                                  help_text="Ex. LOF, LOOF, SIRE, CITES...")
    description = models.TextField(blank=True, verbose_name="Description")
    site_web = models.URLField(blank=True, verbose_name="Site web")
    espece = models.CharField(max_length=20, choices=Espece.choices, verbose_name="Espèce concernée")
    pays = models.CharField(max_length=100, blank=True, verbose_name="Pays")
    est_officiel = models.BooleanField(default=True, verbose_name="Organisme officiel")

    def __str__(self):
        return f"{self.nom_court} — {self.nom}"

    class Meta:
        verbose_name = "Organisme / Fédération"
        verbose_name_plural = "Organismes / Fédérations"
        ordering = ['espece', 'nom_court']
        constraints = [
            models.UniqueConstraint(fields=['espece', 'nom_court'], name='organisme_unique_par_espece')
        ]


class Proprietaire(models.Model):
    """Fiche complète d'un propriétaire d'animal (nom, coordonnées), réutilisable
    d'un animal à l'autre pour un même compte (un même foyer ayant plusieurs
    animaux n'est saisi qu'une fois) — mais propre à ce compte : deux comptes
    distincts sur la même installation ne voient jamais les fiches l'un de
    l'autre (cf. `utilisateur`)."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proprietaires',
        verbose_name="Compte",
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, blank=True, verbose_name="Prénom")
    adresse = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
    code_postal = models.CharField(max_length=10, blank=True, verbose_name="Code postal")
    ville = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    telephone = models.CharField(max_length=14, blank=True, verbose_name="Téléphone")
    email = models.EmailField(verbose_name="Email")
    actif = models.BooleanField(
        default=True, verbose_name="Actif",
        help_text=(
            "Décoché lors d'une « suppression » : la fiche reste en base (les animaux déjà "
            "enregistrés continuent de l'afficher) mais n'est plus proposée pour de nouvelles "
            "saisies, ni affichée sur la fiche animal en PDF."
        ),
    )

    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip() or self.email

    def __str__(self):
        return self.nom_complet()

    class Meta:
        verbose_name = "Propriétaire"
        verbose_name_plural = "Propriétaires"
        ordering = ['nom', 'prenom']
        constraints = [
            models.UniqueConstraint(fields=['utilisateur', 'email'], name='proprietaire_unique_email_par_compte')
        ]


class Animal(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='animaux',
        verbose_name="Compte",
        help_text="Compte auquel appartient cette fiche : chaque compte ne voit que ses propres animaux.",
    )
    nom = models.CharField(max_length=100, verbose_name="Nom de l'animal")
    race = models.ForeignKey(Race, on_delete=models.PROTECT, related_name='animaux', verbose_name="Race")
    espece = models.ForeignKey(Espece, on_delete=models.PROTECT, related_name='animaux', verbose_name="Espèce")
    date_naissance = models.DateField(verbose_name="Date de naissance")
    date_deces = models.DateField(null=True, blank=True, verbose_name="Date de décès")
    robe = models.ForeignKey(Robe, on_delete=models.PROTECT, related_name='animaux', verbose_name="Robe (couleur)")
    proprietaire = models.ForeignKey(
        Proprietaire, on_delete=models.PROTECT, related_name='animaux', verbose_name="Propriétaire",
    )
    photo = models.ImageField(
        upload_to='animaux/photos/',
        null=True,
        blank=True,
        verbose_name="Photo"
    )

    def __str__(self):
        return f"{self.nom} ({self.espece.nom})"

    def identifications_display(self, separateur='; '):
        """Texte récapitulatif de tous les couples identification/organisme de
        l'animal (un animal pouvant être enregistré auprès de plusieurs
        organismes), utilisé pour les exports CSV/Excel et le PDF, ex. :
        « 250269812345678 (LOF); 987654 (SIRE) »."""
        parts = []
        for ident in self.identifications.all():
            organisme = ident.organisme_affiche()
            numero = ident.identification or ''
            if numero and organisme:
                parts.append(f"{numero} ({organisme})")
            else:
                parts.append(numero or organisme)
        return separateur.join(p for p in parts if p)

    def age(self):
        today = date.today()
        if self.date_deces:
            today = self.date_deces
        age = today.year - self.date_naissance.year
        if (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day):
            age -= 1
        return age

    def age_en_mois(self):
        """Âge total en mois révolus (utile pour les jeunes animaux, où l'âge en
        années seules manque de précision)."""
        today = self.date_deces or date.today()
        mois = (today.year - self.date_naissance.year) * 12 + (today.month - self.date_naissance.month)
        if today.day < self.date_naissance.day:
            mois -= 1
        return max(mois, 0)

    def age_display(self):
        """Âge lisible : en mois pour les animaux de moins d'un an, en années
        (+ mois restants) au-delà."""
        total_mois = self.age_en_mois()
        if total_mois < 12:
            return f"{total_mois} mois"
        annees, mois = divmod(total_mois, 12)
        texte = f"{annees} an{'s' if annees > 1 else ''}"
        if mois:
            texte += f" {mois} mois"
        return texte

    def get_absolute_url(self):
        return reverse('animaux:animal_detail', args=[str(self.id)])

    class Meta:
        verbose_name = "Animal"
        verbose_name_plural = "Animaux"
        ordering = ['nom']


class AnimalIdentification(models.Model):
    """Couple identification/organisme d'un animal. Un animal peut être
    enregistré auprès de plusieurs organismes (ex. puce + LOF, ou inscription
    dans plusieurs registres) : chaque couple est donc une ligne à part plutôt
    qu'un champ unique sur Animal. L'ordre d'affichage/de saisie suit l'ordre
    d'insertion (clé primaire), pour respecter l'ordre choisi par l'utilisateur
    dans le formulaire."""

    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='identifications')
    organisme = models.ForeignKey(
        Organisme, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='identifications', verbose_name="Organisme d'inscription",
        help_text="Registre officiel auquel l'animal est inscrit (LOF, LOOF, SIRE...).",
    )
    organisme_autre = models.CharField(
        max_length=200, blank=True, verbose_name="Autre organisme (si non listé)",
        help_text="Nom de l'organisme si absent de la liste ci-dessus.",
    )
    identification = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Identification (puce/numéro)",
        help_text=(
            "Numéro de puce électronique ou tatouage, optionnel"
        )
    )

    def organisme_affiche(self):
        """Libellé lisible de l'organisme d'inscription : nom court de
        l'organisme catalogué, à défaut la saisie libre « Autre », à défaut
        une chaîne vide (aucun organisme renseigné)."""
        if self.organisme_id:
            return self.organisme.nom_court
        return self.organisme_autre or ''

    def __str__(self):
        return f"{self.identification or '—'} ({self.organisme_affiche() or 'sans organisme'})"

    class Meta:
        verbose_name = "Identification"
        verbose_name_plural = "Identifications"
        ordering = ['id']


class Poids(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='poids')
    date = models.DateField(verbose_name="Date de la pesée")
    valeur = models.FloatField(
        validators=[MinValueValidator(0.1)],
        verbose_name="Poids (kg)"
    )

    def __str__(self):
        return f"{self.animal.nom} - {self.valeur} kg ({self.date})"

    class Meta:
        verbose_name = "Poids"
        verbose_name_plural = "Poids"
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['animal', 'date'],
                name='poids_unique_par_animal_et_date'
            )
        ]