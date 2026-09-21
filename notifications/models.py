from django.db import models
from django.contrib.auth.models import User

class Notification(models.Model):
    TYPE_CHOIX = [
        ('RAPPEL_CONSULTATION', 'Rappel de consultation'),
        ('NOUVEAU_DOCUMENT', 'Nouveau document'),
        ('FACTURE_A_PAYER', 'Facture à payer'),
        ('INVITATION_FOYER', 'Invitation à partager un compte'),
    ]

    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=50, choices=TYPE_CHOIX)
    titre = models.CharField(max_length=200)
    message = models.TextField()
    lien = models.URLField(blank=True, null=True)
    lue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_display()} - {self.titre}"

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"