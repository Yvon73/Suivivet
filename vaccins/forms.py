from django import forms
from accueil.utils import comptes_accessibles, filtre_catalogue
from animaux.models import Animal
from .models import SuiviVaccinTraitement, Vaccin, Traitement

class VaccinForm(forms.ModelForm):
    class Meta:
        model = Vaccin
        fields = ['nom', 'description']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Vaccin FeLV'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Entrée rattachée à son compte créateur (cf. Vaccin.utilisateur).
        if user is not None and not self.instance.pk:
            self.instance.utilisateur = user

class TraitementForm(forms.ModelForm):
    class Meta:
        model = Traitement
        fields = ['nom', 'classe', 'description']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Homéopathie'}),
            'classe': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Entrée rattachée à son compte créateur (cf. Traitement.utilisateur).
        if user is not None and not self.instance.pk:
            self.instance.utilisateur = user


class SuiviVaccinTraitementForm(forms.ModelForm):
    # Champ libre (pas une ForeignKey du modèle) : permet de sélectionner
    # plusieurs vaccins administrés le même jour (ex : rappel + primo-vaccination
    # combinés). Chaque vaccin sélectionné donnera sa propre entrée de suivi.
    # Un nouveau vaccin/traitement absent du catalogue se crée via le bouton
    # « + » (panneau htmx, cf. vaccins/form.html et ajouter_vaccin_rapide /
    # ajouter_traitement_rapide) plutôt que via une sélection « Autre » ici :
    # le catalogue est donc toujours à jour au moment de choisir dans ces listes.
    vaccins = forms.MultipleChoiceField(
        required=False,
        label="Vaccin(s)",
        help_text=(
            "Maintiens Ctrl (Cmd sur Mac) pour sélectionner plusieurs vaccins administrés le "
            "même jour. Choisis la première ligne vide pour tout désélectionner."
        ),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 10}),
    )
    traitement = forms.ChoiceField(
        required=False,
        label="Traitement",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    field_order = [
        'animal', 'date',
        'vaccins', 'numero_lot', 'date_prochaine_dose',
        'traitement',
        'duree_traitement', 'dose_unite', 'dose_valeur', 'prise_matin', 'prise_midi', 'prise_soir',
        'notes',
    ]

    class Meta:
        model = SuiviVaccinTraitement
        fields = [
            'animal', 'traitement', 'date',
            'numero_lot', 'date_prochaine_dose',
            'duree_traitement', 'prise_matin', 'prise_midi', 'prise_soir',
            'dose_unite', 'dose_valeur',
            'notes',
        ]
        widgets = {
            'animal': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'numero_lot': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : LOT-2026-0142'}),
            'date_prochaine_dose': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'duree_traitement': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 7 jours'}),
            'prise_matin': forms.CheckboxInput(attrs={'class': 'btn-check'}),
            'prise_midi': forms.CheckboxInput(attrs={'class': 'btn-check'}),
            'prise_soir': forms.CheckboxInput(attrs={'class': 'btn-check'}),
            'dose_unite': forms.Select(attrs={'class': 'form-select'}),
            'dose_valeur': forms.Select(
                attrs={'class': 'form-select'},
                choices=[('', '---')] + [(i, i) for i in range(1, 101)],
            ),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Animaux visibles du compte connecté (lui-même, plus les autres
        # membres de son foyer partagé le cas échéant).
        self.fields['animal'].queryset = Animal.objects.filter(utilisateur__in=comptes_accessibles(user))

        # Catalogues proposés : entrées de référence, plus celles du compte
        # connecté et de son foyer (jamais celles d'un autre compte : un pk
        # forgé est refusé, n'étant pas un choix valide) — et l'entrée déjà
        # choisie pour le suivi en cours de modification, même sortie du filtre.
        vaccins_proposes = Vaccin.objects.filter(
            filtre_catalogue(user, reference=True, garder=getattr(self.instance, 'vaccin_id', None))
        )
        traitements_proposes = Traitement.objects.filter(
            filtre_catalogue(user, reference=True, garder=getattr(self.instance, 'traitement_id', None))
        )

        # --- Liste « Vaccin(s) » : ligne vide (pour pouvoir tout désélectionner
        # d'un clic) + catalogue.
        vaccin_choices = [('', '— cliquer ici pour désélectionner —')]
        vaccin_choices += [(str(v.pk), v.nom) for v in vaccins_proposes]
        self.fields['vaccins'].choices = vaccin_choices

        # --- Liste « Traitement » : regroupée par classe (Comprimé, Crème,
        # Shampooing, ...) sous forme d'optgroups.
        choices = [('', '---------')]
        traitement_classe_map = {}
        for valeur, libelle in Traitement.Classe.choices:
            options = list(traitements_proposes.filter(classe=valeur).values_list('pk', 'nom'))
            if options:
                choices.append((libelle, options))
                for pk, _nom in options:
                    traitement_classe_map[str(pk)] = valeur
        self.fields['traitement'].choices = choices
        self.traitement_classe_map = traitement_classe_map

        if self.instance and self.instance.pk:
            if self.instance.vaccin_id:
                self.fields['vaccins'].initial = [str(self.instance.vaccin_id)]
            if self.instance.traitement_id:
                self.fields['traitement'].initial = str(self.instance.traitement_id)

    # Classes de traitement pour lesquelles une « Dose » (unité + valeur) a un sens.
    CLASSES_AVEC_DOSE = (Traitement.Classe.COMPRIME, Traitement.Classe.SOLUTION_BUVABLE)

    def preparer_blocs(self):
        """Règle l'affichage des blocs « Vaccin(s) » / « Traitement » d'après
        la sélection en cours (à appeler avant le rendu, cf. vaccins/views.py) :
        dès qu'un des deux est renseigné, l'autre est grisé pour éviter une
        saisie incohérente, et le bloc « Dose » n'apparaît (`afficher_dose`)
        que pour un comprimé ou une solution buvable. Purement visuel : seul
        l'attribut HTML `disabled` est posé, la validation reste dans clean()."""
        vaccins = [valeur for valeur in (self['vaccins'].value() or []) if valeur]
        traitement = self['traitement'].value() or ''
        if vaccins and not traitement:
            self.fields['traitement'].widget.attrs['disabled'] = True
        if traitement and not vaccins:
            self.fields['vaccins'].widget.attrs['disabled'] = True
        self.afficher_dose = self.traitement_classe_map.get(str(traitement)) in self.CLASSES_AVEC_DOSE

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            # Un autre champ est déjà en erreur (ex : date manquante) : on doit
            # tout de même renvoyer une valeur "traitement" exploitable (None
            # ou instance existante, jamais une chaîne brute) pour que le
            # ModelForm puisse construire son instance sans planter.
            valeur = cleaned_data.get('traitement')
            cleaned_data['traitement'] = Traitement.objects.filter(pk=valeur).first() if valeur else None
            return cleaned_data

        valeurs_vaccins = [v for v in (cleaned_data.get('vaccins') or []) if v]
        vaccins = Vaccin.objects.filter(pk__in=valeurs_vaccins)
        valeur_traitement = cleaned_data.get('traitement')
        traitement = Traitement.objects.filter(pk=valeur_traitement).first() if valeur_traitement else None
        cleaned_data['vaccins'] = vaccins
        cleaned_data['traitement'] = traitement

        if not vaccins and not traitement:
            raise forms.ValidationError("Sélectionne au moins un vaccin ou un traitement.")
        if vaccins and traitement:
            raise forms.ValidationError("Choisis soit un ou plusieurs vaccins, soit un traitement, pas les deux.")

        if traitement:
            # Champs propres au vaccin non pertinents pour un traitement.
            cleaned_data['numero_lot'] = ''
            cleaned_data['date_prochaine_dose'] = None
            # La « Dose » (unité + valeur) n'a de sens que pour un comprimé ou
            # une solution buvable.
            if traitement.classe not in (Traitement.Classe.COMPRIME, Traitement.Classe.SOLUTION_BUVABLE):
                cleaned_data['dose_unite'] = ''
                cleaned_data['dose_valeur'] = None
        else:
            # Champs propres au traitement non pertinents pour un ou plusieurs vaccins.
            cleaned_data['duree_traitement'] = ''
            cleaned_data['prise_matin'] = False
            cleaned_data['prise_midi'] = False
            cleaned_data['prise_soir'] = False
            cleaned_data['dose_unite'] = ''
            cleaned_data['dose_valeur'] = None
            # Un rappel antérieur à l'injection ne serait jamais proposé.
            date_administration = cleaned_data.get('date')
            date_rappel = cleaned_data.get('date_prochaine_dose')
            if date_administration and date_rappel and date_rappel < date_administration:
                self.add_error(
                    'date_prochaine_dose',
                    "La date de rappel ne peut pas être antérieure à la date d'administration.",
                )
        return cleaned_data
