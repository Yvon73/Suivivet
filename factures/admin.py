from django.contrib import admin
from .models import Designation


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'utilisateur')
    list_filter = ('utilisateur',)
    search_fields = ('nom',)
