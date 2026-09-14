"""Validateurs partagés pour les fichiers uploadés par les utilisateurs.

Objectif sécurité : empêcher le dépôt de fichiers exécutables ou de types
pouvant être interprétés par un navigateur (HTML/SVG/JS -> XSS stocké), et
limiter la taille des fichiers pour éviter les abus (déni de service par
remplissage disque).
"""
import os

from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat

# Extensions autorisées pour les pièces jointes (factures, documents).
ALLOWED_UPLOAD_EXTENSIONS = [
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.doc', '.docx', '.xls', '.xlsx',
]

MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


def validate_file_extension(value):
    """Rejette les fichiers dont l'extension ne fait pas partie de la liste blanche."""
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(
            "Type de fichier non autorisé (%(ext)s). Extensions acceptées : %(allowed)s.",
            params={'ext': ext, 'allowed': ', '.join(ALLOWED_UPLOAD_EXTENSIONS)},
        )


def validate_file_size(value):
    """Rejette les fichiers dépassant la taille maximale autorisée."""
    if value.size > MAX_UPLOAD_SIZE_BYTES:
        raise ValidationError(
            "Le fichier (%(size)s) dépasse la taille maximale autorisée (%(max)s).",
            params={'size': filesizeformat(value.size), 'max': filesizeformat(MAX_UPLOAD_SIZE_BYTES)},
        )
