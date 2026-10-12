import io, logging, matplotlib, base64, csv, re, pandas as pd
from io import BytesIO
from datetime import date
import matplotlib.pyplot as plt
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
from accueil.models import PreferenceAccessibilite
from accueil.utils import comptes_accessibles
from Projet_veto.listes import ListeTriableMixin
from .models import Animal, AnimalIdentification, Poids, Espece, Robe, Race, Organisme, Proprietaire
from . import formulaire
from .forms import AnimalForm, AnimalIdentificationFormSet, PoidsForm, ProprietaireForm
from .forms import AnimalSearchForm, sans_accents

logger = logging.getLogger(__name__)

# Caractères déclenchant l'exécution d'une formule dans Excel/LibreOffice si le
# fichier CSV/XLSX exporté est ouvert tel quel (CSV/Formula Injection).
_FORMULA_TRIGGER_CHARS = ('=', '+', '-', '@', '\t', '\r')


def _sanitize_spreadsheet_value(value):
    """Neutralise une valeur pouvant être interprétée comme une formule par un tableur."""
    if isinstance(value, str) and value.startswith(_FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value


EMAIL_PROPRIETAIRE_INCONNU = 'inconnu@exemple.invalid'


def _proprietaire_depuis_import(valeur, utilisateur):
    """Retrouve (ou crée) le Proprietaire désigné par la colonne
    « Propriétaire » d'une ligne importée. La valeur est soit un email
    (format historique de l'import), soit un nom complet — c'est ce qu'écrit
    l'export CSV, et ce que l'on saisit spontanément.

    - Email : dédoublonnage par email au sein de tout le foyer partagé de
      `utilisateur` (cf. accueil.utils.comptes_accessibles) — pour ne pas
      recréer silencieusement une fiche déjà présente chez un autre membre du
      foyer —, nouvelle fiche rattachée à `utilisateur` sinon, avec un nom
      dérivé de la partie locale de l'adresse à défaut de mieux (ex.
      « jean.dupont@... » -> « Jean Dupont »), à compléter ensuite via la
      fiche propriétaire.
    - Nom : fiche du foyer portant ce nom complet (sans tenir compte des
      majuscules), nouvelle fiche à ce nom sinon. Le nom n'est jamais rangé
      dans le champ email : une fiche créée ainsi reçoit un email qui lui est
      propre dans le domaine réservé « .invalid » (l'email est obligatoire et
      unique par compte), à corriger ensuite via la fiche propriétaire.
    - Valeur vide : fiche « Inconnu » du foyer.

    Seules les fiches actives sont retrouvées : comme dans le formulaire
    (cf. ProprietaireForm.clean_email), un propriétaire « supprimé » puis
    réimporté donne une fiche neuve, jamais l'ancienne fiche archivée."""
    valeur = (valeur or '').strip()
    comptes = comptes_accessibles(utilisateur)
    if not valeur:
        valeur = EMAIL_PROPRIETAIRE_INCONNU
    try:
        validate_email(valeur)
    except ValidationError:
        for proprietaire in Proprietaire.objects.filter(utilisateur__in=comptes, actif=True).order_by('pk'):
            if proprietaire.nom_complet().lower() == valeur.lower():
                return proprietaire
        base = re.sub(r'[^a-z0-9]+', '.', sans_accents(valeur)).strip('.') or 'inconnu'
        email, numero = f'{base}@exemple.invalid', 1
        while Proprietaire.objects.filter(utilisateur=utilisateur, email__iexact=email).exists():
            numero += 1
            email = f'{base}.{numero}@exemple.invalid'
        return Proprietaire.objects.create(nom=valeur[:100], email=email, utilisateur=utilisateur)

    proprietaire = Proprietaire.objects.filter(
        utilisateur__in=comptes, email__iexact=valeur, actif=True,
    ).order_by('pk').first()
    if proprietaire:
        return proprietaire
    partie_locale = valeur.split('@', 1)[0]
    mots = [mot for mot in partie_locale.replace('_', '.').replace('+', '.').split('.') if mot]
    nom = ' '.join(mot.capitalize() for mot in mots) or valeur
    return Proprietaire.objects.create(nom=nom, email=valeur, utilisateur=utilisateur)


class ErreurImport(Exception):
    """Ligne du fichier importé inexploitable ; le message est affiché tel
    quel à l'utilisateur."""


def _valeur_csv(row, colonne):
    """Cellule d'une ligne importée, en texte ; chaîne vide si la colonne est
    absente du fichier ou la cellule vide."""
    valeur = row.get(colonne)
    return '' if valeur is None or pd.isna(valeur) else str(valeur).strip()


def _identifications_csv(row):
    """Couples (numéro, organisme) d'une ligne importée, chaînes vides pour
    ce qui manque. Deux formats sont lus : les colonnes « Identification » +
    « Organisme » de la notice d'import, et la colonne « Identifications » de
    l'export (« 2502… (LOF); 987654 (SIRE) », cf.
    Animal.identifications_display), pour qu'un fichier exporté puis
    réimporté retrouve ses animaux au lieu de les recréer en double. Dans ce
    second format, un élément sans parenthèses ni chiffre est le nom d'un
    organisme sans numéro."""
    numero = _valeur_csv(row, 'Identification')
    organisme = _valeur_csv(row, 'Organisme')
    if numero or not _valeur_csv(row, 'Identifications'):
        return [(numero, organisme)] if numero or organisme else []
    couples = []
    for element in _valeur_csv(row, 'Identifications').split(';'):
        element = element.strip()
        decoupe = re.match(r'^(.*?)\s*\(([^()]*)\)$', element)
        if decoupe:
            couples.append((decoupe.group(1).strip(), decoupe.group(2).strip()))
        elif element and not re.search(r'\d', element):
            couples.append(('', element))
        elif element:
            couples.append((element, ''))
    return couples


def _il_y_a(jour, annees):
    """Même jour `annees` années plus tôt (le 29 février devient le 28
    quand l'année visée n'est pas bissextile)."""
    try:
        return jour.replace(year=jour.year - annees)
    except ValueError:
        return jour.replace(year=jour.year - annees, day=28)

matplotlib.use('Agg')  # Pour générer des graphiques sans interface graphique

class AnimalDetailView(LoginRequiredMixin, DetailView):
    model = Animal
    template_name = 'animaux/detail.html'
    context_object_name = 'animal'

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        animal = self.object
        context['poids_list'] = animal.poids.all().order_by('date')
        context['age'] = animal.age()
        suivis = animal.suivi_vaccins_traitements.all()
        context['vaccins'] = suivis.filter(vaccin__isnull=False).select_related('vaccin')
        context['traitements'] = suivis.filter(traitement__isnull=False).select_related('traitement')
        # Listes passées par le contexte (et non parcourues depuis `animal`
        # dans le gabarit) : chacune n'est ainsi lue qu'une fois, avec ses
        # relations, au lieu d'une requête par ligne.
        context['consultations'] = animal.consultations.select_related('veterinaire')
        context['factures'] = animal.factures.all()
        context['documents'] = animal.documents.select_related('type_document')

        # Coût de revient (cf. factures.Facture.cout_revient_animal) : mensuel
        # (mois en cours) et annuel (année en cours), même granularité que le
        # tableau de bord de la liste des factures.
        from factures.models import Facture
        aujourdhui = date.today()
        context['cout_revient_mensuel'] = Facture.cout_revient_animal(animal, aujourdhui.year, aujourdhui.month)
        context['cout_revient_annuel'] = Facture.cout_revient_animal(animal, aujourdhui.year)

        return context

class AnimalIdentificationsFormsetMixin:
    """Gère, en plus du AnimalForm, le formset AnimalIdentificationFormSet
    (couples organisme/identification, cf. animaux/form.html) sur les vues de
    création et modification d'un animal : un animal pouvant être enregistré
    auprès de plusieurs organismes, ces couples ne sont plus des champs
    directs d'AnimalForm mais des lignes liées, ajoutées/retirées à la
    demande. Fournit aussi au gabarit le contexte de tout ce que htmx pilote
    dans le formulaire (menus Espèce/Race, fiche de race, ajouts rapides,
    identifications — cf. animaux/formulaire.py)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = context.get('identifications_formset')
        if formset is None:
            formset = AnimalIdentificationFormSet(instance=self.object)
        context.update(formulaire.contexte_formulaire(
            context['form'], formset, self.object, afficher_erreurs=formset.is_bound,
        ))
        return context

    def form_valid(self, form):
        formset = AnimalIdentificationFormSet(self.request.POST, instance=self.object)
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, identifications_formset=formset))
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        formset = AnimalIdentificationFormSet(self.request.POST, instance=self.object)
        return self.render_to_response(self.get_context_data(form=form, identifications_formset=formset))

class AnimalCreateView(LoginRequiredMixin, AnimalIdentificationsFormsetMixin, CreateView):
    model = Animal
    form_class = AnimalForm
    template_name = 'animaux/form.html'
    success_url = reverse_lazy('animaux:animal_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.utilisateur = self.request.user
        return super().form_valid(form)

class AnimalUpdateView(LoginRequiredMixin, AnimalIdentificationsFormsetMixin, UpdateView):
    model = Animal
    form_class = AnimalForm
    template_name = 'animaux/form.html'
    success_url = reverse_lazy('animaux:animal_list')

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class AnimalDeleteView(LoginRequiredMixin, DeleteView):
    model = Animal
    template_name = 'animaux/confirm_delete.html'
    success_url = reverse_lazy('animaux:animal_list')

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))

    def get_context_data(self, **kwargs):
        """Nombres réels de ce que la suppression emporte, pour que la page
        de confirmation dise exactement ce qui sera supprimé."""
        # Import différé : factures dépend d'animaux, pas l'inverse.
        from factures.models import factures_emportees_par
        context = super().get_context_data(**kwargs)
        animal = self.object
        emportees = factures_emportees_par(animal)
        context['suppressions'] = {
            'identifications': animal.identifications.count(),
            'poids': animal.poids.count(),
            'suivis': animal.suivi_vaccins_traitements.count(),
            'consultations': animal.consultations.count(),
            'documents': animal.documents.count(),
            'lignes_facture': emportees['lignes'].count(),
            'factures': emportees['factures_non_ventilees'].count() + emportees['factures_videes'].count(),
        }
        return context

class ProprietaireListView(LoginRequiredMixin, ListeTriableMixin, ListView):
    model = Proprietaire
    template_name = 'animaux/proprietaire_liste.html'
    context_object_name = 'proprietaires'
    champs_recherche = ('nom', 'prenom', 'telephone', 'email', 'ville')
    colonnes_tri = {
        'nom': ('nom', 'prenom'),
        'prenom': ('prenom', 'nom'),
        'telephone': 'telephone',
        'email': 'email',
        'animaux': 'nb_animaux',
    }
    tri_defaut = 'nom'

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            utilisateur__in=comptes_accessibles(self.request.user), actif=True,
        ).annotate(nb_animaux=Count('animaux'))
        return self.filtrer_et_trier(queryset)

class ProprietaireDetailView(LoginRequiredMixin, DetailView):
    model = Proprietaire
    template_name = 'animaux/proprietaire_detail.html'
    context_object_name = 'proprietaire'

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['animaux'] = self.object.animaux.select_related('espece')
        return context

class ProprietaireCreateView(LoginRequiredMixin, CreateView):
    model = Proprietaire
    form_class = ProprietaireForm
    template_name = 'animaux/proprietaire_form.html'
    success_url = reverse_lazy('animaux:proprietaire_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class ProprietaireUpdateView(LoginRequiredMixin, UpdateView):
    model = Proprietaire
    form_class = ProprietaireForm
    template_name = 'animaux/proprietaire_form.html'
    success_url = reverse_lazy('animaux:proprietaire_list')

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class ProprietaireDeleteView(LoginRequiredMixin, DeleteView):
    """« Suppression » douce : la fiche est conservée en base (les animaux
    déjà enregistrés continuent de l'afficher) mais désactivée
    (Proprietaire.actif = False), ce qui la retire des listes, des listes
    déroulantes de sélection et de la sortie PDF de la fiche animal."""
    model = Proprietaire
    template_name = 'animaux/proprietaire_confirm_delete.html'
    success_url = reverse_lazy('animaux:proprietaire_list')

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))

    def form_valid(self, form):
        self.object.actif = False
        self.object.save(update_fields=['actif'])
        return redirect(self.get_success_url())

class PoidsCreateView(LoginRequiredMixin, CreateView):
    model = Poids
    form_class = PoidsForm
    template_name = 'animaux/poids_form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.animal = get_object_or_404(
                Animal, pk=kwargs['animal_id'], utilisateur__in=comptes_accessibles(request.user),
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        # L'animal est posé sur l'instance avant la validation, pour que
        # PoidsForm.clean_date() puisse refuser une deuxième pesée à la même
        # date (sinon : IntegrityError à l'enregistrement).
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = Poids(animal=self.animal)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['animal'] = self.animal
        return context

    def get_success_url(self):
        return reverse_lazy('animaux:animal_detail', kwargs={'pk': self.animal.pk})


class PoidsQuerysetMixin:
    """Pesées des animaux visibles du compte connecté (lui-même, plus les
    autres membres de son foyer partagé le cas échéant)."""
    model = Poids

    def get_queryset(self):
        return super().get_queryset().filter(
            animal__utilisateur__in=comptes_accessibles(self.request.user),
        ).select_related('animal')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['animal'] = self.object.animal
        return context

    def get_success_url(self):
        return reverse_lazy('animaux:animal_detail', kwargs={'pk': self.object.animal_id})


class PoidsUpdateView(LoginRequiredMixin, PoidsQuerysetMixin, UpdateView):
    form_class = PoidsForm
    template_name = 'animaux/poids_form.html'


class PoidsDeleteView(LoginRequiredMixin, PoidsQuerysetMixin, DeleteView):
    template_name = 'animaux/poids_confirm_delete.html'

@login_required
def photo_animal(request, animal_id):
    """Sert la photo de l'animal après vérification du propriétaire — la
    photo n'est jamais exposée via une URL /media/ statique (cf. urls.py),
    pour ne pas contourner cette même vérification."""
    animal = get_object_or_404(Animal, pk=animal_id, utilisateur__in=comptes_accessibles(request.user))
    if not animal.photo:
        raise Http404
    try:
        return FileResponse(animal.photo.open('rb'))
    except FileNotFoundError:
        # Fiche présente en base mais photo absente du disque : 404, pas 500.
        raise Http404

@login_required
def graphique_poids(request, animal_id):
    animal = get_object_or_404(Animal, pk=animal_id, utilisateur__in=comptes_accessibles(request.user))
    poids_list = animal.poids.all().order_by('date')

    # Préparation des données pour le graphique
    dates = [p.date for p in poids_list]
    valeurs = [p.valeur for p in poids_list]

    # Image PNG : elle ne suit pas le CSS du thème, on aligne donc ses couleurs
    # sur le mode sombre du compte (fond = celui des cartes en thème sombre).
    mode_sombre = PreferenceAccessibilite.objects.filter(utilisateur=request.user, mode_sombre=True).exists()
    style = {
        'figure.facecolor': '#212529', 'axes.facecolor': '#212529', 'savefig.facecolor': '#212529',
        'text.color': '#dee2e6', 'axes.labelcolor': '#dee2e6', 'axes.edgecolor': '#adb5bd',
        'xtick.color': '#adb5bd', 'ytick.color': '#adb5bd', 'grid.color': '#495057',
    } if mode_sombre else {}

    # Création du graphique avec Matplotlib
    with plt.rc_context(style):
        plt.figure(figsize=(10, 5))
        plt.plot(dates, valeurs, marker='o', linestyle='-', color='#6cb4e4' if mode_sombre else 'b')
        plt.title(f"Courbe de poids pour {animal.nom}")
        plt.xlabel("Date")
        plt.ylabel("Poids (kg)")
        plt.grid(True)

        # Sauvegarde du graphique dans un buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        plt.close()

    # Encodage en base64 pour affichage dans le template
    image_png = buffer.getvalue()
    buffer.close()
    graphique = base64.b64encode(image_png).decode('utf-8')

    return render(request, 'animaux/graphique_poids.html', {
        'animal': animal,
        'graphique': graphique
    })

@login_required
def generer_pdf_fiche_animal(request, animal_id):
    animal = get_object_or_404(Animal, pk=animal_id, utilisateur__in=comptes_accessibles(request.user))
    poids_list = animal.poids.all().order_by('date')
    vaccins = animal.suivi_vaccins_traitements.filter(vaccin__isnull=False).order_by('-date')
    traitements = animal.suivi_vaccins_traitements.filter(traitement__isnull=False).order_by('-date')
    consultations = animal.consultations.all().order_by('-date')
    factures = animal.factures.all().order_by('-date')

    html = render_to_string('animaux/pdf_fiche_animal.html', {
        'animal': animal,
        'poids_list': poids_list,
        'vaccins': vaccins,
        'traitements': traitements,
        'consultations': consultations,
        'factures': factures,
        'today': date.today(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="fiche_{animal.nom}.pdf"'

    HTML(string=html).write_pdf(response, stylesheets=[CSS(string='@page { size: A4; margin: 1cm; }')])
    return response

class AnimalListView(LoginRequiredMixin, ListeTriableMixin, ListView):
    model = Animal
    template_name = 'animaux/liste.html'
    context_object_name = 'animaux'
    champs_recherche = (
        'nom', 'espece__nom', 'race__nom', 'proprietaire__nom', 'proprietaire__prenom',
        'identifications__identification',
        'identifications__organisme__nom_court', 'identifications__organisme_autre',
    )
    colonnes_tri = {
        'nom': 'nom',
        'espece': 'espece__nom',
        'race': 'race__nom',
        # Âge croissant = du plus jeune au plus vieux, donc date de naissance décroissante.
        'age': '-date_naissance',
        'proprietaire': ('proprietaire__nom', 'proprietaire__prenom'),
    }
    tri_defaut = 'nom'

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            utilisateur__in=comptes_accessibles(self.request.user)
        ).select_related(
            'espece', 'race', 'proprietaire'
        ).prefetch_related('identifications__organisme')
        form = AnimalSearchForm(self.request.GET)

        if form.is_valid():
            data = form.cleaned_data

            if data['nom']:
                queryset = queryset.filter(nom__icontains=data['nom'])

            if data['espece']:
                queryset = queryset.filter(espece=data['espece'])

            if data['race']:
                queryset = queryset.filter(race__nom__icontains=data['race'])

            # Âges en années révolues, comme l'âge affiché (Animal.age()).
            # Les valeurs sont bornées par AnimalSearchForm, l'année calculée
            # reste donc toujours valide.
            if data['min_age'] is not None:
                # Au moins N ans : né au plus tard il y a N ans jour pour jour.
                queryset = queryset.filter(date_naissance__lte=_il_y_a(date.today(), data['min_age']))

            if data['max_age'] is not None:
                # Au plus N ans : n'a pas encore fêté ses N + 1 ans.
                queryset = queryset.filter(date_naissance__gt=_il_y_a(date.today(), data['max_age'] + 1))

            if data['robe']:
                queryset = queryset.filter(robe=data['robe'])

        return self.filtrer_et_trier(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AnimalSearchForm(self.request.GET)

        # Coût de revient annuel (année en cours) affiché en colonne sur la
        # liste globale — pas de détail mensuel ici (cf. AnimalDetailView
        # pour le détail mensuel+annuel sur la fiche d'un animal).
        from factures.models import Facture
        couts = Facture.couts_revient_annuels(self.request.user, date.today().year)
        for animal in context['animaux']:
            animal.cout_revient_annuel = couts.get(animal.pk, 0)

        return context

#
# Préparation des vues pour l'import / export
#

@login_required
def exporter_animaux_csv(request):
    animaux = Animal.objects.filter(
        utilisateur__in=comptes_accessibles(request.user)
    ).select_related('espece', 'race', 'robe', 'proprietaire').prefetch_related('identifications__organisme')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="animaux.csv"'
    # Marque d'ordre des octets : sans elle, Excel lit le fichier en
    # Windows-1252 et affiche « EspÃ¨ce ». Le séparateur reste la virgule,
    # celui que relit l'import (qui ignore cette marque).
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['ID', 'Nom', 'Espèce', 'Race', 'Identifications', 'Date de Naissance', 'Âge', 'Propriétaire', 'Robe'])

    for animal in animaux:
        writer.writerow([
            animal.pk,
            _sanitize_spreadsheet_value(animal.nom),
            animal.espece.nom,
            _sanitize_spreadsheet_value(animal.race.nom),
            _sanitize_spreadsheet_value(animal.identifications_display()),
            animal.date_naissance,
            animal.age(),
            _sanitize_spreadsheet_value(str(animal.proprietaire)),
            animal.robe.nom,
        ])

    return response

@login_required
def exporter_animaux_excel(request):
    animaux = Animal.objects.filter(
        utilisateur__in=comptes_accessibles(request.user)
    ).select_related('espece', 'race', 'robe', 'proprietaire').prefetch_related('identifications__organisme')

    df = pd.DataFrame([
        {
            'id': animal.pk,
            'nom': animal.nom,
            'espece': animal.espece.nom,
            'race': animal.race.nom,
            'identifications': animal.identifications_display(),
            'date_naissance': animal.date_naissance,
            'age': animal.age(),
            'proprietaire': str(animal.proprietaire),
            'robe': animal.robe.nom,
        }
        for animal in animaux
    ], columns=[
        # Colonnes explicites : sans animal, le tableau garde ainsi ses
        # colonnes et l'export produit un classeur réduit à ses en-têtes.
        'id', 'nom', 'espece', 'race', 'identifications', 'date_naissance', 'age', 'proprietaire', 'robe',
    ])

    # Neutralisation de l'injection de formules avant écriture dans le classeur
    for col in ('nom', 'race', 'identifications', 'proprietaire'):
        df[col] = df[col].apply(_sanitize_spreadsheet_value)

    # Réorganisation des colonnes
    df = df[['id', 'nom', 'espece', 'race', 'identifications', 'date_naissance', 'age', 'proprietaire', 'robe']]

    # Renommage des colonnes
    df.columns = ['ID', 'Nom', 'Espèce', 'Race', 'Identifications', 'Date de Naissance', 'Âge', 'Propriétaire', 'Robe']

    # Création du fichier Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Animaux')

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="animaux.xlsx"'
    return response

@login_required
def importer_animaux_csv(request):
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Aucun fichier sélectionné.")
            return redirect('animaux:animal_list')

        # Ligne du fichier en cours de traitement (1 = en-têtes), pour la
        # désigner dans le message d'erreur.
        numero_ligne = None
        try:
            # Lecture du fichier CSV. Tout est lu comme du texte : laissé à
            # lui-même, pandas convertit une colonne de numéros de puce en
            # nombres (zéros de tête perdus, « 250269812345678.0 » dès qu'une
            # cellule de la colonne est vide). La marque d'ordre des octets
            # que pose l'export (pour Excel) est ignorée.
            df = pd.read_csv(csv_file, dtype=str, encoding='utf-8-sig')

            # Vérification des colonnes obligatoires
            # (Identification est optionnelle : elle n'est possible qu'à partir de 2-3 mois)
            required_columns = ['Nom', 'Espèce', 'Race', 'Date de Naissance']
            if not all(col in df.columns for col in required_columns):
                messages.error(request, f"Le fichier doit contenir les colonnes suivantes : {', '.join(required_columns)}")
                return redirect('animaux:animal_list')

            # Récupération/création des espèces, robes et races correspondant au fichier
            espece_autre = Espece.objects.get(code='AUTRE')
            robe_autre = Robe.objects.get(code='AUTRE')
            comptes = comptes_accessibles(request.user)

            # Import des animaux : tout ou rien. Une ligne inexploitable
            # annule l'import entier — sinon les lignes précédentes resteraient
            # enregistrées et seraient créées une seconde fois au réimport du
            # fichier corrigé (pas de dédoublonnage sans identification).
            resultats = []
            with transaction.atomic():
                for numero_ligne, row in enumerate(df.to_dict('records'), start=2):
                    nom = _valeur_csv(row, 'Nom')
                    if not nom:
                        raise ErreurImport("le nom de l'animal est vide")
                    date_naissance = pd.to_datetime(_valeur_csv(row, 'Date de Naissance') or None, errors='coerce')
                    if pd.isna(date_naissance):
                        raise ErreurImport(
                            "la date de naissance est absente ou illisible (format attendu : AAAA-MM-JJ)"
                        )
                    date_naissance = date_naissance.date()

                    espece_obj = Espece.objects.filter(nom__iexact=_valeur_csv(row, 'Espèce')).first() or espece_autre
                    nom_race = _valeur_csv(row, 'Race') or 'Autre'
                    race_obj, _ = Race.objects.get_or_create(
                        espece=espece_obj, nom__iexact=nom_race, defaults={'nom': nom_race}
                    )
                    # Colonnes optionnelles : vides ou absentes du fichier,
                    # elles ne s'appliquent qu'à une création (valeurs par
                    # défaut) et ne modifient jamais un animal déjà connu.
                    robe_valeur = _valeur_csv(row, 'Robe')
                    proprietaire_valeur = _valeur_csv(row, 'Propriétaire')

                    # Organisme d'inscription : reconnu par son nom court parmi les
                    # organismes catalogués pour cette espèce, sinon conservé tel
                    # quel comme saisie libre plutôt que rejeté.
                    identifications = []
                    for numero, organisme_valeur in _identifications_csv(row):
                        organisme_obj = None
                        if organisme_valeur:
                            organisme_obj = Organisme.objects.filter(
                                espece=espece_obj.code, nom_court__iexact=organisme_valeur
                            ).first()
                        identifications.append({
                            'identification': numero or None,
                            'organisme': organisme_obj,
                            'organisme_autre': '' if organisme_obj else organisme_valeur,
                        })
                    numeros = [ident['identification'] for ident in identifications if ident['identification']]

                    # Dédoublonnage par identification, parmi les animaux
                    # visibles du compte connecté (lui-même, plus les autres
                    # membres de son foyer partagé le cas échéant — cf.
                    # accueil.utils.comptes_accessibles) : un import ne doit
                    # jamais mettre à jour la fiche d'un compte hors foyer.
                    # Sans identification, impossible de dédoublonner de
                    # manière fiable : on crée systématiquement un nouvel animal.
                    animal_identification = AnimalIdentification.objects.filter(
                        identification__in=numeros, animal__utilisateur__in=comptes,
                    ).select_related('animal').first() if numeros else None

                    if animal_identification:
                        # Animal déjà connu (retrouvé par son identification) : on
                        # applique quand même les valeurs de la ligne, pour que la
                        # ré-importation serve bien à le mettre à jour (cf. message
                        # "déjà existant (mis à jour)" plus bas), pas seulement à le
                        # dédoublonner sans effet. Il reste rattaché à son compte
                        # d'origine, et garde sa robe et son propriétaire si le
                        # fichier n'en dit rien.
                        animal = animal_identification.animal
                        animal.nom = nom
                        animal.espece = espece_obj
                        animal.race = race_obj
                        animal.date_naissance = date_naissance
                        if robe_valeur:
                            animal.robe = Robe.objects.filter(nom__iexact=robe_valeur).first() or robe_autre
                        if proprietaire_valeur and proprietaire_valeur.lower() not in (
                            animal.proprietaire.nom_complet().lower(), animal.proprietaire.email.lower(),
                        ):
                            animal.proprietaire = _proprietaire_depuis_import(proprietaire_valeur, request.user)
                        animal.save()
                        created = False
                    else:
                        if AnimalIdentification.objects.filter(identification__in=numeros).exists():
                            raise ErreurImport(
                                "ce numéro d'identification est déjà utilisé et ne peut pas être repris"
                            )
                        animal = Animal.objects.create(
                            nom=nom, espece=espece_obj, race=race_obj, date_naissance=date_naissance,
                            robe=Robe.objects.filter(nom__iexact=robe_valeur).first() or robe_autre,
                            proprietaire=_proprietaire_depuis_import(proprietaire_valeur, request.user),
                            utilisateur=request.user,
                        )
                        for ident in identifications:
                            AnimalIdentification.objects.create(animal=animal, **ident)
                        created = True
                    resultats.append((created, animal.nom))

            # Messages émis une fois la transaction validée seulement : ils
            # n'annoncent ainsi jamais un import qui a été annulé.
            for created, nom in resultats:
                if created:
                    messages.success(request, f"Animal {nom} importé avec succès.")
                else:
                    messages.warning(request, f"Animal {nom} déjà existant (mis à jour).")

            return redirect('animaux:animal_list')

        except Exception as erreur:
            if isinstance(erreur, ErreurImport):
                logger.warning("Import CSV des animaux refusé, ligne %s : %s", numero_ligne, erreur)
            else:
                logger.exception("Erreur lors de l'import CSV des animaux")
            if numero_ligne is None:
                messages.error(request, "Erreur lors de l'import : vérifiez le format du fichier et réessayez.")
            else:
                detail = f"{erreur}" if isinstance(erreur, ErreurImport) else "vérifiez son contenu"
                messages.error(
                    request,
                    f"Erreur à la ligne {numero_ligne} du fichier ({detail}) : aucun animal n'a été importé. "
                    "Corrigez cette ligne et réimportez le fichier entier.",
                )
            return redirect('animaux:animal_list')

    return render(request, 'animaux/import.html')
