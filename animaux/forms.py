import re
import unicodedata

from django import forms
from django.db.models import Q

from accueil.utils import comptes_accessibles
from .models import Animal, AnimalIdentification, Poids, Espece, Robe, Race, Organisme, Proprietaire
from .widgets import FichierSansLienInput


def generer_code(nom, secours='AUTRE'):
    """Dérive un code technique (majuscules, underscores) à partir d'un nom
    libre, pour les entités dont le code n'est pas saisi par l'utilisateur
    (nouvelle espèce ou nouvelle robe créée à la volée depuis le formulaire
    animal). Les accents sont retirés avant le filtrage (« Élan » donne ELAN
    et non LAN), ce qui correspond aux codes du catalogue (« Équidé » ->
    EQUIDE, « Tigré » -> TIGRE)."""
    decompose = unicodedata.normalize('NFD', nom or '')
    base = ''.join(c for c in decompose if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Za-z0-9]+', '_', base).strip('_').upper()[:20] or secours


def nettoyer_nom_catalogue(nom):
    """Nom d'une espèce ou d'une robe ajoutée à la volée : refusé s'il ne
    contient ni lettre ni chiffre, car son code retomberait alors sur celui
    de l'entrée générique « Autre »."""
    nom = nom.strip()
    if not generer_code(nom, secours=''):
        raise forms.ValidationError("Saisis un nom contenant au moins une lettre ou un chiffre.")
    return nom


def entree_catalogue(model, nom):
    """Entrée de `model` (Espece ou Robe) portant déjà ce nom ou le code qui
    en est dérivé, None sinon. Le code étant unique et sans accents, deux noms
    qui ne diffèrent que par un accent ou une ponctuation (« Tigre » /
    « Tigré », « Equide » / « Équidé ») désignent la même entrée : on la
    réutilise au lieu de tenter une création vouée à l'IntegrityError."""
    return (
        model.objects.filter(nom__iexact=nom).first()
        or model.objects.filter(code=generer_code(nom)).first()
    )


def sans_accents(texte):
    """Texte en minuscules et sans accents, pour comparer des noms sans tenir
    compte ni des uns ni des autres (« equide » retrouve « Équidé »)."""
    decompose = unicodedata.normalize('NFD', texte or '')
    return ''.join(c for c in decompose if unicodedata.category(c) != 'Mn').lower()


def identifiant(valeur):
    """Clé primaire (sous forme de chaîne) portée par la valeur d'un champ de
    formulaire — instance de modèle, entier ou saisie brute —, chaîne vide si
    elle n'en désigne aucune."""
    valeur = getattr(valeur, 'pk', valeur)
    valeur = '' if valeur is None else str(valeur)
    return valeur if valeur.isdigit() else ''


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
            'race': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'proprietaire': forms.Select(attrs={'class': 'form-select'}),
            'robe': forms.Select(attrs={'class': 'form-select'}),
            'photo': FichierSansLienInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, user=None, recherche_race='', **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Propriétaires actifs visibles du compte connecté (lui-même, plus les
        # autres membres de son foyer partagé le cas échéant — cf.
        # accueil.utils.comptes_accessibles) : une fiche « supprimée »
        # (Proprietaire.actif=False) n'est plus proposée pour un nouvel animal,
        # mais reste sélectionnée si c'est déjà la valeur de l'animal en cours
        # de modification (pour ne pas casser l'édition).
        self.fields['proprietaire'].queryset = self._queryset_actifs_ou_valeur_actuelle(
            Proprietaire.objects.filter(utilisateur__in=comptes_accessibles(user)), 'proprietaire'
        )

        # Espèce/robe : masque l'entrée générique « Autre » du catalogue,
        # remplacée par le bouton « + » qui crée une vraie nouvelle entrée
        # (cf. EspeceQuickAddForm / RobeQuickAddForm) plutôt que de router
        # tout le monde vers un choix fourre-tout. On la réintègre toutefois
        # si c'est déjà la valeur de l'animal en cours de modification, pour
        # ne pas casser l'édition d'une fiche existante qui l'utilise encore.
        self.fields['espece'].queryset = self._queryset_sans_autre(Espece, 'espece')
        self.fields['robe'].queryset = self._queryset_sans_autre(Robe, 'robe')

        self.fields['race'].choices = self._choix_races(recherche_race)

    def _choix_races(self, recherche=''):
        """Choix du menu « Race », limités aux races de l'espèce sélectionnée
        (toutes si aucune) et, si `recherche` est renseigné, à celles dont le
        nom contient ce texte (sans tenir compte des accents ni des
        majuscules) — c'est le serveur qui filtre, à chaque changement
        d'espèce ou frappe dans le champ « Filtrer les races » (htmx, cf.
        animaux/formulaire.py), au lieu de faire défiler plusieurs centaines
        de races. La race déjà sélectionnée reste toujours proposée, même si
        elle ne correspond ni à l'espèce ni à la recherche : filtrer
        l'affichage ne doit jamais faire perdre une valeur.

        Les races sont regroupées par espèce puis par catégorie (optgroup
        « Espèce — Catégorie ») : un <select> ne supporte qu'un seul niveau
        d'optgroup, la catégorie est donc intégrée au libellé plutôt
        qu'imbriquée. Elle vient du champ `categorie` (chats, NAC) ou, à
        défaut, de `groupe_fci` (chiens) — cf. static/data/races_*.json.
        Seul l'affichage est filtré : la validation porte toujours sur
        l'ensemble des races (queryset du champ), cf. clean()."""
        espece_id = identifiant(self['espece'].value())
        race_id = identifiant(self['race'].value())
        races = Race.objects.select_related('espece')
        if espece_id:
            filtre = Q(espece_id=espece_id)
            if race_id:
                filtre |= Q(pk=race_id)
            races = races.filter(filtre)

        motif = sans_accents(recherche).strip()
        groupes = {}
        for race in races:
            if motif and str(race.pk) != race_id and motif not in sans_accents(race.nom):
                continue
            cle = (race.espece.nom, self._libelle_categorie_race(race))
            groupes.setdefault(cle, []).append((race.pk, race.nom))

        choices = [('', '---------')]
        # Par espèce, les races sans catégorie d'abord (optgroup « Espèce »
        # simple), puis une optgroup par catégorie triée alphabétiquement.
        for espece_nom, categorie in sorted(groupes, key=lambda c: (sans_accents(c[0]), c[1] != '', c[1])):
            libelle = f"{espece_nom} — {categorie}" if categorie else espece_nom
            choices.append((libelle, groupes[(espece_nom, categorie)]))
        if motif and not groupes:
            choices.append(('Aucune race ne correspond à ce filtre', []))
        return choices

    def _queryset_sans_autre(self, model, champ_instance):
        """Queryset de `model` (Espece ou Robe) sans l'entrée générique
        « Autre », sauf si c'est déjà la valeur actuelle de l'animal en
        cours de modification (édition d'une fiche existante qui l'utilise)
        ou la valeur en cours de saisie — menu redessiné par htmx à partir
        d'un formulaire non lié (cf. formulaire._form_depuis_saisie), par
        exemple quand on choisit une race de l'espèce « Autre » : sans cela
        l'option disparaîtrait et le menu retomberait sur « --------- »."""
        queryset = model.objects.exclude(code='AUTRE')
        valeurs = {
            getattr(self.instance, f'{champ_instance}_id', None),
            int(identifiant(self[champ_instance].value()) or 0),
        } - {None, 0}
        if valeurs:
            queryset = model.objects.filter(
                Q(pk__in=queryset.values('pk')) | Q(pk__in=valeurs)
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
    d'AnimalForm : le formulaire animal en ajoute une nouvelle à la demande
    (htmx, cf. animaux/formulaire.py).

    `organisme_autre` (organisme saisi librement, alimenté par l'import CSV
    quand l'organisme n'est pas au catalogue) n'est volontairement pas un
    champ du formulaire : le gabarit ne le rendant pas, il revenait vide à
    chaque enregistrement et la valeur importée était effacée. Il est affiché
    en lecture seule sous le menu (cf. partials/identifications.html) et
    n'est remis à zéro que si l'on choisit un organisme du catalogue à la
    place (cf. save())."""

    class Meta:
        model = AnimalIdentification
        fields = ['organisme', 'identification']
        widgets = {
            'organisme': forms.Select(attrs={'class': 'form-select'}),
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

    def save(self, commit=True):
        # Un organisme du catalogue remplace la saisie libre importée : sans
        # cela elle resterait en base, masquée, et réapparaîtrait le jour où
        # l'organisme serait retiré de la ligne.
        if self.instance.organisme_id:
            self.instance.organisme_autre = ''
        return super().save(commit=commit)


class BaseAnimalIdentificationFormSet(forms.BaseInlineFormSet):
    """Une identification déjà enregistrée dont on a vidé l'organisme et le
    numéro est supprimée à l'enregistrement, au lieu de subsister comme une
    ligne vide (affichée « — » sur la fiche). Une ligne qui ne porte qu'un
    organisme saisi librement (`organisme_autre`, hors formulaire) n'est pas
    vide : elle est conservée."""

    def _should_delete_form(self, form):
        if super()._should_delete_form(form):
            return True
        donnees = getattr(form, 'cleaned_data', None) or {}
        return bool(
            form.instance.pk and form.is_valid()
            and not donnees.get('organisme') and not donnees.get('identification')
            and not form.instance.organisme_autre
        )


AnimalIdentificationFormSet = forms.inlineformset_factory(
    Animal, AnimalIdentification,
    form=AnimalIdentificationForm, formset=BaseAnimalIdentificationFormSet,
    extra=1, can_delete=True,
)


class EspeceQuickAddForm(forms.Form):
    """Formulaire utilisé par le panneau « Ajouter une espèce » du formulaire
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
        return nettoyer_nom_catalogue(self.cleaned_data['nom'])

    def save(self):
        nom = self.cleaned_data['nom']
        espece = entree_catalogue(Espece, nom)
        if not espece:
            espece = Espece.objects.create(nom=nom, code=generer_code(nom))
        nom_race = (self.cleaned_data.get('nom_race') or '').strip() or 'Autre'
        race, _ = Race.objects.get_or_create(espece=espece, nom__iexact=nom_race, defaults={'nom': nom_race})
        return espece, race


class RaceQuickAddForm(forms.ModelForm):
    """Formulaire utilisé par le panneau « Ajouter une race » du formulaire animal.

    Seuls espèce/nom sont obligatoires (comme avant) ; les champs de fiche
    détaillée (dont ceux des catalogues static/data/ : degré de dangerosité
    de 1 à 5, certificat de détention, comportement, note) sont facultatifs pour ne pas bloquer l'ajout d'une race absente
    du catalogue quand on ne connaît pas toutes ces informations."""

    class Meta:
        model = Race
        fields = [
            'espece', 'nom',
            'echelle_dangerosite', 'certificat_detention', 'comportement', 'note',
            'origine', 'taille_min', 'taille_max', 'poids_min', 'poids_max',
            'esperance_vie', 'description',
        ]
        widgets = {
            'espece': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Bobtail'}),
            'echelle_dangerosite': forms.Select(attrs={'class': 'form-select'}),
            'comportement': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'note': forms.TextInput(attrs={'class': 'form-control'}),
            'certificat_detention': forms.NullBooleanSelect(attrs={'class': 'form-select'}),
            'origine': forms.TextInput(attrs={'class': 'form-control'}),
            'taille_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'taille_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'poids_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'poids_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'esperance_vie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 10-15 ans'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['echelle_dangerosite'].choices = [('', 'Non renseigné')] + [
            (valeur, f'{valeur} — {libelle}') for valeur, libelle in Race.EchelleDangerosite.choices
        ]
        self.fields['certificat_detention'].label = "Certificat de détention"
        self.fields['certificat_detention'].widget.choices = [
            ('unknown', 'Non renseigné'), ('true', 'Requis'), ('false', 'Non requis'),
        ]


class OrganismeQuickAddForm(forms.ModelForm):
    """Formulaire utilisé par le panneau « Ajouter un organisme » du
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
    cf. animaux/proprietaire_form.html) et du panneau « Ajouter un
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
        # pour que save() fonctionne sans argument supplémentaire — à la
        # création seulement : une fiche modifiée par un autre membre du
        # foyer reste rattachée à son créateur (cf. accueil.models.Foyer),
        # sinon elle changerait de compte à chaque modification.
        if user is not None and not self.instance.pk:
            self.instance.utilisateur = user

    def clean_email(self):
        email = self.cleaned_data['email']
        if self.user is not None:
            # Doublon au sein de tout le foyer partagé (pas seulement le
            # compte connecté) : jamais de fusion automatique de fiches
            # existantes (cf. décision produit), seulement un blocage à la
            # création/édition pour ne pas en recréer une de plus.
            doublon = Proprietaire.objects.filter(
                utilisateur__in=comptes_accessibles(self.user), email__iexact=email,
            )
            if self.instance.pk:
                doublon = doublon.exclude(pk=self.instance.pk)
            # Fiches actives seulement. Une fiche « supprimée »
            # (Proprietaire.actif=False, cf. ProprietaireDeleteView) portant
            # cet email ne bloque rien et n'est jamais réactivée ni reprise :
            # recréer ce propriétaire donne une fiche neuve, avec les seules
            # valeurs saisies (décision produit) — l'ancienne reste telle
            # quelle, archivée, sur les animaux qui la référencent. La
            # contrainte d'unicité en base ne porte que sur les fiches actives.
            if doublon.filter(actif=True).exists():
                raise forms.ValidationError(
                    "Un propriétaire avec cet email existe déjà dans ton compte ou chez un membre de ton foyer."
                )
        return email


class RobeQuickAddForm(forms.Form):
    """Formulaire utilisé par le panneau « Ajouter une robe » du formulaire
    animal. Seul le nom est saisi : le code technique (Robe.code, non
    éditorial) est dérivé automatiquement, comme pour la création d'une
    nouvelle espèce à la volée."""

    nom = forms.CharField(
        max_length=50,
        label="Nom de la robe",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Bringé'}),
    )

    def clean_nom(self):
        return nettoyer_nom_catalogue(self.cleaned_data['nom'])

    def save(self):
        nom = self.cleaned_data['nom']
        robe = entree_catalogue(Robe, nom)
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

    def clean_date(self):
        # `animal` n'est pas un champ du formulaire : Django exclut donc la
        # contrainte poids_unique_par_animal_et_date de la validation
        # automatique, et un doublon ne serait détecté qu'à l'INSERT
        # (IntegrityError, page 500). L'animal est posé sur l'instance par la
        # vue avant la validation (cf. PoidsCreateView.get_form_kwargs).
        date = self.cleaned_data['date']
        if self.instance.animal_id and Poids.objects.filter(
            animal_id=self.instance.animal_id, date=date,
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                "Une pesée existe déjà à cette date pour cet animal : modifie-la depuis la fiche de l'animal."
            )
        return date

# Borne haute des filtres d'âge de la recherche avancée : au-delà, l'année de
# naissance calculée sortirait de la plage de `date` (erreur 500).
AGE_MAX_RECHERCHE = 150


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
        min_value=0, max_value=AGE_MAX_RECHERCHE,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'})
    )
    max_age = forms.IntegerField(
        required=False,
        label="Âge maximum (ans)",
        min_value=0, max_value=AGE_MAX_RECHERCHE,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '20'})
    )
    robe = forms.ModelChoiceField(
        required=False,
        queryset=Robe.objects.all(),
        empty_label="Toutes",
        label="Robe",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
