from django.urls import path
from .views import (
    ConsultationListView,
    ConsultationDetailView,
    ConsultationCreateView,
    ConsultationUpdateView,
    ConsultationDeleteView,
    CalendrierView,
    get_consultations_json,
    VeterinaireListView,
    VeterinaireDetailView,
    VeterinaireCreateView,
    VeterinaireUpdateView,
    VeterinaireDeleteView,
    ajouter_veterinaire_ajax,
)

app_name = 'consultations'

urlpatterns = [
    path('', ConsultationListView.as_view(), name='consultation_list'),
    path('animal/<int:animal_id>/', ConsultationListView.as_view(), name='consultation_list_animal'),
    path('<int:pk>/', ConsultationDetailView.as_view(), name='consultation_detail'),
    path('ajouter/', ConsultationCreateView.as_view(), name='consultation_create'),
    path('ajouter/<int:animal_id>/', ConsultationCreateView.as_view(), name='consultation_create'),
    path('<int:pk>/modifier/', ConsultationUpdateView.as_view(), name='consultation_update'),
    path('<int:pk>/supprimer/', ConsultationDeleteView.as_view(), name='consultation_delete'),
    path('calendrier/', CalendrierView.as_view(), name='calendrier'),
    path('calendrier/json/', get_consultations_json, name='calendrier_json'),
    path('veterinaires/', VeterinaireListView.as_view(), name='veterinaire_list'),
    path('veterinaires/ajouter/', VeterinaireCreateView.as_view(), name='veterinaire_create'),
    path('veterinaires/ajouter-ajax/', ajouter_veterinaire_ajax, name='veterinaire_create_ajax'),
    path('veterinaires/<int:pk>/', VeterinaireDetailView.as_view(), name='veterinaire_detail'),
    path('veterinaires/<int:pk>/modifier/', VeterinaireUpdateView.as_view(), name='veterinaire_update'),
    path('veterinaires/<int:pk>/supprimer/', VeterinaireDeleteView.as_view(), name='veterinaire_delete'),
]
