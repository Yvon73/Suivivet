from django.shortcuts import get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_POST
from animaux.models import Animal
from .models import SuiviVaccinTraitement, Vaccin, Traitement
from .forms import SuiviVaccinTraitementForm, VaccinForm, TraitementForm


@login_required
@require_POST
def ajouter_vaccin_ajax(request):
    """Crée un nouveau vaccin depuis la modale du formulaire de suivi, et le
    renvoie en JSON pour l'insérer directement dans la liste « Vaccin(s) »
    côté client (même principe que les modales de l'app animaux)."""
    form = VaccinForm(request.POST)
    if form.is_valid():
        vaccin = form.save()
        return JsonResponse({'success': True, 'id': vaccin.pk, 'nom': vaccin.nom})
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)


@login_required
@require_POST
def ajouter_traitement_ajax(request):
    """Crée un nouveau traitement depuis la modale du formulaire de suivi, et
    le renvoie en JSON pour l'insérer directement dans la liste « Traitement »
    côté client."""
    form = TraitementForm(request.POST)
    if form.is_valid():
        traitement = form.save()
        return JsonResponse({
            'success': True,
            'id': traitement.pk,
            'nom': traitement.nom,
            'classe': traitement.classe,
            'classe_libelle': traitement.get_classe_display(),
        })
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)


def _enregistrer_suivi(form, instance=None):
    """Enregistre un suivi à partir du formulaire.

    - Traitement sélectionné : une seule entrée (mise à jour de `instance` si elle
      est fournie, sinon création).
    - Un ou plusieurs vaccins sélectionnés : chaque vaccin donne sa propre entrée
      (mêmes animal/date/lot/rappel/notes). En modification, l'entrée existante
      est réutilisée pour le premier vaccin ; les suivants sont créés à part.

    Retourne l'entrée « principale » (celle mise à jour, ou la première créée),
    utilisée ensuite pour construire l'URL de redirection.
    """
    donnees = form.cleaned_data
    vaccins = donnees.get('vaccins')

    if not vaccins:
        # `vaccin` n'est pas dans Meta.fields (c'est le champ `vaccins`,
        # multi-sélection, qui pilote plusieurs entrées à la place) : form.save()
        # seul ne le remettrait pas à None si `instance` provenait d'un suivi
        # vaccin qu'on bascule ici vers un traitement, laissant les deux FK
        # renseignées à la fois (incohérent avec le reste du modèle/affichage).
        resultat = form.save(commit=False)
        resultat.vaccin = None
        resultat.save()
        return resultat

    commun = {
        'animal': donnees['animal'],
        'date': donnees['date'],
        'numero_lot': donnees.get('numero_lot', ''),
        'date_prochaine_dose': donnees.get('date_prochaine_dose'),
        'notes': donnees.get('notes', ''),
    }
    premier, *autres = vaccins

    if instance is not None:
        instance.vaccin = premier
        instance.traitement = None
        instance.duree_traitement = ''
        instance.prise_matin = False
        instance.prise_midi = False
        instance.prise_soir = False
        instance.dose_unite = ''
        instance.dose_valeur = None
        for champ, valeur in commun.items():
            setattr(instance, champ, valeur)
        instance.save()
        principal = instance
    else:
        principal = SuiviVaccinTraitement.objects.create(vaccin=premier, **commun)

    if autres:
        SuiviVaccinTraitement.objects.bulk_create([
            SuiviVaccinTraitement(vaccin=vaccin, **commun) for vaccin in autres
        ])

    return principal


class SuiviSaveMixin:
    """Délègue l'enregistrement à `_enregistrer_suivi` (création/mise à jour,
    avec éclatement en plusieurs entrées si plusieurs vaccins sont choisis)."""

    def form_valid(self, form):
        self.object = _enregistrer_suivi(form, instance=self.object)
        return HttpResponseRedirect(self.get_success_url())

class VaccinListView(LoginRequiredMixin, ListView):
    model = Vaccin
    template_name = 'vaccins/liste.html'
    context_object_name = 'vaccins'

class TraitementListView(LoginRequiredMixin, ListView):
    model = Traitement
    template_name = 'vaccins/traitements_liste.html'
    context_object_name = 'traitements'

class SuiviListView(LoginRequiredMixin, ListView):
    model = SuiviVaccinTraitement
    template_name = 'vaccins/suivi_liste.html'
    context_object_name = 'suivis'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('animal', 'vaccin', 'traitement')
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)
        return queryset.order_by('-date')

class TraitementClasseContextMixin:
    """Liste des classes de traitement, pour la modale « Ajouter un
    traitement » du formulaire de suivi (cf. vaccins/form.html)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['traitement_classes'] = Traitement.Classe.choices
        return context

class SuiviCreateView(LoginRequiredMixin, TraitementClasseContextMixin, SuiviSaveMixin, CreateView):
    model = SuiviVaccinTraitement
    form_class = SuiviVaccinTraitementForm
    template_name = 'vaccins/form.html'

    def get_initial(self):
        initial = super().get_initial()
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            initial['animal'] = get_object_or_404(Animal, pk=animal_id)
        return initial

    def get_success_url(self):
        return reverse_lazy('animaux:animal_detail', kwargs={'pk': self.object.animal.pk})

class SuiviUpdateView(LoginRequiredMixin, TraitementClasseContextMixin, SuiviSaveMixin, UpdateView):
    model = SuiviVaccinTraitement
    form_class = SuiviVaccinTraitementForm
    template_name = 'vaccins/form.html'
    success_url = reverse_lazy('vaccins:suivi_list')

class SuiviDeleteView(LoginRequiredMixin, DeleteView):
    model = SuiviVaccinTraitement
    template_name = 'vaccins/confirm_delete.html'
    success_url = reverse_lazy('vaccins:suivi_list')