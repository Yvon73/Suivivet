from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from animaux.models import Animal
from vaccins.models import SuiviVaccinTraitement, Vaccin
from .models import Consultation, Veterinaire
from .forms import ConsultationForm, VeterinaireForm


@login_required
@require_POST
def ajouter_veterinaire_ajax(request):
    """Crée un nouveau vétérinaire depuis la modale du formulaire consultation,
    et le renvoie en JSON pour l'insérer directement dans le menu déroulant
    côté client (même principe que les modales de l'app animaux)."""
    form = VeterinaireForm(request.POST)
    if form.is_valid():
        veterinaire = form.save()
        return JsonResponse({'success': True, 'id': veterinaire.pk, 'nom': str(veterinaire)})
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

class VeterinaireListView(LoginRequiredMixin, ListView):
    model = Veterinaire
    template_name = 'consultations/veterinaire_liste.html'
    context_object_name = 'veterinaires'
    ordering = ['nom', 'prenom']

    def get_queryset(self):
        return super().get_queryset().filter(actif=True)

class VeterinaireDetailView(LoginRequiredMixin, DetailView):
    model = Veterinaire
    template_name = 'consultations/veterinaire_detail.html'
    context_object_name = 'veterinaire'

class VeterinaireCreateView(LoginRequiredMixin, CreateView):
    model = Veterinaire
    form_class = VeterinaireForm
    template_name = 'consultations/veterinaire_form.html'
    success_url = reverse_lazy('consultations:veterinaire_list')

class VeterinaireUpdateView(LoginRequiredMixin, UpdateView):
    model = Veterinaire
    form_class = VeterinaireForm
    template_name = 'consultations/veterinaire_form.html'
    success_url = reverse_lazy('consultations:veterinaire_list')

class VeterinaireDeleteView(LoginRequiredMixin, DeleteView):
    """« Suppression » douce : la fiche est conservée en base (les
    consultations déjà enregistrées continuent de l'afficher) mais désactivée
    (Veterinaire.actif = False), ce qui la retire des listes, des listes
    déroulantes de sélection et de la sortie PDF de la fiche animal."""
    model = Veterinaire
    template_name = 'consultations/veterinaire_confirm_delete.html'
    success_url = reverse_lazy('consultations:veterinaire_list')

    def form_valid(self, form):
        self.object.actif = False
        self.object.save(update_fields=['actif'])
        return redirect(self.get_success_url())

class ConsultationListView(LoginRequiredMixin, ListView):
    model = Consultation
    template_name = 'consultations/liste.html'
    context_object_name = 'consultations'
    ordering = ['-date']

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            animal__utilisateur=self.request.user
        ).select_related('animal', 'veterinaire')
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)
        return queryset

class ConsultationDetailView(LoginRequiredMixin, DetailView):
    model = Consultation
    template_name = 'consultations/detail.html'
    context_object_name = 'consultation'

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur=self.request.user)

class ConsultationCreateView(LoginRequiredMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'

    def get_initial(self):
        initial = super().get_initial()
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            initial['animal'] = get_object_or_404(Animal, pk=animal_id, utilisateur=self.request.user)
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy('animaux:animal_detail', kwargs={'pk': self.object.animal.pk})

class ConsultationUpdateView(LoginRequiredMixin, UpdateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'
    success_url = reverse_lazy('consultations:consultation_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class ConsultationDeleteView(LoginRequiredMixin, DeleteView):
    model = Consultation
    template_name = 'consultations/confirm_delete.html'
    success_url = reverse_lazy('consultations:consultation_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur=self.request.user)

class CalendrierView(LoginRequiredMixin, TemplateView):
    template_name = 'consultations/calendrier.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['animaux'] = Animal.objects.filter(utilisateur=self.request.user)
        context['vaccins_reference'] = Vaccin.objects.all()
        context['prochains_rappels_vaccins'] = (
            SuiviVaccinTraitement.objects
            .filter(
                animal__utilisateur=self.request.user,
                vaccin__isnull=False, date_prochaine_dose__isnull=False,
            )
            .select_related('animal', 'vaccin')
            .order_by('date_prochaine_dose')
        )
        return context

@login_required
def get_consultations_json(request):
    consultations = Consultation.objects.filter(
        animal__utilisateur=request.user,
        date__gte=timezone.now()
    ).select_related('animal')

    events = []
    for consultation in consultations:
        events.append({
            'id': consultation.pk,
            'title': f"{consultation.animal.nom} - {consultation.motif}",
            'start': consultation.date.isoformat(),
            'url': reverse('consultations:consultation_detail', args=[consultation.pk]),
            # Couleur pilotée en CSS (classes .fc-event-*, cf. static/css/style.css)
            # plutôt qu'en dur ici, pour rester compatible avec la palette
            # adaptée daltonisme du panneau accessibilité.
            'classNames': ['fc-event-consultation'],
        })

    # Ajouter les rappels (consultations dans 2 jours)
    rappels = Consultation.objects.filter(
        animal__utilisateur=request.user,
        date__gte=timezone.now(),
        date__lte=timezone.now() + timezone.timedelta(days=2)
    ).select_related('animal')

    for rappel in rappels:
        events.append({
            'id': f"rappel_{rappel.pk}",
            'title': f"⚠️ Rappel: {rappel.animal.nom} - {rappel.motif}",
            'start': (rappel.date - timezone.timedelta(days=2)).isoformat(),
            'url': reverse('consultations:consultation_detail', args=[rappel.pk]),
            'classNames': ['fc-event-rappel-consultation'],
        })

    # Ajouter les rappels de vaccins à venir (date de la prochaine dose)
    rappels_vaccins = SuiviVaccinTraitement.objects.filter(
        animal__utilisateur=request.user,
        vaccin__isnull=False,
        date_prochaine_dose__isnull=False,
    ).select_related('animal', 'vaccin')

    for suivi in rappels_vaccins:
        events.append({
            'id': f"vaccin_{suivi.pk}",
            'title': f"💉 Rappel vaccin : {suivi.animal.nom} - {suivi.vaccin.nom}",
            'start': suivi.date_prochaine_dose.isoformat(),
            'url': reverse('animaux:animal_detail', args=[suivi.animal.pk]),
            'classNames': ['fc-event-rappel-vaccin'],
        })

    return JsonResponse(events, safe=False)
