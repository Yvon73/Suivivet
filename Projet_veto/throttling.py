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
import ipaddress
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

MAX_TENTATIVES = 3

# Durée de blocage appliquée à la 1ère, puis à la 2e récidive. Au-delà
# (nombre_blocages > len(...)), le blocage devient définitif.
PALIERS_BLOCAGE_SECONDES = [15 * 60, 60 * 60]


def _adresse_ip(request):
    """Adresse IP du visiteur, ou None si aucune adresse valide n'est
    disponible (dans ce cas aucune limitation n'est appliquée : mieux vaut ne
    pas limiter que partager un compteur entre tous les visiteurs, ou écrire
    une adresse vide dans BlocageAdresse.adresse_ip, refusée par la base).

    Derrière le reverse-proxy de confiance (BEHIND_REVERSE_PROXY, cf.
    settings.py), REMOTE_ADDR est l'adresse du proxy — voire une chaîne vide
    quand gunicorn écoute sur un socket unix (cf. deploy/) : l'adresse réelle
    est alors le DERNIER élément de X-Forwarded-For, celui qu'ajoute le proxy
    lui-même. Les éléments précédents sont fournis par le client et donc
    falsifiables : jamais le premier."""
    candidats = []
    if getattr(settings, 'BEHIND_REVERSE_PROXY', False):
        transmis = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if transmis:
            candidats.append(transmis.split(',')[-1].strip())
    candidats.append(request.META.get('REMOTE_ADDR', ''))
    for candidat in candidats:
        try:
            return str(ipaddress.ip_address(candidat))
        except ValueError:
            continue
    return None


def _cle(prefixe, request):
    return f'throttle:{prefixe}:{_adresse_ip(request)}'


def est_bloque(prefixe, request):
    """True si `prefixe` (ex. 'login', 'inscription') est actuellement
    bloqué depuis cette adresse — blocage définitif (base) ou fenêtre de
    blocage en cours (cache)."""
    from accueil.models import BlocageAdresse

    ip = _adresse_ip(request)
    if ip is None:
        return False
    if BlocageAdresse.objects.filter(prefixe=prefixe, adresse_ip=ip, bloque_definitivement=True).exists():
        return True
    return cache.get(_cle(prefixe, request), 0) >= MAX_TENTATIVES


def enregistrer_tentative(prefixe, request):
    """Incrémente le compteur de tentatives. Le déclenchement du blocage
    (compteur atteignant MAX_TENTATIVES) fait avancer l'historique persistant
    d'un palier, et détermine la durée de la fenêtre de cache en conséquence."""
    from accueil.models import BlocageAdresse

    ip = _adresse_ip(request)
    if ip is None:
        logger.warning("Limitation de tentatives inactive : aucune adresse IP exploitable pour cette requête.")
        return

    cle = _cle(prefixe, request)
    tentatives = cache.get(cle, 0) + 1

    if tentatives < MAX_TENTATIVES:
        cache.set(cle, tentatives, PALIERS_BLOCAGE_SECONDES[0])
        return

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
    if _adresse_ip(request) is None:
        return
    cache.delete(_cle(prefixe, request))


def message_blocage(prefixe, request):
    """Message à afficher à l'utilisateur, adapté au palier de blocage
    atteint (bloque_definitivement ne peut être levé que depuis /admin/)."""
    from accueil.models import BlocageAdresse

    ip = _adresse_ip(request)
    blocage = BlocageAdresse.objects.filter(prefixe=prefixe, adresse_ip=ip).first() if ip else None
    if blocage and blocage.bloque_definitivement:
        return "Accès bloqué définitivement depuis cette adresse suite à des tentatives répétées."
    if blocage and blocage.nombre_blocages >= 2:
        return "Trop de tentatives depuis cette adresse. Réessaie dans 1 heure."
    return "Trop de tentatives depuis cette adresse. Réessaie dans 15 minutes."


def limite_simple_atteinte(prefixe, request, maximum, duree_secondes):
    """Limitation sans escalade ni historique en base, pour un formulaire
    public où un blocage définitif serait disproportionné (ex. « mot de passe
    oublié », qu'un utilisateur légitime peut redemander plusieurs fois) :
    compte cet envoi et renvoie True s'il dépasse `maximum` envois depuis
    cette adresse sur une fenêtre de `duree_secondes`."""
    if _adresse_ip(request) is None:
        return False
    cle = _cle(prefixe, request)
    # add() ne fait rien si la clé existe déjà : la fenêtre part du 1er envoi.
    cache.add(cle, 0, duree_secondes)
    try:
        return cache.incr(cle) > maximum
    except ValueError:
        # Clé expirée entre add() et incr() : on repart d'une fenêtre neuve.
        cache.set(cle, 1, duree_secondes)
        return False
