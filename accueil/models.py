import secrets

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
    mode_sombre = models.BooleanField(
        default=False, verbose_name="Mode sombre",
        help_text="Fond sombre et texte clair, pour les yeux sensibles à la lumière.",
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


class Foyer(models.Model):
    """Regroupe plusieurs comptes qui partagent l'accès à toutes leurs données
    (animaux, vaccins/traitements, consultations, factures, documents, fiches
    propriétaire) — cf. `accueil.utils.comptes_accessibles`, seul point
    d'entrée utilisé par les vues des apps métier pour élargir leurs filtres
    `utilisateur=...` en `utilisateur__in=...`. Un compte n'appartient jamais
    à plus d'un foyer à la fois (cf. MembreFoyer.utilisateur, OneToOne). Ce
    partage n'est jamais une fusion de comptes : chaque donnée reste rattachée
    à son créateur d'origine (cf. Animal.utilisateur etc.), seule la
    visibilité est élargie."""

    nom = models.CharField(max_length=100, blank=True, verbose_name="Nom du foyer")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")

    def __str__(self):
        return self.nom or f"Foyer #{self.pk}"

    class Meta:
        verbose_name = "Foyer"
        verbose_name_plural = "Foyers"


class MembreFoyer(models.Model):
    """Appartenance d'un compte à un foyer. `utilisateur` en OneToOneField
    (et non ForeignKey) : garantit au niveau base qu'un compte n'appartient
    jamais à plus d'un foyer à la fois."""

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='membre_foyer',
        verbose_name="Compte",
    )
    foyer = models.ForeignKey(Foyer, on_delete=models.CASCADE, related_name='membres', verbose_name="Foyer")
    invite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='membres_invites', verbose_name="Invité par",
        help_text=(
            "Compte à l'origine de l'invitation ayant fait entrer ce membre dans le foyer — "
            "vide pour le membre fondateur (n'a été invité par personne). Seul ce compte peut "
            "retirer ce membre du foyer (cf. accueil.views.retirer_membre_foyer) ; le membre "
            "peut toujours se retirer lui-même (cf. accueil.views.quitter_foyer), sans condition."
        ),
    )
    date_adhesion = models.DateTimeField(auto_now_add=True, verbose_name="Date d'adhésion")

    def __str__(self):
        return f"{self.utilisateur} dans {self.foyer}"

    class Meta:
        verbose_name = "Membre de foyer"
        verbose_name_plural = "Membres de foyer"


class InvitationFoyer(models.Model):
    """Invitation à rejoindre un foyer partagé, envoyée par email à un compte
    existant — le partage n'est actif qu'après acceptation explicite par
    l'invité (jamais un ajout direct, cf. décision produit)."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACCEPTEE = 'acceptee', 'Acceptée'
        REFUSEE = 'refusee', 'Refusée'
        ANNULEE = 'annulee', 'Annulée'

    foyer = models.ForeignKey(Foyer, on_delete=models.CASCADE, related_name='invitations', verbose_name="Foyer")
    invite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invitations_envoyees',
        verbose_name="Invité par",
    )
    email_invite = models.EmailField(verbose_name="Email de l'invité")
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE, verbose_name="Statut",
    )
    token = models.CharField(max_length=64, unique=True, editable=False, verbose_name="Jeton")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date d'envoi")
    date_reponse = models.DateTimeField(null=True, blank=True, verbose_name="Date de réponse")

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invitation de {self.invite_par} à {self.email_invite} ({self.get_statut_display()})"

    class Meta:
        verbose_name = "Invitation à un foyer"
        verbose_name_plural = "Invitations à un foyer"
        ordering = ['-date_creation']
