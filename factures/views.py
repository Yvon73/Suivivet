from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from datetime import datetime
from accueil.utils import comptes_accessibles
from animaux.models import Animal
from .models import Facture
from .forms import FactureForm, LigneFactureFormSet
from .ventilation import PREFIXE, ajouter_ligne, contexte_lignes, creer_designations, retirer_ligne


@login_required
@require_POST
def ventilation_facture(request, pk=None):
    """Point d'entrée HTMX du formulaire de ventilation : reçoit l'état
    courant des lignes, applique l'action demandée (`ajouter`, `retirer`,
    `designation`, `ventiler`, ou aucune pour un simple recalcul en cours de
    saisie) et renvoie le fragment HTML à jour. Rien n'est enregistré ici,
    hormis une nouvelle désignation (cf. factures/ventilation.py)."""
    facture = None
    if pk is not None:
        facture = get_object_or_404(Facture, pk=pk, utilisateur__in=comptes_accessibles(request.user))

    data = request.POST.copy()
    action = data.get('action', '')
    erreurs_designation = {}
    if f'{PREFIXE}-TOTAL_FORMS' not in data:
        # Premier clic sur « Ventiler la facture » : pas encore de lignes.
        data = None
    elif action == 'ajouter':
        ajouter_ligne(data)
    elif action == 'retirer':
        data = retirer_ligne(data, data.get('ligne'))
    elif action == 'designation':
        erreurs_designation = creer_designations(data, data.get('ligne'))

    formset = LigneFactureFormSet(data, instance=facture, form_kwargs={'user': request.user})
    return render(request, 'factures/partials/ventilation_reponse.html', {
        'formset': formset,
        'ventiler': True,
        'verrouillee': bool(facture and facture.est_ventilee()),
        'afficher_erreurs': False,
        'recalcul': not action,
        'url_ventilation': request.path,
        **contexte_lignes(formset, erreurs_designation),
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
        formset = context['formset']
        facture = getattr(self, 'object', None)
        context['ventiler'] = context['verrouillee'] or formset.is_bound
        context['afficher_erreurs'] = formset.is_bound
        context['url_ventilation'] = reverse(
            'factures:facture_ventilation', args=[facture.pk] if facture and facture.pk else [],
        )
        context.update(contexte_lignes(formset))
        if context['ventiler']:
            # Montant calculé à partir des lignes (cf. partials/ventilation_reponse.html).
            context['form'].fields['montant'].widget.attrs['readonly'] = True
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
