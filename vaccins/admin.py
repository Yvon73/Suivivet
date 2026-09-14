from django.contrib import admin
from .models import Vaccin, Traitement, SuiviVaccinTraitement


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


@admin.register(SuiviVaccinTraitement)
class SuiviVaccinTraitementAdmin(admin.ModelAdmin):
    list_display = ('animal', 'vaccin', 'traitement', 'date', 'date_prochaine_dose')
    list_filter = ('vaccin', 'traitement')
    search_fields = ('animal__nom',)
