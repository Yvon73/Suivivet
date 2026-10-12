from django.urls import path
from .views import (
    FactureListView,
    FactureDetailView,
    FactureCreateView,
    FactureUpdateView,
    FactureDeleteView,
    fichier_facture,
    ventilation_facture,
)

app_name = 'factures'

urlpatterns = [
    path('', FactureListView.as_view(), name='facture_list'),
    path('animal/<int:animal_id>/', FactureListView.as_view(), name='facture_list_animal'),
    path('<int:pk>/', FactureDetailView.as_view(), name='facture_detail'),
    path('<int:pk>/fichier/', fichier_facture, name='facture_fichier'),
    path('ajouter/', FactureCreateView.as_view(), name='facture_create'),
    path('ajouter/<int:animal_id>/', FactureCreateView.as_view(), name='facture_create'),
    path('<int:pk>/modifier/', FactureUpdateView.as_view(), name='facture_update'),
    path('<int:pk>/supprimer/', FactureDeleteView.as_view(), name='facture_delete'),
    path('ventilation/', ventilation_facture, name='facture_ventilation'),
    path('<int:pk>/ventilation/', ventilation_facture, name='facture_ventilation'),
]