from django.db import models
from animaux.models import Animal
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from notifications.models import Notification


class Veterinaire(models.Model):
    """Fiche complète d'un vétérinaire (nom, coordonnées), réutilisable d'une
    consultation à l'autre (catalogue partagé, comme Proprietaire côté
    animaux) : un même vétérinaire qui suit plusieurs animaux n'est saisi
    qu'une fois."""

    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, blank=True, verbose_name="Prénom")
    adresse = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    actif = models.BooleanField(
        default=True, verbose_name="Actif",
        help_text=(
            "Décoché lors d'une « suppression » : la fiche reste en base (les consultations déjà "
            "enregistrées continuent de l'afficher) mais n'est plus proposée pour de nouvelles "
            "saisies, ni affichée sur la fiche animal en PDF."
        ),
    )

    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip() or self.email

    def __str__(self):
        return self.nom_complet()

    class Meta:
        verbose_name = "Vétérinaire"
        verbose_name_plural = "Vétérinaires"
        ordering = ['nom', 'prenom']


class Consultation(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='consultations')
    date = models.DateTimeField(verbose_name="Date et heure de la consultation")
    motif = models.TextField(verbose_name="Motif de la consultation")
    compte_rendu = models.TextField(blank=True, verbose_name="Compte rendu")
    veterinaire = models.ForeignKey(
        Veterinaire, on_delete=models.PROTECT, related_name='consultations', verbose_name="Vétérinaire",
    )
    rappel_task_id = models.CharField(
        max_length=255, blank=True, null=True, editable=False,
        verbose_name="Identifiant de la tâche Celery de rappel",
        help_text="Permet d'annuler le rappel programmé si la consultation est supprimée avant son envoi.",
    )

    def __str__(self):
        return f"Consultation pour {self.animal.nom} le {self.date.strftime('%d/%m/%Y à %H:%M')} ({self.motif})"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        date_a_change = True
        if not is_new:
            # Retenu avant le super().save() : nécessaire pour savoir si le
            # rappel déjà programmé (calé sur l'ancienne date) doit être
            # ré-planifié.
            ancienne_date = Consultation.objects.filter(pk=self.pk).values_list('date', flat=True).first()
            date_a_change = ancienne_date != self.date

        super().save(*args, **kwargs)
        # La notification de création est gérée par le signal post_save
        # (voir consultations/signals.py) pour éviter les doublons.

        if date_a_change:
            # Nouvelle consultation, ou date modifiée : le rappel déjà
            # programmé (le cas échéant) correspond à l'ancienne date et
            # doit être annulé avant d'en reprogrammer un pour la date
            # actuelle — sinon un rappel « dans 2 jours » erroné part à
            # l'échéance de l'ancienne date (cf. delete() plus bas).
            if self.rappel_task_id:
                from celery.result import AsyncResult
                AsyncResult(self.rappel_task_id).revoke()
                self.rappel_task_id = None

            rappel_date = self.date - timedelta(days=2)
            nouveau_task_id = None
            if rappel_date > timezone.now():
                # Import différé pour éviter l'import circulaire models <-> tasks
                from .tasks import envoyer_rappel_consultation
                # Planifier le rappel avec Celery
                resultat = envoyer_rappel_consultation.apply_async(
                    (self.pk,),
                    eta=rappel_date
                )
                nouveau_task_id = resultat.id

            # On garde l'id de la tâche pour pouvoir l'annuler si la
            # consultation est supprimée ou re-modifiée avant l'échéance du
            # rappel (cf. delete() ci-dessous). update() plutôt que save()
            # pour ne pas redéclencher cette méthode / le signal post_save.
            Consultation.objects.filter(pk=self.pk).update(rappel_task_id=nouveau_task_id)
            self.rappel_task_id = nouveau_task_id

    def delete(self, *args, **kwargs):
        if self.rappel_task_id:
            # Annule le rappel Celery programmé pour éviter qu'il ne
            # s'exécute (et échoue avec Consultation.DoesNotExist) une fois
            # la consultation supprimée.
            from celery.result import AsyncResult
            AsyncResult(self.rappel_task_id).revoke()
        return super().delete(*args, **kwargs)

    def envoyer_rappel(self):
        """Envoie un rappel par email et crée une notification in-app."""
        sujet = f"Rappel : Consultation pour {self.animal.nom} dans 2 jours"
        message = (
            f"Bonjour,\n\n"
            f"Un rappel pour vous informer que {self.animal.nom} a une consultation prévue "
            f"le {self.date.strftime('%d/%m/%Y à %H:%M')}.\n"
            f"Motif : {self.motif}\n\n"
            f"Cordialement,\n"
            f"Votre application de suivi vétérinaire"
        )

        # Envoi de l'email
        if self.animal.proprietaire.email:
            send_mail(
                sujet,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.animal.proprietaire.email],
                fail_silently=False,
            )

        # Création d'une notification in-app (si un compte utilisateur correspond au propriétaire)
        if self.animal.proprietaire.email:
            from notifications.utils import resoudre_utilisateur
            utilisateur = resoudre_utilisateur(self.animal.proprietaire.email)
            if utilisateur:
                Notification.objects.create(
                    utilisateur=utilisateur,
                    type='RAPPEL_CONSULTATION',
                    titre=f"Rappel : Consultation pour {self.animal.nom}",
                    message=f"Consultation prévue le {self.date.strftime('%d/%m/%Y à %H:%M')} (motif: {self.motif}).",
                    lien=reverse('consultations:consultation_detail', args=[self.pk]),
                )

    class Meta:
        verbose_name = "Consultation"
        verbose_name_plural = "Consultations"
        ordering = ['-date']
