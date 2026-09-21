from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from datetime import datetime
from accueil.utils import comptes_accessibles
from animaux.models import Animal
from .models import Facture, Designation
from .forms import FactureForm, DesignationForm, LigneFactureFormSet


@login_required
@require_POST
def ajouter_designation_ajax(request):
    """Crée une nouvelle désignation depuis la modale du formulaire de
    ventilation, et la renvoie en JSON pour l'insérer directement dans le
    select côté client (même principe que les modales Vétérinaire/Vaccin)."""
    form = DesignationForm(request.POST)
    if form.is_valid():
        designation = form.save()
        return JsonResponse({'success': True, 'id': designation.pk, 'nom': designation.nom})
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)


@login_required
@require_GET
def dernier_prix_designation_ajax(request, pk):
    """Dernier prix unitaire connu pour une désignation (affiché en lecture
    seule à côté du champ de saisie du nouveau prix, avec indicateur
    hausse/baisse calculé côté client)."""
    designation = get_object_or_404(Designation, pk=pk)
    dernier_prix = designation.dernier_prix_unitaire()
    return JsonResponse({
        'dernier_prix': str(dernier_prix) if dernier_prix is not None else None,
    })


@login_required
def fichier_facture(request, pk):
    """Sert le fichier scanné après vérification du propriétaire — jamais
    exposé via une URL /media/ statique (cf. Projet_veto/urls.py)."""
    facture = get_object_or_404(Facture, pk=pk, utilisateur__in=comptes_accessibles(request.user))
    if not facture.fichier:
        raise Http404
    return FileResponse(facture.fichier.open('rb'))


class FactureListView(LoginRequiredMixin, ListView):
    model = Facture
    template_name = 'factures/liste.html'
    context_object_name = 'factures'
    ordering = ['-date']

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            utilisateur__in=comptes_accessibles(self.request.user)
        ).select_related('animal')
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        annee = datetime.now().year
        mois = datetime.now().month
        utilisateur = self.request.user

        # Calcul des dépenses mensuelles et annuelles
        context['annee'] = annee
        context['mois_courant'] = datetime(annee, mois, 1)
        context['depenses_mensuelles_veterinaires'] = Facture.depenses_mensuelles(utilisateur, annee, mois, 'VETERINAIRE')
        context['depenses_mensuelles_alimentaires'] = Facture.depenses_mensuelles(utilisateur, annee, mois, 'ALIMENTAIRE')
        context['depenses_annuelles_veterinaires'] = Facture.depenses_annuelles(utilisateur, annee, 'VETERINAIRE')
        context['depenses_annuelles_alimentaires'] = Facture.depenses_annuelles(utilisateur, annee, 'ALIMENTAIRE')

        return context

class FactureDetailView(LoginRequiredMixin, DetailView):
    model = Facture
    template_name = 'factures/detail.html'
    context_object_name = 'facture'

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lignes'] = self.object.lignes.select_related('designation', 'animal')
        return context


class VentilationFactureMixin:
    """Logique commune à la création et à la modification d'une facture avec
    ventilation (bouton « Ventiler la facture ») : gestion du formset de
    lignes, verrouillage des champs déjà validés, et recalcul du montant
    total à partir des lignes."""

    form_class = FactureForm
    template_name = 'factures/form.html'

    def _verrouillee(self):
        """True si la facture était déjà ventilée avant cette requête (donc
        ses champs propres et le détail des lignes existantes sont figés)."""
        return bool(getattr(self, 'object', None)) and self.object.pk and self.object.est_ventilee()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['verrouillee'] = self._verrouillee()
        return kwargs

    def get_formset(self, data=None):
        return LigneFactureFormSet(
            data, instance=getattr(self, 'object', None), form_kwargs={'user': self.request.user},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'formset' not in kwargs:
            context['formset'] = self.get_formset()
        context['verrouillee'] = self._verrouillee()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if hasattr(self, 'get_object') and self.kwargs.get('pk') else None
        form = self.get_form()
        ventiler = request.POST.get('ventiler') == '1'
        montant_provisoire = False

        if ventiler and not form.data.get('montant'):
            # Le montant est recalculé à partir des lignes : on renseigne une
            # valeur temporaire valide pour passer la validation du champ
            # obligatoire, avant de le recalculer juste après (cf. plus bas).
            form.data = form.data.copy()
            form.data['montant'] = '0.01'
            montant_provisoire = True

        formset = self.get_formset(request.POST) if ventiler else self.get_formset()
        formset_valide = formset.is_valid() if ventiler else True

        if form.is_valid() and formset_valide:
            if montant_provisoire and not any(
                f.cleaned_data and not f.cleaned_data.get('DELETE') for f in formset.forms
            ):
                # Aucune ligne réelle (formset vide/entièrement supprimé) : le
                # montant recalculé à partir des lignes resterait à 0 ligne, donc
                # `recalculer_montant()` ne toucherait pas au 0,01 € provisoire
                # ci-dessus, qui serait alors enregistré tel quel comme montant
                # définitif de la facture.
                form.add_error('montant', "Renseigne un montant, ou ajoute au moins une ligne de ventilation.")
                return self.render_to_response(self.get_context_data(form=form, formset=formset))

            with transaction.atomic():
                self.object = form.save()
                if ventiler:
                    formset.instance = self.object
                    formset.save()
                    self.object.recalculer_montant()
            return self.form_valid_redirect()

        return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def form_valid_redirect(self):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())


class FactureCreateView(VentilationFactureMixin, LoginRequiredMixin, CreateView):
    model = Facture

    def get_initial(self):
        initial = super().get_initial()
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            initial['animal'] = get_object_or_404(
                Animal, pk=animal_id, utilisateur__in=comptes_accessibles(self.request.user)
            )
        return initial

    def get_success_url(self):
        if self.object.animal_id:
            return reverse_lazy('animaux:animal_detail', kwargs={'pk': self.object.animal_id})
        return reverse_lazy('factures:facture_list')


class FactureUpdateView(VentilationFactureMixin, LoginRequiredMixin, UpdateView):
    model = Facture
    success_url = reverse_lazy('factures:facture_list')

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))

class FactureDeleteView(LoginRequiredMixin, DeleteView):
    model = Facture
    template_name = 'factures/confirm_delete.html'
    success_url = reverse_lazy('factures:facture_list')

    def get_queryset(self):
        return super().get_queryset().filter(utilisateur__in=comptes_accessibles(self.request.user))
