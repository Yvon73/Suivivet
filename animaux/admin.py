from django.contrib import admin
from .models import Espece, Robe, Race, Organisme

# Animal, AnimalIdentification et Proprietaire ne sont volontairement PAS
# enregistrés ici : ce sont des données saisies par les comptes utilisateurs
# (isolées par compte, cf. Animal.utilisateur/Proprietaire.utilisateur), pas
# des catalogues de reference — l'Admin gere les comptes et les catalogues
# partages, jamais les donnees personnelles saisies par les utilisateurs.


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


