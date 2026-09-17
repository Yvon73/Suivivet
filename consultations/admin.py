from django.contrib import admin
from .models import Veterinaire

# Consultation n'est volontairement PAS enregistrée ici : c'est une donnée
# saisie par un compte utilisateur (isolée par animal, cf.
# Animal.utilisateur), pas un catalogue de référence.


@admin.register(Veterinaire)
class VeterinaireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'email', 'telephone', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom', 'prenom', 'email')
