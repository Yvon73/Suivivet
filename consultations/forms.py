from django import forms
from django.db.models import Q
from django.utils import timezone
from animaux.models import Animal
from .models import Consultation, Veterinaire

class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ['animal', 'date', 'motif', 'compte_rendu', 'veterinaire']
        widgets = {
            'animal': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'motif': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'compte_rendu': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'veterinaire': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Uniquement les animaux du compte connecté (cf. Animal.utilisateur).
        self.fields['animal'].queryset = Animal.objects.filter(utilisateur=user)

        # Vétérinaires actifs uniquement (catalogue partagé, cf. Veterinaire) :
        # une fiche « supprimée » (Veterinaire.actif=False) n'est plus proposée
        # pour une nouvelle consultation, mais reste sélectionnée si c'est déjà
        # la valeur de la consultation en cours de modification.
        queryset = Veterinaire.objects.filter(actif=True)
        valeur_id = getattr(self.instance, 'veterinaire_id', None)
        if valeur_id and not queryset.filter(pk=valeur_id).exists():
            queryset = Veterinaire.objects.filter(Q(actif=True) | Q(pk=valeur_id))
        self.fields['veterinaire'].queryset = queryset

    def clean_date(self):
        date = self.cleaned_data['date']
        if date <= timezone.now():
            raise forms.ValidationError("La date de la consultation doit être dans le futur.")
        return date


class VeterinaireForm(forms.ModelForm):
    """Formulaire de la fiche vétérinaire (page dédiée d'ajout/modification,
    cf. consultations/veterinaire_form.html) et de la modale « Ajouter un
    vétérinaire » du formulaire consultation (mêmes champs)."""

    class Meta:
        model = Veterinaire
        fields = ['nom', 'adresse', 'telephone', 'email']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }