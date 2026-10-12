"""Widgets de formulaire partagés par les apps (animaux, factures, documents)."""
import os

from django import forms


class FichierSansLienInput(forms.ClearableFileInput):
    """ClearableFileInput dont la mention « Actuellement : … » n'est pas un
    lien. Le widget de Django pointe vers `fichier.url`, c'est-à-dire sous
    /media/, que le projet ne sert volontairement pas : les fichiers ne
    passent que par des vues authentifiées qui vérifient le compte
    (animaux:animal_photo, factures:facture_fichier,
    documents:document_fichier). Le lien menait donc à une page 404 ; seul le
    nom du fichier est affiché, le fichier lui-même restant consultable depuis
    la page de détail.

    Le gabarit est rangé dans une app installée (et non dans templates/ à la
    racine) : le moteur de rendu des formulaires ne cherche que là."""

    template_name = 'animaux/widgets/fichier_sans_lien.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['nom_fichier'] = os.path.basename(getattr(value, 'name', '') or '')
        return context
