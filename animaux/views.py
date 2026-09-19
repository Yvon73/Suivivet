import io, logging, matplotlib, base64, csv, pandas as pd
from io import BytesIO
from datetime import date
import matplotlib.pyplot as plt
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from weasyprint import HTML, CSS
from .models import Animal, AnimalIdentification, Poids, Espece, Robe, Race, Organisme, Proprietaire
from .forms import (
    AnimalForm, AnimalIdentificationFormSet, PoidsForm, RaceQuickAddForm, OrganismeQuickAddForm,
    RobeQuickAddForm, EspeceQuickAddForm, ProprietaireForm,
)
from .forms import AnimalSearchForm

logger = logging.getLogger(__name__)

# Caractères déclenchant l'exécution d'une formule dans Excel/LibreOffice si le
# fichier CSV/XLSX exporté est ouvert tel quel (CSV/Formula Injection).
_FORMULA_TRIGGER_CHARS = ('=', '+', '-', '@', '\t', '\r')


def _sanitize_spreadsheet_value(value):
    """Neutralise une valeur pouvant être interprétée comme une formule par un tableur."""
    if isinstance(value, str) and value.startswith(_FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value


def _proprietaire_depuis_email(email, utilisateur):
    """Retrouve (ou crée) le Proprietaire du compte `utilisateur` correspondant
    à l'email d'une ligne importée (colonne « Propriétaire » du CSV,
    historiquement un simple email) : dédoublonnage par email au sein de ce
    compte uniquement, nom dérivé de la partie locale de l'adresse à défaut
    de mieux (ex. « jean.dupont@... » -> « Jean Dupont »), à compléter ensuite
    via la fiche propriétaire."""
    email = (email or '').strip()
    if not email or email.lower() == 'nan':
        email = 'inconnu@exemple.invalid'
    proprietaire = Proprietaire.objects.filter(utilisateur=utilisateur, email__iexact=email).first()
    if proprietaire:
        return proprietaire
    partie_locale = email.split('@', 1)[0]
    mots = [mot for mot in partie_locale.replace('_', '.').replace('+', '.').split('.') if mot]
    nom = ' '.join(mot.capitalize() for mot in mots) or email
    return Proprietaire.objects.create(nom=nom, email=email, utilisateur=utilisateur)

matplotlib.use('Agg')  # Pour générer des graphiques sans interface graphique

class AnimalDetailView(LoginRequiredMixin, DetailView):
    model = Animal
    template_name = 'animaux/detail.html'
    context_object_name = 'animal'

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        animal = self.get_object()
        context['poids_list'] = animal.poids.all().order_by('date')
        context['age'] = animal.age()
        suivis = animal.suivi_vaccins_traitements.all()
        context['vaccins'] = suivis.filter(vaccin__isnull=False)
        context['traitements'] = suivis.filter(traitement__isnull=False)

        # Coût de revient (cf. factures.Facture.cout_revient_animal) : mensuel
        # (mois en cours) et annuel (année en cours), même granularité que le
        # tableau de bord de la liste des factures.
        from factures.models import Facture
        aujourdhui = date.today()
        context['cout_revient_mensuel'] = Facture.cout_revient_animal(animal, aujourdhui.year, aujourdhui.month)
        context['cout_revient_annuel'] = Facture.cout_revient_animal(animal, aujourdhui.year)

        return context

class AnimalFormContextMixin:
    """Contexte partagé par les vues de création/modification d'animal : liste
    des espèces et niveaux de dangerosité pour la modale « Ajouter une race »,
    fiche descriptive de chaque race (races_info) pour le panneau d'aperçu JS
    affiché quand une race est sélectionnée, et espèces d'organisme pour la
    modale « Ajouter un organisme » (cf. form.html)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['especes'] = Espece.objects.all()
        context['niveaux_dangerosite'] = Race.NiveauDangerosite.choices
        context['races_info'] = {
            race.pk: race.donnees_json() for race in Race.objects.all()
        }
        context['organisme_especes'] = Organisme.Espece.choices
        return context

class AnimalIdentificationsFormsetMixin:
    """Gère, en plus du AnimalForm, le formset AnimalIdentificationFormSet
    (couples organisme/identification, cf. animaux/form.html) sur les vues de
    création et modification d'un animal : un animal pouvant être enregistré
    auprès de plusieurs organismes, ces couples ne sont plus des champs
    directs d'AnimalForm mais des lignes liées, ajoutées/retirées à la volée
    par le bouton « + » du formulaire."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'identifications_formset' not in context:
            context['identifications_formset'] = AnimalIdentificationFormSet(instance=self.object)
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

class AnimalCreateView(LoginRequiredMixin, AnimalFormContextMixin, AnimalIdentificationsFormsetMixin, CreateView):
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

class AnimalUpdateView(LoginRequiredMixin, AnimalFormContextMixin, AnimalIdentificationsFormsetMixin, UpdateView):
    model = Animal
    form_class = AnimalForm
    template_name = 'animaux/form.html'
    success_url = reverse_lazy('animaux:animal_list')

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class AnimalDeleteView(LoginRequiredMixin, DeleteView):
    model = Animal
    template_name = 'animaux/confirm_delete.html'
    success_url = reverse_lazy('animaux:animal_list')

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur=self.request.user)

@login_required
@require_POST
def ajouter_espece_ajax(request):
    """Crée une nouvelle espèce (et éventuellement sa première race) depuis
    la modale du formulaire animal, et les renvoie en JSON pour les insérer
    directement dans les menus déroulants « Espèce » et « Race » côté
    client (remplace l'ancien choix « Autre » du menu déroulant)."""
    form = EspeceQuickAddForm(request.POST)
    if form.is_valid():
        espece, race = form.save()
        return JsonResponse({
            'success': True,
            'espece': {'id': espece.pk, 'nom': espece.nom},
            'race': {'espece_nom': espece.nom, **race.donnees_json()},
        })
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

@login_required
@require_POST
def ajouter_race_ajax(request):
    """Crée une nouvelle race depuis la modale du formulaire animal, sans jamais
    toucher aux données déjà en base, et la renvoie en JSON pour l'insérer
    directement dans le menu déroulant côté client."""
    form = RaceQuickAddForm(request.POST)
    if form.is_valid():
        race = form.save()
        return JsonResponse({
            'success': True,
            'espece_nom': race.espece.nom,
            **race.donnees_json(),
        })
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

@login_required
@require_POST
def ajouter_organisme_ajax(request):
    """Crée un nouvel organisme depuis la modale du formulaire animal, et le
    renvoie en JSON pour l'insérer directement dans le menu déroulant côté
    client (même principe que ajouter_race_ajax)."""
    form = OrganismeQuickAddForm(request.POST)
    if form.is_valid():
        organisme = form.save()
        return JsonResponse({
            'success': True,
            'id': organisme.pk,
            'nom_court': organisme.nom_court,
            'espece': organisme.espece,
            'espece_libelle': organisme.get_espece_display(),
        })
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

@login_required
@require_POST
def ajouter_robe_ajax(request):
    """Crée une nouvelle robe depuis la modale du formulaire animal, et la
    renvoie en JSON pour l'insérer directement dans le menu déroulant côté
    client (même principe que ajouter_race_ajax)."""
    form = RobeQuickAddForm(request.POST)
    if form.is_valid():
        robe = form.save()
        return JsonResponse({'success': True, 'id': robe.pk, 'nom': robe.nom})
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

@login_required
@require_POST
def ajouter_proprietaire_ajax(request):
    """Crée un nouveau propriétaire depuis la modale du formulaire animal, et
    le renvoie en JSON pour l'insérer directement dans le menu déroulant côté
    client (même principe que ajouter_organisme_ajax)."""
    form = ProprietaireForm(request.POST, user=request.user)
    if form.is_valid():
        proprietaire = form.save()
        return JsonResponse({'success': True, 'id': proprietaire.pk, 'nom': str(proprietaire)})
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

class ProprietaireListView(LoginRequiredMixin, ListView):
    model = Proprietaire
    template_name = 'animaux/proprietaire_liste.html'
    context_object_name = 'proprietaires'
    ordering = ['nom', 'prenom']

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur=self.request.user, actif=True)

class ProprietaireDetailView(LoginRequiredMixin, DetailView):
    model = Proprietaire
    template_name = 'animaux/proprietaire_detail.html'
    context_object_name = 'proprietaire'

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur=self.request.user)

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
        return super().get_queryset().filter(utilisateur=self.request.user)

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
        return super().get_queryset().filter(utilisateur=self.request.user)

    def form_valid(self, form):
        self.object.actif = False
        self.object.save(update_fields=['actif'])
        return redirect(self.get_success_url())

class PoidsCreateView(LoginRequiredMixin, CreateView):
    model = Poids
    form_class = PoidsForm
    template_name = 'animaux/poids_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['animal'] = get_object_or_404(Animal, pk=self.kwargs['animal_id'], utilisateur=self.request.user)
        return context

    def form_valid(self, form):
        form.instance.animal = get_object_or_404(Animal, pk=self.kwargs['animal_id'], utilisateur=self.request.user)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('animaux:animal_detail', kwargs={'pk': self.kwargs['animal_id']})

@login_required
def photo_animal(request, animal_id):
    """Sert la photo de l'animal après vérification du propriétaire — la
    photo n'est jamais exposée via une URL /media/ statique (cf. urls.py),
    pour ne pas contourner cette même vérification."""
    animal = get_object_or_404(Animal, pk=animal_id, utilisateur=request.user)
    if not animal.photo:
        raise Http404
    return FileResponse(animal.photo.open('rb'))

@login_required
def graphique_poids(request, animal_id):
    animal = get_object_or_404(Animal, pk=animal_id, utilisateur=request.user)
    poids_list = animal.poids.all().order_by('date')

    # Préparation des données pour le graphique
    dates = [p.date for p in poids_list]
    valeurs = [p.valeur for p in poids_list]

    # Création du graphique avec Matplotlib
    plt.figure(figsize=(10, 5))
    plt.plot(dates, valeurs, marker='o', linestyle='-', color='b')
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
    animal = get_object_or_404(Animal, pk=animal_id, utilisateur=request.user)
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

class AnimalListView(LoginRequiredMixin, ListView):
    model = Animal
    template_name = 'animaux/liste.html'
    context_object_name = 'animaux'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().filter(utilisateur=self.request.user).select_related(
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

            if data['min_age'] is not None:
                today = date.today()
                min_birth_date = date(today.year - data['min_age'] - 1, today.month, today.day)
                queryset = queryset.filter(date_naissance__lte=min_birth_date)

            if data['max_age'] is not None:
                today = date.today()
                max_birth_date = date(today.year - data['max_age'], today.month, today.day)
                queryset = queryset.filter(date_naissance__gte=max_birth_date)

            if data['robe']:
                queryset = queryset.filter(robe=data['robe'])

        return queryset.order_by('nom')

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
    animaux = Animal.objects.filter(utilisateur=request.user).select_related('espece', 'race', 'robe', 'proprietaire').prefetch_related('identifications__organisme')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="animaux.csv"'

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
    animaux = Animal.objects.filter(utilisateur=request.user).select_related('espece', 'race', 'robe', 'proprietaire').prefetch_related('identifications__organisme')

    df = pd.DataFrame([
        {
            'id': animal.pk,
            'nom': animal.nom,
            'espece': animal.espece.nom,
            'race': animal.race.nom,
            'identifications': animal.identifications_display(),
            'date_naissance': animal.date_naissance,
            'proprietaire': str(animal.proprietaire),
            'robe': animal.robe.nom,
        }
        for animal in animaux
    ])

    # Calcul de l'âge
    df['age'] = df['date_naissance'].apply(
        lambda x: date.today().year - x.year - ((date.today().month, date.today().day) < (x.month, x.day))
    )

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

        try:
            # Lecture du fichier CSV
            df = pd.read_csv(csv_file)

            # Vérification des colonnes obligatoires
            # (Identification est optionnelle : elle n'est possible qu'à partir de 2-3 mois)
            required_columns = ['Nom', 'Espèce', 'Race', 'Date de Naissance']
            if not all(col in df.columns for col in required_columns):
                messages.error(request, f"Le fichier doit contenir les colonnes suivantes : {', '.join(required_columns)}")
                return redirect('animaux:animal_list')

            # Récupération/création des espèces, robes et races correspondant au fichier
            espece_autre = Espece.objects.get(code='AUTRE')
            robe_autre = Robe.objects.get(code='AUTRE')

            # Import des animaux
            for _, row in df.iterrows():
                espece_obj = Espece.objects.filter(nom__iexact=str(row['Espèce']).strip()).first() or espece_autre
                robe_obj = Robe.objects.filter(nom__iexact=str(row.get('Robe', '')).strip()).first() or robe_autre
                nom_race = str(row['Race']).strip() or 'Autre'
                race_obj, _ = Race.objects.get_or_create(
                    espece=espece_obj, nom__iexact=nom_race, defaults={'nom': nom_race}
                )

                identification = row.get('Identification')
                if pd.isna(identification) or str(identification).strip() == '':
                    identification = None
                else:
                    identification = str(identification).strip()

                # Organisme d'inscription : reconnu par son nom court parmi les
                # organismes catalogués pour cette espèce, sinon conservé tel
                # quel comme saisie libre plutôt que rejeté.
                organisme_obj = None
                organisme_autre = ''
                organisme_valeur = str(row.get('Organisme', '')).strip()
                if organisme_valeur and organisme_valeur.lower() != 'nan':
                    organisme_obj = Organisme.objects.filter(
                        espece=espece_obj.code, nom_court__iexact=organisme_valeur
                    ).first()
                    if not organisme_obj:
                        organisme_autre = organisme_valeur

                defaults = {
                    'nom': row['Nom'],
                    'race': race_obj,
                    'espece': espece_obj,
                    'date_naissance': pd.to_datetime(row['Date de Naissance']).date(),
                    'proprietaire': _proprietaire_depuis_email(str(row.get('Propriétaire', '')), request.user),
                    'robe': robe_obj,
                    'utilisateur': request.user,
                }

                if identification:
                    # Dédoublonnage par identification, parmi les animaux du
                    # compte connecté uniquement (même si l'identification en
                    # tant que numéro de puce est globalement unique, un
                    # import ne doit jamais mettre à jour la fiche d'un autre
                    # compte).
                    animal_identification = AnimalIdentification.objects.filter(
                        identification=identification, animal__utilisateur=request.user,
                    ).select_related('animal').first()
                    if animal_identification:
                        # Animal déjà connu (retrouvé par son identification) : on
                        # applique quand même les valeurs de la ligne, pour que la
                        # ré-importation serve bien à le mettre à jour (cf. message
                        # "déjà existant (mis à jour)" plus bas), pas seulement à le
                        # dédoublonner sans effet.
                        animal = animal_identification.animal
                        for champ, valeur in defaults.items():
                            setattr(animal, champ, valeur)
                        animal.save()
                        created = False
                    else:
                        animal = Animal.objects.create(**defaults)
                        AnimalIdentification.objects.create(
                            animal=animal, organisme=organisme_obj,
                            organisme_autre=organisme_autre, identification=identification,
                        )
                        created = True
                else:
                    # Pas d'identification : impossible de dédoublonner de manière fiable,
                    # on crée systématiquement un nouvel animal.
                    animal = Animal.objects.create(**defaults)
                    if organisme_obj or organisme_autre:
                        AnimalIdentification.objects.create(
                            animal=animal, organisme=organisme_obj, organisme_autre=organisme_autre,
                        )
                    created = True

                if created:
                    messages.success(request, f"Animal {animal.nom} importé avec succès.")
                else:
                    messages.warning(request, f"Animal {animal.nom} déjà existant (mis à jour).")

            return redirect('animaux:animal_list')

        except Exception:
            logger.exception("Erreur lors de l'import CSV des animaux")
            messages.error(request, "Erreur lors de l'import : vérifiez le format du fichier et réessayez.")
            return redirect('animaux:animal_list')

    return render(request, 'animaux/import.html')
