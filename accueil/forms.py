from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import PreferenceAccessibilite


class PremierUtilisateurForm(UserCreationForm):
    """Création du tout premier compte de l'application (cf. AccueilView /
    PremierUtilisateurCreateView) : mêmes règles que UserCreationForm
    (identifiant + mot de passe confirmé deux fois), avec un email en plus
    (utilisé notamment par l'admin Django pour le contact du compte), et des
    cases à cocher pour activer d'emblée des options d'accessibilité — sans
    attendre que la personne pense à ouvrir le panneau accessibilité une fois
    connectée (cf. PreferenceAccessibilite, enregistrée par la vue à partir
    de ces champs)."""

    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )

    # --- Options d'accessibilité (facultatives), cf. PreferenceAccessibilite ---
    texte_agrandi = forms.BooleanField(
        required=False, label="Texte agrandi",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    contraste_eleve = forms.BooleanField(
        required=False, label="Contraste élevé",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    police_lisible = forms.BooleanField(
        required=False, label="Police plus lisible (basse vision)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    reduire_animations = forms.BooleanField(
        required=False, label="Réduire les animations",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    palette_daltonisme = forms.BooleanField(
        required=False, label="Palette adaptée daltonisme",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'username'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'new-password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'new-password'})

    def creer_preferences_accessibilite(self, utilisateur):
        """À appeler après la création du compte (cf. PremierUtilisateurCreateView)."""
        return PreferenceAccessibilite.objects.create(
            utilisateur=utilisateur,
            taille_texte=(
                PreferenceAccessibilite.Taille.GRAND
                if self.cleaned_data.get('texte_agrandi')
                else PreferenceAccessibilite.Taille.NORMAL
            ),
            contraste_eleve=self.cleaned_data.get('contraste_eleve', False),
            police_lisible=self.cleaned_data.get('police_lisible', False),
            reduire_animations=self.cleaned_data.get('reduire_animations', False),
            palette_daltonisme=self.cleaned_data.get('palette_daltonisme', False),
        )
