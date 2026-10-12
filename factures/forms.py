from django import forms
from django.forms import inlineformset_factory

from accueil.utils import comptes_accessibles, filtre_catalogue
from animaux.models import Animal
from animaux.widgets import FichierSansLienInput
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
            'fichier': FichierSansLienInput(attrs={
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
        # depuis un animal absent. À la création seulement : une facture
        # modifiée par un autre membre du foyer reste rattachée à son
        # créateur (cf. accueil.utils.comptes_accessibles), sinon elle
        # changerait de compte à chaque modification.
        if user is not None and not self.instance.utilisateur_id:
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
    """Formulaire de l'ajout rapide « Ajouter une désignation absente du
    catalogue » (même principe que les ajouts rapides Vétérinaire/Vaccin)."""

    class Meta:
        model = Designation
        fields = ['nom']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # `utilisateur` n'étant pas un champ du formulaire, Django n'applique
        # pas la contrainte d'unicité (utilisateur, nom) à la validation :
        # d'où clean_nom() ci-dessous.
        if user is not None and not self.instance.pk:
            self.instance.utilisateur = user

    def clean_nom(self):
        nom = self.cleaned_data['nom']
        if self.user is not None:
            # Doublon dans le compte ou chez un membre du foyer (la même
            # désignation y est déjà proposée) ; un autre compte peut, lui,
            # avoir la sienne sous le même nom. Même comparaison que le
            # regroupement des homonymes dans la liste des lignes (casse et
            # espaces de bord ignorés, cf. Designation.cle_nom) : « croquettes »
            # ne se crée pas à côté de « Croquettes », il y serait masqué.
            doublon = Designation.avec_cle_nom(
                Designation.objects.filter(filtre_catalogue(self.user))
            ).filter(cle_nom=Designation.cle_nom(nom))
            if self.instance.pk:
                doublon = doublon.exclude(pk=self.instance.pk)
            if doublon.exists():
                raise forms.ValidationError(
                    "Cette désignation existe déjà dans ton catalogue ou celui d'un membre de ton foyer."
                )
        return nom


class LigneFactureForm(forms.ModelForm):
    """Une ligne de la ventilation d'une facture. Le champ `animal` du
    modèle et le booléen `pour_tous_les_animaux` sont fusionnés côté
    formulaire en un unique sélecteur `cible` (soit un animal précis, soit
    « Tous les animaux »)."""

    TOUS_LES_ANIMAUX = 'TOUS'
    ANIMAL_SUPPRIME = '— Animal supprimé : à réattribuer —'

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
        # Désignations du compte connecté et de son foyer (jamais celles d'un
        # autre compte) — et celle déjà portée par la ligne, même sortie du
        # filtre. C'est ce queryset qui valide la valeur postée ; les options
        # affichées, elles, sont dédoublonnées en fin de constructeur (cf.
        # _choix_designations).
        self.fields['designation'].queryset = Designation.objects.filter(
            filtre_catalogue(user, garder=self.instance.designation_id)
        )
        # Animaux visibles du compte connecté (lui-même, plus les autres
        # membres de son foyer partagé le cas échéant).
        self.fields['cible'].choices = (
            [(self.TOUS_LES_ANIMAUX, 'Tous les animaux')]
            + [(str(a.pk), a.nom) for a in Animal.objects.filter(utilisateur__in=comptes_accessibles(user))]
        )

        if self.instance.pk:
            if self.instance.pour_tous_les_animaux:
                self.fields['cible'].initial = self.TOUS_LES_ANIMAUX
            elif self.instance.animal_id:
                self.fields['cible'].initial = str(self.instance.animal_id)
            else:
                # Ligne dont l'animal a été supprimé (SET_NULL) : une option
                # vide explicite, sinon aucune option ne serait sélectionnée,
                # le navigateur afficherait « Tous les animaux » et le
                # prochain enregistrement en ferait, sans le dire, une ligne
                # partagée. Le champ étant obligatoire, il faut choisir.
                self.fields['cible'].choices = (
                    [('', self.ANIMAL_SUPPRIME)] + list(self.fields['cible'].choices)
                )
                self.fields['cible'].initial = ''
            # Ligne déjà enregistrée : seule la cible (animal) reste
            # modifiable, désignation/quantité/prix sont figés.
            self.fields['designation'].disabled = True
            self.fields['quantite'].disabled = True
            self.fields['prix_unitaire'].disabled = True
        else:
            self.fields['cible'].initial = self.TOUS_LES_ANIMAUX

        # En dernier : la valeur courante du champ dépend de `disabled`.
        self.fields['designation'].choices = self._choix_designations(user)

    def _choix_designations(self, user):
        """Options du menu « Désignation » : une seule par nom (cf.
        Designation.cle_nom). Dans un foyer, deux membres peuvent avoir créé
        chacun leur « Croquettes » avant de se rejoindre : deux options
        identiques n'auraient aucun sens à l'écran. Est retenue, dans
        l'ordre : la désignation que porte déjà la ligne (enregistrée ou en
        cours de saisie), sinon celle du compte connecté, sinon la plus
        ancienne.

        Seul l'affichage est concerné : la validation reste faite sur le
        queryset complet, donc la clé d'un homonyme masqué mais accessible
        (ligne existante, page ouverte avant le regroupement) reste acceptée."""
        champ = self.fields['designation']
        courante = str(self['designation'].value() or '')
        compte = getattr(user, 'pk', None)

        def rang(designation):
            return (str(designation.pk) != courante, designation.utilisateur_id != compte, designation.pk)

        designations = list(champ.queryset.order_by('nom', 'pk'))
        retenues = {}
        for designation in designations:
            cle = Designation.cle_nom(designation.nom)
            if cle not in retenues or rang(designation) < rang(retenues[cle]):
                retenues[cle] = designation
        choix = [] if champ.empty_label is None else [('', champ.empty_label)]
        choix += [
            (designation.pk, champ.label_from_instance(designation))
            for designation in designations
            if retenues[Designation.cle_nom(designation.nom)] is designation
        ]
        return choix

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
