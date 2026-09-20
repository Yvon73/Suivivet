import logging

from django.core.exceptions import DisallowedHost


class SkipDisallowedHost(logging.Filter):
    """Empêche `DisallowedHost` (en-tête `Host` usurpé) de partir sur
    `mail_admins` : un VPS à IP publique en reçoit en continu (scans
    automatisés qui essaient le nom d'hôte du serveur, un sous-domaine
    existant type mail.*, etc.) — déjà bloqués en amont par Apache
    (cf. deploy/apache/ispconfig-directives.conf), mais on garde ce filet de
    sécurité côté Django au cas où une requête l'atteindrait quand même.
    Reste journalisé dans erreurs.log (ce filtre ne s'applique qu'au handler
    mail_admins), juste sans envoi d'email à chaque tentative."""

    def filter(self, record):
        exc_info = record.exc_info
        return not (exc_info and issubclass(exc_info[0], DisallowedHost))
