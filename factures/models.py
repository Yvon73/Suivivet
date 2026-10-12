from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.urls import reverse
from animaux.models import Animal
from django.db.models import Sum
from django.db.models.functions import Lower, Trim

from accueil.utils import comptes_accessibles
from accueil.catalogues import REATTRIBUER_OU_SUPPRIMER
from notifications.models import Notification
from notifications.utils import resoudre_utilisateur
from Projet_veto.fichiers import brancher_menage_fichier
from Projet_veto.validators import validate_file_extension, validate_file_size


class TypeDepense(models.Model):
    nom = models.CharField(max_length=100, verbose_name="Type de dépense")

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Type de dépense"
        verbose_name_plural = "Types de dépenses"


class Designation(models.Model):
    """Catalogue des désignations de produits/prestations utilisées dans la
    ventilation d'une facture : permet de retrouver le dernier prix unitaire
    pratiqué pour une même désignation. Chaque désignation est rattachée à
    son compte créateur (`utilisateur`) et visible par tout le foyer partagé
    de ce compte (cf. accueil.utils.filtre_catalogue) — jamais par un autre
    compte, qui peut donc créer la sienne sous le même nom. Les prix, eux, ne
    se lisent que dans les factures du compte et de son foyer — cf.
    dernier_prix_unitaire()."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=REATTRIBUER_OU_SUPPRIMER, related_name='designations',
        verbose_name="Compte",
    )
    nom = models.CharField(max_length=200, verbose_name="Désignation")

    @staticmethod
    def cle_nom(nom):
        """Forme de comparaison d'un nom de désignation : sans espaces de
        bord ni distinction de casse. Deux désignations de même clé sont des
        « homonymes » — chaque compte pouvant créer la sienne, un foyer en
        réunit dès que deux de ses membres avaient la même avant de se
        rejoindre (cf. dernier_prix_unitaire, LigneFactureForm)."""
        return (nom or '').strip().lower()

    @classmethod
    def avec_cle_nom(cls, queryset, champ='nom'):
        """`queryset` annoté de `cle_nom` : l'équivalent SQL de cle_nom()
        pour le nom de désignation porté par `champ`."""
        return queryset.annotate(cle_nom=Lower(Trim(champ)))

    def dernier_prix_unitaire(self, utilisateur):
        """Dernier prix unitaire connu pour cette désignation parmi les
        factures visibles de `utilisateur` (les siennes et celles de son
        foyer partagé — jamais le prix payé par un autre compte), ou None
        si elle n'y a jamais été utilisée.

        Cherché par *nom* (cf. cle_nom), pas par clé : dans un foyer où deux
        membres ont chacun leur « Croquettes », l'historique des prix est
        celui du produit, quelle que soit celle des deux désignations que
        porte chaque ligne."""
        derniere_ligne = (
            Designation.avec_cle_nom(LigneFacture.objects.all(), 'designation__nom')
            .filter(
                facture__utilisateur__in=comptes_accessibles(utilisateur),
                cle_nom=self.cle_nom(self.nom),
            )
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
        constraints = [
            # Unique par compte (et non plus dans toute l'installation) : deux
            # comptes peuvent avoir chacun leur « Croquettes ». Le doublon au
            # sein d'un foyer est refusé par DesignationForm.clean_nom ; ceux
            # qui existaient avant que les comptes ne se rejoignent sont
            # regroupés à l'affichage (cf. LigneFactureForm).
            models.UniqueConstraint(fields=['utilisateur', 'nom'], name='designation_unique_nom_par_compte'),
        ]


class Facture(models.Model):
    TYPE_DEPENSE_CHOIX = [
        ('VETERINAIRE', 'Vétérinaire'),
        ('ALIMENTAIRE', 'Alimentaire'),
    ]

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='factures',
        verbose_name="Compte",
        help_text=(
            "Compte auquel appartient cette facture (créateur) : visible par ce compte et, le "
            "cas échéant, les autres membres de son foyer partagé (cf. accueil.utils."
            "comptes_accessibles). Déduit automatiquement du propriétaire de l'animal "
            "concerné quand il y en a un (cf. save()) ; obligatoire à préciser "
            "explicitement pour une facture partagée sans animal renseigné."
        ),
    )
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
    def depenses_mensuelles(cls, utilisateur, annee, mois, type_depense=None):
        filtre = {'utilisateur__in': comptes_accessibles(utilisateur), 'date__year': annee, 'date__month': mois}
        if type_depense:
            filtre['type_depense'] = type_depense
        return cls.objects.filter(**filtre).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.00')

    @classmethod
    def depenses_annuelles(cls, utilisateur, annee, type_depense=None):
        filtre = {'utilisateur__in': comptes_accessibles(utilisateur), 'date__year': annee}
        if type_depense:
            filtre['type_depense'] = type_depense
        return cls.objects.filter(**filtre).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.00')

    @classmethod
    def cout_revient_animal(cls, animal, annee, mois=None):
        """Coût de revient d'un animal sur une période (année seule, ou mois
        d'une année si `mois` est fourni) :
        - la totalité des lignes de ventilation qui lui sont attribuées,
        - + la totalité des factures non ventilées où il est l'animal renseigné,
        - + une part égale (÷ nombre d'animaux visibles) des coûts
          « partagés » : les lignes ventilées marquées « Tous les animaux »,
          et les factures non ventilées sans aucun animal renseigné — au sein
          des comptes accessibles au propriétaire de `animal` (lui-même, plus
          les autres membres de son foyer partagé le cas échéant — cf.
          accueil.utils.comptes_accessibles —, jamais mélangé avec les
          animaux d'un compte hors foyer).
        """
        comptes = comptes_accessibles(animal.utilisateur)
        nb_animaux = Animal.objects.filter(utilisateur__in=comptes).count()
        if not nb_animaux:
            return Decimal('0')

        filtre_lignes = {'facture__date__year': annee, 'facture__utilisateur__in': comptes}
        filtre_factures = {'date__year': annee, 'utilisateur__in': comptes}
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
    def couts_revient_annuels(cls, utilisateur, annee):
        """Coût de revient annuel de chaque animal visible de `utilisateur`
        (lui-même, plus les autres membres de son foyer partagé le cas
        échéant), en une seule passe (peu de requêtes, indépendant du nombre
        d'animaux) — pour la colonne « Coût de revient » de la liste globale
        des animaux."""
        comptes = comptes_accessibles(utilisateur)
        animaux_ids = list(Animal.objects.filter(utilisateur__in=comptes).values_list('pk', flat=True))
        nb_animaux = len(animaux_ids)
        if not nb_animaux:
            return {}

        par_animal_lignes = dict(
            LigneFacture.objects.filter(
                animal__isnull=False, facture__utilisateur__in=comptes, facture__date__year=annee
            ).values('animal').annotate(total=Sum('prix_total')).values_list('animal', 'total')
        )
        par_animal_factures = dict(
            cls.objects.filter(animal__isnull=False, utilisateur__in=comptes, lignes__isnull=True, date__year=annee)
            .values('animal').annotate(total=Sum('montant')).values_list('animal', 'total')
        )
        total_lignes_partagees = LigneFacture.objects.filter(
            pour_tous_les_animaux=True, facture__utilisateur__in=comptes, facture__date__year=annee
        ).aggregate(Sum('prix_total'))['prix_total__sum'] or Decimal('0')
        total_factures_partagees = cls.objects.filter(
            animal__isnull=True, utilisateur__in=comptes, lignes__isnull=True, date__year=annee
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
        if not self.utilisateur_id and self.animal_id:
            self.utilisateur_id = self.animal.utilisateur_id
        super().save(*args, **kwargs)

        if is_new and self.animal and self.animal.proprietaire.email:
            # Seulement un compte qui voit cette facture (le sien ou son
            # foyer) : l'email d'une fiche propriétaire est une saisie libre.
            utilisateur = resoudre_utilisateur(
                self.animal.proprietaire.email, parmi=comptes_accessibles(self.utilisateur),
            )
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


# Le fichier scanné quitte le disque avec sa facture, ou quand il est remplacé.
brancher_menage_fichier(Facture, 'fichier')


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


def factures_emportees_par(animal):
    """Ce que la suppression de `animal` emporte côté factures (décision
    produit : « supprimer avec l'animal »), sous forme de trois QuerySets :

    - `lignes` : ses lignes de facture ventilées ;
    - `factures_videes` : les factures ventilées dont *toutes* les lignes lui
      sont attribuées — sans plus aucune ligne, elles sont supprimées aussi
      (une facture ventilée qui garde d'autres lignes est conservée, son
      montant recalculé) ;
    - `factures_non_ventilees` : les factures non ventilées qui le nomment.

    Les lignes « Tous les animaux » et les factures sans animal ne sont jamais
    concernées. Sert à la fois à la suppression elle-même (signal ci-dessous)
    et à la page de confirmation (cf. animaux.views.AnimalDeleteView), pour
    que celle-ci annonce exactement ce qui sera supprimé."""
    lignes = LigneFacture.objects.filter(animal=animal)
    factures_videes = Facture.objects.filter(
        pk__in=lignes.values('facture'),
    ).exclude(
        pk__in=LigneFacture.objects.exclude(animal=animal).values('facture'),
    )
    factures_non_ventilees = Facture.objects.filter(animal=animal, lignes__isnull=True)
    return {
        'lignes': lignes,
        'factures_videes': factures_videes,
        'factures_non_ventilees': factures_non_ventilees,
    }


@receiver(pre_delete, sender=Animal, dispatch_uid='factures_supprimer_avec_animal')
def supprimer_factures_avec_animal(sender, instance, **kwargs):
    """Supprimer un animal supprime ses lignes de facture et ses factures non
    ventilées (cf. factures_emportees_par). Sans cela, les clés `animal` en
    SET_NULL transformaient ses factures en dépenses partagées entre les
    animaux restants et faisaient disparaître ses lignes des coûts de revient.

    Branché sur pre_delete plutôt que dans la vue : vaut pour tout chemin de
    suppression (vue, admin, shell, QuerySet.delete(), cascade depuis le
    compte). Django émet ce signal à l'intérieur de la transaction de la
    suppression : tout est annulé ensemble en cas d'erreur, et les fichiers
    scannés ne quittent le disque qu'une fois celle-ci validée (signal
    post_delete de Facture, cf. Projet_veto.fichiers)."""
    emportees = factures_emportees_par(instance)
    # Listes figées avant toute suppression : les QuerySets ci-dessus
    # dépendent des lignes que l'on s'apprête à retirer.
    ids_a_supprimer = set(emportees['factures_videes'].values_list('pk', flat=True))
    ids_a_supprimer.update(emportees['factures_non_ventilees'].values_list('pk', flat=True))
    factures_a_recalculer = list(
        Facture.objects.filter(pk__in=emportees['lignes'].values('facture')).exclude(pk__in=ids_a_supprimer)
    )
    # QuerySet.delete() ne passe pas par LigneFacture.delete() : le montant
    # des factures qui gardent d'autres lignes est donc recalculé ici.
    emportees['lignes'].delete()
    for facture in factures_a_recalculer:
        facture.recalculer_montant()
    Facture.objects.filter(pk__in=ids_a_supprimer).delete()
