# PreferenceAccessibilite n'est volontairement PAS enregistrée ici : ce sont
# des préférences personnelles de chaque compte, pas une donnée
# d'administration.
from django.contrib import admin

from .models import BlocageAdresse


@admin.register(BlocageAdresse)
class BlocageAdresseAdmin(admin.ModelAdmin):
    """Permet au superuser de consulter et lever un blocage — y compris un
    blocage définitif, qui n'a sinon aucune autre porte de sortie (cf.
    Projet_veto.throttling)."""

    list_display = ('prefixe', 'adresse_ip', 'nombre_blocages', 'bloque_definitivement', 'derniere_maj')
    list_filter = ('prefixe', 'bloque_definitivement')
    search_fields = ('adresse_ip',)
