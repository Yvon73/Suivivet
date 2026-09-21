"""Envoi des emails soignés de l'application (rappel de consultation,
invitation de partage de compte...) — centralise le rendu HTML+texte brut et
l'intégration du logo en entête, pour ne pas dupliquer cette logique à chaque
point d'envoi (cf. consultations.models.Consultation.envoyer_rappel,
accueil.views.envoyer_invitation_foyer).
"""
from email.message import MIMEPart
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

_CHEMIN_LOGO = Path(settings.BASE_DIR) / 'static' / 'img' / 'apple-touch-icon.png'


def _piece_jointe_logo():
    """Logo de l'application en pièce jointe CID (`cid:logo_entete` dans
    emails/base_email.html) plutôt qu'en image distante à charger depuis le
    serveur : un rendu fiable même dans les clients qui bloquent par défaut
    les images externes, et qui fonctionne aussi bien en développement (sans
    domaine public joignable) qu'en production. Construite avec l'API
    `email.message.MIMEPart` moderne — la classe historiquement utilisée pour
    ça, `email.mime.image.MIMEImage`, n'est plus acceptée par
    EmailMessage.attach() sans avertissement de dépréciation dans Django 6."""
    partie = MIMEPart()
    with open(_CHEMIN_LOGO, 'rb') as fichier_logo:
        partie.set_content(
            fichier_logo.read(), maintype='image', subtype='png',
            disposition='inline', filename='logo.png', cid='<logo_entete>',
        )
    return partie


def envoyer_email(template_nom, contexte, sujet, destinataires):
    """Envoie un email HTML (texte brut en repli obligatoire pour les
    lecteurs qui l'exigent et les filtres anti-spam) à partir d'une paire de
    templates `emails/<template_nom>.html`/`.txt` partageant le même
    contexte, avec le logo de l'application en entête (cf.
    _piece_jointe_logo)."""
    texte = render_to_string(f'emails/{template_nom}.txt', contexte)
    html = render_to_string(f'emails/{template_nom}.html', contexte)

    message = EmailMultiAlternatives(
        subject=sujet, body=texte, from_email=settings.DEFAULT_FROM_EMAIL, to=destinataires,
    )
    message.attach_alternative(html, 'text/html')
    message.attach(_piece_jointe_logo())

    message.send(fail_silently=False)
