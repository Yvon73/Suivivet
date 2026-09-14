from django.contrib import admin
from .models import PreferenceAccessibilite


@admin.register(PreferenceAccessibilite)
class PreferenceAccessibiliteAdmin(admin.ModelAdmin):
    list_display = (
        'utilisateur', 'taille_texte', 'contraste_eleve', 'police_lisible',
        'reduire_animations', 'palette_daltonisme',
    )
    list_filter = ('taille_texte', 'contraste_eleve', 'police_lisible', 'reduire_animations', 'palette_daltonisme')
    search_fields = ('utilisateur__username', 'utilisateur__email')
