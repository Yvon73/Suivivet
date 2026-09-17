from django.contrib import admin
from .models import Vaccin, Traitement

# SuiviVaccinTraitement n'est volontairement PAS enregistré ici : c'est une
# donnée saisie par un compte utilisateur (isolée par animal, cf.
# Animal.utilisateur), pas un catalogue de référence.


@admin.register(Vaccin)
class VaccinAdmin(admin.ModelAdmin):
    list_display = ('nom', 'categorie', 'rappel_interval')
    list_filter = ('categorie',)
    search_fields = ('nom',)


@admin.register(Traitement)
class TraitementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'classe')
    list_filter = ('classe',)
    search_fields = ('nom',)


