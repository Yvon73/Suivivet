"""Limitation du nombre de tentatives sur les formulaires publics les plus
susceptibles d'être visés par des robots (connexion, inscription) — cf.
Projet_veto.middleware.NoIndexMiddleware pour le volet indexation/crawl.

Deux niveaux :
- un compteur volatil dans le cache Django (CACHES, cf. settings.py — Redis
  partagé entre workers, comme le broker Celery) pour la fenêtre de blocage
  en cours ;
- un historique persistant en base (accueil.models.BlocageAdresse) pour
  escalader la durée en cas de récidive, même après expiration du cache ou
  redémarrage du process : 15 min la 1ère fois, 1h la 2e, blocage définitif
  à partir de la 3e (levable uniquement depuis /admin/).
"""
from django.core.cache import cache

MAX_TENTATIVES = 3

# Durée de blocage appliquée à la 1ère, puis à la 2e récidive. Au-delà
# (nombre_blocages > len(...)), le blocage devient définitif.
PALIERS_BLOCAGE_SECONDES = [15 * 60, 60 * 60]


def _adresse_ip(request):
    # NB : si BEHIND_REVERSE_PROXY est actif, REMOTE_ADDR est l'adresse du
    # proxy (aucun middleware ici ne restitue l'adresse réelle du client via
    # X-Forwarded-For) — tous les visiteurs passant par ce proxy partagent
    # alors le même compteur.
    return request.META.get('REMOTE_ADDR', '')


def _cle(prefixe, request):
    return f'throttle:{prefixe}:{_adresse_ip(request)}'


def est_bloque(prefixe, request):
    """True si `prefixe` (ex. 'login', 'inscription') est actuellement
    bloqué depuis cette adresse — blocage définitif (base) ou fenêtre de
    blocage en cours (cache)."""
    from accueil.models import BlocageAdresse

    ip = _adresse_ip(request)
    if BlocageAdresse.objects.filter(prefixe=prefixe, adresse_ip=ip, bloque_definitivement=True).exists():
        return True
    return cache.get(_cle(prefixe, request), 0) >= MAX_TENTATIVES


def enregistrer_tentative(prefixe, request):
    """Incrémente le compteur de tentatives. Le déclenchement du blocage
    (compteur atteignant MAX_TENTATIVES) fait avancer l'historique persistant
    d'un palier, et détermine la durée de la fenêtre de cache en conséquence."""
    from accueil.models import BlocageAdresse

    cle = _cle(prefixe, request)
    tentatives = cache.get(cle, 0) + 1

    if tentatives < MAX_TENTATIVES:
        cache.set(cle, tentatives, PALIERS_BLOCAGE_SECONDES[0])
        return

    ip = _adresse_ip(request)
    blocage, _ = BlocageAdresse.objects.get_or_create(prefixe=prefixe, adresse_ip=ip)

    if tentatives == MAX_TENTATIVES:
        # Ce blocage vient de se déclencher (pas juste une tentative de plus
        # pendant un blocage déjà actif) : une récidive de plus.
        blocage.nombre_blocages += 1
        if blocage.nombre_blocages > len(PALIERS_BLOCAGE_SECONDES):
            blocage.bloque_definitivement = True
        blocage.save()

    if blocage.bloque_definitivement:
        return  # plus besoin du cache, le blocage est définitif en base

    index_palier = min(blocage.nombre_blocages, len(PALIERS_BLOCAGE_SECONDES)) - 1
    cache.set(cle, tentatives, PALIERS_BLOCAGE_SECONDES[index_palier])


def reinitialiser_tentatives(prefixe, request):
    """Ne remet à zéro que le compteur volatil (une connexion réussie
    n'efface pas l'historique des récidives passées)."""
    cache.delete(_cle(prefixe, request))


def message_blocage(prefixe, request):
    """Message à afficher à l'utilisateur, adapté au palier de blocage
    atteint (bloque_definitivement ne peut être levé que depuis /admin/)."""
    from accueil.models import BlocageAdresse

    blocage = BlocageAdresse.objects.filter(prefixe=prefixe, adresse_ip=_adresse_ip(request)).first()
    if blocage and blocage.bloque_definitivement:
        return "Accès bloqué définitivement depuis cette adresse suite à des tentatives répétées."
    if blocage and blocage.nombre_blocages >= 2:
        return "Trop de tentatives depuis cette adresse. Réessaie dans 1 heure."
    return "Trop de tentatives depuis cette adresse. Réessaie dans 15 minutes."
