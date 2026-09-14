from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from animaux.models import Animal
from django.db.models import Sum

from notifications.models import Notification
from notifications.utils import resoudre_utilisateur
from Projet_veto.validators import validate_file_extension, validate_file_size


class TypeDepense(models.Model):
    nom = models.CharField(max_length=100, verbose_name="Type de dépense")

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Type de dépense"
        verbose_name_plural = "Types de dépenses"


class Designation(models.Model):
    """Catalogue partagé des désignations de produits/prestations utilisées
    dans la ventilation d'une facture (catalogue réutilisable, comme
    Veterinaire/Organisme) : permet de retrouver le dernier prix unitaire
    pratiqué pour une même désignation, quelle que soit la facture."""

    nom = models.CharField(max_length=200, unique=True, verbose_name="Désignation")

    def dernier_prix_unitaire(self):
        """Dernier prix unitaire connu pour cette désignation (toutes
        factures confondues), ou None si elle n'a jamais été utilisée."""
        derniere_ligne = (
            self.lignes_facture
            .order_by('-facture__date', '-pk')
            .first()
        )
        return derniere_ligne.prix_unitaire if derniere_ligne else None

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Désignation"
        verbose_name_plural = "Désignations"
        ordering = ['nom']


class Facture(models.Model):
    TYPE_DEPENSE_CHOIX = [
        ('VETERINAIRE', 'Vétérinaire'),
        ('ALIMENTAIRE', 'Alimentaire'),
    ]

    numero = models.CharField(
        max_length=50, blank=True, verbose_name="N° de facture",
    )
    animal = models.ForeignKey(
        Animal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='factures',
        verbose_name="Animal concerné"
    )
    type_depense = models.CharField(
        max_length=20,
        choices=TYPE_DEPENSE_CHOIX,
        verbose_name="Type de dépense"
    )
    titre = models.CharField(max_length=200, verbose_name="Titre de la facture")
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant (€)"
    )
    date = models.DateField(verbose_name="Date de la facture")
    fichier = models.FileField(
        upload_to='factures/',
        verbose_name="Fichier scanné",
        validators=[validate_file_extension, validate_file_size],
    )
    description = models.TextField(blank=True, verbose_name="Description")

    def __str__(self):
        return f"{self.titre} - {self.montant}€ ({self.date})"

    def est_ventilee(self):
        """Une facture « ventilée » a au moins une ligne de détail — dans ce
        cas c'est la somme des lignes qui fait foi pour le montant et le
        champ `animal` global n'est plus pertinent (cf. recalculer_montant)."""
        return self.lignes.exists()

    def recalculer_montant(self):
        """Remet `montant` en cohérence avec la somme des lignes de
        ventilation, pour que les agrégats existants (depenses_mensuelles/
        annuelles, coûts de revient) restent corrects sans changement.
        Recalculé même à zéro ligne (dernière ligne supprimée) : sinon
        `montant` resterait figé sur l'ancien total de lignes qui n'existent
        plus, tout en continuant à compter dans les dépenses mensuelles/
        annuelles comme si la ventilation tenait toujours."""
        total = self.lignes.aggregate(Sum('prix_total'))['prix_total__sum'] or Decimal('0')
        self.montant = total
        Facture.objects.filter(pk=self.pk).update(montant=total)

    @classmethod
    def depenses_mensuelles(cls, annee, mois, type_depense=None):
        if type_depense:
            return cls.objects.filter(
                date__year=annee,
                date__month=mois,
                type_depense=type_depense
            ).aggregate(Sum('montant'))['montant__sum'] or 0
        else:
            return cls.objects.filter(
                date__year=annee,
                date__month=mois
            ).aggregate(Sum('montant'))['montant__sum'] or 0

    @classmethod
    def depenses_annuelles(cls, annee, type_depense=None):
        if type_depense:
            return cls.objects.filter(
                date__year=annee,
                type_depense=type_depense
            ).aggregate(Sum('montant'))['montant__sum'] or 0
        else:
            return cls.objects.filter(
                date__year=annee
            ).aggregate(Sum('montant'))['montant__sum'] or 0

    @classmethod
    def cout_revient_animal(cls, animal, annee, mois=None):
        """Coût de revient d'un animal sur une période (année seule, ou mois
        d'une année si `mois` est fourni) :
        - la totalité des lignes de ventilation qui lui sont attribuées,
        - + la totalité des factures non ventilées où il est l'animal renseigné,
        - + une part égale (÷ nombre d'animaux enregistrés) des coûts
          « partagés » : les lignes ventilées marquées « Tous les animaux »,
          et les factures non ventilées sans aucun animal renseigné.
        """
        nb_animaux = Animal.objects.count()
        if not nb_animaux:
            return Decimal('0')

        filtre_lignes = {'facture__date__year': annee}
        filtre_factures = {'date__year': annee}
        if mois:
            filtre_lignes['facture__date__month'] = mois
            filtre_factures['date__month'] = mois

        total_lignes_animal = LigneFacture.objects.filter(
            animal=animal, **filtre_lignes
        ).aggregate(Sum('prix_total'))['prix_total__sum'] or Decimal('0')

        total_factures_animal = cls.objects.filter(
            animal=animal, lignes__isnull=True, **filtre_factures
        ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0')

        total_lignes_partagees = LigneFacture.objects.filter(
            pour_tous_les_animaux=True, **filtre_lignes
        ).aggregate(Sum('prix_total'))['prix_total__sum'] or Decimal('0')

        total_factures_partagees = cls.objects.filter(
            animal__isnull=True, lignes__isnull=True, **filtre_factures
        ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0')

        part_partagee = (total_lignes_partagees + total_factures_partagees) / nb_animaux

        return total_lignes_animal + total_factures_animal + part_partagee

    @classmethod
    def couts_revient_annuels(cls, annee):
        """Coût de revient annuel de chaque animal enregistré, en une seule
        passe (peu de requêtes, indépendant du nombre d'animaux) — pour la
        colonne « Coût de revient » de la liste globale des animaux."""
        animaux_ids = list(Animal.objects.values_list('pk', flat=True))
        nb_animaux = len(animaux_ids)
        if not nb_animaux:
            return {}

        par_animal_lignes = dict(
            LigneFacture.objects.filter(animal__isnull=False, facture__date__year=annee)
            .values('animal').annotate(total=Sum('prix_total')).values_list('animal', 'total')
        )
        par_animal_factures = dict(
            cls.objects.filter(animal__isnull=False, lignes__isnull=True, date__year=annee)
            .values('animal').annotate(total=Sum('montant')).values_list('animal', 'total')
        )
        total_lignes_partagees = LigneFacture.objects.filter(
            pour_tous_les_animaux=True, facture__date__year=annee
        ).aggregate(Sum('prix_total'))['prix_total__sum'] or Decimal('0')
        total_factures_partagees = cls.objects.filter(
            animal__isnull=True, lignes__isnull=True, date__year=annee
        ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
        part_partagee = (total_lignes_partagees + total_factures_partagees) / nb_animaux

        return {
            animal_id: (par_animal_lignes.get(animal_id) or Decimal('0'))
                       + (par_animal_factures.get(animal_id) or Decimal('0'))
                       + part_partagee
            for animal_id in animaux_ids
        }

    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)

        if is_new and self.animal and self.animal.proprietaire.email:
            utilisateur = resoudre_utilisateur(self.animal.proprietaire.email)
            if utilisateur:
                Notification.objects.create(
                    utilisateur=utilisateur,
                    type='FACTURE_A_PAYER',
                    titre=f"Nouvelle facture pour {self.animal.nom}",
                    message=f"Une nouvelle facture '{self.titre}' de {self.montant}€ a été ajoutée pour {self.animal.nom}.",
                    lien=reverse('factures:facture_detail', args=[self.pk]),
                )

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-date']


class LigneFacture(models.Model):
    """Une ligne de la ventilation d'une facture (bouton « Ventiler la
    facture ») : un produit/une prestation, attribué(e) soit à un animal
    précis, soit à tous les animaux (coût partagé, cf.
    Facture.cout_revient_animal)."""

    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='lignes')
    designation = models.ForeignKey(
        Designation, on_delete=models.SET_NULL, null=True, related_name='lignes_facture',
        verbose_name="Désignation",
    )
    quantite = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('1'),
        validators=[MinValueValidator(Decimal('0.01'))], verbose_name="Quantité",
    )
    prix_unitaire = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))], verbose_name="Prix unitaire (€)",
    )
    prix_total = models.DecimalField(
        max_digits=10, decimal_places=2, editable=False, verbose_name="Prix total (€)",
    )
    animal = models.ForeignKey(
        Animal, on_delete=models.SET_NULL, null=True, blank=True, related_name='lignes_facture',
        verbose_name="Animal concerné",
    )
    pour_tous_les_animaux = models.BooleanField(
        default=False, verbose_name="Tous les animaux",
        help_text="Coût partagé également entre tous les animaux enregistrés plutôt qu'attribué à un seul.",
    )

    def clean(self):
        if bool(self.animal_id) == bool(self.pour_tous_les_animaux):
            raise ValidationError(
                "Choisis soit un animal précis, soit « Tous les animaux » (l'un des deux, pas les deux)."
            )

    def save(self, *args, **kwargs):
        self.prix_total = (self.quantite or Decimal('0')) * (self.prix_unitaire or Decimal('0'))
        super().save(*args, **kwargs)
        self.facture.recalculer_montant()

    def delete(self, *args, **kwargs):
        facture = self.facture
        super().delete(*args, **kwargs)
        facture.recalculer_montant()

    def __str__(self):
        cible = "Tous les animaux" if self.pour_tous_les_animaux else self.animal
        return f"{self.designation} x{self.quantite} ({cible})"

    class Meta:
        verbose_name = "Ligne de facture"
        verbose_name_plural = "Lignes de facture"
