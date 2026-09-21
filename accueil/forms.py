from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import InvitationFoyer, MembreFoyer, PreferenceAccessibilite


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


class InvitationFoyerForm(forms.Form):
    """Formulaire d'envoi d'une invitation à partager son compte (cf.
    accueil.views.envoyer_invitation_foyer) — l'invité doit correspondre à un
    compte déjà existant (jamais d'invitation « à froid » par email seul, cf.
    décision produit) et ne pas déjà appartenir à un foyer."""

    email = forms.EmailField(
        label="Email du compte à inviter",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )

    def __init__(self, *args, utilisateur=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.utilisateur = utilisateur
        self.invite = None

    def clean_email(self):
        from notifications.utils import resoudre_utilisateur

        email = self.cleaned_data['email']
        invite = resoudre_utilisateur(email)
        if invite is None:
            raise forms.ValidationError("Aucun compte ne correspond à cet email.")
        if invite == self.utilisateur:
            raise forms.ValidationError("Tu ne peux pas t'inviter toi-même.")
        if MembreFoyer.objects.filter(utilisateur=invite).exists():
            raise forms.ValidationError("Ce compte appartient déjà à un foyer.")
        if InvitationFoyer.objects.filter(
            invite_par=self.utilisateur, email_invite__iexact=email, statut=InvitationFoyer.Statut.EN_ATTENTE,
        ).exists():
            raise forms.ValidationError("Une invitation est déjà en attente pour cet email.")
        self.invite = invite
        return email
