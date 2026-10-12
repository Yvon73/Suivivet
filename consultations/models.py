import logging

from django.conf import settings
from django.db import models
from accueil.utils import comptes_accessibles
from accueil.catalogues import REATTRIBUER_OU_SUPPRIMER
from animaux.models import Animal
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from notifications.models import Notification
from Projet_veto.emailing import envoyer_email

logger = logging.getLogger(__name__)

FORMAT_DATE_HEURE = '%d/%m/%Y à %H:%M'


class Veterinaire(models.Model):
    """Fiche complète d'un vétérinaire (nom, coordonnées), réutilisable d'une
    consultation à l'autre : un même vétérinaire qui suit plusieurs animaux
    n'est saisi qu'une fois. Comme Proprietaire côté animaux, la fiche est
    rattachée à son compte créateur (`utilisateur`) et visible par tout le
    foyer partagé de ce compte (cf. accueil.utils.filtre_catalogue) — jamais
    par un autre compte."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=REATTRIBUER_OU_SUPPRIMER, related_name='veterinaires',
        verbose_name="Compte",
    )
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
    # RESTRICT et non PROTECT : un vétérinaire qui a des consultations reste
    # impossible à supprimer seul, mais pas quand ces consultations partent
    # dans la même suppression (compte supprimé avec ses animaux).
    veterinaire = models.ForeignKey(
        Veterinaire, on_delete=models.RESTRICT, related_name='consultations', verbose_name="Vétérinaire",
    )
    rappel_task_id = models.CharField(
        max_length=255, blank=True, null=True, editable=False,
        verbose_name="Identifiant de la tâche Celery de rappel",
        help_text=(
            "Identifiant de la seule tâche autorisée à envoyer le rappel : elle ne l'envoie que si "
            "elle le retrouve ici, et le vide en le prenant (cf. consultations.tasks). Vide = aucun "
            "rappel en attente (déjà envoyé, annulé, ou jamais programmé)."
        ),
    )

    def date_locale(self):
        """Date et heure de la consultation dans le fuseau de l'application
        (Europe/Paris). Relue en base, `self.date` est en UTC : un strftime
        direct afficherait 1 à 2 h de moins que l'heure saisie."""
        return timezone.localtime(self.date).strftime(FORMAT_DATE_HEURE)

    def __str__(self):
        return f"Consultation pour {self.animal.nom} le {self.date_locale()} ({self.motif})"

    def _revoquer_rappel(self):
        """Annule le rappel Celery programmé. Un courtier (Redis) injoignable
        ne doit pas faire échouer l'enregistrement ou la suppression : la
        tâche n'envoie rien si son identifiant n'est plus celui enregistré
        sur la consultation (cf. tasks.py), on se contente donc de
        journaliser."""
        from celery.result import AsyncResult
        try:
            AsyncResult(self.rappel_task_id).revoke()
        except Exception:
            logger.exception("Révocation du rappel impossible (consultation %s)", self.pk)

    def save(self, *args, **kwargs):
        # Vrai quand le rappel n'a pas pu être programmé (courtier Celery
        # injoignable) : la vue s'en sert pour prévenir l'utilisateur.
        self.rappel_non_planifie = False
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
                self._revoquer_rappel()
                self.rappel_task_id = None

            rappel_date = self.date - timedelta(days=2)
            nouveau_task_id = None
            if rappel_date > timezone.now():
                # Import différé pour éviter l'import circulaire models <-> tasks
                from .tasks import envoyer_rappel_consultation
                # Planifier le rappel avec Celery. La consultation est déjà
                # enregistrée : si le courtier est injoignable (l'exception
                # varie selon que c'est le courtier ou le backend de résultats
                # qui ne répond pas), on la garde sans rappel plutôt que de
                # répondre par une erreur 500 qui pousserait à la ressaisir.
                # L'identifiant est choisi ici et enregistré *avant* la
                # publication : la tâche n'envoie le rappel que si elle le
                # retrouve sur la consultation (cf. tasks.py), il doit donc y
                # être avant qu'un worker puisse la recevoir.
                from celery import uuid
                nouveau_task_id = uuid()
                Consultation.objects.filter(pk=self.pk).update(rappel_task_id=nouveau_task_id)
                try:
                    envoyer_rappel_consultation.apply_async(
                        (self.pk,),
                        eta=rappel_date,
                        task_id=nouveau_task_id,
                    )
                except Exception:
                    logger.exception("Planification du rappel impossible (consultation %s)", self.pk)
                    self.rappel_non_planifie = True
                    nouveau_task_id = None

            # L'id enregistré désigne la seule tâche autorisée à envoyer le
            # rappel : le remplacer (ou le vider) périme toute tâche
            # antérieure, même si sa révocation s'est perdue. update() plutôt
            # que save() pour ne pas redéclencher cette méthode / le signal
            # post_save.
            Consultation.objects.filter(pk=self.pk).update(rappel_task_id=nouveau_task_id)
            self.rappel_task_id = nouveau_task_id

    def delete(self, *args, **kwargs):
        if self.rappel_task_id:
            # Annule le rappel Celery programmé pour éviter qu'il ne
            # s'exécute (et échoue avec Consultation.DoesNotExist) une fois
            # la consultation supprimée.
            self._revoquer_rappel()
        return super().delete(*args, **kwargs)

    def envoyer_rappel(self):
        """Crée une notification in-app puis envoie un rappel par email
        (HTML soigné, cf. Projet_veto.emailing). La notification d'abord :
        elle reste acquise si l'email ne part pas (la tâche ne retente pas
        l'envoi, cf. tasks.py)."""
        # Création d'une notification in-app (si un compte utilisateur correspond au propriétaire)
        if self.animal.proprietaire.email:
            from notifications.utils import resoudre_utilisateur
            # Seulement un compte qui voit cette consultation (celui de
            # l'animal ou son foyer) : l'email d'une fiche propriétaire est une
            # saisie libre.
            utilisateur = resoudre_utilisateur(
                self.animal.proprietaire.email, parmi=comptes_accessibles(self.animal.utilisateur),
            )
            if utilisateur:
                Notification.objects.create(
                    utilisateur=utilisateur,
                    type='RAPPEL_CONSULTATION',
                    titre=f"Rappel : Consultation pour {self.animal.nom}",
                    message=f"Consultation prévue le {self.date_locale()} (motif: {self.motif}).",
                    lien=reverse('consultations:consultation_detail', args=[self.pk]),
                )

        # Envoi de l'email
        if self.animal.proprietaire.email:
            envoyer_email(
                'rappel_consultation',
                {
                    'animal_nom': self.animal.nom,
                    'date_consultation': self.date_locale(),
                    'motif': self.motif,
                },
                f"Rappel : Consultation pour {self.animal.nom} dans 2 jours",
                [self.animal.proprietaire.email],
            )

    class Meta:
        verbose_name = "Consultation"
        verbose_name_plural = "Consultations"
        ordering = ['-date']
