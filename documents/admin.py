from django.contrib import admin
from .models import Document, TypeDocument


@admin.register(TypeDocument)
class TypeDocumentAdmin(admin.ModelAdmin):
    list_display = ('nom',)
    search_fields = ('nom',)
    ordering = ('nom',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('titre', 'animal', 'type_document', 'date_ajout')
    list_filter = ('type_document',)
    search_fields = ('titre', 'animal__nom')
    date_hierarchy = 'date_ajout'
