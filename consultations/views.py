from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from accueil.utils import comptes_accessibles, filtre_catalogue
from Projet_veto.listes import ListeTriableMixin, date_texte
from Projet_veto import ajout_rapide
from animaux.models import Animal
from vaccins.models import SuiviVaccinTraitement, Vaccin
from . import calendrier
from .models import Consultation, Veterinaire
from .forms import ConsultationForm, VeterinaireForm


PREFIXE_AJOUT_VETERINAIRE = 'nouveau_veterinaire'


def _ajout_veterinaire(form, form_ajout=None, ouvert=False):
    """Ajout rapide d'un vétérinaire à côté du menu « Vétérinaire » du
    formulaire consultation `form` (cf. Projet_veto/ajout_rapide.py)."""
    return ajout_rapide.contexte(
        nom='veterinaire', titre='Ajouter un vétérinaire absent de la liste',
        url=reverse('consultations:veterinaire_ajout_rapide'),
        form=form_ajout or VeterinaireForm(prefix=PREFIXE_AJOUT_VETERINAIRE),
        champ=form['veterinaire'], ouvert=ouvert,
    )


@login_required
@require_POST
def ajouter_veterinaire_rapide(request):
    """Crée un vétérinaire depuis le panneau « + » du formulaire consultation
    et renvoie le panneau redessiné, plus le menu « Vétérinaire » où il est
    sélectionné (htmx, cf. Projet_veto/ajout_rapide.py)."""
    form_ajout = VeterinaireForm(request.POST, prefix=PREFIXE_AJOUT_VETERINAIRE, user=request.user)
    if not form_ajout.is_valid():
        form = ConsultationForm(user=request.user)
        return ajout_rapide.reponse(request, _ajout_veterinaire(form, form_ajout, ouvert=True), succes=False)
    veterinaire = form_ajout.save()
    form = ConsultationForm(initial={'veterinaire': veterinaire.pk}, user=request.user)
    return ajout_rapide.reponse(request, _ajout_veterinaire(form), succes=True)


class AvertissementRappelMixin:
    """Prévient l'utilisateur quand la consultation est bien enregistrée mais
    que son rappel par email n'a pas pu être programmé (courtier Celery
    injoignable, cf. Consultation.save())."""

    def form_valid(self, form):
        response = super().form_valid(form)
        if getattr(self.object, 'rappel_non_planifie', False):
            messages.warning(
                self.request,
                "La consultation est enregistrée, mais le rappel par email n'a pas pu être programmé "
                "(service de rappels indisponible). Inutile de la saisir à nouveau.",
            )
        return response


class AjoutVeterinaireMixin:
    """Fournit au gabarit du formulaire consultation le contexte de l'ajout
    rapide d'un vétérinaire."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ajout_veterinaire'] = _ajout_veterinaire(context['form'])
        return context


class VeterinaireListView(LoginRequiredMixin, ListeTriableMixin, ListView):
    model = Veterinaire
    template_name = 'consultations/veterinaire_liste.html'
    context_object_name = 'veterinaires'
    champs_recherche = ('nom', 'prenom', 'telephone', 'email', 'adresse')
    colonnes_tri = {
        'nom': ('nom', 'prenom'),
        'prenom': ('prenom', 'nom'),
        'telephone': 'telephone',
        'email': 'email',
        'consultations': 'nb_consultations',
    }
    tri_defaut = 'nom'

    def get_queryset(self):
        # Fiches du compte et de son foyer ; seules les consultations des
        # animaux accessibles sont comptées.
        queryset = super().get_queryset().filter(
            filtre_catalogue(self.request.user), actif=True,
        ).annotate(nb_consultations=Count(
            'consultations',
            filter=Q(consultations__animal__utilisateur__in=comptes_accessibles(self.request.user)),
        ))
        return self.filtrer_et_trier(queryset)

class VeterinaireDetailView(LoginRequiredMixin, DetailView):
    model = Veterinaire
    template_name = 'consultations/veterinaire_detail.html'
    context_object_name = 'veterinaire'

    def get_queryset(self):
        # Fiches du compte et de son foyer, plus celles que référence encore
        # une de ses consultations (fiche d'un ancien membre du foyer, par
        # exemple : la fiche animal y renvoie, elle reste consultable).
        comptes = comptes_accessibles(self.request.user)
        return super().get_queryset().filter(
            Q(utilisateur__in=comptes)
            | Q(pk__in=Consultation.objects.filter(animal__utilisateur__in=comptes).values('veterinaire'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Seules les consultations des animaux accessibles à l'utilisateur y
        # figurent (jamais veterinaire.consultations.all).
        context['modifiable'] = Veterinaire.objects.filter(
            filtre_catalogue(self.request.user), pk=self.object.pk,
        ).exists()
        context['consultations'] = self.object.consultations.filter(
            animal__utilisateur__in=comptes_accessibles(self.request.user)
        ).select_related('animal')
        return context

class VeterinaireCreateView(LoginRequiredMixin, CreateView):
    model = Veterinaire
    form_class = VeterinaireForm
    template_name = 'consultations/veterinaire_form.html'
    success_url = reverse_lazy('consultations:veterinaire_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class VeterinaireUpdateView(LoginRequiredMixin, UpdateView):
    model = Veterinaire
    form_class = VeterinaireForm
    template_name = 'consultations/veterinaire_form.html'
    success_url = reverse_lazy('consultations:veterinaire_list')

    def get_queryset(self):
        return super().get_queryset().filter(filtre_catalogue(self.request.user))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class VeterinaireDeleteView(LoginRequiredMixin, DeleteView):
    """« Suppression » douce : la fiche est conservée en base (les
    consultations déjà enregistrées continuent de l'afficher) mais désactivée
    (Veterinaire.actif = False), ce qui la retire des listes, des listes
    déroulantes de sélection et de la sortie PDF de la fiche animal."""
    model = Veterinaire
    template_name = 'consultations/veterinaire_confirm_delete.html'
    success_url = reverse_lazy('consultations:veterinaire_list')

    def get_queryset(self):
        return super().get_queryset().filter(filtre_catalogue(self.request.user))

    def form_valid(self, form):
        self.object.actif = False
        self.object.save(update_fields=['actif'])
        return redirect(self.get_success_url())

class ConsultationListView(LoginRequiredMixin, ListeTriableMixin, ListView):
    model = Consultation
    template_name = 'consultations/liste.html'
    context_object_name = 'consultations'
    # `date_txt` : annotation de get_queryset() (date et heure telles qu'affichées).
    champs_recherche = ('animal__nom', 'motif', 'veterinaire__nom', 'veterinaire__prenom', 'date_txt')
    colonnes_tri = {
        'animal': 'animal__nom',
        'date': 'date',
        'motif': 'motif',
        'veterinaire': ('veterinaire__nom', 'veterinaire__prenom'),
    }
    tri_defaut = '-date'

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            animal__utilisateur__in=comptes_accessibles(self.request.user)
        ).select_related('animal', 'veterinaire')
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)
        queryset = queryset.annotate(date_txt=date_texte('date', heure=True))
        return self.filtrer_et_trier(queryset)

class ConsultationDetailView(LoginRequiredMixin, DetailView):
    model = Consultation
    template_name = 'consultations/detail.html'
    context_object_name = 'consultation'

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur__in=comptes_accessibles(self.request.user))

class ConsultationCreateView(LoginRequiredMixin, AjoutVeterinaireMixin, AvertissementRappelMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'

    def get_initial(self):
        initial = super().get_initial()
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            initial['animal'] = get_object_or_404(
                Animal, pk=animal_id, utilisateur__in=comptes_accessibles(self.request.user)
            )
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy('animaux:animal_detail', kwargs={'pk': self.object.animal.pk})

class ConsultationUpdateView(LoginRequiredMixin, AjoutVeterinaireMixin, AvertissementRappelMixin, UpdateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'
    success_url = reverse_lazy('consultations:consultation_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur__in=comptes_accessibles(self.request.user))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class ConsultationDeleteView(LoginRequiredMixin, DeleteView):
    model = Consultation
    template_name = 'consultations/confirm_delete.html'
    success_url = reverse_lazy('consultations:consultation_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur__in=comptes_accessibles(self.request.user))

class CalendrierView(LoginRequiredMixin, TemplateView):
    template_name = 'consultations/calendrier.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['animaux'] = Animal.objects.filter(utilisateur__in=comptes_accessibles(self.request.user))
        context['vaccins_reference'] = Vaccin.objects.filter(filtre_catalogue(self.request.user, reference=True))
        context['prochains_rappels_vaccins'] = (
            SuiviVaccinTraitement.objects
            .filter(
                animal__utilisateur__in=comptes_accessibles(self.request.user),
                vaccin__isnull=False, date_prochaine_dose__isnull=False,
            )
            .select_related('animal', 'vaccin')
            .order_by('date_prochaine_dose')
        )
        context.update(calendrier.contexte(self.request))
        return context
