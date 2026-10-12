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
    mode_sombre = forms.BooleanField(
        required=False, label="Mode sombre",
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

    def clean_email(self):
        # L'email identifie le compte pour les invitations de foyer et les
        # notifications (cf. notifications.utils.resoudre_utilisateur) : un
        # second compte avec la même adresse, à la casse près, rendrait le
        # premier impossible à inviter et à notifier.
        email = self.cleaned_data['email'].strip()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet email.")
        return email

    def creer_preferences_accessibilite(self, utilisateur, taille_visiteur=None):
        """À appeler après la création du compte (cf. PremierUtilisateurCreateView).

        `taille_visiteur` : taille de texte que le visiteur avait réglée dans
        le panneau accessibilité avant de créer son compte (cf.
        PreferencesVisiteurMixin) — la case « Texte agrandi » ne distinguant
        pas « grand » de « très grand », c'est elle qui conserve ce dernier."""
        if not self.cleaned_data.get('texte_agrandi'):
            taille = PreferenceAccessibilite.Taille.NORMAL
        elif taille_visiteur == PreferenceAccessibilite.Taille.TRES_GRAND:
            taille = PreferenceAccessibilite.Taille.TRES_GRAND
        else:
            taille = PreferenceAccessibilite.Taille.GRAND
        return PreferenceAccessibilite.objects.create(
            utilisateur=utilisateur,
            taille_texte=taille,
            contraste_eleve=self.cleaned_data.get('contraste_eleve', False),
            police_lisible=self.cleaned_data.get('police_lisible', False),
            reduire_animations=self.cleaned_data.get('reduire_animations', False),
            palette_daltonisme=self.cleaned_data.get('palette_daltonisme', False),
            mode_sombre=self.cleaned_data.get('mode_sombre', False),
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
        email = self.cleaned_data['email']
        # Insensible à la casse (l'email est enregistré tel que saisi à
        # l'inscription), et un seul compte exactement : en cas de doublon
        # hérité, on ne choisit pas au hasard à qui ouvrir le foyer.
        comptes = list(get_user_model().objects.filter(email__iexact=email)[:2])
        invite = comptes[0] if len(comptes) == 1 else None
        if invite is None:
            raise forms.ValidationError("Aucun compte ne correspond à cet email.")
        if invite == self.utilisateur:
            raise forms.ValidationError("Tu ne peux pas t'inviter toi-même.")
        # Un foyer où l'invité est seul (créé à la volée par une invitation
        # qu'il a envoyée, puis annulée ou refusée) ne partage rien : il ne
        # doit pas l'empêcher d'être invité (cf. accepter_invitation_foyer,
        # qui supprime ce foyer vide à l'acceptation).
        membre = MembreFoyer.objects.filter(utilisateur=invite).first()
        if membre and MembreFoyer.objects.filter(foyer=membre.foyer_id).exclude(pk=membre.pk).exists():
            raise forms.ValidationError("Ce compte appartient déjà à un foyer.")
        if InvitationFoyer.objects.filter(
            invite_par=self.utilisateur, email_invite__iexact=email, statut=InvitationFoyer.Statut.EN_ATTENTE,
        ).exists():
            raise forms.ValidationError("Une invitation est déjà en attente pour cet email.")
        self.invite = invite
        return email
