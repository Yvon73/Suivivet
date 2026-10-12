from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from datetime import datetime
from accueil.utils import comptes_accessibles
from Projet_veto.listes import ListeTriableMixin, date_texte, libelle_choix_texte, montant_texte
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
        erreurs_designation = creer_designations(data, data.get('ligne'), utilisateur=request.user)

    formset = LigneFactureFormSet(data, instance=facture, form_kwargs={'user': request.user})
    return render(request, 'factures/partials/ventilation_reponse.html', {
        'formset': formset,
        'ventiler': True,
        'verrouillee': bool(facture and facture.est_ventilee()),
        'afficher_erreurs': False,
        'recalcul': not action,
        'url_ventilation': request.path,
        **contexte_lignes(formset, erreurs_designation, utilisateur=request.user),
    })


@login_required
def fichier_facture(request, pk):
    """Sert le fichier scanné après vérification du propriétaire — jamais
    exposé via une URL /media/ statique (cf. Projet_veto/urls.py)."""
    facture = get_object_or_404(Facture, pk=pk, utilisateur__in=comptes_accessibles(request.user))
    if not facture.fichier:
        raise Http404
    try:
        return FileResponse(facture.fichier.open('rb'))
    except FileNotFoundError:
        # Ligne présente en base mais fichier absent du disque (base
        # restaurée sans son dossier media/, par exemple) : 404, pas 500.
        raise Http404


class FactureListView(LoginRequiredMixin, ListeTriableMixin, ListView):
    model = Facture
    template_name = 'factures/liste.html'
    context_object_name = 'factures'
    # `type_depense` (code sans accent) et les annotations `*_txt` de
    # get_queryset() : toutes les colonnes affichées sont ainsi cherchables.
    champs_recherche = (
        'numero', 'animal__nom', 'titre', 'description',
        'type_depense', 'type_txt', 'date_txt', 'montant_txt',
    )
    colonnes_tri = {
        'numero': 'numero',
        'animal': 'animal__nom',
        'date': 'date',
        'type': 'type_depense',
        'titre': 'titre',
        'montant': 'montant',
    }
    tri_defaut = '-date'

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            utilisateur__in=comptes_accessibles(self.request.user)
        ).select_related('animal')
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)
        queryset = queryset.annotate(
            type_txt=libelle_choix_texte('type_depense', Facture.TYPE_DEPENSE_CHOIX),
            date_txt=date_texte('date'),
            montant_txt=montant_texte('montant'),
        )
        return self.filtrer_et_trier(queryset)

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
        # Totaux calculés ici : le filtre de gabarit `add` convertit d'abord ses
        # opérandes en entiers, ce qui tronquait les centimes.
        context['depenses_mensuelles_total'] = (
            context['depenses_mensuelles_veterinaires'] + context['depenses_mensuelles_alimentaires']
        )
        context['depenses_annuelles_total'] = (
            context['depenses_annuelles_veterinaires'] + context['depenses_annuelles_alimentaires']
        )

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
        context.update(contexte_lignes(formset, utilisateur=self.request.user))
        if context['ventiler']:
            # Montant calculé à partir des lignes (cf. partials/ventilation_reponse.html).
            context['form'].fields['montant'].widget.attrs['readonly'] = True
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if hasattr(self, 'get_object') and self.kwargs.get('pk') else None
        form = self.get_form()
        ventiler = request.POST.get('ventiler') == '1'
        # Évalué avant tout enregistrement : formset.save() peut supprimer la
        # dernière ligne, la facture ne serait alors plus « ventilée ».
        verrouillee = self._verrouillee()
        montant_provisoire = False

        formset = self.get_formset(request.POST) if ventiler else self.get_formset()

        if ventiler and not verrouillee:
            # Le montant d'une facture ventilée est la somme de ses lignes : on
            # ne se fie jamais à la valeur postée, qui est celle du dernier
            # recalcul HTMX reçu par le navigateur (« 0.00 » juste après le
            # clic sur « Ventiler », ou un total périmé si le formulaire est
            # envoyé avant la réponse). Facture verrouillée : le champ est
            # `disabled`, donc déjà ignoré.
            total = contexte_lignes(formset)['total']
            form.data = form.data.copy()
            # Sans ligne chiffrée, une valeur temporaire valide pour que seule
            # l'erreur explicite ci-dessous s'affiche sur le champ.
            form.data['montant'] = f'{total:.2f}' if total > 0 else '0.01'
            montant_provisoire = total <= 0

        formset_valide = formset.is_valid() if ventiler else True

        if form.is_valid() and formset_valide:
            if montant_provisoire:
                # Aucune ligne, ou des lignes dont le total est nul : le
                # montant recalculé serait de 0 €, refusé par le modèle.
                form.add_error('montant', "Ajoute au moins une ligne de ventilation d'un montant non nul.")
                form.data['montant'] = '0.00'
                return self.render_to_response(self.get_context_data(form=form, formset=formset))

            with transaction.atomic():
                self.object = form.save()
                if ventiler:
                    formset.instance = self.object
                    formset.save()
                    self.object.recalculer_montant()

            if verrouillee and not self.object.est_ventilee():
                # Toutes les lignes ont été supprimées : la facture n'est plus
                # ventilée et son montant est retombé à 0 (cf.
                # Facture.recalculer_montant). Ses champs sont de nouveau
                # modifiables : on y renvoie pour saisir le montant.
                messages.warning(
                    request,
                    "Toutes les lignes ont été supprimées : la facture n'est plus ventilée. "
                    "Renseigne son montant, ou ventile-la de nouveau.",
                )
                return HttpResponseRedirect(reverse('factures:facture_update', args=[self.object.pk]))
            return self.form_valid_redirect()

        if montant_provisoire:
            form.data['montant'] = '0.00'
        return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def form_valid_redirect(self):
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
