from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import Consultation
from notifications.models import Notification
from notifications.utils import resoudre_utilisateur

@receiver(post_save, sender=Consultation)
def créer_notification_consultation(sender, instance, created, **kwargs):
    if created:
        # Trouver le compte utilisateur associé au propriétaire par email, s'il existe
        if instance.animal.proprietaire.email:
            utilisateur = resoudre_utilisateur(instance.animal.proprietaire.email)
            if utilisateur:
                Notification.objects.create(
                    utilisateur=utilisateur,
                    type='RAPPEL_CONSULTATION',
                    titre=f"Nouvelle consultation pour {instance.animal.nom}",
                    message=f"Une consultation a été planifiée pour {instance.animal.nom} le {instance.date.strftime('%d/%m/%Y à %H:%M')} (motif: {instance.motif}).",
                    lien=reverse('consultations:consultation_detail', args=[instance.pk]),
                )