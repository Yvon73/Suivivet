from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from animaux.models import Animal

class Vaccin(models.Model):
    CATEGORIE_CHOIX = [
        ('OBLIGATOIRE', 'Obligatoire (selon la réglementation)'),
        ('ESSENTIEL', 'Essentiel (recommandé pour tous)'),
        ('RECOMMANDE', 'Recommandé selon le mode de vie'),
    ]

    nom = models.CharField(max_length=100, verbose_name="Nom du vaccin")
    description = models.TextField(blank=True, verbose_name="Description")
    categorie = models.CharField(
        max_length=20,
        choices=CATEGORIE_CHOIX,
        default='RECOMMANDE',
        verbose_name="Catégorie",
    )
    rappel_interval = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Intervalle de rappel",
        help_text="Ex : « Annuel », « Tous les 3 ans ».",
    )

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Vaccin"
        verbose_name_plural = "Vaccins"
        ordering = ['categorie', 'nom']

class Traitement(models.Model):
    class Classe(models.TextChoices):
        COMPRIME = 'COMPRIME', 'Comprimé'
        SOLUTION_BUVABLE = 'SOLUTION_BUVABLE', 'Solution buvable'
        PIPETTE = 'PIPETTE', 'Pipette (spot-on)'
        COLLIER = 'COLLIER', 'Collier'
        SHAMPOOING = 'SHAMPOOING', 'Shampooing'
        SPRAY = 'SPRAY', 'Spray'
        CREME = 'CREME', 'Crème / Pommade'
        GEL = 'GEL', 'Gel'
        COLLYRE = 'COLLYRE', 'Collyre (gouttes oculaires)'
        GOUTTES_AURICULAIRES = 'GOUTTES_AURICULAIRES', 'Gouttes auriculaires'
        AUTRE = 'AUTRE', 'Autre'

    nom = models.CharField(max_length=100, verbose_name="Nom du traitement")
    description = models.TextField(blank=True, verbose_name="Description")
    classe = models.CharField(
        max_length=25,
        choices=Classe.choices,
        default=Classe.AUTRE,
        verbose_name="Classe (forme galénique)",
        help_text="Forme d'administration du traitement, utilisée pour regrouper le catalogue.",
    )

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Traitement"
        verbose_name_plural = "Traitements"
        ordering = ['classe', 'nom']

class SuiviVaccinTraitement(models.Model):
    class UniteDose(models.TextChoices):
        PAR_KG = 'KG', 'Dose par Kg'
        ML = 'ML', 'ml'

    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='suivi_vaccins_traitements')
    vaccin = models.ForeignKey(
        Vaccin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suivi_animaux'
    )
    traitement = models.ForeignKey(
        Traitement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suivi_animaux'
    )
    date = models.DateField(verbose_name="Date d'administration")
    date_prochaine_dose = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de rappel prévue"
    )
    notes = models.TextField(blank=True, verbose_name="Observations / Annotations")

    # --- Champs spécifiques à un vaccin -----------------------------------
    numero_lot = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="N° de lot du vaccin"
    )

    # --- Champs spécifiques à un traitement médical -------------------------
    duree_traitement = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Durée du traitement",
        help_text="Ex : « 7 jours », « 2 semaines »."
    )
    prise_matin = models.BooleanField(default=False, verbose_name="Matin")
    prise_midi = models.BooleanField(default=False, verbose_name="Midi")
    prise_soir = models.BooleanField(default=False, verbose_name="Soir")
    # Dose (comprimé ou solution buvable) : une unité (au poids ou en volume) et
    # une valeur numérique de 1 à 100 (ex : « 2 » + « Dose par Kg », ou « 5 » + « ml »).
    dose_unite = models.CharField(
        max_length=5,
        choices=UniteDose.choices,
        blank=True,
        verbose_name="Unité de dose"
    )
    dose_valeur = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="Dose"
    )

    def __str__(self):
        if self.vaccin:
            type_suivi, nom = "Vaccin", self.vaccin.nom
        elif self.traitement:
            type_suivi, nom = "Traitement", self.traitement.nom
        else:
            # Le vaccin ET le traitement d'origine ont été supprimés du
            # catalogue (SET_NULL) : entrée orpheline, mais on l'affiche
            # quand même plutôt que de planter (AttributeError).
            type_suivi, nom = "Suivi", "(vaccin/traitement supprimé du catalogue)"
        return f"{self.animal.nom} - {type_suivi}: {nom} ({self.date})"

    class Meta:
        verbose_name = "Suivi Vaccin/Traitement"
        verbose_name_plural = "Suivis Vaccins/Traitements"
        ordering = ['-date']