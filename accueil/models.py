from django.conf import settings
from django.db import models


class BlocageAdresse(models.Model):
    """Historique de blocage par adresse IP pour un formulaire public sensible
    au bourrage de robots (`prefixe` = 'login' ou 'inscription', cf.
    Projet_veto.throttling) : persiste en base, contrairement au compteur de
    tentatives (en cache, donc volatil), pour escalader la durée de blocage en
    cas de récidive même après expiration du cache ou redémarrage du process
    — 15 min la 1ère fois, 1h la 2e, blocage définitif à partir de la 3e."""

    prefixe = models.CharField(max_length=50, verbose_name="Formulaire concerné")
    adresse_ip = models.GenericIPAddressField(verbose_name="Adresse IP")
    nombre_blocages = models.PositiveIntegerField(default=0, verbose_name="Nombre de blocages")
    bloque_definitivement = models.BooleanField(default=False, verbose_name="Bloqué définitivement")
    derniere_maj = models.DateTimeField(auto_now=True, verbose_name="Dernière mise à jour")

    class Meta:
        verbose_name = "Blocage d'adresse"
        verbose_name_plural = "Blocages d'adresse"
        constraints = [
            models.UniqueConstraint(fields=['prefixe', 'adresse_ip'], name='blocage_unique_prefixe_ip')
        ]

    def __str__(self):
        etat = "bloqué définitivement" if self.bloque_definitivement else f"{self.nombre_blocages} blocage(s)"
        return f"{self.prefixe} / {self.adresse_ip} ({etat})"


class PreferenceAccessibilite(models.Model):
    """Préférences d'accessibilité d'un compte utilisateur : cochées à la
    création du compte (cf. PremierUtilisateurForm/CreateView) ou modifiées
    plus tard depuis le panneau accessibilité (cf.
    templates/partials/panneau_accessibilite.html) — dans les deux cas
    enregistrées ici pour être réappliquées automatiquement à chaque
    connexion, sur n'importe quel navigateur (contrairement au panneau seul,
    qui ne mémorisait que dans le navigateur courant via localStorage)."""

    class Taille(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        GRAND = 'grand', 'Grand'
        TRES_GRAND = 'tres-grand', 'Très grand'

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preferences_accessibilite',
        verbose_name="Utilisateur",
    )
    taille_texte = models.CharField(
        max_length=10, choices=Taille.choices, default=Taille.NORMAL, verbose_name="Taille du texte",
    )
    contraste_eleve = models.BooleanField(default=False, verbose_name="Contraste élevé")
    police_lisible = models.BooleanField(
        default=False, verbose_name="Police plus lisible",
        help_text="Police adaptée à la basse vision (Atkinson Hyperlegible).",
    )
    reduire_animations = models.BooleanField(default=False, verbose_name="Réduire les animations")
    palette_daltonisme = models.BooleanField(
        default=False, verbose_name="Palette adaptée daltonisme",
        help_text="Remplace les rouge/vert/orange par la palette Okabe-Ito.",
    )

    def classes_css(self):
        """Classes à poser sur <html> pour appliquer ces préférences (cf.
        static/css/style.css) — utilisé au rendu de chaque page pour un
        utilisateur connecté (cf. Projet_veto/context_processors.py)."""
        classes = []
        if self.taille_texte == self.Taille.GRAND:
            classes.append('a11y-taille-grand')
        elif self.taille_texte == self.Taille.TRES_GRAND:
            classes.append('a11y-taille-tres-grand')
        if self.contraste_eleve:
            classes.append('a11y-contraste')
        if self.police_lisible:
            classes.append('a11y-police-lisible')
        if self.reduire_animations:
            classes.append('a11y-reduire-animations')
        if self.palette_daltonisme:
            classes.append('a11y-palette-daltonisme')
        return ' '.join(classes)

    def __str__(self):
        return f"Préférences accessibilité de {self.utilisateur}"

    class Meta:
        verbose_name = "Préférence d'accessibilité"
        verbose_name_plural = "Préférences d'accessibilité"
