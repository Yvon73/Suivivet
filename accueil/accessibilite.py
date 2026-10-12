"""Préférences du panneau accessibilité (cf.
templates/partials/panneau_accessibilite.html) : lecture, validation et
enregistrement, que le visiteur soit connecté ou non.

- Compte connecté : enregistrées sur le compte (PreferenceAccessibilite),
  donc réappliquées à chaque connexion, sur n'importe quel navigateur.
- Visiteur non connecté (accueil, connexion, inscription) : pas de compte
  auquel les rattacher, elles sont gardées dans un cookie signé de ce seul
  navigateur — un cookie de personnalisation de l'interface, demandé par le
  visiteur lui-même.

Dans les deux cas, c'est le serveur qui les applique au rendu de chaque page
(classes sur <html>, cf. Projet_veto/context_processors.py) : aucun script
n'est nécessaire, ni pour les appliquer ni pour les mémoriser.
"""
import json

from django.core import signing

from .models import PreferenceAccessibilite

COOKIE = 'accessibilite'
SEL_COOKIE = 'accueil.accessibilite'
DUREE_COOKIE = 365 * 24 * 3600  # un an

CHAMPS_BOOLEENS = ('contraste_eleve', 'police_lisible', 'reduire_animations', 'palette_daltonisme', 'mode_sombre')


def par_defaut():
    preferences = {'taille_texte': PreferenceAccessibilite.Taille.NORMAL.value}
    preferences.update({champ: False for champ in CHAMPS_BOOLEENS})
    return preferences


def _valider(brut):
    """Préférences sûres à partir de données quelconques (formulaire, cookie) :
    tout ce qui est absent ou inattendu retombe sur la valeur par défaut."""
    preferences = par_defaut()
    if not isinstance(brut, dict):
        return preferences
    if brut.get('taille_texte') in PreferenceAccessibilite.Taille.values:
        preferences['taille_texte'] = brut['taille_texte']
    for champ in CHAMPS_BOOLEENS:
        preferences[champ] = bool(brut.get(champ))
    return preferences


def depuis_formulaire(donnees):
    """Préférences correspondant à l'état du panneau tel qu'il est envoyé :
    la taille choisie, et une case cochée = un champ présent."""
    brut = {champ: champ in donnees for champ in CHAMPS_BOOLEENS}
    brut['taille_texte'] = donnees.get('taille_texte')
    return _valider(brut)


def lire(request):
    """Préférences en vigueur pour cette requête."""
    if request.user.is_authenticated:
        enregistrees = PreferenceAccessibilite.objects.filter(utilisateur=request.user).first()
        if enregistrees is None:
            return par_defaut()
        return _valider({champ: getattr(enregistrees, champ) for champ in ('taille_texte', *CHAMPS_BOOLEENS)})
    try:
        return _valider(json.loads(request.get_signed_cookie(COOKIE, salt=SEL_COOKIE)))
    except (KeyError, ValueError, signing.BadSignature):
        return par_defaut()


def enregistrer(request, response, preferences):
    """Mémorise `preferences` : sur le compte connecté, sinon dans le cookie
    posé sur `response`."""
    preferences = _valider(preferences)
    if request.user.is_authenticated:
        PreferenceAccessibilite.objects.update_or_create(utilisateur=request.user, defaults=preferences)
    else:
        response.set_signed_cookie(
            COOKIE, json.dumps(preferences), salt=SEL_COOKIE, max_age=DUREE_COOKIE,
            httponly=True, samesite='Lax', secure=request.is_secure(),
        )


def classes_css(preferences):
    """Classes à poser sur <html> pour appliquer `preferences`."""
    champs = {champ: valeur for champ, valeur in preferences.items() if champ != 'mode_sombre'}
    return PreferenceAccessibilite(**champs).classes_css()
