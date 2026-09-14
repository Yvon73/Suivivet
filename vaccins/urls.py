from django.urls import path
from .views import (
    VaccinListView,
    TraitementListView,
    SuiviListView,
    SuiviCreateView,
    SuiviUpdateView,
    SuiviDeleteView,
    ajouter_vaccin_ajax,
    ajouter_traitement_ajax,
)

app_name = 'vaccins'

urlpatterns = [
    path('vaccins/', VaccinListView.as_view(), name='vaccin_list'),
    path('traitements/', TraitementListView.as_view(), name='traitement_list'),
    path('suivi/', SuiviListView.as_view(), name='suivi_list'),
    path('suivi/animal/<int:animal_id>/', SuiviListView.as_view(), name='suivi_list_animal'),
    path('suivi/ajouter/<int:animal_id>/', SuiviCreateView.as_view(), name='suivi_create'),
    path('suivi/<int:pk>/modifier/', SuiviUpdateView.as_view(), name='suivi_update'),
    path('suivi/<int:pk>/supprimer/', SuiviDeleteView.as_view(), name='suivi_delete'),
    path('vaccins/ajouter/', ajouter_vaccin_ajax, name='vaccin_create_ajax'),
    path('traitements/ajouter/', ajouter_traitement_ajax, name='traitement_create_ajax'),
]