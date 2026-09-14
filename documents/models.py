from django.db import models
from django.urls import reverse
from animaux.models import Animal
from notifications.models import Notification
from notifications.utils import resoudre_utilisateur
from Projet_veto.validators import validate_file_extension, validate_file_size


class TypeDocument(models.Model):
    nom = models.CharField(max_length=100, verbose_name="Type de document")

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
            utilisateur = resoudre_utilisateur(self.animal.proprietaire.email)
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
