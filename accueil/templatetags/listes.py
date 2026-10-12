"""Tags de gabarit des listes triables (cf. Projet_veto/listes.py)."""
from django import template

register = template.Library()


@register.inclusion_tag('partials/liste_entete_tri.html', takes_context=True)
def entete_tri(context, cle, intitule):
    """En-tête de colonne `<th>` dont l'intitulé est un lien de tri : un
    premier clic trie par ordre croissant, le suivant inverse le sens. Une
    colonne absente de `colonnes_tri` s'affiche en simple intitulé."""
    triable = cle in context.get('colonnes_tri', {})
    actif = triable and context.get('tri') == cle
    sens = context.get('sens', 'asc') if actif else ''
    url = ''
    if triable:
        parametres = context['request'].GET.copy()
        parametres['tri'] = cle
        parametres['sens'] = 'desc' if sens == 'asc' else 'asc'
        parametres.pop('page', None)
        url = '?' + parametres.urlencode()
    return {'intitule': intitule, 'triable': triable, 'sens': sens, 'url': url}
