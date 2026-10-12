from django.urls import path
from .views import (
    VaccinListView,
    TraitementListView,
    SuiviListView,
    SuiviCreateView,
    SuiviUpdateView,
    SuiviDeleteView,
    choix_suivi,
    ajouter_vaccin_rapide,
    ajouter_traitement_rapide,
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
    # Fragments htmx du formulaire de suivi : sans clé en création, avec celle
    # du suivi en modification (cf. views._suivi_en_cours).
    path('suivi/choix/', choix_suivi, name='suivi_choix'),
    path('suivi/<int:pk>/choix/', choix_suivi, name='suivi_choix'),
    path('vaccins/ajout-rapide/', ajouter_vaccin_rapide, name='vaccin_ajout_rapide'),
    path('suivi/<int:pk>/vaccin-ajout-rapide/', ajouter_vaccin_rapide, name='vaccin_ajout_rapide'),
    path('traitements/ajout-rapide/', ajouter_traitement_rapide, name='traitement_ajout_rapide'),
    path('suivi/<int:pk>/traitement-ajout-rapide/', ajouter_traitement_rapide, name='traitement_ajout_rapide'),
]