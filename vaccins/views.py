from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_POST
from accueil.utils import comptes_accessibles, filtre_catalogue
from Projet_veto import ajout_rapide
from animaux.models import Animal
from .models import SuiviVaccinTraitement, Vaccin, Traitement
from .forms import SuiviVaccinTraitementForm, VaccinForm, TraitementForm


PREFIXE_AJOUT_VACCIN = 'nouveau_vaccin'
PREFIXE_AJOUT_TRAITEMENT = 'nouveau_traitement'


def _contexte_blocs(form, form_vaccin=None, form_traitement=None):
    """Contexte des blocs « Vaccin(s) » / « Traitement » du formulaire de
    suivi `form` : état d'affichage (cf. SuiviVaccinTraitementForm.preparer_blocs)
    et ajouts rapides au catalogue (cf. Projet_veto/ajout_rapide.py).

    En modification, les URL des fragments htmx portent la clé du suivi
    (comme factures:facture_ventilation) : les listes redessinées doivent
    garder l'entrée que ce suivi référence déjà (cf. _form_depuis_saisie)."""
    form.preparer_blocs()
    args = [form.instance.pk] if form.instance.pk else []
    return {
        'form': form,
        'url_choix': reverse('vaccins:suivi_choix', args=args),
        'ajout_vaccin': ajout_rapide.contexte(
            nom='vaccins', titre='Ajouter un vaccin absent du catalogue',
            url=reverse('vaccins:vaccin_ajout_rapide', args=args),
            form=form_vaccin or VaccinForm(prefix=PREFIXE_AJOUT_VACCIN),
            champ=form['vaccins'], ouvert=bool(form_vaccin),
            bouton='Nouveau vaccin', inclure='#zoneChoix',
        ),
        'ajout_traitement': ajout_rapide.contexte(
            nom='traitement', titre='Ajouter un traitement absent du catalogue',
            url=reverse('vaccins:traitement_ajout_rapide', args=args),
            form=form_traitement or TraitementForm(prefix=PREFIXE_AJOUT_TRAITEMENT),
            champ=form['traitement'], ouvert=bool(form_traitement),
            bouton='Nouveau traitement', inclure='#zoneChoix',
        ),
    }


def _suivi_en_cours(request, pk):
    """Suivi en cours de modification (`pk` de l'URL du fragment), ou None en
    création. Même contrôle d'accès que SuiviUpdateView : 404 pour le suivi
    d'un animal que le compte ne voit pas."""
    if pk is None:
        return None
    return get_object_or_404(
        SuiviVaccinTraitement, pk=pk, animal__utilisateur__in=comptes_accessibles(request.user),
    )


def _form_depuis_saisie(request, suivi=None, **selection):
    """Formulaire de suivi non lié reprenant la sélection en cours dans les
    blocs « Vaccin(s) » / « Traitement » (envoyée par htmx), sans validation
    ni message d'erreur : il ne sert qu'à redessiner ces blocs.

    `suivi` : le suivi en cours de modification. Son vaccin / traitement
    reste proposé dans les listes redessinées même s'il est sorti du
    catalogue visible (entrée d'un ancien membre du foyer), exactement comme
    dans le formulaire complet (`garder=`, cf. SuiviVaccinTraitementForm) —
    sinon la liste renvoyée en hx-swap-oob le perdrait, et le suivi avec
    elle à l'enregistrement. La sélection affichée reste celle de la saisie
    (`initial`, toujours renseigné, l'emporte sur les valeurs du suivi)."""
    initial = {
        'vaccins': request.POST.getlist('vaccins'),
        'traitement': request.POST.get('traitement', ''),
        'dose_unite': request.POST.get('dose_unite', ''),
        'dose_valeur': request.POST.get('dose_valeur', ''),
    }
    initial.update(selection)
    return SuiviVaccinTraitementForm(initial=initial, instance=suivi, user=request.user)


@login_required
@require_POST
def choix_suivi(request, pk=None):
    """Redessine les listes « Vaccin(s) » / « Traitement » et le bloc « Dose »
    à chaque changement de sélection (htmx) : l'une grise l'autre, et la dose
    ne s'affiche que pour un comprimé ou une solution buvable. `pk` : suivi
    en cours de modification (absent en création)."""
    contexte = _contexte_blocs(_form_depuis_saisie(request, _suivi_en_cours(request, pk)))
    contexte['source'] = request.headers.get('HX-Trigger', '')
    return render(request, 'vaccins/partials/blocs_reponse.html', contexte)


@login_required
@require_POST
def ajouter_vaccin_rapide(request, pk=None):
    """Crée un vaccin depuis le panneau « Nouveau vaccin » du formulaire de
    suivi et le sélectionne dans la liste « Vaccin(s) » (htmx). `pk` : suivi
    en cours de modification (absent en création)."""
    suivi = _suivi_en_cours(request, pk)
    form_ajout = VaccinForm(request.POST, prefix=PREFIXE_AJOUT_VACCIN, user=request.user)
    if not form_ajout.is_valid():
        contexte = _contexte_blocs(_form_depuis_saisie(request, suivi), form_vaccin=form_ajout)
        return ajout_rapide.reponse(request, contexte['ajout_vaccin'], succes=False)
    vaccin = form_ajout.save()
    vaccins = [valeur for valeur in request.POST.getlist('vaccins') if valeur] + [str(vaccin.pk)]
    # Le dernier ajout l'emporte : un traitement encore sélectionné est vidé,
    # sinon vaccin et traitement resteraient choisis en même temps.
    contexte = _contexte_blocs(_form_depuis_saisie(request, suivi, vaccins=vaccins, traitement=''))
    contexte['ajout'] = contexte['ajout_vaccin']
    return render(request, 'vaccins/partials/blocs_reponse.html', contexte)


@login_required
@require_POST
def ajouter_traitement_rapide(request, pk=None):
    """Crée un traitement depuis le panneau « Nouveau traitement » du
    formulaire de suivi et le sélectionne dans la liste « Traitement » (htmx).
    `pk` : suivi en cours de modification (absent en création)."""
    suivi = _suivi_en_cours(request, pk)
    form_ajout = TraitementForm(request.POST, prefix=PREFIXE_AJOUT_TRAITEMENT, user=request.user)
    if not form_ajout.is_valid():
        contexte = _contexte_blocs(_form_depuis_saisie(request, suivi), form_traitement=form_ajout)
        return ajout_rapide.reponse(request, contexte['ajout_traitement'], succes=False)
    traitement = form_ajout.save()
    # Même règle que pour l'ajout d'un vaccin : les vaccins sélectionnés sont vidés.
    contexte = _contexte_blocs(_form_depuis_saisie(request, suivi, traitement=str(traitement.pk), vaccins=[]))
    contexte['ajout'] = contexte['ajout_traitement']
    return render(request, 'vaccins/partials/blocs_reponse.html', contexte)


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

    def get_queryset(self):
        # Entrées de référence + celles du compte et de son foyer.
        return super().get_queryset().filter(filtre_catalogue(self.request.user, reference=True))

class TraitementListView(LoginRequiredMixin, ListView):
    model = Traitement
    template_name = 'vaccins/traitements_liste.html'
    context_object_name = 'traitements'

    def get_queryset(self):
        # Entrées de référence + celles du compte et de son foyer.
        return super().get_queryset().filter(filtre_catalogue(self.request.user, reference=True))

class SuiviListView(LoginRequiredMixin, ListView):
    model = SuiviVaccinTraitement
    template_name = 'vaccins/suivi_liste.html'
    context_object_name = 'suivis'

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            animal__utilisateur__in=comptes_accessibles(self.request.user)
        ).select_related('animal', 'vaccin', 'traitement')
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)
        return queryset.order_by('-date')

class BlocsSuiviContextMixin:
    """Contexte des blocs « Vaccin(s) » / « Traitement » du formulaire de
    suivi (cf. _contexte_blocs)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_contexte_blocs(context['form']))
        return context

class SuiviCreateView(LoginRequiredMixin, BlocsSuiviContextMixin, SuiviSaveMixin, CreateView):
    model = SuiviVaccinTraitement
    form_class = SuiviVaccinTraitementForm
    template_name = 'vaccins/form.html'

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

class SuiviUpdateView(LoginRequiredMixin, BlocsSuiviContextMixin, SuiviSaveMixin, UpdateView):
    model = SuiviVaccinTraitement
    form_class = SuiviVaccinTraitementForm
    template_name = 'vaccins/form.html'
    success_url = reverse_lazy('vaccins:suivi_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur__in=comptes_accessibles(self.request.user))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class SuiviDeleteView(LoginRequiredMixin, DeleteView):
    model = SuiviVaccinTraitement
    template_name = 'vaccins/confirm_delete.html'
    success_url = reverse_lazy('vaccins:suivi_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur__in=comptes_accessibles(self.request.user))