from django import forms
from django.db.models import Q
from django.utils import timezone
from accueil.utils import comptes_accessibles, filtre_catalogue
from animaux.models import Animal
from .models import Consultation, Veterinaire

class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ['animal', 'date', 'motif', 'compte_rendu', 'veterinaire']
        widgets = {
            'animal': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'motif': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'compte_rendu': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'veterinaire': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Animaux visibles du compte connecté (lui-même, plus les autres
        # membres de son foyer partagé le cas échéant).
        self.fields['animal'].queryset = Animal.objects.filter(utilisateur__in=comptes_accessibles(user))

        # Vétérinaires actifs du compte connecté et de son foyer (cf.
        # Veterinaire.utilisateur) : la fiche d'un autre compte, ou une fiche
        # « supprimée » (Veterinaire.actif=False), n'est pas proposée pour une
        # nouvelle consultation — mais reste sélectionnée si c'est déjà la
        # valeur de la consultation en cours de modification.
        valeur_id = getattr(self.instance, 'veterinaire_id', None)
        self.fields['veterinaire'].queryset = Veterinaire.objects.filter(
            (filtre_catalogue(user) & Q(actif=True)) | Q(pk=valeur_id or 0)
        )

    def clean_date(self):
        date = self.cleaned_data['date']
        if self.instance.pk and self.instance.date:
            # Modification : une date inchangée reste acceptée même passée,
            # sinon on ne pourrait jamais saisir le compte rendu après le
            # rendez-vous. Comparaison à la minute près : le champ
            # datetime-local ne renvoie pas les secondes. (À ce stade,
            # self.instance.date est encore l'ancienne valeur.)
            ancienne = self.instance.date.replace(second=0, microsecond=0)
            if date.replace(second=0, microsecond=0) == ancienne:
                return date
        if date <= timezone.now():
            raise forms.ValidationError("La date de la consultation doit être dans le futur.")
        return date


class VeterinaireForm(forms.ModelForm):
    """Formulaire de la fiche vétérinaire (page dédiée d'ajout/modification,
    cf. consultations/veterinaire_form.html) et du panneau « Ajouter un
    vétérinaire » du formulaire consultation (mêmes champs)."""

    class Meta:
        model = Veterinaire
        fields = ['nom', 'prenom', 'adresse', 'telephone', 'email']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Rattachée à son compte créateur, à la création seulement : une fiche
        # modifiée par un autre membre du foyer ne change pas de compte.
        if user is not None and not self.instance.pk:
            self.instance.utilisateur = user
