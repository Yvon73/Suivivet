"""Ajout rapide d'une entrée de catalogue depuis un formulaire (bouton « + »
à droite d'un menu déroulant : vétérinaire, vaccin, race, propriétaire...).

Pas de JavaScript propre : le bouton « + » déplie un panneau (collapse
Bootstrap) dont les champs sont rattachés, par leur attribut `form`, à un
petit formulaire htmx distinct du formulaire principal — un appui sur Entrée
y crée donc l'entrée de catalogue au lieu d'enregistrer la fiche en cours.
La vue appelée renvoie le panneau redessiné (replié si l'ajout a réussi,
avec ses erreurs sinon) et, en cas de succès, le menu déroulant mis à jour
en `hx-swap-oob`, la nouvelle entrée y étant sélectionnée.

Gabarits : templates/partials/ajout_rapide_{champ,panneau,form,reponse}.html.
"""
from django.shortcuts import render


def contexte(nom, titre, url, form, champ, ouvert=False, bouton='', inclure=''):
    """Contexte attendu par les gabarits `partials/ajout_rapide_*.html`.

    `nom` identifie l'ajout rapide dans la page (ids HTML), `form` est le
    formulaire de création de l'entrée de catalogue (à instancier avec un
    `prefix`, pour que ses champs ne se confondent pas avec ceux du
    formulaire principal), `champ` le champ lié (BoundField) du formulaire
    principal à côté duquel le bouton « + » s'affiche. `bouton` : libellé
    d'un bouton affiché sous le champ plutôt qu'accolé à lui (liste à
    sélection multiple, trop haute pour un bouton accolé). `inclure` :
    sélecteur CSS des champs du formulaire principal à joindre à l'envoi
    (par défaut, le seul champ concerné).
    """
    for champ_ajout in form.fields.values():
        champ_ajout.widget.attrs['form'] = f'form-ajout-{nom}'
    return {
        'nom': nom, 'titre': titre, 'url': url, 'form': form, 'champ': champ, 'ouvert': ouvert,
        'bouton': bouton, 'inclure': inclure or f'#champ-{nom}',
    }


def reponse(request, ajout, succes):
    """Réponse htmx à la soumission d'un ajout rapide."""
    return render(request, 'partials/ajout_rapide_reponse.html', {'ajout': ajout, 'succes': succes})
