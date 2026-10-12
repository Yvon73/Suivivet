"""Ventilation « en direct » d'une facture, côté serveur.

Le formulaire de facture n'a plus de JavaScript propre : chaque interaction
(saisie d'une quantité, ajout/retrait d'une ligne, nouvelle désignation)
est envoyée par HTMX à `views.ventilation_facture`, qui s'appuie sur ce
module pour manipuler les données du formset puis recalculer les totaux
affichés. Rien n'est enregistré ici, à l'exception d'une nouvelle
désignation du catalogue : la facture et ses lignes ne le sont qu'à la
soumission du formulaire complet (cf. VentilationFactureMixin.post).
"""
import re
from decimal import Decimal, InvalidOperation

from django.http import QueryDict

from accueil.utils import filtre_catalogue

from .forms import DesignationForm, LigneFactureFormSet
from .models import Designation

PREFIXE = LigneFactureFormSet.get_default_prefix()
CHAMP_NOUVELLE_DESIGNATION = 'nouvelle_designation'

_CLE_LIGNE = re.compile(rf'^({PREFIXE}|{CHAMP_NOUVELLE_DESIGNATION})-(\d+)(-.*)?$')
_CENTIME = Decimal('0.01')


def _decimal(valeur):
    """Nombre saisi (virgule ou point décimal acceptés), ou None s'il est
    vide ou illisible."""
    if valeur is None:
        return None
    try:
        nombre = Decimal(str(valeur).strip().replace(',', '.'))
    except InvalidOperation:
        return None
    return nombre if nombre.is_finite() else None


def _entier(valeur, defaut=0):
    try:
        return max(int(valeur), 0)
    except (TypeError, ValueError):
        return defaut


def _prix_total(quantite, prix_unitaire):
    try:
        return ((quantite or Decimal('0')) * (prix_unitaire or Decimal('0'))).quantize(_CENTIME)
    except InvalidOperation:
        return Decimal('0.00')


def ajouter_ligne(data):
    """Ajoute une ligne vide en fin de formset. L'animal concerné reprend
    par défaut celui de la dernière ligne (saisie plus rapide quand
    plusieurs lignes consécutives concernent le même animal)."""
    nombre = _entier(data.get(f'{PREFIXE}-TOTAL_FORMS'))
    if nombre:
        cible = data.get(f'{PREFIXE}-{nombre - 1}-cible')
        if cible:
            data[f'{PREFIXE}-{nombre}-cible'] = cible
    data[f'{PREFIXE}-{nombre}-quantite'] = '1'
    data[f'{PREFIXE}-TOTAL_FORMS'] = str(nombre + 1)
    return data


def retirer_ligne(data, index):
    """Retire une ligne pas encore enregistrée et renumérote les suivantes.
    Une ligne déjà enregistrée ne se retire pas ainsi : elle se supprime via
    sa case « Suppr. », à l'enregistrement de la facture."""
    nombre = _entier(data.get(f'{PREFIXE}-TOTAL_FORMS'))
    index = _entier(index, defaut=-1)
    if not _entier(data.get(f'{PREFIXE}-INITIAL_FORMS')) <= index < nombre:
        return data

    resultat = QueryDict(mutable=True)
    for cle, valeurs in data.lists():
        correspondance = _CLE_LIGNE.match(cle)
        if correspondance:
            champ, position, suffixe = correspondance.groups()
            position = int(position)
            if position == index:
                continue
            if position > index:
                cle = f'{champ}-{position - 1}{suffixe or ""}'
        resultat.setlist(cle, valeurs)
    resultat[f'{PREFIXE}-TOTAL_FORMS'] = str(nombre - 1)
    return resultat


def creer_designations(data, ligne_demandee=None, utilisateur=None):
    """Crée chaque désignation saisie dans un champ « Nouvelle désignation »,
    rattachée au compte `utilisateur`, et la sélectionne sur sa ligne.
    Renvoie les erreurs par index de ligne."""
    erreurs = {}
    creees = set()
    for cle in list(data.keys()):
        champ, _, index = cle.rpartition('-')
        if champ != CHAMP_NOUVELLE_DESIGNATION or not index.isdigit():
            continue
        nom = data.get(cle, '').strip()
        if not nom:
            continue
        form = DesignationForm({'nom': nom}, user=utilisateur)
        if form.is_valid():
            designation = form.save()
            data[f'{PREFIXE}-{index}-designation'] = str(designation.pk)
            data[cle] = ''
            creees.add(int(index))
        else:
            erreurs[int(index)] = [erreur for liste in form.errors.values() for erreur in liste]

    # Bouton « Ajouter » cliqué sur une ligne dont le champ est resté vide.
    # Seulement si la requête n'a rien créé ni refusé ailleurs : la touche
    # Entrée dans le champ d'une autre ligne « clique » le premier bouton
    # « Ajouter » du formulaire, pas celui de la ligne où l'on tape.
    if not creees and not erreurs and str(ligne_demandee).isdigit():
        index = int(ligne_demandee)
        if f'{CHAMP_NOUVELLE_DESIGNATION}-{index}' in data:
            erreurs[index] = ["La désignation est obligatoire."]
    return erreurs


def contexte_lignes(formset, erreurs_designation=None, utilisateur=None):
    """Contexte d'affichage des lignes : prix total de chacune, rappel du
    dernier prix pratiqué pour sa désignation, et montant total de la
    facture (hors lignes cochées « Suppr. »). Le dernier prix n'est cherché
    que parmi les factures visibles de `utilisateur` (aucun rappel sans lui)."""
    erreurs_designation = erreurs_designation or {}
    data = formset.data if formset.is_bound else {}
    lignes = []
    total = Decimal('0')

    for index, form in enumerate(formset.forms):
        enregistree = bool(form.instance.pk)
        if enregistree:
            prix_unitaire = form.instance.prix_unitaire
            prix_total = form.instance.prix_total
            designation_id = form.instance.designation_id
        else:
            prix_unitaire = _decimal(form['prix_unitaire'].value())
            prix_total = _prix_total(_decimal(form['quantite'].value()), prix_unitaire)
            designation_id = form['designation'].value()

        if not data.get(f'{form.prefix}-DELETE'):
            total += prix_total

        dernier_prix = comparaison = None
        if utilisateur and designation_id and str(designation_id).isdigit():
            # Désignation du compte ou de son foyer, ou celle que porte déjà
            # la ligne enregistrée — jamais celle d'un autre compte.
            designation = Designation.objects.filter(
                filtre_catalogue(utilisateur, garder=form.instance.designation_id), pk=designation_id,
            ).first()
            dernier_prix = designation.dernier_prix_unitaire(utilisateur) if designation else None
        if dernier_prix is not None and prix_unitaire is not None:
            if prix_unitaire > dernier_prix:
                comparaison = 'plus'
            elif prix_unitaire < dernier_prix:
                comparaison = 'moins'
            else:
                comparaison = 'identique'

        lignes.append({
            'form': form,
            'index': index,
            'enregistree': enregistree,
            'prix_total': prix_total,
            'dernier_prix': dernier_prix,
            'comparaison': comparaison,
            'nouvelle_designation': data.get(f'{CHAMP_NOUVELLE_DESIGNATION}-{index}', ''),
            'erreurs_designation': erreurs_designation.get(index, []),
        })

    return {'lignes': lignes, 'total': total, 'total_str': f'{total:.2f}'}
