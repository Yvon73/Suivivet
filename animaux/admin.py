from django.contrib import admin
from .forms import AnimalIdentificationForm
from .models import Animal, AnimalIdentification, Espece, Robe, Race, Organisme, Proprietaire


@admin.register(Espece)
class EspeceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code')
    search_fields = ('nom', 'code')


@admin.register(Organisme)
class OrganismeAdmin(admin.ModelAdmin):
    list_display = ('nom_court', 'nom', 'espece', 'pays', 'est_officiel')
    list_filter = ('espece', 'est_officiel', 'pays')
    search_fields = ('nom', 'nom_court')


@admin.register(Robe)
class RobeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code')
    search_fields = ('nom', 'code')


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'espece', 'categorie', 'origine', 'esperance_vie', 'niveau_dangerosite')
    list_filter = ('espece', 'categorie', 'niveau_dangerosite')
    search_fields = ('nom', 'nom_scientifique', 'origine')


@admin.register(Proprietaire)
class ProprietaireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'email', 'telephone', 'code_postal', 'ville', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom', 'prenom', 'email', 'code_postal', 'ville')


class AnimalIdentificationInline(admin.TabularInline):
    model = AnimalIdentification
    form = AnimalIdentificationForm
    extra = 1


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ('nom', 'espece', 'race', 'robe', 'identifications_display', 'proprietaire')
    list_filter = ('espece', 'robe')
    search_fields = ('nom', 'identifications__identification', 'proprietaire__nom', 'proprietaire__email')
    inlines = [AnimalIdentificationInline]
