from django.urls import path
from .views import (
    DocumentListView,
    DocumentDetailView,
    DocumentCreateView,
    DocumentUpdateView,
    DocumentDeleteView,
    fichier_document,
)

app_name = 'documents'

urlpatterns = [
    path('', DocumentListView.as_view(), name='document_list'),
    path('animal/<int:animal_id>/', DocumentListView.as_view(), name='document_list_animal'),
    path('<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    path('<int:pk>/fichier/', fichier_document, name='document_fichier'),
    path('ajouter/', DocumentCreateView.as_view(), name='document_create'),
    path('ajouter/<int:animal_id>/', DocumentCreateView.as_view(), name='document_create'),
    path('<int:pk>/modifier/', DocumentUpdateView.as_view(), name='document_update'),
    path('<int:pk>/supprimer/', DocumentDeleteView.as_view(), name='document_delete'),
]