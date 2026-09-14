from celery import shared_task
from .models import Consultation


@shared_task
def envoyer_rappel_consultation(consultation_id):
    try:
        consultation = Consultation.objects.get(pk=consultation_id)
    except Consultation.DoesNotExist:
        # La consultation a été supprimée avant l'échéance du rappel (la
        # révocation de la tâche dans Consultation.delete() n'a pas toujours
        # de garantie, ex. worker redémarré entretemps) : rien à envoyer.
        return
    consultation.envoyer_rappel()
