from django.conf import settings
from django.db import models
from django.urls import reverse
from accueil.utils import comptes_accessibles
from accueil.catalogues import REATTRIBUER_OU_SUPPRIMER
from animaux.models import Animal
from notifications.models import Notification
from notifications.utils import resoudre_utilisateur
from Projet_veto.fichiers import brancher_menage_fichier
from Projet_veto.validators import validate_file_extension, validate_file_size


class TypeDocument(models.Model):
    """Catalogue des types de document : entrées de référence livrées par les
    migrations du projet (`utilisateur` vide, proposées à tous les comptes)
    et types ajoutés par un compte depuis le formulaire de document,
    rattachés à ce compte et visibles de son seul foyer — cf.
    accueil.utils.filtre_catalogue."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=REATTRIBUER_OU_SUPPRIMER, null=True, blank=True,
        related_name='types_document', verbose_name="Compte",
        help_text=(
            "Compte qui a ajouté cette entrée au catalogue : visible par ce compte et son foyer "
            "partagé. Vide pour une entrée de référence, livrée avec l'application et proposée à "
            "tous les comptes."
        ),
    )
    nom = models.CharField(max_length=100, verbose_name="Type de document")

    @property
    def est_reference(self):
        """Entrée de référence livrée avec l'application (aucun compte créateur)."""
        return self.utilisateur_id is None

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Type de document"
        verbose_name_plural = "Types de documents"

class Document(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='documents')
    type_document = models.ForeignKey(TypeDocument, on_delete=models.SET_NULL, null=True, verbose_name="Type de document")
    titre = models.CharField(max_length=200, verbose_name="Titre du document")
    fichier = models.FileField(
        upload_to='documents/',
        verbose_name="Fichier",
        validators=[validate_file_extension, validate_file_size],
    )
    date_ajout = models.DateField(auto_now_add=True, verbose_name="Date d'ajout")
    description = models.TextField(blank=True, verbose_name="Description")

    def __str__(self):
        return f"{self.titre} ({self.animal.nom})"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)

        if is_new and self.animal and self.animal.proprietaire.email:
            # Seulement un compte qui voit ce document (celui de l'animal ou
            # son foyer) : l'email d'une fiche propriétaire est une saisie libre.
            utilisateur = resoudre_utilisateur(
                self.animal.proprietaire.email, parmi=comptes_accessibles(self.animal.utilisateur),
            )
            if utilisateur:
                Notification.objects.create(
                    utilisateur=utilisateur,
                    type='NOUVEAU_DOCUMENT',
                    titre=f"Nouveau document pour {self.animal.nom}",
                    message=f"Un nouveau document '{self.titre}' a été ajouté pour {self.animal.nom}.",
                    lien=reverse('documents:document_detail', args=[self.pk]),
                )

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-date_ajout']


# Le fichier quitte le disque avec sa ligne, ou quand il est remplacé.
brancher_menage_fichier(Document, 'fichier')
