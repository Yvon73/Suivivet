from django.contrib import admin
from .models import Consultation, Veterinaire


@admin.register(Veterinaire)
class VeterinaireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'email', 'telephone', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom', 'prenom', 'email')


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('animal', 'date', 'motif', 'veterinaire')
    list_filter = ('veterinaire',)
    search_fields = ('animal__nom', 'motif', 'veterinaire__nom')
