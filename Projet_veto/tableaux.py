"""Tableaux lisibles sur téléphone, préparés côté serveur.

Sous 768 px de large (cf. section « Mobile » de static/css/style.css), un
tableau `table.table` d'au moins 4 colonnes est réaffiché en une carte par
ligne, chaque valeur précédée de l'intitulé de sa colonne — au lieu d'un
tableau écrasé qu'il faut faire défiler de côté. Le CSS a pour cela besoin
que chaque cellule porte l'intitulé de sa colonne (attribut `data-label`).

`TableauxEmpilablesMiddleware` l'ajoute dans le HTML de chaque réponse, à la
place du script qui le faisait dans le navigateur : il recopie l'intitulé de
chaque colonne (son <th>) dans le `data-label` de chaque cellule, marque la
colonne « Actions » (ou sans intitulé) pour que ses boutons s'alignent en bas
de la carte, et pose les rôles ARIA de tableau — passer les cellules en
display:block fait perdre aux lecteurs d'écran la sémantique native du
<table>, que ces rôles rétablissent. Les gabarits n'ont rien de particulier à
faire, sinon donner un <th> parlant à chaque colonne ; les fragments renvoyés
à htmx sont traités comme les pages entières.

Seules des balises ouvrantes sont complétées, à leur position exacte dans le
texte d'origine : le reste du document n'est ni reformaté ni réécrit.
"""
import logging
import re
from html import escape
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

NB_COLONNES_MIN = 4
CLASSE_TABLEAU = 'tableau-empilable'
CLASSE_ACTIONS = 'cellule-actions'
INTITULE_ACTIONS = 'Actions'

_ATTRIBUT_CLASS = re.compile(r'''(\sclass\s*=\s*)(["'])(.*?)\2''', re.IGNORECASE | re.DOTALL)
_ESPACES = re.compile(r'\s+')


def _completer_balise(balise, attributs=None, classe=None):
    """Balise ouvrante `balise` (texte brut) avec les attributs et la classe
    demandés en plus. Un attribut déjà présent n'est pas remplacé."""
    ajout = ''
    for nom, valeur in (attributs or {}).items():
        if not re.search(rf'\s{re.escape(nom)}\s*=', balise, re.IGNORECASE):
            ajout += f' {nom}="{escape(valeur, quote=True)}"'
    if classe:
        correspondance = _ATTRIBUT_CLASS.search(balise)
        if correspondance:
            classes = f'{correspondance.group(3)} {classe}'.strip()
            balise = (
                balise[:correspondance.start()] + correspondance.group(1) + correspondance.group(2)
                + classes + correspondance.group(2) + balise[correspondance.end():]
            )
        else:
            ajout += f' class="{classe}"'
    fin = len(balise) - (2 if balise.endswith('/>') else 1)
    return balise[:fin] + ajout + balise[fin:]


class _Balise:
    """Balise ouvrante repérée dans le document : sa position, son texte brut,
    et ce qu'il faudra éventuellement lui ajouter."""

    def __init__(self, position, texte, attributs):
        self.position = position
        self.texte = texte
        self.colspan = 1
        valeur = dict(attributs).get('colspan') or ''
        if valeur.strip().isdigit():
            self.colspan = max(int(valeur), 1)
        self.contenu = []  # texte de la cellule (pour un <th> d'en-tête)

    def intitule(self):
        return _ESPACES.sub(' ', ''.join(self.contenu)).strip()


class _Tableau:
    def __init__(self, balise, classes):
        self.balise = balise
        self.classes = classes
        self.entete = None         # balise <thead>
        self.corps = []            # balises <tbody>
        self.lignes_entete = []    # [(balise <tr>, [cellules])]
        self.lignes_corps = []
        self.section = ''          # 'thead', 'tbody', 'tfoot' ou ''
        self.ligne = None          # (balise <tr>, [cellules]) en cours
        self.cellule = None        # cellule en cours


class _Analyseur(HTMLParser):
    """Repère les tableaux `table.table` et produit la liste des balises à
    compléter : [(position, ancien texte, nouveau texte)]."""

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.modifications = []
        self.pile = []
        # getpos() donne (ligne, colonne) : début de chaque ligne dans le texte.
        self.debuts_de_ligne = [0]
        for correspondance in re.finditer('\n', source):
            self.debuts_de_ligne.append(correspondance.end())

    def _balise(self, attributs):
        ligne, colonne = self.getpos()
        return _Balise(self.debuts_de_ligne[ligne - 1] + colonne, self.get_starttag_text(), attributs)

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            classes = (dict(attrs).get('class') or '').split()
            self.pile.append(_Tableau(self._balise(attrs), classes))
            return
        if not self.pile:
            return
        tableau = self.pile[-1]
        if tag in ('thead', 'tbody', 'tfoot'):
            tableau.section = tag
            if tag == 'thead':
                tableau.entete = self._balise(attrs)
            elif tag == 'tbody':
                tableau.corps.append(self._balise(attrs))
        elif tag == 'tr':
            tableau.ligne = (self._balise(attrs), [])
            if tableau.section == 'thead':
                tableau.lignes_entete.append(tableau.ligne)
            elif tableau.section != 'tfoot':
                tableau.lignes_corps.append(tableau.ligne)
        elif tag in ('td', 'th') and tableau.ligne is not None:
            tableau.cellule = self._balise(attrs)
            tableau.ligne[1].append(tableau.cellule)

    def handle_data(self, data):
        if self.pile and self.pile[-1].cellule is not None:
            self.pile[-1].cellule.contenu.append(data)

    def handle_endtag(self, tag):
        if not self.pile:
            return
        tableau = self.pile[-1]
        if tag in ('td', 'th'):
            tableau.cellule = None
        elif tag == 'tr':
            tableau.ligne = tableau.cellule = None
        elif tag in ('thead', 'tbody', 'tfoot'):
            tableau.section = ''
        elif tag == 'table':
            self._preparer(self.pile.pop())

    def _modifier(self, balise, attributs=None, classe=None):
        nouveau = _completer_balise(balise.texte, attributs, classe)
        if nouveau != balise.texte:
            self.modifications.append((balise.position, balise.texte, nouveau))

    def _preparer(self, tableau):
        if 'table' not in tableau.classes or CLASSE_TABLEAU in tableau.classes or not tableau.lignes_entete:
            return
        # Intitulés : ceux de la dernière ligne d'en-tête, répétés sur la
        # largeur (colspan) de chaque cellule.
        intitules = []
        for cellule in tableau.lignes_entete[-1][1]:
            intitules.extend([cellule.intitule()] * cellule.colspan)
        if len(intitules) < NB_COLONNES_MIN:
            return

        self._modifier(tableau.balise, {'role': 'table'}, CLASSE_TABLEAU)
        if tableau.entete is not None:
            self._modifier(tableau.entete, {'role': 'rowgroup'})
        for ligne, cellules in tableau.lignes_entete:
            self._modifier(ligne, {'role': 'row'})
            for cellule in cellules:
                self._modifier(cellule, {'role': 'columnheader'})
        for corps in tableau.corps:
            self._modifier(corps, {'role': 'rowgroup'})
        for ligne, cellules in tableau.lignes_corps:
            self._modifier(ligne, {'role': 'row'})
            colonne = 0
            for cellule in cellules:
                intitule = intitules[colonne] if colonne < len(intitules) else None
                colonne += cellule.colspan
                if cellule.colspan > 1:
                    # Ligne « aucun élément » qui couvre tout le tableau.
                    self._modifier(cellule, {'role': 'cell'})
                elif intitule in ('', INTITULE_ACTIONS):
                    self._modifier(cellule, {'role': 'cell'}, CLASSE_ACTIONS)
                elif intitule is not None:
                    self._modifier(cellule, {'role': 'cell', 'data-label': intitule})
                else:
                    self._modifier(cellule, {'role': 'cell'})


def etiqueter_tableaux(html):
    """`html` (page ou fragment) dont les tableaux d'au moins 4 colonnes sont
    prêts à être affichés en cartes sur téléphone."""
    if '<table' not in html:
        return html
    analyseur = _Analyseur(html)
    analyseur.feed(html)
    analyseur.close()
    morceaux = []
    fin = len(html)
    # De la fin vers le début, pour que les positions restent valables.
    for position, ancien, nouveau in sorted(analyseur.modifications, reverse=True):
        if html[position:position + len(ancien)] != ancien:
            # Position inattendue : on ne touche à rien plutôt que d'abîmer la page.
            raise ValueError(f"balise introuvable à la position {position}")
        morceaux.append(html[position + len(ancien):fin])
        morceaux.append(nouveau)
        fin = position
    morceaux.append(html[:fin])
    return ''.join(reversed(morceaux))


class TableauxEmpilablesMiddleware:
    """Applique `etiqueter_tableaux` au HTML de chaque réponse. Un échec ne
    doit jamais empêcher l'affichage d'une page : la réponse part alors telle
    quelle (le tableau reste un tableau classique sur téléphone)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            getattr(response, 'streaming', False)
            or not response.get('Content-Type', '').startswith('text/html')
            or b'<table' not in response.content
        ):
            return response
        try:
            html = response.content.decode(response.charset)
            response.content = etiqueter_tableaux(html)
        except Exception:
            logger.exception("Préparation des tableaux pour téléphone impossible sur %s", request.path)
            return response
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response
