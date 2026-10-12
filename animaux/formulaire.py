"""Interactions « en direct » du formulaire animal, côté serveur.

Le formulaire animal n'a plus de JavaScript propre : chaque interaction est
envoyée par htmx à l'une des vues de ce module, qui renvoie le HTML à
afficher —

- choix de l'espèce / de la race, filtre des races (`choix_race`) : le menu
  « Race » ne propose que les races de l'espèce choisie, et la fiche de la
  race sélectionnée s'affiche en dessous ;
- aperçu de la photo choisie avant enregistrement (`apercu_photo`) ;
- lignes « organisme + identification » ajoutées / retirées
  (`identifications`) ;
- ajouts rapides au catalogue par les boutons « + » : propriétaire, espèce,
  race, robe, organisme (cf. Projet_veto/ajout_rapide.py).

Rien n'est enregistré ici en dehors de ces entrées de catalogue : l'animal
et ses identifications ne le sont qu'à la soumission du formulaire complet
(cf. views.AnimalIdentificationsFormsetMixin).
"""
import base64
import io
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps

from accueil.utils import comptes_accessibles
from Projet_veto import ajout_rapide
from .forms import (
    AnimalForm, AnimalIdentificationFormSet, EspeceQuickAddForm, OrganismeQuickAddForm,
    ProprietaireForm, RaceQuickAddForm, RobeQuickAddForm, identifiant,
)
from .models import Animal, Race

logger = logging.getLogger(__name__)

PREFIXE_IDENTIFICATIONS = AnimalIdentificationFormSet.get_default_prefix()

# Au-delà, pas d'aperçu (la photo reste envoyée normalement à l'enregistrement).
TAILLE_MAX_APERCU = 15 * 1024 * 1024
COTE_MAX_APERCU = 480


# --- Contexte du gabarit ---------------------------------------------------

def _race_selectionnee(form):
    race_id = identifiant(form['race'].value())
    return Race.objects.select_related('espece').filter(pk=race_id).first() if race_id else None


def contexte_identifications(formset, animal=None, afficher_erreurs=False):
    """Contexte de la zone des identifications (animaux/partials/identifications.html).
    Une ligne retirée reste dans la page, masquée, sa case DELETE cochée :
    c'est l'enregistrement du formulaire qui la supprime réellement en base
    si elle y existait déjà."""
    lignes = [
        {'form': ligne, 'retiree': bool(ligne['DELETE'].value()), 'index': index}
        for index, ligne in enumerate(formset.forms)
    ]
    # Les libellés des colonnes sont portés par la première ligne visible
    # (la toute première peut avoir été retirée). Toute ligne se retire, y
    # compris la première quand elle est déjà enregistrée — sauf une ligne
    # vierge restée seule, qu'il n'y aurait aucun intérêt à masquer.
    visibles = [ligne for ligne in lignes if not ligne['retiree']]
    for ligne in lignes:
        ligne['premiere'] = bool(visibles) and ligne is visibles[0]
        ligne['retirable'] = len(visibles) > 1 or bool(ligne['form'].instance.pk)
    arguments = [animal.pk] if animal is not None and animal.pk else []
    return {
        'identifications_formset': formset,
        'lignes_identification': lignes,
        'afficher_erreurs_identifications': afficher_erreurs,
        'url_identifications': reverse('animaux:animal_identifications', args=arguments),
    }


def contexte_formulaire(form, formset=None, animal=None, afficher_erreurs=False, formulaires_ajout=None):
    """Contexte des parties du formulaire animal pilotées par htmx (sans la
    zone des identifications si `formset` n'est pas fourni).
    `formulaires_ajout` : formulaires d'ajout rapide déjà soumis et invalides
    (par nom), à réafficher ouverts avec leurs erreurs."""
    formulaires_ajout = formulaires_ajout or {}
    arguments = [animal.pk] if animal is not None and animal.pk else []

    def ajout(nom, titre, url_name, classe_form, champ, arguments_url=(), arguments_form=None, inclure=''):
        form_ajout = formulaires_ajout.get(nom)
        if form_ajout is None:
            form_vierge = classe_form(prefix=f'nouveau_{nom}', **(arguments_form or {}))
        return ajout_rapide.contexte(
            nom=nom, titre=titre, url=reverse(f'animaux:{url_name}', args=arguments_url),
            form=form_ajout or form_vierge, champ=champ, ouvert=form_ajout is not None, inclure=inclure,
        )

    contexte = {
        'form': form,
        'race_fiche': _race_selectionnee(form),
        'recherche_race': getattr(form, 'recherche_race', ''),
        'url_choix_race': reverse('animaux:animal_choix_race'),
        'url_apercu_photo': reverse('animaux:animal_apercu_photo'),
        'ajout_proprietaire': ajout(
            'proprietaire', 'Ajouter un propriétaire absent de la liste', 'proprietaire_ajout_rapide',
            ProprietaireForm, form['proprietaire'], arguments_form={'user': form.user},
        ),
        'ajout_espece': ajout(
            'espece', 'Ajouter une espèce absente de la liste', 'espece_ajout_rapide',
            EspeceQuickAddForm, form['espece'], inclure='#id_espece, #id_race, #recherche_race',
        ),
        'ajout_race': ajout(
            'race', 'Ajouter une race absente du catalogue', 'race_ajout_rapide',
            RaceQuickAddForm, form['race'], inclure='#id_espece, #id_race, #recherche_race',
            arguments_form={'initial': {'espece': identifiant(form['espece'].value()) or None}},
        ),
        'ajout_robe': ajout(
            'robe', 'Ajouter une robe absente de la liste', 'robe_ajout_rapide',
            RobeQuickAddForm, form['robe'],
        ),
        'ajout_organisme': ajout(
            'organisme', 'Ajouter un organisme absent de la liste', 'organisme_ajout_rapide',
            OrganismeQuickAddForm, None, arguments_url=arguments, inclure='#zoneIdentifications',
        ),
    }
    if formset is not None:
        contexte.update(contexte_identifications(formset, animal, afficher_erreurs))
    return contexte


def _form_depuis_saisie(request, **surcharges):
    """Formulaire animal non lié reprenant les menus déroulants tels que
    saisis (envoyés par htmx), sans validation ni message d'erreur : il ne
    sert qu'à redessiner l'un ou l'autre de ces menus."""
    initial = {champ: request.POST.get(champ, '') for champ in ('proprietaire', 'espece', 'race', 'robe')}
    recherche = request.POST.get('recherche_race', '')
    initial.update(surcharges)
    form = AnimalForm(initial=initial, user=request.user, recherche_race=recherche)
    form.recherche_race = recherche
    return form


def _formset_depuis_saisie(request, animal=None, data=None):
    return AnimalIdentificationFormSet(
        request.POST if data is None else data, instance=animal, prefix=PREFIXE_IDENTIFICATIONS,
    )


def _animal(request, pk):
    """Animal en cours de modification (None à la création), s'il est bien
    visible du compte connecté."""
    if pk is None:
        return None
    return get_object_or_404(Animal, pk=pk, utilisateur__in=comptes_accessibles(request.user))


def _reponse_menus(request, form, ajout=None, **mises_a_jour):
    """Réponse htmx redessinant les menus « Espèce » / « Race » et la fiche de
    race : tout revient en hx-swap-oob, précédé du panneau d'ajout rapide
    `ajout` replié quand la réponse fait suite à un ajout au catalogue."""
    contexte = contexte_formulaire(form)
    if mises_a_jour.get('maj_panneau_race'):
        contexte['ajout_race']['form'].fields['espece'].widget.attrs['hx-swap-oob'] = 'true'
    contexte.update(mises_a_jour)
    contexte['ajout'] = contexte[ajout] if ajout else None
    return render(request, 'animaux/partials/choix_race_reponse.html', contexte)


# --- Espèce / race ---------------------------------------------------------

@login_required
@require_POST
def choix_race(request):
    """Changement d'espèce, de race, ou frappe dans le filtre des races.

    - Espèce changée : le menu « Race » ne propose plus que ses races ; une
      race sélectionnée qui ne lui correspond pas est désélectionnée pour
      forcer un nouveau choix (seul l'affichage change, rien en base).
    - Race choisie avant l'espèce : l'espèce correspondante est renseignée
      d'office.
    - Dans tous les cas, la fiche de la race sélectionnée est mise à jour.

    Le menu dans lequel on vient de choisir n'est jamais redessiné, sauf
    quand sa liste doit changer."""
    source = request.headers.get('HX-Trigger', '')
    espece_id = identifiant(request.POST.get('espece'))
    race = Race.objects.filter(pk=identifiant(request.POST.get('race')) or None).first()
    surcharges = {}
    mises_a_jour = {'maj_race': source != 'zone-race'}

    if source == 'zone-espece':
        if race and espece_id and str(race.espece_id) != espece_id:
            surcharges['race'] = ''
        mises_a_jour.update(maj_panneau_race=True)
    elif source == 'zone-race' and race and not espece_id:
        surcharges['espece'] = str(race.espece_id)
        mises_a_jour.update(maj_espece=True, maj_race=True, maj_panneau_race=True)

    return _reponse_menus(request, _form_depuis_saisie(request, **surcharges), **mises_a_jour)


@login_required
@require_POST
def ajouter_espece_rapide(request):
    """Crée une espèce (et sa première race, « Autre » par défaut) depuis le
    panneau « + » du menu « Espèce », puis les sélectionne toutes les deux."""
    form_ajout = EspeceQuickAddForm(request.POST, prefix='nouveau_espece')
    if not form_ajout.is_valid():
        contexte = contexte_formulaire(_form_depuis_saisie(request), formulaires_ajout={'espece': form_ajout})
        return ajout_rapide.reponse(request, contexte['ajout_espece'], succes=False)
    espece, race = form_ajout.save()
    form = _form_depuis_saisie(request, espece=str(espece.pk), race=str(race.pk))
    return _reponse_menus(request, form, ajout='ajout_espece', maj_espece=True, maj_race=True, maj_panneau_race=True)


@login_required
@require_POST
def ajouter_race_rapide(request):
    """Crée une race depuis le panneau « + » du menu « Race », sans jamais
    toucher aux données déjà en base, puis la sélectionne (et aligne le menu
    « Espèce » sur la sienne)."""
    form_ajout = RaceQuickAddForm(request.POST, prefix='nouveau_race')
    if not form_ajout.is_valid():
        contexte = contexte_formulaire(_form_depuis_saisie(request), formulaires_ajout={'race': form_ajout})
        return ajout_rapide.reponse(request, contexte['ajout_race'], succes=False)
    race = form_ajout.save()
    form = _form_depuis_saisie(request, espece=str(race.espece_id), race=str(race.pk))
    return _reponse_menus(request, form, ajout='ajout_race', maj_espece=True, maj_race=True)


# --- Propriétaire / robe ---------------------------------------------------

def _ajout_simple(request, nom, classe_form, champ, **arguments_form):
    """Ajout rapide dont le seul effet est de sélectionner la nouvelle entrée
    dans le menu `champ` du formulaire animal."""
    form_ajout = classe_form(request.POST, prefix=f'nouveau_{nom}', **arguments_form)
    if not form_ajout.is_valid():
        contexte = contexte_formulaire(_form_depuis_saisie(request), formulaires_ajout={nom: form_ajout})
        return ajout_rapide.reponse(request, contexte[f'ajout_{nom}'], succes=False)
    entree = form_ajout.save()
    contexte = contexte_formulaire(_form_depuis_saisie(request, **{champ: str(entree.pk)}))
    return ajout_rapide.reponse(request, contexte[f'ajout_{nom}'], succes=True)


@login_required
@require_POST
def ajouter_proprietaire_rapide(request):
    """Crée un propriétaire depuis le panneau « + » du menu « Propriétaire »
    et le sélectionne."""
    return _ajout_simple(request, 'proprietaire', ProprietaireForm, 'proprietaire', user=request.user)


@login_required
@require_POST
def ajouter_robe_rapide(request):
    """Crée une robe depuis le panneau « + » du menu « Robe » et la sélectionne."""
    return _ajout_simple(request, 'robe', RobeQuickAddForm, 'robe')


# --- Identifications -------------------------------------------------------

def _entier(valeur, defaut=0):
    try:
        return max(int(valeur), 0)
    except (TypeError, ValueError):
        return defaut


@login_required
@require_POST
def identifications(request, pk=None):
    """Ajoute ou retire une ligne « organisme + identification » et renvoie
    la zone redessinée, les saisies en cours étant conservées."""
    animal = _animal(request, pk)
    data = request.POST.copy()
    nombre = _entier(data.get(f'{PREFIXE_IDENTIFICATIONS}-TOTAL_FORMS'))
    action = data.get('action')
    if action == 'ajouter':
        data[f'{PREFIXE_IDENTIFICATIONS}-TOTAL_FORMS'] = str(nombre + 1)
    elif action == 'retirer':
        ligne = data.get('ligne', '')
        ligne = int(ligne) if ligne.isdigit() else -1
        if 0 <= ligne < nombre:
            data[f'{PREFIXE_IDENTIFICATIONS}-{ligne}-DELETE'] = 'on'
    formset = _formset_depuis_saisie(request, animal, data)
    return render(request, 'animaux/partials/identifications.html', contexte_identifications(formset, animal))


@login_required
@require_POST
def ajouter_organisme_rapide(request, pk=None):
    """Crée un organisme depuis le panneau « Nouvel organisme » et le
    sélectionne sur la dernière ligne d'identification encore vierge (ni
    organisme ni numéro) : celle que l'on vient d'ajouter pour lui. Une ligne
    déjà renseignée — un numéro de puce sans organisme, cas courant — n'est
    jamais modifiée d'office ; s'il n'y a aucune ligne vierge, rien n'est
    présélectionné et l'organisme est simplement proposé dans tous les menus."""
    animal = _animal(request, pk)
    form_ajout = OrganismeQuickAddForm(request.POST, prefix='nouveau_organisme')
    if not form_ajout.is_valid():
        contexte = contexte_formulaire(
            _form_depuis_saisie(request), _formset_depuis_saisie(request, animal), animal,
            formulaires_ajout={'organisme': form_ajout},
        )
        return ajout_rapide.reponse(request, contexte['ajout_organisme'], succes=False)
    organisme = form_ajout.save()

    data = request.POST.copy()
    for index in reversed(range(_entier(data.get(f'{PREFIXE_IDENTIFICATIONS}-TOTAL_FORMS')))):
        prefixe = f'{PREFIXE_IDENTIFICATIONS}-{index}'
        if not any(data.get(f'{prefixe}-{champ}', '').strip() for champ in ('organisme', 'identification', 'DELETE', 'id')):
            data[f'{prefixe}-organisme'] = str(organisme.pk)
            break
    contexte = contexte_formulaire(_form_depuis_saisie(request), _formset_depuis_saisie(request, animal, data), animal)
    contexte.update(ajout=contexte['ajout_organisme'], oob=True)
    return render(request, 'animaux/partials/organisme_reponse.html', contexte)


# --- Photo -----------------------------------------------------------------

@login_required
@require_POST
def apercu_photo(request):
    """Aperçu de la photo choisie, avant enregistrement : vignette renvoyée
    directement dans la page (image encodée en base64, rien n'est stocké).
    Réponse vide (204, la page reste telle quelle) si le fichier n'est pas
    une image lisible."""
    fichier = request.FILES.get('photo')
    if not fichier or fichier.size > TAILLE_MAX_APERCU:
        return HttpResponse(status=204)
    try:
        image = ImageOps.exif_transpose(Image.open(fichier))
        image.thumbnail((COTE_MAX_APERCU, COTE_MAX_APERCU))
        tampon = io.BytesIO()
        image.convert('RGB').save(tampon, format='JPEG', quality=80)
    except Exception:  # Pillow lève des exceptions très diverses sur un fichier illisible.
        logger.info("Aperçu de photo impossible pour « %s »", fichier.name)
        return HttpResponse(status=204)
    source = 'data:image/jpeg;base64,' + base64.b64encode(tampon.getvalue()).decode('ascii')
    return render(request, 'animaux/partials/apercu_photo.html', {'apercu_source': source})
