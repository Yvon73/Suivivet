from django.urls import path
from .views import (
    AccueilView, PremierUtilisateurCreateView, InscriptionCreateView,
    mettre_a_jour_preferences_accessibilite, robots_txt,
)

app_name = 'accueil'

urlpatterns = [
    path('', AccueilView.as_view(), name='accueil'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('premier-compte/', PremierUtilisateurCreateView.as_view(), name='premier_compte'),
    path('inscription/', InscriptionCreateView.as_view(), name='inscription'),
    path('preferences-accessibilite/', mettre_a_jour_preferences_accessibilite, name='preferences_accessibilite'),
]
