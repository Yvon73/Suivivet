from django.contrib import admin
from .models import TypeDocument

# Document n'est volontairement PAS enregistré ici : c'est une donnée saisie
# par un compte utilisateur (isolée par animal, cf. Animal.utilisateur), pas
# un catalogue de référence.


@admin.register(TypeDocument)
class TypeDocumentAdmin(admin.ModelAdmin):
    list_display = ('nom',)
    search_fields = ('nom',)
    ordering = ('nom',)
