from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from accueil.utils import comptes_accessibles
from Projet_veto.listes import ListeTriableMixin, date_texte
from animaux.models import Animal
from .models import Document
from .forms import DocumentForm


@login_required
def fichier_document(request, pk):
    """Sert le fichier après vérification du propriétaire (via l'animal) —
    jamais exposé via une URL /media/ statique (cf. Projet_veto/urls.py)."""
    document = get_object_or_404(Document, pk=pk, animal__utilisateur__in=comptes_accessibles(request.user))
    if not document.fichier:
        raise Http404
    try:
        return FileResponse(document.fichier.open('rb'))
    except FileNotFoundError:
        # Ligne présente en base mais fichier absent du disque (base
        # restaurée sans son dossier media/, par exemple) : 404, pas 500.
        raise Http404


class DocumentListView(LoginRequiredMixin, ListeTriableMixin, ListView):
    model = Document
    template_name = 'documents/liste.html'
    context_object_name = 'documents'
    # `date_txt` : annotation de get_queryset() (date telle qu'affichée).
    champs_recherche = ('animal__nom', 'titre', 'type_document__nom', 'description', 'date_txt')
    colonnes_tri = {
        'animal': 'animal__nom',
        'titre': 'titre',
        'type': 'type_document__nom',
        'date': 'date_ajout',
    }
    tri_defaut = '-date'

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            animal__utilisateur__in=comptes_accessibles(self.request.user)
        ).select_related('animal', 'type_document')
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)
        queryset = queryset.annotate(date_txt=date_texte('date_ajout'))
        return self.filtrer_et_trier(queryset)

class DocumentDetailView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'documents/detail.html'
    context_object_name = 'document'

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur__in=comptes_accessibles(self.request.user))

class DocumentCreateView(LoginRequiredMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/form.html'

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

class DocumentUpdateView(LoginRequiredMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/form.html'
    success_url = reverse_lazy('documents:document_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur__in=comptes_accessibles(self.request.user))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class DocumentDeleteView(LoginRequiredMixin, DeleteView):
    model = Document
    template_name = 'documents/confirm_delete.html'
    success_url = reverse_lazy('documents:document_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur__in=comptes_accessibles(self.request.user))