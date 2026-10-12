from django.contrib import admin
from .models import Vaccin, Traitement

# SuiviVaccinTraitement n'est volontairement PAS enregistré ici : c'est une
# donnée saisie par un compte utilisateur (isolée par animal, cf.
# Animal.utilisateur), pas un catalogue de référence.
#
# Vaccin/Traitement : « Compte » vide = entrée de référence, proposée à tous
# les comptes ; sinon l'entrée n'est visible que de ce compte et de son foyer.


@admin.register(Vaccin)
class VaccinAdmin(admin.ModelAdmin):
    list_display = ('nom', 'categorie', 'rappel_interval', 'utilisateur')
    list_filter = ('categorie', 'utilisateur')
    search_fields = ('nom',)


@admin.register(Traitement)
class TraitementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'classe', 'utilisateur')
    list_filter = ('classe', 'utilisateur')
    search_fields = ('nom',)


