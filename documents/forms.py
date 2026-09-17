from django import forms
from animaux.models import Animal
from .models import Document, TypeDocument

class DocumentForm(forms.ModelForm):
    nouveau_type_document = forms.CharField(
        required=False,
        max_length=100,
        label="Nouveau type (si absent de la liste)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Ex : Analyse d'urine"}),
    )

    field_order = ['animal', 'type_document', 'nouveau_type_document', 'titre', 'fichier', 'description']

    class Meta:
        model = Document
        fields = ['animal', 'type_document', 'titre', 'fichier', 'description']
        widgets = {
            'animal': forms.Select(attrs={'class': 'form-select'}),
            'type_document': forms.Select(attrs={'class': 'form-select'}),
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'fichier': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.gif,.webp,.doc,.docx,.xls,.xlsx',
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Uniquement les animaux du compte connecté (cf. Animal.utilisateur).
        self.fields['animal'].queryset = Animal.objects.filter(utilisateur=user)
        self.fields['type_document'].required = False
        self.fields['type_document'].help_text = (
            "Absent de la liste ? Laissez ce champ vide et saisissez le nouveau type ci-dessous."
        )

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            # Un autre champ est déjà en erreur : on ne crée pas de nouveau
            # type de document pour un formulaire qui sera de toute façon
            # rejeté (évite une entrée de catalogue orpheline).
            return cleaned_data

        type_document = cleaned_data.get('type_document')
        nouveau_type = (cleaned_data.get('nouveau_type_document') or '').strip()

        if nouveau_type:
            type_document, _ = TypeDocument.objects.get_or_create(
                nom__iexact=nouveau_type,
                defaults={'nom': nouveau_type},
            )
            cleaned_data['type_document'] = type_document
        elif not type_document:
            self.add_error(
                'type_document',
                "Sélectionnez un type existant ou saisissez-en un nouveau ci-dessous.",
            )

        return cleaned_data
