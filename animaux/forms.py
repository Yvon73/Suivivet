import re

from django import forms
from django.db.models import Prefetch, Q
from .models import Animal, AnimalIdentification, Poids, Espece, Robe, Race, Organisme, Proprietaire


def generer_code(nom, secours='AUTRE'):
    """Dérive un code technique (majuscules, underscores) à partir d'un nom
    libre, pour les entités dont le code n'est pas saisi par l'utilisateur
    (nouvelle espèce ou nouvelle robe créée à la volée depuis le formulaire
    animal)."""
    return re.sub(r'[^A-Za-z0-9]+', '_', nom).strip('_').upper()[:20] or secours


class RaceSelect(forms.Select):
    """
    Select des races qui ajoute un attribut data-espece sur chaque <option>,
    utilisé côté client (voir animaux/form.html) pour ne proposer que les
    races de l'espèce sélectionnée sans jamais modifier les données stockées.
    """

    def __init__(self, *args, race_espece_map=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.race_espece_map = race_espece_map or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value:
            espece_id = self.race_espece_map.get(str(value))
            if espece_id is not None:
                option['attrs']['data-espece'] = str(espece_id)
        return option


class AnimalForm(forms.ModelForm):
    field_order = [
        'nom', 'photo', 'espece', 'race',
        'robe', 'date_naissance', 'date_deces', 'proprietaire',
    ]

    class Meta:
        model = Animal
        fields = [
            'nom', 'espece', 'race', 'photo',
            'date_naissance', 'date_deces', 'robe', 'proprietaire'
        ]
        widgets = {
            'date_naissance': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'date_deces': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'espece': forms.Select(attrs={'class': 'form-select'}),
            'race': RaceSelect(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'proprietaire': forms.Select(attrs={'class': 'form-select'}),
            'robe': forms.Select(attrs={'class': 'form-select'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Propriétaires actifs du compte connecté uniquement (chaque compte a
        # ses propres fiches Proprietaire, cf. Proprietaire.utilisateur) :
        # une fiche « supprimée » (Proprietaire.actif=False) n'est plus proposée
        # pour un nouvel animal, mais reste sélectionnée si c'est déjà la valeur
        # de l'animal en cours de modification (pour ne pas casser l'édition).
        self.fields['proprietaire'].queryset = self._queryset_actifs_ou_valeur_actuelle(
            Proprietaire.objects.filter(utilisateur=user), 'proprietaire'
        )

        # Espèce/robe : masque l'entrée générique « Autre » du catalogue,
        # remplacée par le bouton « + » qui crée une vraie nouvelle entrée
        # (cf. EspeceQuickAddForm / RobeQuickAddForm) plutôt que de router
        # tout le monde vers un choix fourre-tout. On la réintègre toutefois
        # si c'est déjà la valeur de l'animal en cours de modification, pour
        # ne pas casser l'édition d'une fiche existante qui l'utilise encore.
        self.fields['espece'].queryset = self._queryset_sans_autre(Espece, 'espece')
        self.fields['robe'].queryset = self._queryset_sans_autre(Robe, 'robe')

        # Regrouper les races par espèce puis par catégorie dans le menu
        # déroulant (optgroup «Espèce — Catégorie»), à l'image du champ
        # combiné «Vaccin ou traitement» de l'app vaccins. Un <select> ne
        # supporte qu'un seul niveau d'optgroup : la catégorie est donc
        # intégrée au libellé plutôt qu'imbriquée. La catégorie vient du
        # champ `categorie` (chats, NAC) ou, à défaut, de `groupe_fci`
        # (chiens) — cf. static/data/races_*.json.
        choices = [('', '---------')]
        race_espece_map = {}
        especes = Espece.objects.prefetch_related(
            Prefetch('races', queryset=Race.objects.select_related('espece'))
        )
        for espece in especes:
            races = list(espece.races.all())
            if not races:
                continue
            races_par_categorie = {}
            ordre_categories = []
            for race in races:
                categorie = self._libelle_categorie_race(race)
                if categorie not in races_par_categorie:
                    races_par_categorie[categorie] = []
                    ordre_categories.append(categorie)
                races_par_categorie[categorie].append((race.pk, race.nom))
                race_espece_map[str(race.pk)] = espece.pk
            # Les races sans catégorie d'abord (optgroup «Espèce» simple),
            # puis une optgroup par catégorie triée alphabétiquement.
            for categorie in sorted(ordre_categories, key=lambda c: (c != '', c)):
                libelle = f"{espece.nom} — {categorie}" if categorie else espece.nom
                choices.append((libelle, races_par_categorie[categorie]))
        self.fields['race'].choices = choices
        self.fields['race'].widget.race_espece_map = race_espece_map

    def _queryset_sans_autre(self, model, champ_instance):
        """Queryset de `model` (Espece ou Robe) sans l'entrée générique
        « Autre », sauf si c'est déjà la valeur actuelle de l'animal en
        cours de modification (édition d'une fiche existante qui l'utilise)."""
        queryset = model.objects.exclude(code='AUTRE')
        valeur_id = getattr(self.instance, f'{champ_instance}_id', None)
        if valeur_id and not queryset.filter(pk=valeur_id).exists():
            queryset = model.objects.filter(
                Q(pk__in=queryset.values('pk')) | Q(pk=valeur_id)
            )
        return queryset

    def _queryset_actifs_ou_valeur_actuelle(self, base_queryset, champ_instance):
        """Restreint `base_queryset` (Proprietaire d'un compte donné...) aux
        fiches actives, sauf si c'est déjà la valeur actuelle de l'instance en
        cours de modification (fiche « supprimée » mais conservée en base,
        pour ne pas casser l'édition d'une fiche existante qui la référence
        encore)."""
        model = base_queryset.model
        queryset = base_queryset.filter(actif=True)
        valeur_id = getattr(self.instance, f'{champ_instance}_id', None)
        if valeur_id and not queryset.filter(pk=valeur_id).exists():
            queryset = base_queryset.filter(Q(actif=True) | Q(pk=valeur_id))
        return queryset

    @staticmethod
    def _libelle_categorie_race(race):
        """Libellé de regroupement d'une race dans le menu déroulant :
        `categorie` (type de poil pour un chat, famille pour un NAC...) ou,
        à défaut, le groupe FCI pour un chien — raccourci avant le premier
        « : » (« Groupe 1 : Chiens de berger... » -> « Groupe 1 ») pour
        rester lisible en optgroup. Chaîne vide si la race n'a ni l'un ni
        l'autre (races sans fiche détaillée), ou si la catégorie ne fait que
        répéter le nom de l'espèce (ex. NAC « Rongeur » classés sous
        l'espèce Rongeur : l'optgroup « Rongeur — Rongeur » n'apporterait rien)."""
        valeur = race.categorie or race.groupe_fci
        if not valeur:
            return ''
        libelle = valeur.split(':', 1)[0].strip()
        if libelle.lower() == race.espece.nom.lower():
            return ''
        return libelle

    def clean(self):
        cleaned_data = super().clean()
        espece = cleaned_data.get('espece')
        race = cleaned_data.get('race')
        if espece and race and race.espece_id != espece.pk:
            self.add_error('race', "Cette race ne correspond pas à l'espèce sélectionnée.")
        return cleaned_data


class AnimalIdentificationForm(forms.ModelForm):
    """Une ligne « organisme + identification » du formulaire animal. Un animal
    pouvant être enregistré auprès de plusieurs organismes, ce formulaire est
    utilisé via AnimalIdentificationFormSet plutôt que comme des champs directs
    d'AnimalForm : le bouton « + » du formulaire animal en ajoute une nouvelle
    à la volée (cf. animaux/form.html)."""

    class Meta:
        model = AnimalIdentification
        fields = ['organisme', 'organisme_autre', 'identification']
        widgets = {
            'organisme': forms.Select(attrs={'class': 'form-select'}),
            'organisme_autre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': "Nom de l'organisme si absent de la liste",
            }),
            'identification': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Regrouper les organismes par espèce (optgroup), sans filtrage strict
        # à l'espèce de l'animal contrairement à la race : un organisme
        # (registre, fédération...) est une information déclarative qui ne
        # doit jamais bloquer la saisie, et certaines espèces d'organismes
        # (Cheval, Abeille, Pigeon) n'ont pas d'équivalent dans le référentiel
        # Espece de l'application.
        organisme_choices = [('', '---------')]
        especes_par_code = dict(Organisme.Espece.choices)
        for code, _libelle in Organisme.Espece.choices:
            organismes = list(
                Organisme.objects.filter(espece=code).values_list('pk', 'nom_court')
            )
            if organismes:
                organisme_choices.append((especes_par_code[code], organismes))
        self.fields['organisme'].choices = organisme_choices
        self.fields['organisme'].required = False

    def clean_identification(self):
        # Normaliser en None plutôt qu'une chaîne vide : l'identification n'est
        # possible qu'à partir de 2-3 mois, donc plusieurs animaux peuvent ne pas
        # encore en avoir. Avec None, la contrainte d'unicité ne les compare pas
        # entre elles (contrairement à plusieurs chaînes vides "").
        return self.cleaned_data.get('identification') or None


AnimalIdentificationFormSet = forms.inlineformset_factory(
    Animal, AnimalIdentification,
    form=AnimalIdentificationForm,
    extra=1, can_delete=True,
)


class EspeceQuickAddForm(forms.Form):
    """Formulaire utilisé par la modale « Ajouter une espèce » du formulaire
    animal (remplace l'ancien choix « Autre » du menu déroulant). Crée
    l'espèce et, optionnellement, sa première race (par défaut « Autre » si
    non précisée) — même principe que RobeQuickAddForm."""

    nom = forms.CharField(
        max_length=50,
        label="Nom de l'espèce",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Furet'}),
    )
    nom_race = forms.CharField(
        required=False,
        max_length=100,
        label="Nom de la race (optionnel)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Par défaut : « Autre »'}),
    )

    def clean_nom(self):
        return self.cleaned_data['nom'].strip()

    def save(self):
        nom = self.cleaned_data['nom']
        espece = Espece.objects.filter(nom__iexact=nom).first()
        if not espece:
            espece = Espece.objects.create(nom=nom, code=generer_code(nom))
        nom_race = (self.cleaned_data.get('nom_race') or '').strip() or 'Autre'
        race, _ = Race.objects.get_or_create(espece=espece, nom__iexact=nom_race, defaults={'nom': nom_race})
        return espece, race


class RaceQuickAddForm(forms.ModelForm):
    """Formulaire utilisé par la modale « Ajouter une race » du formulaire animal.

    Seuls espèce/nom sont obligatoires (comme avant) ; les champs de fiche
    détaillée sont facultatifs pour ne pas bloquer l'ajout d'une race absente
    du catalogue quand on ne connaît pas toutes ces informations."""

    class Meta:
        model = Race
        fields = [
            'espece', 'nom', 'niveau_dangerosite',
            'origine', 'taille_min', 'taille_max', 'poids_min', 'poids_max',
            'esperance_vie', 'description',
        ]
        widgets = {
            'origine': forms.TextInput(attrs={'class': 'form-control'}),
            'taille_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'taille_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'poids_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'poids_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'esperance_vie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 10-15 ans'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class OrganismeQuickAddForm(forms.ModelForm):
    """Formulaire utilisé par la modale « Ajouter un organisme » du
    formulaire animal. Reprend exactement les champs des entrées du
    catalogue static/data/organismes_officiel.json (nom, nom_court,
    description, site_web, espece, pays, est_officiel) ; seuls nom, nom_court
    et espece sont obligatoires."""

    class Meta:
        model = Organisme
        fields = ['nom', 'nom_court', 'espece', 'pays', 'site_web', 'description', 'est_officiel']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : LOF (Livre des Origines Français)'}),
            'nom_court': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : LOF'}),
            'espece': forms.Select(attrs={'class': 'form-select'}),
            'pays': forms.TextInput(attrs={'class': 'form-control'}),
            'site_web': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'est_officiel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProprietaireForm(forms.ModelForm):
    """Formulaire de la fiche propriétaire (page dédiée d'ajout/modification,
    cf. animaux/proprietaire_form.html) et de la modale « Ajouter un
    propriétaire » du formulaire animal (mêmes champs)."""

    class Meta:
        model = Proprietaire
        fields = ['nom', 'prenom', 'adresse', 'code_postal', 'ville', 'telephone', 'email']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'code_postal': forms.TextInput(attrs={'class': 'form-control'}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # `utilisateur` n'est pas un champ du formulaire : Django exclut donc
        # automatiquement ce champ (et toute contrainte d'unicité qui le
        # mentionne, cf. Proprietaire.Meta.constraints) de la validation
        # d'unicité automatique du ModelForm — d'où la vérification manuelle
        # dans clean_email() ci-dessous. On le pose quand même sur l'instance
        # pour que save() fonctionne sans argument supplémentaire.
        if user is not None:
            self.instance.utilisateur = user

    def clean_email(self):
        email = self.cleaned_data['email']
        if self.user is not None:
            doublon = Proprietaire.objects.filter(utilisateur=self.user, email__iexact=email)
            if self.instance.pk:
                doublon = doublon.exclude(pk=self.instance.pk)
            if doublon.exists():
                raise forms.ValidationError("Un propriétaire avec cet email existe déjà dans ton compte.")
        return email


class RobeQuickAddForm(forms.Form):
    """Formulaire utilisé par la modale « Ajouter une robe » du formulaire
    animal. Seul le nom est saisi : le code technique (Robe.code, non
    éditorial) est dérivé automatiquement, comme pour la création d'une
    nouvelle espèce à la volée."""

    nom = forms.CharField(
        max_length=50,
        label="Nom de la robe",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Bringé'}),
    )

    def clean_nom(self):
        return self.cleaned_data['nom'].strip()

    def save(self):
        nom = self.cleaned_data['nom']
        robe = Robe.objects.filter(nom__iexact=nom).first()
        if robe:
            return robe
        return Robe.objects.create(nom=nom, code=generer_code(nom))


class PoidsForm(forms.ModelForm):
    class Meta:
        model = Poids
        fields = ['date', 'valeur']
        widgets = {
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'valeur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        }

class AnimalSearchForm(forms.Form):
    nom = forms.CharField(
        required=False,
        label="Nom",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Nom de l'animal"})
    )
    espece = forms.ModelChoiceField(
        required=False,
        queryset=Espece.objects.all(),
        empty_label="Toutes",
        label="Espèce",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    race = forms.CharField(
        required=False,
        label="Race",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Race'})
    )
    min_age = forms.IntegerField(
        required=False,
        label="Âge minimum (ans)",
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'})
    )
    max_age = forms.IntegerField(
        required=False,
        label="Âge maximum (ans)",
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '20'})
    )
    robe = forms.ModelChoiceField(
        required=False,
        queryset=Robe.objects.all(),
        empty_label="Toutes",
        label="Robe",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
