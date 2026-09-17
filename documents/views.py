from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from animaux.models import Animal
from .models import Document
from .forms import DocumentForm

class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'documents/liste.html'
    context_object_name = 'documents'
    ordering = ['-date_ajout']

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            animal__utilisateur=self.request.user
        ).select_related('animal', 'type_document')
        animal_id = self.kwargs.get('animal_id')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)
        return queryset

class DocumentDetailView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'documents/detail.html'
    context_object_name = 'document'

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur=self.request.user)

class DocumentCreateView(LoginRequiredMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/form.html'

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

class DocumentUpdateView(LoginRequiredMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/form.html'
    success_url = reverse_lazy('documents:document_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class DocumentDeleteView(LoginRequiredMixin, DeleteView):
    model = Document
    template_name = 'documents/confirm_delete.html'
    success_url = reverse_lazy('documents:document_list')

    def get_queryset(self):
        return super().get_queryset().filter(animal__utilisateur=self.request.user)