Oui, c'est tout à fait possible ! Voici une solution complète pour créer des masques de saisie intelligents pour les différents types d'identifiants des organismes de certification animaux (LOF, LOOF, SIRE, CITES, etc.).
Je vais te proposer plusieurs approches, avec des exemples concrets et du code prêt à l'emploi.
🎯 Objectif
Créer des champs de formulaire avec masques de saisie qui :
✅ Guident l'utilisateur en affichant le format attendu (ex: LOF-XXXXXX).
✅ Valident automatiquement le format saisi (ex: LOF-123456).
✅ S'adaptent dynamiquement en fonction de l'organisme sélectionné.
✅ Améliorent l'expérience utilisateur (UX).
📌 Approche 1 : Masques de Saisie avec JavaScript (Recommandé)
Utilisation de librairies JavaScript pour appliquer des masques dynamiques aux champs de formulaire.
🔹 Étape 1 : Installer une librairie de masquage
Nous allons utiliser Inputmask (léger, puissant, et compatible avec Django).
Installation via CDN (dans base.html)
Ajoute ces lignes dans le <head> ou avant la fermeture du <body> :
html
Copier

<!-- Dans base.html -->

<!-- Inputmask (pour les masques de saisie) -->

<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.0/jquery.min.js"></script>

<script src="https://cdnjs.cloudflare.com/ajax/libs/inputmask/5.0.8/jquery.inputmask.min.js"></script>

🔹 Étape 2 : Créer un Champ Personnalisé pour les Identifiants
Fichier animaux/forms.py
python
Copier

from django import forms
from .models import Animal, Organisme

class AnimalForm(forms.ModelForm):
class Meta:
model = Animal
fields = [
'nom', 'race', 'espece', 'identification',
'date_naissance', 'date_deces', 'lof', 'robe',
'propriétaire', 'organismes', 'numero_identification'
]
widgets = {
'date_naissance': forms.DateInput(attrs={'type': 'date'}),
'date_deces': forms.DateInput(attrs={'type': 'date'}),
'organismes': forms.Select(attrs={'class': 'form-select', 'id': 'id_organismes'}),
'numero_identification': forms.TextInput(attrs={
'class': 'form-control',
'id': 'id_numero_identification',
'placeholder': 'Ex: LOF-123456'
}),
}

def __init__(self, *args, **kwargs):
super().__init__(*args, **kwargs)

# Filtrer les organismes par espèce sélectionnée

if 'espece' in self.data:
espece = self.data['espece']
self.fields['organismes'].queryset = Organisme.objects.filter(espece=espece)
elif self.instance and self.instance.pk:
self.fields['organismes'].queryset = Organisme.objects.filter(espece=self.instance.espece)
🔹 Étape 3 : Ajouter le JavaScript pour les Masques
Fichier static/js/masques_identification.js
javascript
Copier

// Masques pour les identifiants des organismes
document.addEventListener('DOMContentLoaded', function() {
// Dictionnaire des masques par organisme
const masques = {
// Chiens
'LOF': 'LOF-999999',          // LOF-123456
'SCC': 'SCC-999999',          // SCC-123456
'FCI': 'FCI-999999',          // FCI-123456
'AKC': 'AKC-99999999',        // AKC-12345678
'The Kennel Club': 'KC-999999', // KC-123456

// Chats
'LOOF': 'LOOF-999999',        // LOOF-ABC123
'FIFé': 'FIFé-999999',         // FIFé-123456
'TICA': 'TICA-999999',         // TICA-123456
'GCCF': 'GCCF-999999',         // GCCF-123456

// Chevaux
'SIRE': 'SIRE-FR99999999',    // SIRE-FR12345678
'IFCE': 'IFCE-99999999',      // IFCE-12345678
'FEI': 'FEI-99999999',         // FEI-12345678

// Rongeurs
'UFA': 'UFA-999999',          // UFA-123456
'AFFA': 'AFFA-999999',        // AFFA-123456
'FFC': 'FFC-999999',          // FFC-123456

// Oiseaux
'SNOF': 'SNOF-999999',        // SNOF-123456
'OMJ': 'OMJ-999999',          // OMJ-123456

// Reptiles
'AFA': 'AFA-999999',          // AFA-123456
'CITES': 'CITES-FR-999999',   // CITES-FR-123456

// Poissons
'FFS': 'FFS-999999',          // FFS-123456

// Abeilles
'GDSA': 'GDSA-999999',        // GDSA-123456
'UNAF': 'UNAF-999999',        // UNAF-123456

// Pigeons
'FCPR': 'FCPR-999999',        // FCPR-123456
};

// Sélecteur pour le champ "organismes"
const organismeSelect = document.getElementById('id_organismes');
// Sélecteur pour le champ "numero_identification"
const numeroInput = document.getElementById('id_numero_identification');

if (organismeSelect && numeroInput) {
// Appliquer le masque en fonction de l'organisme sélectionné
organismeSelect.addEventListener('change', function() {
const selectedOrganisme = this.options[this.selectedIndex].text;
applyMask(selectedOrganisme);
});

// Appliquer le masque au chargement si un organisme est déjà sélectionné
if (organismeSelect.selectedIndex !== -1) {
const selectedOrganisme = organismeSelect.options[organismeSelect.selectedIndex].text;
applyMask(selectedOrganisme);
}
}

// Fonction pour appliquer le masque
function applyMask(organismeNom) {
// Réinitialiser le champ
numeroInput.value = '';

// Trouver le masque correspondant
for (const [nom, masque] of Object.entries(masques)) {
if (organismeNom.includes(nom)) {
// Appliquer le masque
$(numeroInput).inputmask(masque, {
placeholder: ' ',
clearIncomplete: true,
showMaskOnHover: true,
showMaskOnFocus: true
});
return;
}
}

// Si aucun masque ne correspond, désactiver le masquage
$(numeroInput).inputmask('remove');
numeroInput.placeholder = 'Ex: LOF-123456';
}
});

🔹 Étape 4 : Charger le Script dans le Template
Dans base.html, ajoute le chargement du script :
html
Copier

<!-- Dans base.html, avant la fermeture du </body> -->

{% block extra_js %}
{{ block.super }}

<script src="{% static 'js/masques_identification.js' %}"></script>

{% endblock %}

🔹 Étape 5 : Personnaliser les Masques
Tu peux ajuster les masques dans le dictionnaire masques pour correspondre aux formats réels des organismes.
Exemples de formats réels :
LOF : LOF-XXXXXX (6 chiffres).
LOOF : LOOF-XXX-XXXX (3 chiffres, tiret, 4 chiffres).
SIRE : FRXXXXXXXX (10 caractères alphanumériques, commençant par FR).
CITES : CITES-FR-XXXXX (5 chiffres après le préfixe).
📌 Approche 2 : Masques de Saisie avec HTML5 (Sans JavaScript)
Si tu préfères une solution sans JavaScript, tu peux utiliser l’attribut pattern de HTML5 pour valider les formats.
🔹 Exemple avec pattern
Fichier animaux/forms.py
python
Copier

from django import forms
from .models import Animal, Organisme

class AnimalForm(forms.ModelForm):
class Meta:
model = Animal
fields = [
'nom', 'race', 'espece', 'identification',
'date_naissance', 'date_deces', 'lof', 'robe',
'propriétaire', 'organismes', 'numero_identification'
]
widgets = {
'date_naissance': forms.DateInput(attrs={'type': 'date'}),
'date_deces': forms.DateInput(attrs={'type': 'date'}),
'organismes': forms.Select(attrs={'class': 'form-select', 'id': 'id_organismes'}),
'numero_identification': forms.TextInput(attrs={
'class': 'form-control',
'id': 'id_numero_identification',
'placeholder': 'Ex: LOF-123456',
'pattern': '^[A-Z]{2,4}-[0-9]{4,8}$',  # Exemple : LOF-123456
'title': 'Format invalide. Exemple : LOF-123456'
}),
}

def __init__(self, *args, **kwargs):
super().__init__(*args, **kwargs)

# Filtrer les organismes par espèce sélectionnée

if 'espece' in self.data:
espece = self.data['espece']
self.fields['organismes'].queryset = Organisme.objects.filter(espece=espece)
elif self.instance and self.instance.pk:
self.fields['organismes'].queryset = Organisme.objects.filter(espece=self.instance.espece)

# Mettre à jour le pattern en fonction de l'organisme sélectionné

if 'organismes' in self.data:
organisme_id = self.data['organismes']
organisme = Organisme.objects.filter(pk=organisme_id).first()
if organisme:
self.fields['numero_identification'].widget.attrs['pattern'] = self.get_pattern_for_organisme(organisme)
self.fields['numero_identification'].widget.attrs['title'] = f'Format : {self.get_placeholder_for_organisme(organisme)}'
def get_pattern_for_organisme(self, organisme):
patterns = {
'LOF': '^LOF-[0-9]{6}$',          # LOF-123456
'SCC': '^SCC-[0-9]{6}$',          # SCC-123456
'FCI': '^FCI-[0-9]{6}$',          # FCI-123456
'LOOF': '^LOOF-[0-9A-Z]{6}$',     # LOOF-ABC123
'SIRE': '^FR[0-9]{8}$',           # FR12345678
'CITES': '^CITES-FR-[0-9]{5}$',   # CITES-FR-12345
}
return patterns.get(organisme.nom_court, '^[A-Z0-9-]{6,15}$')  # Pattern par défaut

def get_placeholder_for_organisme(self, organisme):
placeholders = {
'LOF': 'LOF-123456',
'SCC': 'SCC-123456',
'FCI': 'FCI-123456',
'LOOF': 'LOOF-ABC123',
'SIRE': 'FR12345678',
'CITES': 'CITES-FR-12345',
}
return placeholders.get(organisme.nom_court, 'Ex: LOF-123456')
🔹 Limites de l’Approche HTML5
Moins flexible : Le pattern ne peut pas être modifié dynamiquement sans JavaScript.
Moins user-friendly : Pas de masquage automatique (l’utilisateur doit saisir le format correctement).
Moins de feedback visuel : Pas de guide visuel comme avec Inputmask.
📌 Approche 3 : Masques de Saisie avec Django et JavaScript (Recommandé)
Combinaison des deux approches pour une solution optimale :
Masquage dynamique avec JavaScript (Inputmask).
Validation côté serveur avec Django.
🔹 Étape 1 : Valider le Numéro d’Identification dans le Formulaire
Fichier animaux/forms.py
python
Copier

from django import forms
from django.core.exceptions import ValidationError
from .models import Animal, Organisme

class AnimalForm(forms.ModelForm):
class Meta:
model = Animal
fields = [
'nom', 'race', 'espece', 'identification',
'date_naissance', 'date_deces', 'lof', 'robe',
'propriétaire', 'organismes', 'numero_identification'
]
widgets = {
'date_naissance': forms.DateInput(attrs={'type': 'date'}),
'date_deces': forms.DateInput(attrs={'type': 'date'}),
'organismes': forms.Select(attrs={'class': 'form-select', 'id': 'id_organismes'}),
'numero_identification': forms.TextInput(attrs={
'class': 'form-control',
'id': 'id_numero_identification',
'placeholder': 'Ex: LOF-123456'
}),
}

def __init__(self, *args, **kwargs):
super().__init__(*args, **kwargs)

# Filtrer les organismes par espèce sélectionnée

if 'espece' in self.data:
espece = self.data['espece']
self.fields['organismes'].queryset = Organisme.objects.filter(espece=espece)
elif self.instance and self.instance.pk:
self.fields['organismes'].queryset = Organisme.objects.filter(espece=self.instance.espece)

def clean_numero_identification(self):
numero_identification = self.cleaned_data.get('numero_identification')
organismes = self.cleaned_data.get('organismes')

if numero_identification and organismes:
for organisme in organismes:
if not self.validate_numero_identification(numero_identification, organisme):
raise ValidationError(
f"Le numéro d'identification '{numero_identification}' ne correspond pas au format attendu pour {organisme.nom}. "
f"Exemple : {self.get_placeholder_for_organisme(organisme)}"
)
return numero_identification
def validate_numero_identification(self, numero, organisme):
patterns = {
'LOF': r'^LOF-[0-9]{6}$',          # LOF-123456
'SCC': r'^SCC-[0-9]{6}$',          # SCC-123456
'FCI': r'^FCI-[0-9]{6}$',          # FCI-123456
'LOOF': r'^LOOF-[0-9A-Z]{6}$',     # LOOF-ABC123
'SIRE': r'^FR[0-9]{8}$',           # FR12345678
'CITES': r'^CITES-FR-[0-9]{5}$',   # CITES-FR-12345
}
pattern = patterns.get(organisme.nom_court, r'^[A-Z0-9-]{6,15}$')
return bool(re.match(pattern, numero))

def get_placeholder_for_organisme(self, organisme):
placeholders = {
'LOF': 'LOF-123456',
'SCC': 'SCC-123456',
'FCI': 'FCI-123456',
'LOOF': 'LOOF-ABC123',
'SIRE': 'FR12345678',
'CITES': 'CITES-FR-12345',
}
return placeholders.get(organisme.nom_court, 'Ex: LOF-123456')
🔹 Étape 2 : Afficher les Erreurs dans le Template
Dans animaux/form.html, assure-toi que les erreurs sont bien affichées :
html
Copier

<div class="mb-3">
    {{ form.numero_identification.label_tag }}
    {{ form.numero_identification }}
    {% if form.numero_identification.errors %}
        <div class="text-danger">
            {{ form.numero_identification.errors|first }}
        </div>
    {% endif %}
    <div class="form-text">
        Format attendu : <span id="format-attendu">Ex: LOF-123456</span>
    </div>
</div>

🔹 Étape 3 : Mettre à Jour le JavaScript pour Afficher le Format Attendu
Fichier static/js/masques_identification.js (version mise à jour)
javascript
Copier

document.addEventListener('DOMContentLoaded', function() {
const masques = {
'LOF': { masque: 'LOF-999999', placeholder: 'LOF-123456' },
'SCC': { masque: 'SCC-999999', placeholder: 'SCC-123456' },
'FCI': { masque: 'FCI-999999', placeholder: 'FCI-123456' },
'LOOF': { masque: 'LOOF-999999', placeholder: 'LOOF-ABC123' },
'SIRE': { masque: 'FR99999999', placeholder: 'FR12345678' },
'CITES': { masque: 'CITES-FR-99999', placeholder: 'CITES-FR-12345' },
// Ajoute d'autres organismes ici
};

const organismeSelect = document.getElementById('id_organismes');
const numeroInput = document.getElementById('id_numero_identification');
const formatAttenduSpan = document.getElementById('format-attendu');

if (organismeSelect && numeroInput) {
organismeSelect.addEventListener('change', function() {
const selectedOption = this.options[this.selectedIndex];
const organismeNom = selectedOption.text;
const organismeId = selectedOption.value;

// Trouver le masque correspondant
for (const [nom, infos] of Object.entries(masques)) {
if (organismeNom.includes(nom)) {
applyMask(infos.masque, infos.placeholder);
return;
}
}

// Si aucun masque ne correspond, désactiver le masquage
resetMask();
});

// Appliquer le masque au chargement si un organisme est déjà sélectionné
if (organismeSelect.selectedIndex !== -1) {
const selectedOption = organismeSelect.options[organismeSelect.selectedIndex];
const organismeNom = selectedOption.text;

for (const [nom, infos] of Object.entries(masques)) {
if (organismeNom.includes(nom)) {
applyMask(infos.masque, infos.placeholder);
return;
}
}
}
}

function applyMask(masque, placeholder) {
$(numeroInput).inputmask(masque, {
placeholder: ' ',
clearIncomplete: true,
showMaskOnHover: true,
showMaskOnFocus: true
});
if (formatAttenduSpan) {
formatAttenduSpan.textContent = placeholder;
}
}

function resetMask() {
$(numeroInput).inputmask('remove');
if (formatAttenduSpan) {
formatAttenduSpan.textContent = 'Ex: LOF-123456';
}
}
});

📌 Approche 4 : Masques de Saisie avec des Champs Dynamiques
Si tu veux créer des champs dynamiques qui apparaissent uniquement quand un organisme est sélectionné, tu peux utiliser cette approche.
🔹 Étape 1 : Modifier le Formulaire pour Afficher un Champ par Organisme
Fichier animaux/forms.py
python
Copier

from django import forms
from .models import Animal, Organisme

class AnimalForm(forms.ModelForm):
class Meta:
model = Animal
fields = [
'nom', 'race', 'espece', 'identification',
'date_naissance', 'date_deces', 'lof', 'robe',
'propriétaire', 'organismes'
]
widgets = {
'date_naissance': forms.DateInput(attrs={'type': 'date'}),
'date_deces': forms.DateInput(attrs={'type': 'date'}),
'organismes': forms.Select(attrs={'class': 'form-select', 'id': 'id_organismes'}),
}

def __init__(self, *args, **kwargs):
super().__init__(*args, **kwargs)

# Filtrer les organismes par espèce sélectionnée

if 'espece' in self.data:
espece = self.data['espece']
self.fields['organismes'].queryset = Organisme.objects.filter(espece=espece)
elif self.instance and self.instance.pk:
self.fields['organismes'].queryset = Organisme.objects.filter(espece=self.instance.espece)

# Ajouter des champs dynamiques pour les numéros d'identification

for organisme in Organisme.objects.all():
self.fields[f'numero_{organisme.nom_court}'] = forms.CharField(
required=False,
label=f"Numéro {organisme.nom_court}",
widget=forms.TextInput(attrs={
'class': 'form-control d-none',
'id': f'id_numero_{organisme.nom_court}',
'placeholder': f'Ex: {organisme.nom_court}-123456'
})
)

# Masquer tous les champs dynamiques par défaut

for field_name in self.fields:
if field_name.startswith('numero_'):
self.fields[field_name].widget.attrs['class'] += ' d-none'
🔹 Étape 2 : Modifier le Template pour Afficher les Champs Dynamiques
Fichier animaux/form.html
html
Copier

<!-- Champ "organismes" -->

<div class="mb-3">
    {{ form.organismes.label_tag }}
    {{ form.organismes }}
    {% if form.organismes.errors %}
        <div class="text-danger">{{ form.organismes.errors }}</div>
    {% endif %}
</div>

<!-- Champs dynamiques pour les numéros d'identification -->

{% for field in form %}
{% if field.name.startswith('numero_') %}

<div class="mb-3 d-none" id="div_{{ field.name }}">
{{ field.label_tag }}
{{ field }}
{% if field.errors %}
<div class="text-danger">{{ field.errors }}</div>
{% endif %}
</div>
{% endif %}
{% endfor %}

🔹 Étape 3 : JavaScript pour Afficher/Masquer les Champs Dynamiques
Fichier static/js/masques_identification_dynamiques.js
javascript
Copier

document.addEventListener('DOMContentLoaded', function() {
const organismeSelect = document.getElementById('id_organismes');
const masques = {
'LOF': { placeholder: 'LOF-123456', masque: 'LOF-999999' },
'SCC': { placeholder: 'SCC-123456', masque: 'SCC-999999' },
'LOOF': { placeholder: 'LOOF-ABC123', masque: 'LOOF-999999' },
'SIRE': { placeholder: 'FR12345678', masque: 'FR99999999' },
'CITES': { placeholder: 'CITES-FR-12345', masque: 'CITES-FR-99999' },
};

if (organismeSelect) {
organismeSelect.addEventListener('change', function() {
const selectedOption = this.options[this.selectedIndex];
const organismeNom = selectedOption.text;
const organismeId = selectedOption.value;

// Masquer tous les champs dynamiques
document.querySelectorAll('[id^="div_numero_"]').forEach(el => {
el.classList.add('d-none');
});

// Trouver le champ correspondant
for (const [nom, infos] of Object.entries(masques)) {
if (organismeNom.includes(nom)) {
const fieldName = `numero_${nom}`;
const divId = `div_${fieldName}`;
const field = document.getElementById(`id_${fieldName}`);

if (field) {
    const div = document.getElementById(divId);
    if (div) {
        div.classList.remove('d-none');
        $(field).inputmask(infos.masque, {
            placeholder: ' ',
            clearIncomplete: true,
            showMaskOnHover: true,
            showMaskOnFocus: true
        });
    }
}
return;
}
}
});

// Afficher le champ correspondant au chargement
if (organismeSelect.selectedIndex !== -1) {
const selectedOption = organismeSelect.options[organismeSelect.selectedIndex];
const organismeNom = selectedOption.text;

for (const [nom, infos] of Object.entries(masques)) {
if (organismeNom.includes(nom)) {
const fieldName = `numero_${nom}`;
const divId = `div_${fieldName}`;
const div = document.getElementById(divId);
if (div) {
div.classList.remove('d-none');
const field = document.getElementById(`id_${fieldName}`);
if (field) {
$(field).inputmask(infos.masque, {
placeholder: ' ',
clearIncomplete: true,
showMaskOnHover: true,
showMaskOnFocus: true
});
}
}
return;
}
}
}
}
});

📌 Approche 5 : Utiliser une Librairie de Masquage Avancée (Cleave.js)
Si tu veux une solution plus moderne et flexible, tu peux utiliser Cleave.js.
🔹 Étape 1 : Installer Cleave.js
Dans base.html, ajoute :
html
Copier

<!-- Cleave.js -->

<script src="https://cdnjs.cloudflare.com/ajax/libs/cleave.js/1.6.0/cleave.min.js"></script>

🔹 Étape 2 : Créer un Script pour Cleave.js
Fichier static/js/masques_cleave.js
javascript
Copier

document.addEventListener('DOMContentLoaded', function() {
const masques = {
'LOF': { format: 'LOF-######', placeholder: 'LOF-123456' },
'SCC': { format: 'SCC-######', placeholder: 'SCC-123456' },
'LOOF': { format: 'LOOF-######', placeholder: 'LOOF-123456' },
'SIRE': { format: 'FR########', placeholder: 'FR12345678' },
'CITES': { format: 'CITES-FR-#####', placeholder: 'CITES-FR-12345' },
};

const organismeSelect = document.getElementById('id_organismes');
const numeroInput = document.getElementById('id_numero_identification');

if (organismeSelect && numeroInput) {
organismeSelect.addEventListener('change', function() {
const selectedOption = this.options[this.selectedIndex];
const organismeNom = selectedOption.text;

// Réinitialiser Cleave
if (numeroInput.cleave) {
numeroInput.cleave.destroy();
}

// Trouver le masque correspondant
for (const [nom, infos] of Object.entries(masques)) {
if (organismeNom.includes(nom)) {
new Cleave(numeroInput, {
delimiter: infos.format.includes('-') ? '-' : '',
blocks: getBlocksFromFormat(infos.format),
numericOnly: true,
uppercase: true,
placeholder: infos.placeholder
});
return;
}
}
});

// Appliquer le masque au chargement
if (organismeSelect.selectedIndex !== -1) {
const selectedOption = organismeSelect.options[organismeSelect.selectedIndex];
const organismeNom = selectedOption.text;

for (const [nom, infos] of Object.entries(masques)) {
if (organismeNom.includes(nom)) {
new Cleave(numeroInput, {
delimiter: infos.format.includes('-') ? '-' : '',
blocks: getBlocksFromFormat(infos.format),
numericOnly: true,
uppercase: true,
placeholder: infos.placeholder
});
return;
}
}
}
}

// Fonction pour extraire les blocks à partir du format
function getBlocksFromFormat(format) {
const blocks = [];
let currentBlock = '';
for (const char of format) {
if (char === '#') {
currentBlock += '0';
} else if (char === '-') {
if (currentBlock) {
blocks.push(currentBlock.length);
currentBlock = '';
}
}
}
if (currentBlock) {
blocks.push(currentBlock.length);
}
return blocks;
}
});

📌 Liste des Formats d'Identifiants par Organisme
Voici une liste complète des formats pour les principaux organismes, que tu peux utiliser pour configurer tes masques :

Organisme
Espèce
Format de l'Identifiant
Exemple
Regex

LOF
Chien
LOF-XXXXXX
LOF-123456
^LOF-[0-9]{6}$

SCC
Chien
SCC-XXXXXX
SCC-123456
^SCC-[0-9]{6}$

FCI
Chien
FCI-XXXXXX
FCI-123456
^FCI-[0-9]{6}$

AKC
Chien
AKC-XXXXXXXX
AKC-12345678
^AKC-[0-9]{8}$

The Kennel Club
Chien
KC-XXXXXX
KC-123456
^KC-[0-9]{6}$

LOOF
Chat
LOOF-XXXXXX
LOOF-ABC123
^LOOF-[0-9A-Z]{6}$

FIFé
Chat
FIFé-XXXXXX
FIFé-123456
^FIFé-[0-9]{6}$

TICA
Chat
TICA-XXXXXX
TICA-123456
^TICA-[0-9]{6}$

SIRE
Cheval
FRXXXXXXXX
FR12345678
^FR[0-9]{8}$

IFCE
Cheval
IFCE-XXXXXX
IFCE-123456
^IFCE-[0-9]{6}$

FEI
Cheval
FEI-XXXXXX
FEI-123456
^FEI-[0-9]{6}$

UFA
Rongeur
UFA-XXXXXX
UFA-123456
^UFA-[0-9]{6}$

AFFA
Furet
AFFA-XXXXXX
AFFA-123456
^AFFA-[0-9]{6}$

FFC
Lapin
FFC-XXXXXX
FFC-123456
^FFC-[0-9]{6}$

SNOF
Oiseau
SNOF-XXXXXX
SNOF-123456
^SNOF-[0-9]{6}$

OMJ
Oiseau
OMJ-XXXXXX
OMJ-123456
^OMJ-[0-9]{6}$

AFA
Reptile
AFA-XXXXXX
AFA-123456
^AFA-[0-9]{6}$

CITES
Reptile
CITES-FR-XXXXX
CITES-FR-12345
^CITES-FR-[0-9]{5}$

FFS
Poisson
FFS-XXXXXX
FFS-123456
^FFS-[0-9]{6}$

GDSA
Abeille
GDSA-XXXXXX
GDSA-123456
^GDSA-[0-9]{6}$

FCPR
Pigeon
FCPR-XXXXXX
FCPR-123456
^FCPR-[0-9]{6}$
🎯 Solution Recommandée : Approche 3 (Django + JavaScript + Inputmask)
C’est la meilleure solution car elle combine :
✅ Masquage dynamique (Inputmask).
✅ Validation côté client (JavaScript).
✅ Validation côté serveur (Django).
✅ Expérience utilisateur optimale.
📌 Étapes Complètes pour Intégrer la Solution Recommandée

1. Installer les Dépendances
   Ajoute jQuery et Inputmask dans base.html :html
   Copier

<!-- Dans base.html, avant la fermeture du </body> -->

<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.0/jquery.min.js"></script>

<script src="https://cdnjs.cloudflare.com/ajax/libs/inputmask/5.0.8/jquery.inputmask.min.js"></script>

2. Créer le Fichier JavaScript
   Crée le fichier static/js/masques_identification.js avec le code de l’Approche 3.
3. Charger le Script dans base.html
   Ajoute le chargement du script :html
   Copier

{% block extra_js %}
{{ block.super }}

<script src="{% static 'js/masques_identification.js' %}"></script>

{% endblock %}

4. Mettre à Jour le Modèle Animal
   Ajoute les champs organismes et numero_identification (voir Approche 3).
5. Mettre à Jour le Formulaire AnimalForm
   Ajoute la validation et les attributs pour le champ numero_identification (voir Approche 3).
6. Mettre à Jour le Template animaux/form.html
   Ajoute le champ numero_identification avec un div pour afficher le format attendu :html
   Copier

<div class="mb-3">
    {{ form.organismes.label_tag }}
    {{ form.organismes }}
    {% if form.organismes.errors %}
        <div class="text-danger">{{ form.organismes.errors }}</div>
    {% endif %}
</div>

<div class="mb-3">
    {{ form.numero_identification.label_tag }}
    {{ form.numero_identification }}
    {% if form.numero_identification.errors %}
        <div class="text-danger">{{ form.numero_identification.errors }}</div>
    {% endif %}
    <div class="form-text">
        Format attendu : <span id="format-attendu">Ex: LOF-123456</span>
    </div>
</div>

7. Tester le Fonctionnement
   Sélectionne un organisme dans le formulaire.
   Vérifie que le masque s’applique automatiquement au champ numero_identification.
   Vérifie que le format attendu est affiché.
   Vérifie que la validation fonctionne (essaye de soumettre un numéro invalide).
   🎉 Résultat Final
   Avec cette solution, ton formulaire ressemblera à ceci :
   Exemple : Ajout d’un Berger Allemand
   Sélection de l’espèce : Chien.
   Sélection de l’organisme : LOF.
   Champ numero_identification :Masque appliqué : LOF-______.
   Placeholder : LOF-123456.
   Format attendu : LOF-123456.
   Validation : Seule une valeur comme LOF-123456 sera acceptée.

Exemple : Ajout d’un Python Royal
Sélection de l’espèce : Reptile.
Sélection de l’organisme : CITES.
Champ numero_identification :Masque appliqué : CITES-FR-_____.
Placeholder : CITES-FR-12345.
Format attendu : CITES-FR-12345.
Validation : Seule une valeur comme CITES-FR-12345 sera acceptée.

✅ Checklist pour Vérifier l’Intégration

Étape
Action
Statut

✅ Installer jQuery et Inputmask
Ajout des CDN dans base.html
⬜

✅ Créer le fichier masques_identification.js
Copier le code de l’Approche 3
⬜

✅ Charger le script dans base.html
Ajout dans extra_js
⬜

✅ Mettre à jour le modèle Animal
Ajout des champs organismes et numero_identification
⬜

✅ Mettre à jour le formulaire AnimalForm
Ajout de la validation et des attributs
⬜

✅ Mettre à jour le template form.html
Ajout du champ numero_identification et du span pour le format
⬜

✅ Tester le masquage dynamique
Sélectionner un organisme et vérifier le masque
⬜

✅ Tester la validation
Soumettre un numéro invalide et vérifier l’erreur
⬜
💡 Conseils pour une Meilleure Expérience Utilisateur
Afficher des exemples concrets :
Dans le placeholder ou le texte d’aide, affiche des exemples réels (ex: LOF-123456 pour le LOF).

Valider en temps réel :
Ajoute une validation en temps réel avec JavaScript pour afficher une erreur immédiate si le format est incorrect.

Utiliser des tooltips :
Ajoute des tooltips (infobulles) pour expliquer le format attendu.

Gérer les cas particuliers :
Certains organismes ont des formats variables (ex: LOOF peut avoir des lettres). Adapte les masques en conséquence.

Documenter les formats :
Crée une page d’aide qui explique les formats attendus pour chaque organisme.

📌 Exemple de Page d’Aide pour les Identifiants
Fichier templates/aide_identifiants.html
html
Copier

{% extends 'base.html' %}

{% block title %}Aide - Formats des identifiants{% endblock %}

{% block content %}

<h1>Aide : Formats des identifiants</h1>

<div class="card mb-4">
    <div class="card-body">
        <h5 class="card-title">Pourquoi ces identifiants ?</h5>
        <p class="card-text">
            Les identifiants officiels (LOF, LOOF, SIRE, CITES, etc.) permettent de :
        </p>
        <ul class="card-text">
            <li>Prouver l’authenticité de l’animal (race pure, origine, etc.).</li>
            <li>Participer à des compétitions ou expositions.</li>
            <li>Respecter la législation en vigueur (ex: déclaration obligatoire pour les reptiles).</li>
            <li>Faciliter le suivi vétérinaire et la traçabilité.</li>
        </ul>
    </div>
</div>

<div class="card mb-4">
    <div class="card-header">
        <h5 class="mb-0">Formats par organisme</h5>
    </div>
    <div class="card-body">
        <div class="table-responsive">
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Organisme</th>
                        <th>Espèce</th>
                        <th>Format</th>
                        <th>Exemple</th>
                        <th>Obligatoire ?</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>LOF</td>
                        <td>Chien</td>
                        <td>LOF-XXXXXX</td>
                        <td>LOF-123456</td>
                        <td>✅ Oui (pour les chiens de race)</td>
                    </tr>
                    <tr>
                        <td>SCC</td>
                        <td>Chien</td>
                        <td>SCC-XXXXXX</td>
                        <td>SCC-123456</td>
                        <td>❌ Non</td>
                    </tr>
                    <tr>
                        <td>LOOF</td>
                        <td>Chat</td>
                        <td>LOOF-XXXXXX</td>
                        <td>LOOF-ABC123</td>
                        <td>✅ Oui (pour les chats de race)</td>
                    </tr>
                    <tr>
                        <td>SIRE</td>
                        <td>Cheval</td>
                        <td>FRXXXXXXXX</td>
                        <td>FR12345678</td>
                        <td>✅ Oui (pour tous les équidés)</td>
                    </tr>
                    <tr>
                        <td>CITES</td>
                        <td>Reptile</td>
                        <td>CITES-FR-XXXXX</td>
                        <td>CITES-FR-12345</td>
                        <td>✅ Oui (déclaration obligatoire)</td>
                    </tr>
                    <tr>
                        <td>UFA</td>
                        <td>Oiseau/Rongeur</td>
                        <td>UFA-XXXXXX</td>
                        <td>UFA-123456</td>
                        <td>❌ Non</td>
                    </tr>
                    <tr>
                        <td>AFFA</td>
                        <td>Furet</td>
                        <td>AFFA-XXXXXX</td>
                        <td>AFFA-123456</td>
                        <td>❌ Non</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>

<div class="card">
    <div class="card-body">
        <h5 class="card-title">Comment trouver ces identifiants ?</h5>
        <p class="card-text">
            Voici où trouver les identifiants officiels pour chaque organisme :
        </p>
        <ul class="card-text">
            <li>
                <strong>LOF/LOOF/SIRE</strong> : Ces identifiants sont fournis par l’éleveur ou le club officiel lors de l’achat de l’animal.
                Vous pouvez aussi les retrouver sur les <strong>pédigrées</strong> ou <strong>certificats d’origine</strong>.
            </li>
            <li>
                <strong>CITES</strong> : Pour les reptiles, le numéro CITES est fourni lors de l’achat ou de l’importation.
                Il est <strong>obligatoire de le déclarer</strong> en préfecture.
            </li>
            <li>
                <strong>UFA/AFFA</strong> : Ces identifiants sont fournis par les clubs ou associations lors de l’inscription de l’animal.
            </li>
        </ul>
    </div>
</div>
{% endblock %}

Ajouter un Lien vers la Page d’Aide
Dans animaux/form.html, ajoute un lien vers la page d’aide :
html
Copier

<div class="mb-3">
    {{ form.numero_identification.label_tag }}
    {{ form.numero_identification }}
    {% if form.numero_identification.errors %}
        <div class="text-danger">{{ form.numero_identification.errors }}</div>
    {% endif %}
    <div class="form-text">
        Format attendu : <span id="format-attendu">Ex: LOF-123456</span>
        <a href="{% url 'aide_identifiants' %}" target="_blank" class="text-decoration-none">
            <i class="bi bi-info-circle"></i> Aide sur les formats
        </a>
    </div>
</div>

🎯 Solution Ultime : Masques + Validation + Aide Contextuelle
Voici un exemple complet combinant toutes les fonctionnalités :
Masquage dynamique (Inputmask).
Validation côté client et serveur (JavaScript + Django).
Aide contextuelle (lien vers une page d’aide).

1. Modèle Animal (Mis à Jour)
   python
   Copier

from django.db import models
from django.core.validators import RegexValidator

class Animal(models.Model):

# ... (autres champs existants)

organismes = models.ManyToManyField(
'Organisme',
blank=True,
verbose_name="Organismes",
help_text="Organismes auxquels l'animal est inscrit (ex: LOF, LOOF, CITES)."
)
numero_identification = models.CharField(
max_length=50,
blank=True,
null=True,
verbose_name="Numéro d'identification",
help_text="Numéro LOF, LOOF, SIRE, CITES, etc.",
validators=[
RegexValidator(
regex=r'^[A-Z0-9-]{6,20}$',
message='Format invalide. Exemple : LOF-123456',
code='invalid_format'
)
]
)

def clean(self):
"""Valider que le numéro d'identification correspond aux organismes sélectionnés."""
if self.numero_identification and self.organismes.count() > 0:
for organisme in self.organismes.all():
if not self.validate_numero_identification(self.numero_identification, organisme):
raise ValidationError({
'numero_identification':
f"Le numéro '{self.numero_identification}' ne correspond pas au format attendu pour {organisme.nom}. "
f"Exemple : {self.get_placeholder_for_organisme(organisme)}"
})

def validate_numero_identification(self, numero, organisme):
"""Valide que le numéro correspond au format de l'organisme."""
patterns = {
'LOF': r'^LOF-[0-9]{6}$',
'SCC': r'^SCC-[0-9]{6}$',
'LOOF': r'^LOOF-[0-9A-Z]{6}$',
'SIRE': r'^FR[0-9]{8}$',
'CITES': r'^CITES-FR-[0-9]{5}$',
}
pattern = patterns.get(organisme.nom_court, r'^[A-Z0-9-]{6,20}$')
return bool(re.match(pattern, numero))

def get_placeholder_for_organisme(self, organisme):
"""Retourne un exemple de numéro pour l'organisme."""
placeholders = {
'LOF': 'LOF-123456',
'SCC': 'SCC-123456',
'LOOF': 'LOOF-ABC123',
'SIRE': 'FR12345678',
'CITES': 'CITES-FR-12345',
}
return placeholders.get(organisme.nom_court, 'Ex: LOF-123456')
2. Formulaire AnimalForm (Mis à Jour)
python
Copier

from django import forms
from django.core.exceptions import ValidationError
import re
from .models import Animal, Organisme

class AnimalForm(forms.ModelForm):
class Meta:
model = Animal
fields = [
'nom', 'race', 'espece', 'identification',
'date_naissance', 'date_deces', 'lof', 'robe',
'propriétaire', 'organismes', 'numero_identification'
]
widgets = {
'date_naissance': forms.DateInput(attrs={'type': 'date'}),
'date_deces': forms.DateInput(attrs={'type': 'date'}),
'organismes': forms.Select(attrs={
'class': 'form-select',
'id': 'id_organismes'
}),
'numero_identification': forms.TextInput(attrs={
'class': 'form-control',
'id': 'id_numero_identification',
'placeholder': 'Ex: LOF-123456'
}),
}

def __init__(self, *args, **kwargs):
super().__init__(*args, **kwargs)

# Filtrer les organismes par espèce sélectionnée

if 'espece' in self.data:
espece = self.data['espece']
self.fields['organismes'].queryset = Organisme.objects.filter(espece=espece)
elif self.instance and self.instance.pk:
self.fields['organismes'].queryset = Organisme.objects.filter(espece=self.instance.espece)

def clean_numero_identification(self):
numero_identification = self.cleaned_data.get('numero_identification')
organismes = self.cleaned_data.get('organismes')

if numero_identification and organismes:
for organisme in organismes:
if not self.validate_numero_identification(numero_identification, organisme):
raise ValidationError(
f"Le numéro '{numero_identification}' ne correspond pas au format attendu pour {organisme.nom}. "
f"Exemple : {self.get_placeholder_for_organisme(organisme)}"
)
return numero_identification
def validate_numero_identification(self, numero, organisme):
patterns = {
'LOF': r'^LOF-[0-9]{6}$',
'SCC': r'^SCC-[0-9]{6}$',
'LOOF': r'^LOOF-[0-9A-Z]{6}$',
'SIRE': r'^FR[0-9]{8}$',
'CITES': r'^CITES-FR-[0-9]{5}$',
}
pattern = patterns.get(organisme.nom_court, r'^[A-Z0-9-]{6,20}$')
return bool(re.match(pattern, numero))

def get_placeholder_for_organisme(self, organisme):
placeholders = {
'LOF': 'LOF-123456',
'SCC': 'SCC-123456',
'LOOF': 'LOOF-ABC123',
'SIRE': 'FR12345678',
'CITES': 'CITES-FR-12345',
}
return placeholders.get(organisme.nom_court, 'Ex: LOF-123456')
3. Template animaux/form.html (Version Finale)
html

'---
{% extends 'base.html' %}
{% block title %}
{% if object %}
Modifier {{ object.nom }}
{% else %}
Ajouter un animal
{% endif %}
{% endblock %}
{% block extra_js %}
{{ block.super }}

<script src="{% static 'js/masques_identification.js' %}"></script>

{% endblock %}
{% block content %}

<h1>
{% if object %}
<i class="bi bi-pencil"></i> Modifier {{ object.nom }}
{% else %}
<i class="bi bi-plus-circle"></i> Ajouter un animal
{% endif %}
</h1>
<div class="card">
<div class="card-body">
<form method="post" id="animalForm">
{% csrf_token %}
<!-- Champs de base -->
<div class="row">
<div class="col-md-6">
<div class="mb-3">
{{ form.nom.label_tag }}
{{ form.nom }}
{% if form.nom.errors %}
<div class="text-danger">{{ form.nom.errors }}</div>
{% endif %}
</div>
</div>
<div class="col-md-6">
<div class="mb-3">
{{ form.identification.label_tag }}
{{ form.identification }}
{% if form.identification.errors %}
<div class="text-danger">{{ form.identification.errors }}</div>
{% endif %}
</div>
</div>
</div>
<div class="row">
<div class="col-md-6">
<div class="mb-3">
{{ form.espece.label_tag }}
{{ form.espece }}
{% if form.espece.errors %}
<div class="text-danger">{{ form.espece.errors }}</div>
{% endif %}
</div>
</div>
<div class="col-md-6">
<div class="mb-3">
{{ form.race.label_tag }}
{{ form.race }}
{% if form.race.errors %}
<div class="text-danger">{{ form.race.errors }}</div>
{% endif %}
</div>
</div>
</div>
<!-- Organismes -->
<div class="mb-3">
{{ form.organismes.label_tag }}
{{ form.organismes }}
{% if form.organismes.errors %}
<div class="text-danger">{{ form.organismes.errors }}</div>
{% endif %}
<div class="form-text">
Sélectionnez un ou plusieurs organismes pour cet animal.
</div>
</div>
<!-- Numéro d'identification -->
<div class="mb-3">
{{ form.numero_identification.label_tag }}
{{ form.numero_identification }}
{% if form.numero_identification.errors %}
<div class="text-danger">{{ form.numero_identification.errors }}</div>
{% endif %}
<div class="form-text">
Format attendu : <span id="format-attendu">Ex: LOF-123456</span>
<a href="{% url 'aide_identifiants' %}" target="_blank" class="text-decoration-none ms-2">
<i class="bi bi-info-circle"></i> Aide sur les formats
</a>
</div>
</div>
<!-- Autres champs -->
<div class="row">
<div class="col-md-4">
<div class="mb-3">
{{ form.date_naissance.label_tag }}
{{ form.date_naissance }}
{% if form.date_naissance.errors %}
<div class="text-danger">{{ form.date_naissance.errors }}</div>
{% endif %}
</div>
</div>
<div class="col-md-4">
<div class="mb-3">
{{ form.date_deces.label_tag }}
{{ form.date_deces }}
{% if form.date_deces.errors %}
<div class="text-danger">{{ form.date_deces.errors }}</div>
{% endif %}
</div>
</div>
<div class="col-md-4">
<div class="mb-3">
{{ form.proprietaire.label_tag }}
{{ form.proprietaire }}
{% if form.proprietaire.errors %}
<div class="text-danger">{{ form.proprietaire.errors }}</div>
{% endif %}
</div>
</div>
</div>
<div class="row">
<div class="col-md-6">
<div class="mb-3">
{{ form.lof.label_tag }}
{{ form.lof }}
</div>
</div>
<div class="col-md-6">
<div class="mb-3">
{{ form.robe.label_tag }}
{{ form.robe }}
</div>
</div>
</div>
<!-- Boutons -->
<div class="d-flex justify-content-end gap-2">
<button type="submit" class="btn btn-primary">
<i class="bi bi-check-circle"></i> Enregistrer
</button>
<a href="{% url 'animaux:animal_list' %}" class="btn btn-secondary">
<i class="bi bi-x-circle"></i> Annuler
</a>
</div>
</form>
</div>
</div>
{% endblock %}
{% endblock %}
---
'

4. JavaScript Final (static/js/masques_identification.js)
   javascript

---

document.addEventListener('DOMContentLoaded', function() {
// Dictionnaire des masques et placeholders par organisme
const organismeMasques = {
// Chiens
'LOF': { masque: 'LOF-999999', placeholder: 'LOF-123456' },
'SCC': { masque: 'SCC-999999', placeholder: 'SCC-123456' },
'FCI': { masque: 'FCI-999999', placeholder: 'FCI-123456' },
'AKC': { masque: 'AKC-99999999', placeholder: 'AKC-12345678' },
'The Kennel Club': { masque: 'KC-999999', placeholder: 'KC-123456' },

// Chats
'LOOF': { masque: 'LOOF-999999', placeholder: 'LOOF-ABC123' },
'FIFé': { masque: 'FIFé-999999', placeholder: 'FIFé-123456' },
'TICA': { masque: 'TICA-999999', placeholder: 'TICA-123456' },
'GCCF': { masque: 'GCCF-999999', placeholder: 'GCCF-123456' },

// Chevaux
'SIRE': { masque: 'FR99999999', placeholder: 'FR12345678' },
'IFCE': { masque: 'IFCE-999999', placeholder: 'IFCE-123456' },
'FEI': { masque: 'FEI-999999', placeholder: 'FEI-123456' },

// Rongeurs
'UFA': { masque: 'UFA-999999', placeholder: 'UFA-123456' },
'AFFA': { masque: 'AFFA-999999', placeholder: 'AFFA-123456' },
'FFC': { masque: 'FFC-999999', placeholder: 'FFC-123456' },

// Oiseaux
'SNOF': { masque: 'SNOF-999999', placeholder: 'SNOF-123456' },
'OMJ': { masque: 'OMJ-999999', placeholder: 'OMJ-123456' },

// Reptiles
'AFA': { masque: 'AFA-999999', placeholder: 'AFA-123456' },
'CITES': { masque: 'CITES-FR-99999', placeholder: 'CITES-FR-12345' },

// Poissons
'FFS': { masque: 'FFS-999999', placeholder: 'FFS-123456' },

// Abeilles
'GDSA': { masque: 'GDSA-999999', placeholder: 'GDSA-123456' },
'UNAF': { masque: 'UNAF-999999', placeholder: 'UNAF-123456' },

// Pigeons
'FCPR': { masque: 'FCPR-999999', placeholder: 'FCPR-123456' },
};

const organismeSelect = document.getElementById('id_organismes');
const numeroInput = document.getElementById('id_numero_identification');
const formatAttenduSpan = document.getElementById('format-attendu');

if (organismeSelect && numeroInput) {
// Écouter les changements de sélection d'organisme
organismeSelect.addEventListener('change', function() {
const selectedOptions = Array.from(this.selectedOptions);
if (selectedOptions.length > 0) {
// Si un seul organisme est sélectionné, appliquer son masque
if (selectedOptions.length === 1) {
const organismeNom = selectedOptions[0].text;
applyMaskForOrganisme(organismeNom);
} else {
// Si plusieurs organismes sont sélectionnés, appliquer un masque générique
applyGenericMask();
}
} else {
// Si aucun organisme n'est sélectionné, désactiver le masquage
resetMask();
}
});

// Appliquer le masque au chargement si des organismes sont déjà sélectionnés
if (organismeSelect.selectedOptions.length > 0) {
const selectedOptions = Array.from(organismeSelect.selectedOptions);
if (selectedOptions.length === 1) {
const organismeNom = selectedOptions[0].text;
applyMaskForOrganisme(organismeNom);
} else {
applyGenericMask();
}
}
}

// Appliquer le masque pour un organisme spécifique
function applyMaskForOrganisme(organismeNom) {
for (const [nom, infos] of Object.entries(organismeMasques)) {
if (organismeNom.includes(nom)) {
$(numeroInput).inputmask(infos.masque, {
placeholder: ' ',
clearIncomplete: true,
showMaskOnHover: true,
showMaskOnFocus: true
});
if (formatAttenduSpan) {
formatAttenduSpan.textContent = infos.placeholder;
}
return;
}
}
// Si aucun masque ne correspond, appliquer un masque générique
applyGenericMask();
}

// Appliquer un masque générique (pour plusieurs organismes)
function applyGenericMask() {
$(numeroInput).inputmask('^[A-Z0-9-]{6,20}$', {
placeholder: ' ',
clearIncomplete: true,
showMaskOnHover: true,
showMaskOnFocus: true,
regex: true
});
if (formatAttenduSpan) {
formatAttenduSpan.textContent = 'Ex: LOF-123456, SIRE-FR12345678';
}
}

// Réinitialiser le masque
function resetMask() {
$(numeroInput).inputmask('remove');
if (formatAttenduSpan) {
formatAttenduSpan.textContent = 'Ex: LOF-123456';
}
}
});
---

🎉 Résultat Final
Avec cette solution, ton application aura :
✅ Des masques de saisie dynamiques qui s’adaptent à l’organisme sélectionné.
✅ Une validation côté client et serveur pour garantir la conformité des numéros.
✅ Une aide contextuelle pour guider l’utilisateur.
✅ Une expérience utilisateur optimale (UX/UI améliorée).
✅ Checklist Finale pour Vérifier Tout

Étape
Action
Statut

✅ Installer jQuery et Inputmask
Ajout des CDN dans base.html
⬜

✅ Créer le fichier masques_identification.js
Copier le code final
⬜

✅ Charger le script dans base.html
Ajout dans extra_js
⬜

✅ Mettre à jour le modèle Animal
Ajout des champs organismes et numero_identification
⬜

✅ Mettre à jour le formulaire AnimalForm
Ajout de la validation et des attributs
⬜

✅ Mettre à jour le template form.html
Ajout du champ numero_identification et du span pour le format
⬜

✅ Créer la page d’aide aide_identifiants.html
Ajout du template
⬜

✅ Ajouter le lien vers la page d’aide
Dans form.html
⬜

✅ Tester le masquage dynamique
Sélectionner un organisme et vérifier le masque
⬜

✅ Tester la validation côté client
Saisir un numéro invalide et vérifier l’erreur
⬜

✅ Tester la validation côté serveur
Soumettre un numéro invalide et vérifier l’erreur
⬜
💡 Conseils pour Aller Plus Loin
Ajouter une vérification en temps réel :
Utilise JavaScript pour valider le numéro à chaque frappe et afficher une erreur immédiate.

Intégrer une API de vérification :
Pour les organismes comme le LOF ou le SIRE, tu peux intégrer une API de vérification pour confirmer que le numéro existe.

Générer des numéros automatiquement :
Pour les organismes internes (ex: ton propre système d’identification), tu peux générer automatiquement des numéros uniques.

Ajouter des infobulles :
Utilise Bootstrap Tooltips pour afficher des exemples de formats quand l’utilisateur survole le champ.

Créer un système de suggestions :
Si l’utilisateur saisit un numéro partiel, propose des suggestions basées sur les formats connus.

🎯 Exemple de Code pour une Vérification en Temps Réel
JavaScript pour la Validation en Temps Réel
javascript

---

// Ajoute cela à la fin de masques_identification.js
if (numeroInput) {
numeroInput.addEventListener('input', function() {
const selectedOptions = Array.from(organismeSelect.selectedOptions);
if (selectedOptions.length === 1) {
const organismeNom = selectedOptions[0].text;
const infos = getOrganismeInfos(organismeNom);
if (infos) {
const regex = getRegexFromMasque(infos.masque);
if (!regex.test(this.value)) {
this.classList.add('is-invalid');
} else {
this.classList.remove('is-invalid');
}
}
}
});

// Fonction pour obtenir les infos d'un organisme
function getOrganismeInfos(organismeNom) {
for (const [nom, infos] of Object.entries(organismeMasques)) {
if (organismeNom.includes(nom)) {
return infos;
}
}
return null;
}

// Fonction pour convertir un masque Inputmask en regex
function getRegexFromMasque(masque) {
// Remplace les 9 par [0-9] et les A par [A-Z]
let regex = masque
.replace(/9/g, '[0-9]')
.replace(/A/g, '[A-Z]')
.replace(/-/g, '\\-');
return new RegExp(`^${regex}$`);
}
}
-

CSS pour les Champs Invalides.

Dans static/css/style.css, ajoute

css

```
    /* Champs invalides */
    .is-invalid {
        border-color: #dc3545 !important;
        box-shadow: 0 0 0 0.25rem rgba(220, 53, 69, 0.25) !important;
    }
    .is-invalid:focus {
        border-color: #dc3545 !important; 
        box-shadow: 0 0 0 0.25rem rgba(220, 53, 69, 0.25) !important;
    }
```
🎉 Conclusion
Tu as maintenant une solution complète et professionnelle pour gérer les masques de saisie des identifiants dans ton application.
Avec cette implémentation :
✅ Les utilisateurs sont guidés par des masques dynamiques.
✅ Les données sont validées côté client et serveur.
✅ L’expérience utilisateur est optimisée avec des aides contextuelles.
Si tu as besoin d’aide pour :
Personnaliser davantage les masques.
Ajouter une vérification en temps réel.
Intégrer une API de vérification (ex: vérification LOF en ligne).
Fais-moi signe ! 😊
Ton application a maintenant des masques de saisie professionnels pour les identifiants ! 🎭🔠
