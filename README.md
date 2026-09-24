# Manuel d'utilisation — Suivi Vétérinaire

21 sept. 2026 · rédigé par @Yvon

---

## <u>Présentation</u>

Suivi Vétérinaire est une application personnelle pour gérer les animaux d'un foyer :

* Fiches animaux
* Suivi de poids
* Vaccins et traitements
* Consultations avec rappels automatiques
* Factures et documents
* Possibilité de tout partager avec un proche (voir Partager son compte).


Ce n'est pas un portail de clientèle vétérinaire : c'est un outil individuel, pensé pour du grand public, pas pour un usage professionnel.

Ce manuel couvre, dans l'ordre :

* la création de compte,
* la gestion des animaux,
* les fiches propriétaires,
* le suivi vaccinal,
* les consultations,
* les factures,
* les documents,
* le partage de compte entre proches,
* les notifications,
* l'accessibilité et les questions fréquentes.

L'application s'organise autour de cinq domaines, **tous rattachés à la fiche d'un animal** :

* Animaux — identité de chaque compagnon (espèce, race, poids, identification, photo)
* Vaccins — suivi vaccinal et traitements en cours
* Consultations — rendez-vous vétérinaires et rappels
* Factures — dépenses et coût de revient par animal
* Documents — pièces jointes (analyses, ordonnances...)

Elle gère aussi bien les chiens et chats que les NAC (nouveaux animaux de compagnie), chevaux, oiseaux ou reptiles.

## <u>Premiers pas</u>

**Premier lancement :** tant qu'aucun compte n'existe sur l'installation, la page d'accueil propose de créer le tout premier compte (bouton « Créer le premier compte »).

**Comptes suivants :** une fois un compte créé, la page d'accueil propose de s'inscrire librement ou de se connecter avec un compte existant.

À la création d'un compte, tu peux cocher d'emblée des options d'accessibilité (texte agrandi, contraste élevé, police plus lisible, animations réduites, palette adaptée daltonisme, mode sombre) — voir Accessibilité pour les modifier plus tard.

Pour changer son mot de passe une fois connecté : menu utilisateur (en haut à droite) > Changer mon mot de passe.

Chaque compte ne voit par défaut que ses propres données — pour les partager avec un proche, voir Partager son compte.

Par sécurité, les formulaires de connexion et d'inscription sont limités à 3 tentatives par adresse : au-delà, l'accès est bloqué temporairement (15 minutes, puis 1 heure en cas de récidive).

## <u>Gérer ses animaux</u>

Le menu Animaux liste tous tes animaux, avec une recherche avancée (nom, espèce, race, âge, robe).

Créer une fiche : bouton « Ajouter un animal » — nom, espèce, race (regroupées par catégorie), robe, dates de naissance/décès, propriétaire (voir Fiches propriétaires), photo, et une ou plusieurs identifications (puce, tatouage...) rattachées à un organisme (LOF, SIRE...).

Suivi de poids : depuis la fiche d'un animal, ajoute une pesée à une date donnée ; une courbe de poids se construit automatiquement au fil des pesées.

Fiche PDF : depuis la fiche animal, exporte un résumé complet (poids, vaccins/traitements, consultations, factures) en PDF.

Import/export en masse : depuis la liste des animaux, exporte en CSV ou Excel, ou importe un fichier CSV pour créer/mettre à jour plusieurs fiches d'un coup (colonnes : Nom, Espèce, Race, Identification, Date de Naissance, Propriétaire, Robe).

Ajout rapide de catalogue : si la race, l'espèce, la robe ou l'organisme d'identification recherchés n'existent pas encore, un bouton « + » à côté du champ ouvre une petite fenêtre pour les créer à la volée, sans quitter le formulaire.

Plusieurs identifications : un animal peut être enregistré auprès de plusieurs organismes (par exemple puce SIRE et inscription LOF) — le bouton « + » du bloc identification ajoute une nouvelle ligne organisme/numéro à la fiche.

Suppression : supprimer un animal retire définitivement sa fiche (contrairement aux fiches propriétaire et vétérinaire, qui sont seulement désactivées — voir plus bas).

## <u>Fiches propriétaires</u>

Une fiche Propriétaire (nom, coordonnées, e mail) est réutilisable d'un animal à l'autre — un même foyer avec plusieurs animaux ne la saisit qu'une fois. Menu Propriétaires pour la liste, ou directement depuis le formulaire animal (bouton « + »).

Supprimer une fiche ne l'efface pas réellement : elle est retirée des listes et des nouveaux choix, mais reste affichée sur les animaux qui l'utilisent déjà.

Si tu partages ton compte (voir Partager son compte), l'application empêche la création d'une fiche avec un e mail déjà utilisé par un autre membre de ton foyer, pour éviter les doublons.
Champs de la fiche : nom, prénom (facultatif), adresse, code postal, ville, téléphone, email. Sans prénom renseigné, la fiche s'affiche par son email dans les listes.

Une même fiche propriétaire peut être associée à plusieurs animaux (c'est le principe de la réutilisation), mais un animal n'a qu'un seul propriétaire à la fois.

## <u>Vaccins et traitements</u>

**Menu Vaccins :** suivi des vaccinations et traitements de chaque animal, avec la date de dose et la prochaine date de rappel.

Depuis la fiche d'un animal (ou le menu Vaccins), ajoute un suivi : choisis un ou plusieurs vaccins (une entrée est créée pour chacun) ou un traitement (comprimé, crème, solution buvable...) avec sa posologie. Le catalogue de vaccins/traitements est partagé entre tous les comptes ; le bouton « + » à côté du champ permet d'en ajouter un nouveau au catalogue s'il manque.

Les prochains rappels de vaccin apparaissent sur le calendrier (voir Consultations et calendrier).

**Vaccin ou traitement, pas les deux :** un suivi concerne soit un ou plusieurs vaccins (chacun donnant sa propre entrée dans l'historique), soit un traitement avec sa posologie propre (comprimés avec prises du matin/midi/soir, ou dose en solution buvable) et sa durée. Passer d'un vaccin à un traitement (ou l'inverse) en modifiant un suivi bascule proprement l'entrée, sans laisser de champs incohérents.

**Autres champs utiles :** numéro de lot, notes libres, et — pour un vaccin — la date de la prochaine dose, qui alimente les rappels du calendrier.

## <u>Consultations et calendrier</u>

**Menu Consultations :** liste et création des consultations (animal, date/heure, motif, compte-rendu, vétérinaire). Le catalogue de vétérinaires est partagé et réutilisable, comme les fiches propriétaires.

Le bouton Calendrier affiche une vue mensuelle de toutes les consultations à venir et des rappels de vaccin.

**Rappel automatique par email :** dès qu'une consultation est enregistrée avec une date future, un email de rappel (mise en forme soignée, logo en entête) part automatiquement à l'adresse du propriétaire de l'animal, 2 jours avant le rendez-vous.

**Fiche vétérinaire :** comme les propriétaires, les vétérinaires forment un catalogue réutilisable (nom, coordonnées) ; les « supprimer » les désactive sans effacer l'historique des consultations déjà liées à eux.

Sur le calendrier, chaque type d’évènement a sa propre couleur : consultations à venir, rappels de consultation à 2 jours, et rappels de vaccin — pratique pour distinguer d'un coup d'œil ce qui approche.

## <u>Factures et budget</u>

**Menu Factures :** chaque dépense (vétérinaire ou alimentaire) est enregistrée avec un fichier scanné, un montant et un animal concerné (ou aucun, si la dépense est partagée entre tous les animaux).

**Ventiler une facture :** le bouton « Ventiler la facture » permet de la détailler en plusieurs lignes (désignation, quantité, prix), chacune attribuée à un animal précis ou à « Tous les animaux » (coût partagé également). Une fois ventilée, la facture est verrouillée : seule la réattribution d'une ligne, sa suppression, ou l'ajout d'une nouvelle ligne restent possibles.
La liste des factures affiche un tableau de bord des dépenses mensuelles et annuelles. La fiche de chaque animal affiche son coût de revient (mensuel et annuel) : ses propres dépenses, plus une part égale des dépenses partagées.

Chaque facture précise un type de dépense (vétérinaire ou alimentaire), un numéro (facultatif), un titre, un montant, une date et un fichier scanné obligatoire (photo ou PDF de la facture).
Ventilation, en détail : chaque ligne choisit une désignation (catalogue de produits/prestations réutilisable, avec rappel du dernier prix pratiqué), une quantité et un prix unitaire — le prix total et le montant global se recalculent automatiquement. Dès qu'une ligne existe, impossible de revenir à une facture simple : seule la ventilation reste modifiable ensuite.

## <u>Documents</u>

**Menu Documents :** pièces jointes libres rattachées à un animal (analyses, ordonnances, résultats d'examen...), classées par type de document. Ajoute-en depuis la fiche animal ou le menu Documents.

Les types de documents (analyse, ordonnance, certificat...) forment un catalogue réutilisable ; un nouveau type peut être créé directement depuis le formulaire d'ajout s'il manque à la liste. Formats acceptés : PDF, images (JPG, PNG, GIF, WebP), Word et Excel.

## <u>Partager son compte</u>

Depuis le menu utilisateur > Partage de compte, tu peux inviter un autre compte existant (par son email) à partager l'accès complet à tes données (animaux, vaccins, consultations, factures, documents, fiches propriétaire) — utile pour un couple ou une famille qui gère les mêmes animaux depuis des comptes séparés.

**Comment ça marche :**
Tu envoies une invitation à un email correspondant à un compte déjà existant ; un email et une notification in-app partent vers cette personne.

Elle doit l'accepter explicitement depuis sa propre page Partage de compte — rien n'est partagé avant son accord.

Une fois acceptée, les deux comptes voient et modifient les mêmes données, comme s'il s'agissait d'un seul compte — sans jamais fusionner les comptes eux-mêmes.

Chaque compte n'appartient qu'à un seul foyer à la fois. Tu peux quitter un foyer partagé à tout moment depuis cette même page. Retirer un autre membre n'est possible que par la personne qui l'a invité.

***Important :*** l'email invité doit correspondre à un compte déjà créé sur l'installation — ce n'est pas une invitation « à froid » qui créerait un compte pour quelqu'un qui n'en a pas encore.
Qui peut retirer qui : seule la personne qui a envoyé une invitation peut retirer le membre qu'elle a fait entrer dans le foyer ; chacun peut en revanche quitter le foyer de lui-même, à tout moment, sans que personne d'autre n'ait à l'approuver.

## <u>Notifications et e mails</u>

Une cloche en haut de page affiche tes notifications in-app (rappel de consultation, nouveau document, facture à payer, invitation de partage de compte).

Certains évènements envoient aussi un email soigné, avec le logo de l'application en entête : rappel de consultation 2 jours avant, invitation à partager un compte.

La liste complète des notifications (lues et non lues) reste consultable depuis « Voir toutes les notifications », avec un bouton pour tout marquer comme lu d'un coup.

Types de notifications : rappel de consultation, nouveau document, facture à payer, invitation de partage de compte.

## <u>Accessibilité</u>

Le bouton d'accessibilité (icône dans la barre de navigation) ouvre un panneau avec, indépendamment les uns des autres : mode sombre (fond sombre et texte clair, si le blanc fatigue les yeux), taille de texte (3 niveaux), contraste élevé, police plus lisible (pensée basse vision), animations réduites, palette adaptée daltonisme, et un bouton « lire cette page à voix haute ».

Une fois connecté, tes réglages sont mémorisés sur ton compte et ré-appliqués automatiquement à chaque connexion, sur n'importe quel navigateur.

Avant même de te connecter, le panneau fonctionne déjà (réglages mémorisés dans ton navigateur, le temps de la visite). Un lien « Aller au contenu principal » et un contour de focus toujours visible facilitent en plus la navigation au clavier, sur toutes les pages.

## <u>Questions fréquentes</u>

**Je ne reçois pas les e mails de rappel.**

Vérifie l'adresse email de la fiche Propriétaire de l'animal concerné : c'est elle qui reçoit le rappel, pas forcément ton adresse de compte.

**J'ai supprimé une fiche par erreur (propriétaire, vétérinaire).**

Ces suppressions sont « douces » : la fiche reste en base et continue de s'afficher sur les éléments déjà enregistrés, elle est juste retirée des listes pour de nouvelles saisies.

**Je veux partager mes animaux avec mon/ma conjoint(e).**

Voir Partager son compte.

**J'ai oublié mon mot de passe.**

Clique sur « Mot de passe oublié ? » sur la page de connexion : un email avec les instructions de réinitialisation t'est envoyé.

**Mon import CSV échoue ou crée des doublons.**

Vérifie que les colonnes obligatoires (Nom, Espèce, Race, Date de Naissance) sont bien présentes ; le dédoublonnage se fait par numéro d'identification, donc deux lignes sans identification créeront toujours deux animaux distincts.

Un problème persiste ? Contacte l'administrateur de l'installation, mentionné en bas de la page d'accueil.
