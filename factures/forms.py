from django import forms
from django.forms import inlineformset_factory

from accueil.utils import comptes_accessibles
from animaux.models import Animal
from .models import Facture, Designation, LigneFacture


class FactureForm(forms.ModelForm):
    class Meta:
        model = Facture
        fields = [
            'numero', 'animal', 'type_depense', 'titre', 'montant',
            'date', 'fichier', 'description'
        ]
        widgets = {
            'numero': forms.TextInput(attrs={'class': 'form-control'}),
            'animal': forms.Select(attrs={'class': 'form-select'}),
            'type_depense': forms.Select(attrs={'class': 'form-select'}),
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'fichier': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.gif,.webp,.doc,.docx,.xls,.xlsx',
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, user=None, verrouillee=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Posé sur l'instance avant save() (cf. VentilationFactureMixin.post,
        # qui appelle form.save() directement plutôt que le form_valid par
        # défaut) : nécessaire notamment pour une facture partagée sans
        # animal renseigné, où Facture.save() ne peut pas déduire le compte
        # depuis un animal absent.
        if user is not None:
            self.instance.utilisateur = user
        # Animaux visibles du compte connecté (lui-même, plus les autres
        # membres de son foyer partagé le cas échéant — cf.
        # accueil.utils.comptes_accessibles).
        self.fields['animal'].queryset = Animal.objects.filter(utilisateur__in=comptes_accessibles(user))
        # Le champ vide signifie « facture partagée entre tous les animaux »
        # dans le calcul du coût de revient (cf. Facture.cout_revient_animal)
        # — on le dit explicitement plutôt que de laisser l'option vide
        # générique de Django (« - Choisir une option - »).
        self.fields['animal'].empty_label = "Tous les animaux (facture partagée)"
        if verrouillee:
            # Facture déjà ventilée précédemment : ses champs propres sont
            # figés, seules les lignes (formset) restent modifiables (cf.
            # FactureUpdateView et LigneFactureForm).
            for champ in self.fields.values():
                champ.disabled = True


class DesignationForm(forms.ModelForm):
    """Formulaire de la modale « Ajouter une désignation absente du
    catalogue » (même principe que les modales Vétérinaire/Vaccin)."""

    class Meta:
        model = Designation
        fields = ['nom']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
        }


class LigneFactureForm(forms.ModelForm):
    """Une ligne de la ventilation d'une facture. Le champ `animal` du
    modèle et le booléen `pour_tous_les_animaux` sont fusionnés côté
    formulaire en un unique sélecteur `cible` (soit un animal précis, soit
    « Tous les animaux »)."""

    TOUS_LES_ANIMAUX = 'TOUS'

    cible = forms.ChoiceField(label="Animal concerné")

    class Meta:
        model = LigneFacture
        fields = ['designation', 'quantite', 'prix_unitaire']
        widgets = {
            'designation': forms.Select(attrs={'class': 'form-select ligne-designation'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control ligne-quantite', 'step': '0.01', 'min': '0.01'}),
            'prix_unitaire': forms.NumberInput(attrs={'class': 'form-control ligne-prix-unitaire', 'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cible'].widget.attrs['class'] = 'form-select ligne-cible'
        # Animaux visibles du compte connecté (lui-même, plus les autres
        # membres de son foyer partagé le cas échéant).
        self.fields['cible'].choices = (
            [(self.TOUS_LES_ANIMAUX, 'Tous les animaux')]
            + [(str(a.pk), a.nom) for a in Animal.objects.filter(utilisateur__in=comptes_accessibles(user))]
        )

        if self.instance.pk:
            self.fields['cible'].initial = (
                self.TOUS_LES_ANIMAUX if self.instance.pour_tous_les_animaux
                else str(self.instance.animal_id)
            )
            # Ligne déjà enregistrée : seule la cible (animal) reste
            # modifiable, désignation/quantité/prix sont figés.
            self.fields['designation'].disabled = True
            self.fields['quantite'].disabled = True
            self.fields['prix_unitaire'].disabled = True
        else:
            self.fields['cible'].initial = self.TOUS_LES_ANIMAUX

    def clean(self):
        cleaned_data = super().clean()
        # Reporté sur l'instance ici (plutôt que dans save()) : ModelForm
        # appelle instance.full_clean()/clean() juste après, qui a besoin de
        # voir animal/pour_tous_les_animaux déjà à jour pour sa validation
        # « l'un des deux, pas les deux » (cf. LigneFacture.clean()).
        cible = cleaned_data.get('cible')
        if cible == self.TOUS_LES_ANIMAUX:
            self.instance.pour_tous_les_animaux = True
            self.instance.animal_id = None
        elif cible:
            self.instance.pour_tous_les_animaux = False
            self.instance.animal_id = int(cible)
        return cleaned_data


LigneFactureFormSet = inlineformset_factory(
    Facture, LigneFacture, form=LigneFactureForm,
    extra=1, can_delete=True,
)
