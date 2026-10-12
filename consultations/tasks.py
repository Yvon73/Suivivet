import logging

from celery import shared_task
from .models import Consultation

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def envoyer_rappel_consultation(self, consultation_id):
    """Envoie le rappel d'une consultation, au plus une fois et seulement
    s'il est toujours d'actualité.

    La tâche « prend » le rappel de façon atomique : un UPDATE conditionnel
    vide `Consultation.rappel_task_id` à condition qu'il contienne encore
    l'identifiant de *cette* tâche. Zéro ligne modifiée = tâche périmée, rien
    n'est envoyé : consultation replanifiée (un autre identifiant a été
    enregistré), rappel annulé, consultation supprimée, ou seconde livraison
    du même message (la première l'a déjà pris). La révocation faite par
    Consultation.save()/delete() n'est donc plus qu'une économie : perdue
    (worker redémarré, courtier injoignable), elle ne fait plus partir de
    rappel à l'ancienne date ni en double.

    Si l'envoi échoue après la prise (SMTP injoignable...), l'erreur est
    journalisée et la tâche s'arrête là, sans nouvelle tentative : le rappel
    reste pris. Choix assumé — mieux vaut un rappel manquant, visible dans
    logs/erreurs.log (et la notification dans l'application, créée avant
    l'email, est déjà là), qu'un rappel envoyé plusieurs fois par des reprises
    en boucle. Résultat ignoré (ignore_result) : il n'est lu nulle part.

    Renvoie True si le rappel a été envoyé (utile aux tests seulement)."""
    task_id = self.request.id
    if not task_id:
        # Appel direct de la fonction, sans passer par Celery : aucun
        # identifiant à comparer, donc aucun moyen de prendre le rappel.
        logger.warning("Rappel de la consultation %s ignoré : tâche sans identifiant", consultation_id)
        return False

    pris = Consultation.objects.filter(
        pk=consultation_id, rappel_task_id=task_id,
    ).update(rappel_task_id=None)
    if not pris:
        logger.info(
            "Rappel périmé ignoré (consultation %s replanifiée, annulée, supprimée ou déjà rappelée)",
            consultation_id,
        )
        return False

    try:
        consultation = Consultation.objects.get(pk=consultation_id)
    except Consultation.DoesNotExist:
        # Supprimée entre la prise et la lecture : rien à envoyer.
        return False
    try:
        consultation.envoyer_rappel()
    except Exception:
        logger.exception("Envoi du rappel impossible (consultation %s) : il ne sera pas retenté", consultation_id)
        return False
    return True
