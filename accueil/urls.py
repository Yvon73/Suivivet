from django.urls import path
from .views import (
    AccueilView, PremierUtilisateurCreateView, InscriptionCreateView,
    mettre_a_jour_preferences_accessibilite, robots_txt,
    PartageCompteView, envoyer_invitation_foyer, accepter_invitation_foyer,
    refuser_invitation_foyer, annuler_invitation_foyer, retirer_membre_foyer, quitter_foyer,
)

app_name = 'accueil'

urlpatterns = [
    path('', AccueilView.as_view(), name='accueil'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('premier-compte/', PremierUtilisateurCreateView.as_view(), name='premier_compte'),
    path('inscription/', InscriptionCreateView.as_view(), name='inscription'),
    path('preferences-accessibilite/', mettre_a_jour_preferences_accessibilite, name='preferences_accessibilite'),
    path('partage/', PartageCompteView.as_view(), name='partage_compte'),
    path('partage/inviter/', envoyer_invitation_foyer, name='partage_inviter'),
    path('partage/invitation/<str:token>/accepter/', accepter_invitation_foyer, name='partage_accepter'),
    path('partage/invitation/<str:token>/refuser/', refuser_invitation_foyer, name='partage_refuser'),
    path('partage/invitation/<int:pk>/annuler/', annuler_invitation_foyer, name='partage_annuler'),
    path('partage/membre/<int:pk>/retirer/', retirer_membre_foyer, name='partage_retirer_membre'),
    path('partage/quitter/', quitter_foyer, name='partage_quitter'),
]
