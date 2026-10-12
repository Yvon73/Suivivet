"""Listes à recherche, tri et pagination côté serveur.

Remplace DataTables (qui triait et filtrait dans le navigateur) : le texte
cherché, la colonne de tri et la page voulue sont de simples paramètres
d'URL (`q`, `tri`, `sens`, `page`), appliqués ici à la requête SQL. La page
fonctionne donc telle quelle par des liens et un formulaire GET ordinaires ;
htmx ne fait qu'éviter de recharger toute la page, en ne remplaçant que la
zone `#zoneListe` (cf. templates/partials/liste_*.html et le tag
`entete_tri` de accueil/templatetags/listes.py).
"""
from django.db.models import Case, CharField, F, Func, Q, Value, When
from django.db.models.functions import Cast, Concat, Replace, Trunc


def date_texte(champ, heure=False):
    """Annotation : la date telle qu'elle est affichée dans les listes
    (jj/mm/aaaa, suivie de hh:mm si `heure`), pour qu'une saisie comme
    « 03/2026 » la retrouve — à déclarer ensuite dans `champs_recherche`.
    Avec `heure` (DateTimeField), l'instant est d'abord ramené au fuseau
    courant, comme à l'affichage. `to_char` : PostgreSQL, seul moteur du projet."""
    source = Trunc(champ, 'minute') if heure else F(champ)
    return Func(
        source, Value('DD/MM/YYYY HH24:MI' if heure else 'DD/MM/YYYY'),
        function='to_char', output_field=CharField(),
    )


def libelle_choix_texte(champ, choix):
    """Annotation : le libellé affiché d'un champ à `choices` (« Vétérinaire »
    pour le code `VETERINAIRE`), la base ne contenant que le code."""
    return Case(
        *[When(**{champ: code}, then=Value(libelle)) for code, libelle in choix],
        default=Value(''), output_field=CharField(),
    )


def montant_texte(champ):
    """Annotation : le montant écrit avec un point puis avec une virgule
    (« 45.90 45,90 »), les deux saisies devant le retrouver."""
    texte = Cast(champ, CharField())
    return Concat(texte, Value(' '), Replace(texte, Value('.'), Value(',')), output_field=CharField())


class ListeTriableMixin:
    """À placer devant ListView. La vue déclare :

    - `champs_recherche` : champs (lookups ORM) dans lesquels chercher le
      texte saisi — chaque mot doit se retrouver dans au moins l'un d'eux ;
      une annotation du queryset convient aussi (cf. `date_texte`,
      `libelle_choix_texte` et `montant_texte` ci-dessus, pour les colonnes
      dont le texte affiché n'est pas celui stocké) ;
    - `colonnes_tri` : clé de colonne (celle passée à `{% entete_tri %}`) ->
      champ ORM, ou tuple de champs, sur lequel trier ;
    - `tri_defaut` : clé de la colonne triée par défaut, précédée de « - »
      pour un tri décroissant ;

    et applique `self.filtrer_et_trier(queryset)` à la fin de son
    `get_queryset()`.
    """

    paginate_by = 10
    champs_recherche = ()
    colonnes_tri = {}
    tri_defaut = ''

    def get_recherche(self):
        # Sans octet NUL : PostgreSQL le refuse dans une chaîne (DataError,
        # donc erreur 500 sur une URL forgée du type ?q=a%00b).
        return self.request.GET.get('q', '').replace('\x00', '').strip()

    def get_tri(self):
        """(clé de colonne, 'asc' ou 'desc') d'après l'URL, sinon le tri par défaut."""
        cle = self.request.GET.get('tri', '')
        if cle in self.colonnes_tri:
            return cle, 'desc' if self.request.GET.get('sens') == 'desc' else 'asc'
        if self.tri_defaut.startswith('-'):
            return self.tri_defaut[1:], 'desc'
        return self.tri_defaut, 'asc'

    def filtrer_et_trier(self, queryset):
        recherche = self.get_recherche()
        if recherche and self.champs_recherche:
            correspondances = queryset
            for mot in recherche.split():
                filtre = Q()
                for champ in self.champs_recherche:
                    filtre |= Q(**{f'{champ}__icontains': mot})
                correspondances = correspondances.filter(filtre)
            # Par sous-requête : chercher à travers une relation multiple
            # (ex. les identifications d'un animal) ne duplique ainsi aucune ligne.
            queryset = queryset.filter(pk__in=correspondances.values('pk'))

        cle, sens = self.get_tri()
        champs = self.colonnes_tri.get(cle)
        if not champs:
            return queryset
        if isinstance(champs, str):
            champs = (champs,)
        if sens == 'desc':
            champs = [champ[1:] if champ.startswith('-') else f'-{champ}' for champ in champs]
        # La clé primaire en dernier critère : un ordre stable d'une page à l'autre.
        return queryset.order_by(*champs, 'pk')

    def paginate_queryset(self, queryset, page_size):
        """Comme ListView, mais un numéro de page absent, illisible ou trop
        grand (liste raccourcie par une recherche ou une suppression) ramène
        à une page existante au lieu d'une erreur 404."""
        paginator = self.get_paginator(
            queryset, page_size, orphans=self.get_paginate_orphans(), allow_empty_first_page=True,
        )
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cle, sens = self.get_tri()
        context.update(q=self.get_recherche(), tri=cle, sens=sens, colonnes_tri=self.colonnes_tri)
        page = context.get('page_obj')
        if page is not None:
            context['pages_affichees'] = list(
                page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)
            )
            context['ellipse_pagination'] = page.paginator.ELLIPSIS
        return context
