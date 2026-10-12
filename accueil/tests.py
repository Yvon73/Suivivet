import re
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import Foyer, InvitationFoyer, MembreFoyer, PreferenceAccessibilite
from .utils import comptes_accessibles

from Projet_veto.tableaux import etiqueter_tableaux


class AccueilViewTest(TestCase):
    """Tests de la page d'accueil publique."""

    def test_propose_la_creation_du_premier_compte_si_aucun_utilisateur(self):
        response = self.client.get(reverse('accueil:accueil'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['premier_lancement'])
        self.assertContains(response, 'Créer le premier compte')

    def test_masque_la_creation_du_premier_compte_si_un_utilisateur_existe(self):
        User.objects.create_user(username='dejainscrit', password='motdepasse123')
        response = self.client.get(reverse('accueil:accueil'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['premier_lancement'])
        self.assertNotContains(response, 'Créer le premier compte')
        self.assertContains(response, reverse('accueil:inscription'))

    def test_affiche_les_informations_legales(self):
        response = self.client.get(reverse('accueil:accueil'))
        self.assertContains(response, 'Mentions légales')
        self.assertContains(response, 'RGPD')
        self.assertContains(response, "Déclaration d'accessibilité")


class PremierUtilisateurCreateViewTest(TestCase):
    """Tests de la création du tout premier compte de l'application."""

    def test_cree_un_compte_administrateur_et_connecte_l_utilisateur(self):
        response = self.client.post(reverse('accueil:premier_compte'), {
            'username': 'admin',
            'email': 'admin@example.com',
            'password1': 'un-mot-de-passe-solide-42',
            'password2': 'un-mot-de-passe-solide-42',
        })
        self.assertEqual(response.status_code, 302)

        utilisateur = User.objects.get(username='admin')
        self.assertTrue(utilisateur.is_staff)
        self.assertTrue(utilisateur.is_superuser)
        self.assertEqual(utilisateur.email, 'admin@example.com')

        # La session du client doit être authentifiée en tant que ce nouvel utilisateur.
        self.assertEqual(int(self.client.session['_auth_user_id']), utilisateur.pk)

    def test_bloque_la_creation_si_un_compte_existe_deja(self):
        User.objects.create_user(username='dejainscrit', password='motdepasse123')

        response = self.client.post(reverse('accueil:premier_compte'), {
            'username': 'intrus',
            'email': 'intrus@example.com',
            'password1': 'un-mot-de-passe-solide-42',
            'password2': 'un-mot-de-passe-solide-42',
        })

        self.assertRedirects(response, reverse('accueil:accueil'))
        self.assertFalse(User.objects.filter(username='intrus').exists())

    def test_get_bloque_aussi_si_un_compte_existe_deja(self):
        User.objects.create_user(username='dejainscrit', password='motdepasse123')
        response = self.client.get(reverse('accueil:premier_compte'))
        self.assertRedirects(response, reverse('accueil:accueil'))

    def test_les_cases_d_accessibilite_cochees_creent_les_preferences_correspondantes(self):
        self.client.post(reverse('accueil:premier_compte'), {
            'username': 'admin',
            'email': 'admin@example.com',
            'password1': 'un-mot-de-passe-solide-42',
            'password2': 'un-mot-de-passe-solide-42',
            'texte_agrandi': 'on',
            'contraste_eleve': 'on',
            # police_lisible, reduire_animations, palette_daltonisme : non cochées
        })
        utilisateur = User.objects.get(username='admin')
        prefs = PreferenceAccessibilite.objects.get(utilisateur=utilisateur)
        self.assertEqual(prefs.taille_texte, PreferenceAccessibilite.Taille.GRAND)
        self.assertTrue(prefs.contraste_eleve)
        self.assertFalse(prefs.police_lisible)
        self.assertFalse(prefs.reduire_animations)
        self.assertFalse(prefs.palette_daltonisme)

    def test_aucune_case_cochee_cree_des_preferences_par_defaut(self):
        self.client.post(reverse('accueil:premier_compte'), {
            'username': 'admin',
            'email': 'admin@example.com',
            'password1': 'un-mot-de-passe-solide-42',
            'password2': 'un-mot-de-passe-solide-42',
        })
        prefs = PreferenceAccessibilite.objects.get(utilisateur__username='admin')
        self.assertEqual(prefs.taille_texte, PreferenceAccessibilite.Taille.NORMAL)
        self.assertFalse(prefs.contraste_eleve)

    def test_les_preferences_sont_appliquees_sur_les_pages_apres_connexion(self):
        self.client.post(reverse('accueil:premier_compte'), {
            'username': 'admin',
            'email': 'admin@example.com',
            'password1': 'un-mot-de-passe-solide-42',
            'password2': 'un-mot-de-passe-solide-42',
            'contraste_eleve': 'on',
            'palette_daltonisme': 'on',
        })
        response = self.client.get(reverse('animaux:animal_list'))
        self.assertContains(response, 'a11y-contraste')
        self.assertContains(response, 'a11y-palette-daltonisme')


class InscriptionCreateViewTest(TestCase):
    """Tests de la création d'un compte « classique » (self-service, à la
    différence du tout premier compte administrateur)."""

    def test_cree_un_compte_non_administrateur_meme_si_un_compte_existe_deja(self):
        User.objects.create_user(username='dejainscrit', password='motdepasse123')

        response = self.client.post(reverse('accueil:inscription'), {
            'username': 'nouveau',
            'email': 'nouveau@example.com',
            'password1': 'un-mot-de-passe-solide-42',
            'password2': 'un-mot-de-passe-solide-42',
        })
        self.assertEqual(response.status_code, 302)

        utilisateur = User.objects.get(username='nouveau')
        self.assertFalse(utilisateur.is_staff)
        self.assertFalse(utilisateur.is_superuser)
        self.assertEqual(int(self.client.session['_auth_user_id']), utilisateur.pk)


class AdministrationRestreinteAuxDonneesTest(TestCase):
    """Le site admin Django ne doit exposer que des comptes/catalogues, jamais
    les données personnelles saisies par un compte utilisateur."""

    def test_les_modeles_de_donnees_utilisateur_ne_sont_pas_enregistres(self):
        from django.contrib import admin
        from animaux.models import Animal, Proprietaire
        from consultations.models import Consultation
        from documents.models import Document
        from vaccins.models import SuiviVaccinTraitement

        for model in (Animal, Proprietaire, Consultation, Document, SuiviVaccinTraitement):
            self.assertNotIn(model, admin.site._registry, f"{model.__name__} ne doit pas être dans l'admin")

    def test_les_catalogues_restent_enregistres(self):
        from django.contrib import admin
        from animaux.models import Espece, Race, Robe, Organisme
        from vaccins.models import Vaccin, Traitement
        from consultations.models import Veterinaire
        from documents.models import TypeDocument

        for model in (Espece, Race, Robe, Organisme, Vaccin, Traitement, Veterinaire, TypeDocument):
            self.assertIn(model, admin.site._registry, f"{model.__name__} devrait rester dans l'admin")


class PreferencesAccessibiliteViewTest(TestCase):
    """Panneau accessibilité : un formulaire envoyé en entier à chaque
    changement (htmx), enregistré par le serveur puis appliqué au rendu —
    sans JavaScript ni localStorage."""

    def setUp(self):
        self.utilisateur = User.objects.create_user(username='alex', password='motdepasse123')
        self.url = reverse('accueil:preferences_accessibilite')

    def test_enregistre_l_etat_du_panneau_sur_le_compte(self):
        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(self.url, {
            'taille_texte': 'tres-grand', 'palette_daltonisme': 'on', 'suite': reverse('animaux:animal_list'),
        })
        self.assertRedirects(response, reverse('animaux:animal_list'))
        prefs = PreferenceAccessibilite.objects.get(utilisateur=self.utilisateur)
        self.assertTrue(prefs.palette_daltonisme)
        self.assertFalse(prefs.contraste_eleve)
        self.assertEqual(prefs.taille_texte, PreferenceAccessibilite.Taille.TRES_GRAND)

    def test_case_decochee_desactive_le_reglage(self):
        PreferenceAccessibilite.objects.create(utilisateur=self.utilisateur, contraste_eleve=True, mode_sombre=True)
        self.client.login(username='alex', password='motdepasse123')
        self.client.post(self.url, {'taille_texte': 'normal', 'mode_sombre': 'on'})
        prefs = PreferenceAccessibilite.objects.get(utilisateur=self.utilisateur)
        self.assertFalse(prefs.contraste_eleve)
        self.assertTrue(prefs.mode_sombre)

    def test_valeurs_inattendues_ignorees(self):
        self.client.login(username='alex', password='motdepasse123')
        self.client.post(self.url, {'taille_texte': 'gigantesque', 'est_admin': 'on'})
        prefs = PreferenceAccessibilite.objects.get(utilisateur=self.utilisateur)
        self.assertEqual(prefs.taille_texte, PreferenceAccessibilite.Taille.NORMAL)
        self.assertFalse(User.objects.get(pk=self.utilisateur.pk).is_superuser)

    def test_htmx_redemande_la_page_courante(self):
        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(self.url, {'taille_texte': 'grand'}, headers={
            'HX-Request': 'true', 'HX-Current-URL': 'http://testserver/animaux/?q=rex#contenu-principal',
        })
        self.assertEqual(response.status_code, 204)
        # Sans le fragment : sinon le navigateur ne rechargerait pas la page.
        self.assertEqual(response['HX-Redirect'], 'http://testserver/animaux/?q=rex')

    def test_jamais_de_redirection_externe(self):
        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(self.url, {'taille_texte': 'grand', 'suite': 'https://exemple.invalid/piege'})
        self.assertRedirects(response, reverse('accueil:accueil'), fetch_redirect_response=False)
        response = self.client.post(self.url, {'taille_texte': 'grand'}, headers={
            'HX-Request': 'true', 'HX-Current-URL': 'https://exemple.invalid/piege',
        })
        self.assertEqual(response['HX-Redirect'], reverse('accueil:accueil'))

    def test_mode_sombre_enregistre_puis_applique_sur_les_pages(self):
        self.client.login(username='alex', password='motdepasse123')
        self.assertNotContains(self.client.get(reverse('animaux:animal_list')), 'data-bs-theme="dark"')

        self.client.post(self.url, {'taille_texte': 'normal', 'mode_sombre': 'on'})
        self.assertTrue(PreferenceAccessibilite.objects.get(utilisateur=self.utilisateur).mode_sombre)
        response = self.client.get(reverse('animaux:animal_list'))
        self.assertContains(response, 'data-bs-theme="dark"')
        # Le panneau reflète l'état enregistré.
        self.assertContains(response, 'name="mode_sombre"\n                       checked')

        self.client.post(self.url, {'taille_texte': 'normal'})
        self.assertNotContains(self.client.get(reverse('animaux:animal_list')), 'data-bs-theme="dark"')

    def test_visiteur_non_connecte_reglages_dans_un_cookie(self):
        """Sans compte, les réglages vont dans un cookie de ce navigateur et
        sont appliqués par le serveur aux pages publiques."""
        response = self.client.post(self.url, {
            'taille_texte': 'grand', 'contraste_eleve': 'on', 'mode_sombre': 'on', 'suite': reverse('login'),
        })
        self.assertRedirects(response, reverse('login'))
        self.assertFalse(PreferenceAccessibilite.objects.exists())
        self.assertIn('accessibilite', self.client.cookies)
        self.assertTrue(self.client.cookies['accessibilite']['httponly'])

        for url in (reverse('login'), reverse('accueil:accueil'), reverse('accueil:inscription')):
            response = self.client.get(url)
            self.assertContains(response, 'class="a11y-taille-grand a11y-contraste" data-bs-theme="dark"', msg_prefix=url)
            self.assertNotContains(response, 'localStorage', msg_prefix=url)

    def test_cookie_falsifie_ignore(self):
        self.client.cookies['accessibilite'] = '{"mode_sombre": true}'
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-bs-theme="dark"')

    def test_mode_sombre_coche_a_la_creation_du_compte(self):
        User.objects.all().delete()
        self.client.post(reverse('accueil:premier_compte'), {
            'username': 'admin',
            'email': 'admin@example.com',
            'password1': 'un-mot-de-passe-solide-42',
            'password2': 'un-mot-de-passe-solide-42',
            'mode_sombre': 'on',
        })
        self.assertTrue(PreferenceAccessibilite.objects.get(utilisateur__username='admin').mode_sombre)


class PartageCompteTest(TestCase):
    """Tests du partage de compte entre propriétaires (« foyer »)."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex', email='alex@example.com', password='motdepasse123')
        self.sam = User.objects.create_user(username='sam', email='sam@example.com', password='motdepasse123')
        self.tiers = User.objects.create_user(username='tiers', email='tiers@example.com', password='motdepasse123')

    def _inviter_sam_depuis_alex(self):
        self.client.login(username='alex', password='motdepasse123')
        self.client.post(reverse('accueil:partage_inviter'), {'email': 'sam@example.com'})
        self.client.logout()
        return InvitationFoyer.objects.get(email_invite='sam@example.com')

    def test_invitation_creation_et_acceptation_partage_les_comptes(self):
        invitation = self._inviter_sam_depuis_alex()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.EN_ATTENTE)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('sam@example.com', mail.outbox[0].to)

        self.client.login(username='sam', password='motdepasse123')
        response = self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]))
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.ACCEPTEE)

        self.assertEqual(
            set(comptes_accessibles(self.alex).values_list('pk', flat=True)), {self.alex.pk, self.sam.pk},
        )
        self.assertEqual(
            set(comptes_accessibles(self.sam).values_list('pk', flat=True)), {self.alex.pk, self.sam.pk},
        )
        # Un compte tiers, hors foyer, ne fait jamais partie des comptes
        # accessibles de personne (régression de sécurité la plus critique).
        self.assertEqual(set(comptes_accessibles(self.tiers).values_list('pk', flat=True)), {self.tiers.pk})

    def test_refus_invitation_ne_partage_rien(self):
        invitation = self._inviter_sam_depuis_alex()
        self.client.login(username='sam', password='motdepasse123')
        self.client.post(reverse('accueil:partage_refuser', args=[invitation.token]))
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.REFUSEE)
        self.assertFalse(MembreFoyer.objects.filter(utilisateur=self.sam).exists())
        self.assertEqual(set(comptes_accessibles(self.sam).values_list('pk', flat=True)), {self.sam.pk})

    def test_impossible_d_inviter_un_email_sans_compte(self):
        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(reverse('accueil:partage_inviter'), {'email': 'personne@example.com'})
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        self.assertFalse(InvitationFoyer.objects.exists())

    def test_impossible_d_inviter_quelqu_un_deja_dans_un_foyer(self):
        # Un foyer réellement partagé (au moins un autre membre) : un foyer où
        # l'invité est seul ne bloque plus l'invitation, cf.
        # FoyerSoloEtInvitationsPerimeesTest.
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.tiers, foyer=foyer, invite_par=self.sam)

        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(reverse('accueil:partage_inviter'), {'email': 'sam@example.com'})
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        self.assertFalse(InvitationFoyer.objects.exists())

    def test_le_fondateur_peut_retirer_le_membre_qu_il_a_invite(self):
        invitation = self._inviter_sam_depuis_alex()
        self.client.login(username='sam', password='motdepasse123')
        self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]))
        membre_sam = MembreFoyer.objects.get(utilisateur=self.sam)

        # Sam n'est pas le fondateur : cette action lui est fermée,
        # y compris pour se retirer lui-même (réservée à quitter_foyer).
        response = self.client.post(reverse('accueil:partage_retirer_membre', args=[membre_sam.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(MembreFoyer.objects.filter(pk=membre_sam.pk).exists())

        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(reverse('accueil:partage_retirer_membre', args=[membre_sam.pk]))
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        self.assertFalse(MembreFoyer.objects.filter(pk=membre_sam.pk).exists())

    def test_un_membre_peut_toujours_quitter_le_foyer_lui_meme(self):
        invitation = self._inviter_sam_depuis_alex()
        self.client.login(username='sam', password='motdepasse123')
        self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]))

        response = self.client.post(reverse('accueil:partage_quitter'))
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        self.assertFalse(MembreFoyer.objects.filter(utilisateur=self.sam).exists())

    def test_acceptation_echoue_proprement_si_deja_dans_un_autre_foyer_entretemps(self):
        """Course : Sam rejoint un autre foyer entre l'envoi de l'invitation
        d'Alex et son acceptation — doit échouer proprement (message d'erreur,
        redirection), pas planter avec une transaction avortée."""
        invitation = self._inviter_sam_depuis_alex()

        # Un foyer partagé avec quelqu'un d'autre (un foyer où Sam serait seul
        # serait simplement abandonné à l'acceptation).
        autre_foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=autre_foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.tiers, foyer=autre_foyer, invite_par=self.sam)

        self.client.login(username='sam', password='motdepasse123')
        response = self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]))
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.EN_ATTENTE)
        # Sam doit rester dans son foyer d'origine, pas celui d'Alex.
        self.assertEqual(MembreFoyer.objects.get(utilisateur=self.sam).foyer, autre_foyer)

    def test_seul_l_invite_peut_repondre_a_son_invitation(self):
        invitation = self._inviter_sam_depuis_alex()
        self.client.login(username='tiers', password='motdepasse123')
        response = self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]))
        self.assertEqual(response.status_code, 404)
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.EN_ATTENTE)


class TableauxEmpilablesTest(SimpleTestCase):
    """Préparation côté serveur des tableaux pour l'affichage en cartes sur
    téléphone (cf. Projet_veto/tableaux.py), à la place de l'ancien script."""

    TABLEAU = (
        '<table class="table table-striped" id="t">\n'
        '  <thead class="table-dark">\n'
        '    <tr><th>Nom</th><th scope="col">\n   <a href="?tri=espece">Espèce<i class="bi"></i></a>\n</th>'
        '<th>Âge &amp; poids</th><th>Actions</th></tr>\n'
        '  </thead>\n'
        '  <tbody>\n'
        '    <tr><td><a href="/1/">Rex</a></td><td class="x">Chien</td><td>3 ans</td><td><a class="btn">Modifier</a></td></tr>\n'
        '    <tr><td colspan="4" class="text-center">Aucun élément</td></tr>\n'
        '  </tbody>\n'
        '</table>'
    )

    def test_cellules_etiquetees(self):
        resultat = etiqueter_tableaux(self.TABLEAU)
        self.assertIn('<table class="table table-striped tableau-empilable" id="t" role="table">', resultat)
        self.assertIn('<thead class="table-dark" role="rowgroup">', resultat)
        self.assertIn('<th role="columnheader">Nom</th>', resultat)
        self.assertIn('<tbody role="rowgroup">', resultat)
        self.assertIn('<td role="cell" data-label="Nom"><a href="/1/">Rex</a></td>', resultat)
        # Intitulé d'une colonne triable : le texte du lien, sans ses espaces.
        self.assertIn('<td class="x" role="cell" data-label="Espèce">Chien</td>', resultat)
        self.assertIn('<td role="cell" data-label="Âge &amp; poids">3 ans</td>', resultat)
        # Colonne « Actions » : pas d'intitulé répété, boutons en bas de carte.
        self.assertIn('<td role="cell" class="cellule-actions"><a class="btn">Modifier</a></td>', resultat)
        # Ligne qui couvre tout le tableau : aucun intitulé.
        self.assertIn('<td colspan="4" class="text-center" role="cell">Aucun élément</td>', resultat)

    def test_le_reste_du_document_est_intact(self):
        page = '<p title="a > b">Avant\n</p>\n' + self.TABLEAU + '\n<script>var t = "<table>";</script>'
        resultat = etiqueter_tableaux(page)
        self.assertTrue(resultat.startswith('<p title="a > b">Avant\n</p>\n<table'))
        self.assertTrue(resultat.endswith('</table>\n<script>var t = "<table>";</script>'))
        # Appliqué deux fois, il ne change plus rien.
        self.assertEqual(etiqueter_tableaux(resultat), resultat)

    def test_tableaux_non_concernes(self):
        trois_colonnes = '<table class="table"><thead><tr><th>A</th><th>B</th><th>C</th></tr></thead><tbody><tr><td>1</td><td>2</td><td>3</td></tr></tbody></table>'
        self.assertEqual(etiqueter_tableaux(trois_colonnes), trois_colonnes)
        sans_classe = self.TABLEAU.replace('class="table table-striped"', 'class="calendrier-grille"')
        self.assertEqual(etiqueter_tableaux(sans_classe), sans_classe)
        self.assertEqual(etiqueter_tableaux('<p>Aucun tableau</p>'), '<p>Aucun tableau</p>')

    def test_colonne_sans_intitule_et_colspan_d_entete(self):
        html = (
            '<table class="table"><thead><tr><th colspan="2">Dose</th><th>Date</th><th></th></tr></thead>'
            '<tbody><tr><td>1</td><td>ml</td><td>hier</td><td>x</td></tr></tbody></table>'
        )
        resultat = etiqueter_tableaux(html)
        self.assertIn('<td role="cell" data-label="Dose">1</td><td role="cell" data-label="Dose">ml</td>', resultat)
        self.assertIn('<td role="cell" class="cellule-actions">x</td>', resultat)

    def test_tableau_imbrique(self):
        interieur = self.TABLEAU.replace(' id="t"', '')
        html = '<table class="table"><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>' + interieur + '</td><td>2</td></tr></tbody></table>'
        resultat = etiqueter_tableaux(html)
        self.assertEqual(resultat.count('tableau-empilable'), 1)
        self.assertIn('data-label="Nom"', resultat)


class TableauxEmpilablesMiddlewareTest(TestCase):
    def test_pages_de_l_application_preparees_sans_script(self):
        from animaux.models import Animal, Espece, Proprietaire, Race, Robe
        utilisateur = User.objects.create_user(username='u_tableaux', password='p')
        self.client.login(username='u_tableaux', password='p')
        chien = Espece.objects.get(code='CHIEN')
        Animal.objects.create(
            nom='TEST_TEMP', espece=chien, race=Race.objects.filter(espece=chien).first(),
            robe=Robe.objects.get(code='NOIR'), date_naissance='2020-01-01', utilisateur=utilisateur,
            proprietaire=Proprietaire.objects.create(nom='TEST_TEMP', email='tableaux@example.com', utilisateur=utilisateur),
        )
        response = self.client.get(reverse('animaux:animal_list'))
        self.assertContains(response, 'tableau-empilable')
        self.assertContains(response, 'role="cell" data-label="Nom"')
        self.assertContains(response, 'data-label="Propriétaire"')
        self.assertContains(response, 'class="cellule-actions"')
        self.assertNotContains(response, 'tableaux-responsives.js')
        self.assertEqual(int(response.get('Content-Length', len(response.content))), len(response.content))


class ToutesLesPagesSansScriptTest(TestCase):
    """Parcourt toutes les pages de l'application avec un compte qui a des
    données dans chaque module : chacune doit s'afficher sans erreur, et ne
    contenir ni script inline ni gestionnaire d'événement inline — toute
    l'interactivité passe par htmx (cf. CLAUDE.md), les seuls scripts servis
    étant Bootstrap, htmx et la lecture à voix haute."""

    SCRIPTS_AUTORISES = {
        '/static/vendor/bootstrap/bootstrap.bundle.min.js',
        '/static/vendor/htmx/htmx.min.js',
        '/static/js/lecture-voix-haute.js',
    }

    @classmethod
    def setUpTestData(cls):
        from datetime import date, timedelta

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.utils import timezone

        from animaux.models import Animal, AnimalIdentification, Espece, Poids, Proprietaire, Race, Robe
        from consultations.models import Consultation, Veterinaire
        from documents.models import Document, TypeDocument
        from factures.models import Designation, Facture, LigneFacture
        from notifications.models import Notification
        from vaccins.models import SuiviVaccinTraitement, Traitement, Vaccin

        cls.dossier_media = tempfile.mkdtemp(prefix='test_media_')
        cls.reglages = override_settings(MEDIA_ROOT=cls.dossier_media)
        cls.reglages.enable()
        cls.addClassCleanup(shutil.rmtree, cls.dossier_media, ignore_errors=True)
        cls.addClassCleanup(cls.reglages.disable)

        cls.utilisateur = User.objects.create_user(username='u_pages', email='pages@example.com', password='p')
        autre = User.objects.create_user(username='u_pages_2', email='pages2@example.com', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(foyer=foyer, utilisateur=cls.utilisateur)
        MembreFoyer.objects.create(foyer=foyer, utilisateur=autre, invite_par=cls.utilisateur)

        chat = Espece.objects.get(code='CHAT')
        cls.proprietaire = Proprietaire.objects.create(nom='TEST_TEMP', email='pages_p@example.com', utilisateur=cls.utilisateur)
        cls.animal = Animal.objects.create(
            nom='TEST_TEMP', espece=chat, race=Race.objects.get(espece=chat, nom='Persan'),
            robe=Robe.objects.get(code='NOIR'), date_naissance=date(2020, 1, 1),
            proprietaire=cls.proprietaire, utilisateur=cls.utilisateur,
        )
        AnimalIdentification.objects.create(animal=cls.animal, identification='TEST_TEMP_250')
        Poids.objects.create(animal=cls.animal, date=date(2026, 1, 1), valeur=4)
        cls.veterinaire = Veterinaire.objects.create(nom='TEST_TEMP', utilisateur=cls.utilisateur)
        cls.consultation = Consultation.objects.create(
            animal=cls.animal, date=timezone.now() + timedelta(days=1), motif='TEST_TEMP', veterinaire=cls.veterinaire,
        )
        cls.suivi_vaccin = SuiviVaccinTraitement.objects.create(
            animal=cls.animal, vaccin=Vaccin.objects.create(nom='TEST_TEMP'), date=date(2026, 1, 1),
            date_prochaine_dose=timezone.localdate() + timedelta(days=3),
        )
        cls.suivi_traitement = SuiviVaccinTraitement.objects.create(
            animal=cls.animal, date=date(2026, 1, 1),
            traitement=Traitement.objects.create(nom='TEST_TEMP', classe=Traitement.Classe.COMPRIME),
        )
        fichier = SimpleUploadedFile('test.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        cls.facture = Facture.objects.create(
            animal=cls.animal, utilisateur=cls.utilisateur, type_depense='VETERINAIRE', titre='TEST_TEMP',
            montant=Decimal('10.00'), date=timezone.localdate(), fichier=fichier,
        )
        cls.facture_ventilee = Facture.objects.create(
            utilisateur=cls.utilisateur, type_depense='ALIMENTAIRE', titre='TEST_TEMP ventilée',
            montant=Decimal('1.00'), date=timezone.localdate(), fichier=SimpleUploadedFile('v.pdf', b'%PDF-1.4 test'),
        )
        LigneFacture.objects.create(
            facture=cls.facture_ventilee, designation=Designation.objects.create(nom='TEST_TEMP', utilisateur=cls.utilisateur),
            quantite=Decimal('2'), prix_unitaire=Decimal('3.50'), animal=cls.animal,
        )
        cls.document = Document.objects.create(
            animal=cls.animal, titre='TEST_TEMP', type_document=TypeDocument.objects.create(nom='TEST_TEMP'),
            fichier=SimpleUploadedFile('d.pdf', b'%PDF-1.4 test'),
        )
        Notification.objects.create(utilisateur=cls.utilisateur, type='RAPPEL', titre='TEST_TEMP', message='TEST_TEMP')

    def _pages(self):
        a, p, v = self.animal.pk, self.proprietaire.pk, self.veterinaire.pk
        return [
            reverse('animaux:animal_list'), reverse('animaux:animal_list') + '?q=test&tri=age&sens=desc',
            reverse('animaux:animal_detail', args=[a]), reverse('animaux:animal_create'),
            reverse('animaux:animal_update', args=[a]), reverse('animaux:animal_delete', args=[a]),
            reverse('animaux:poids_create', args=[a]), reverse('animaux:importer_csv'),
            reverse('animaux:proprietaire_list'), reverse('animaux:proprietaire_create'),
            reverse('animaux:proprietaire_detail', args=[p]), reverse('animaux:proprietaire_update', args=[p]),
            reverse('animaux:proprietaire_delete', args=[p]),
            reverse('vaccins:vaccin_list'), reverse('vaccins:traitement_list'), reverse('vaccins:suivi_list'),
            reverse('vaccins:suivi_list_animal', args=[a]), reverse('vaccins:suivi_create', args=[a]),
            reverse('vaccins:suivi_update', args=[self.suivi_vaccin.pk]),
            reverse('vaccins:suivi_update', args=[self.suivi_traitement.pk]),
            reverse('vaccins:suivi_delete', args=[self.suivi_vaccin.pk]),
            reverse('consultations:consultation_list'), reverse('consultations:consultation_list') + '?tri=veterinaire',
            reverse('consultations:consultation_list_animal', args=[a]),
            reverse('consultations:consultation_detail', args=[self.consultation.pk]),
            reverse('consultations:consultation_create'), reverse('consultations:consultation_create', args=[a]),
            reverse('consultations:consultation_update', args=[self.consultation.pk]),
            reverse('consultations:consultation_delete', args=[self.consultation.pk]),
            reverse('consultations:calendrier'), reverse('consultations:calendrier') + '?vue=planning',
            reverse('consultations:calendrier') + '?vue=grille&annee=2027&mois=2',
            reverse('consultations:veterinaire_list'), reverse('consultations:veterinaire_create'),
            reverse('consultations:veterinaire_detail', args=[v]), reverse('consultations:veterinaire_update', args=[v]),
            reverse('consultations:veterinaire_delete', args=[v]),
            reverse('factures:facture_list'), reverse('factures:facture_list') + '?tri=montant&sens=desc&q=test',
            reverse('factures:facture_list_animal', args=[a]),
            reverse('factures:facture_detail', args=[self.facture.pk]),
            reverse('factures:facture_detail', args=[self.facture_ventilee.pk]),
            reverse('factures:facture_create'), reverse('factures:facture_create', args=[a]),
            reverse('factures:facture_update', args=[self.facture.pk]),
            reverse('factures:facture_update', args=[self.facture_ventilee.pk]),
            reverse('factures:facture_delete', args=[self.facture.pk]),
            reverse('documents:document_list'), reverse('documents:document_list') + '?tri=type',
            reverse('documents:document_list_animal', args=[a]),
            reverse('documents:document_detail', args=[self.document.pk]), reverse('documents:document_create'),
            reverse('documents:document_create', args=[a]), reverse('documents:document_update', args=[self.document.pk]),
            reverse('documents:document_delete', args=[self.document.pk]),
            reverse('notifications:notification_list'), reverse('accueil:partage_compte'),
            reverse('password_change'),
        ]

    PAGES_PUBLIQUES = ['accueil:accueil', 'accueil:inscription', 'login', 'password_reset', 'password_reset_done',
                       'password_reset_complete']

    def _controler(self, url, response):
        self.assertEqual(response.status_code, 200, url)
        contenu = response.content.decode()
        scripts = re.findall(r'<script\b([^>]*)>', contenu)
        for attributs in scripts:
            source = re.search(r'src="([^"]+)"', attributs)
            self.assertIsNotNone(source, f"script inline dans {url}")
            self.assertIn(source.group(1), self.SCRIPTS_AUTORISES, url)
        self.assertIsNone(re.search(r'<[^>]+\son[a-z]+\s*=', contenu), f"gestionnaire d'événement inline dans {url}")
        self.assertNotIn('javascript:', contenu, url)
        self.assertIn('/static/vendor/htmx/htmx.min.js', contenu, url)
        for bibliotheque in ('jquery', 'datatables', 'fullcalendar', 'tom-select', 'cdn.'):
            self.assertNotIn(bibliotheque, contenu.lower(), f"{bibliotheque} dans {url}")
        # Toute cible htmx désignée par son identifiant existe bien dans la page.
        for cible in set(re.findall(r'hx-(?:target|select)="#([\w-]+)"', contenu)):
            self.assertIn(f'id="{cible}"', contenu, f"cible htmx #{cible} absente de {url}")
        # Tout champ rattaché à un autre formulaire désigne un formulaire présent.
        for formulaire in set(re.findall(r'\sform="([\w-]+)"', contenu)):
            self.assertIn(f'id="{formulaire}"', contenu, f"formulaire #{formulaire} absent de {url}")

    def test_pages_connectees(self):
        self.client.login(username='u_pages', password='p')
        for url in self._pages():
            with self.subTest(url=url):
                self._controler(url, self.client.get(url))

    def test_pages_publiques(self):
        for nom in self.PAGES_PUBLIQUES:
            with self.subTest(page=nom):
                self._controler(reverse(nom), self.client.get(reverse(nom)))

    def test_fichiers_et_exports(self):
        """Les réponses qui ne sont pas des pages (fichiers, exports, PDF,
        graphique) fonctionnent toujours."""
        self.client.login(username='u_pages', password='p')
        for url in (
            reverse('animaux:exporter_csv'), reverse('animaux:exporter_excel'),
            reverse('animaux:pdf_fiche_animal', args=[self.animal.pk]),
            reverse('animaux:graphique_poids', args=[self.animal.pk]),
            reverse('factures:facture_fichier', args=[self.facture.pk]),
            reverse('documents:document_fichier', args=[self.document.pk]),
            reverse('accueil:robots_txt') if self._existe('accueil:robots_txt') else '/robots.txt',
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200, url)

    @staticmethod
    def _existe(nom):
        from django.urls import NoReverseMatch
        try:
            reverse(nom)
        except NoReverseMatch:
            return False
        return True

    def test_pages_des_modules_htmx_refusees_sans_connexion(self):
        """Les vues htmx des formulaires exigent toujours d'être connecté."""
        for nom in ('animaux:animal_choix_race', 'animaux:animal_apercu_photo', 'animaux:animal_identifications',
                    'animaux:espece_ajout_rapide', 'animaux:race_ajout_rapide', 'animaux:organisme_ajout_rapide',
                    'animaux:robe_ajout_rapide', 'animaux:proprietaire_ajout_rapide', 'vaccins:suivi_choix',
                    'vaccins:vaccin_ajout_rapide', 'vaccins:traitement_ajout_rapide',
                    'consultations:veterinaire_ajout_rapide', 'factures:facture_ventilation'):
            with self.subTest(vue=nom):
                response = self.client.post(reverse(nom), {})
                self.assertEqual(response.status_code, 302, nom)
                self.assertIn(reverse('login'), response['Location'], nom)


class LimitationTentativesAdresseTest(TestCase):
    """Projet_veto.throttling derrière le reverse-proxy : gunicorn sur socket
    unix donne un REMOTE_ADDR vide, qui faisait planter la 3e tentative (500)
    et mettait tous les visiteurs sur le même compteur."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)

    def _requete(self, **meta):
        from django.test import RequestFactory
        return RequestFactory().post('/accounts/login/', **meta)

    def test_adresse_vide_sans_proxy_aucune_limitation_ni_erreur(self):
        from Projet_veto import throttling
        from .models import BlocageAdresse

        requete = self._requete(REMOTE_ADDR='')
        self.assertIsNone(throttling._adresse_ip(requete))
        for _ in range(5):
            throttling.enregistrer_tentative('login', requete)
        self.assertFalse(throttling.est_bloque('login', requete))
        throttling.reinitialiser_tentatives('login', requete)
        self.assertFalse(BlocageAdresse.objects.exists())

    @override_settings(BEHIND_REVERSE_PROXY=True)
    def test_derriere_le_proxy_adresse_reelle_dernier_element_de_x_forwarded_for(self):
        from Projet_veto import throttling

        requete = self._requete(REMOTE_ADDR='', HTTP_X_FORWARDED_FOR='198.51.100.7, 203.0.113.9')
        # Le premier élément vient du client (falsifiable) : c'est le dernier,
        # ajouté par le proxy, qui fait foi.
        self.assertEqual(throttling._adresse_ip(requete), '203.0.113.9')

    @override_settings(BEHIND_REVERSE_PROXY=False)
    def test_x_forwarded_for_ignore_sans_proxy_de_confiance(self):
        from Projet_veto import throttling

        requete = self._requete(REMOTE_ADDR='192.0.2.4', HTTP_X_FORWARDED_FOR='203.0.113.9')
        self.assertEqual(throttling._adresse_ip(requete), '192.0.2.4')

    @override_settings(BEHIND_REVERSE_PROXY=True)
    def test_connexion_socket_unix_blocage_par_visiteur_sans_erreur_500(self):
        from .models import BlocageAdresse

        User.objects.create_user(username='alex', password='motdepasse123')
        mauvais = {'username': 'alex', 'password': 'faux'}
        for _ in range(3):
            response = self.client.post(
                reverse('login'), mauvais, REMOTE_ADDR='', HTTP_X_FORWARDED_FOR='203.0.113.9',
            )
            self.assertEqual(response.status_code, 200)
        self.assertTrue(BlocageAdresse.objects.filter(prefixe='login', adresse_ip='203.0.113.9').exists())

        # Ce visiteur est bloqué (même avec le bon mot de passe)...
        response = self.client.post(
            reverse('login'), {'username': 'alex', 'password': 'motdepasse123'},
            REMOTE_ADDR='', HTTP_X_FORWARDED_FOR='203.0.113.9',
        )
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        # ... mais pas un autre visiteur passant par le même proxy.
        response = self.client.post(
            reverse('login'), {'username': 'alex', 'password': 'motdepasse123'},
            REMOTE_ADDR='', HTTP_X_FORWARDED_FOR='203.0.113.50',
        )
        self.assertIn('_auth_user_id', self.client.session)

    def test_connexion_adresse_inexploitable_pas_d_erreur_500(self):
        User.objects.create_user(username='alex', password='motdepasse123')
        for _ in range(4):
            response = self.client.post(
                reverse('login'), {'username': 'alex', 'password': 'faux'}, REMOTE_ADDR='',
            )
            self.assertEqual(response.status_code, 200)

    def test_message_de_blocage_affiche_en_rouge(self):
        """messages.error() -> classe Bootstrap alert-danger (MESSAGE_TAGS),
        et non alert-error qui n'existe pas."""
        for _ in range(3):
            self.client.post(reverse('login'), {'username': 'x', 'password': 'faux'})
        response = self.client.post(reverse('login'), {'username': 'x', 'password': 'faux'}, follow=True)
        self.assertContains(response, 'Trop de tentatives')
        self.assertContains(response, 'alert alert-danger')
        self.assertNotContains(response, 'alert-error')


class ConnexionAdminEtMotDePasseOublieTest(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)

    def test_connexion_de_l_admin_renvoyee_vers_la_connexion_limitee(self):
        response = self.client.get('/admin/login/?next=/admin/')
        self.assertRedirects(response, reverse('login') + '?next=/admin/', fetch_redirect_response=False)
        # Aucun formulaire de connexion distinct n'accepte de mot de passe.
        response = self.client.post('/admin/login/', {'username': 'a', 'password': 'b'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('login'))

    def test_le_superutilisateur_accede_toujours_a_l_admin(self):
        User.objects.create_superuser(username='chef', email='chef@example.com', password='motdepasse123')
        self.client.login(username='chef', password='motdepasse123')
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_mot_de_passe_oublie_limite_par_adresse(self):
        User.objects.create_user(username='alex', email='alex@example.com', password='motdepasse123')
        for _ in range(5):
            response = self.client.post(reverse('password_reset'), {'email': 'alex@example.com'})
            self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 5)

        response = self.client.post(reverse('password_reset'), {'email': 'alex@example.com'}, follow=True)
        self.assertRedirects(response, reverse('password_reset'))
        self.assertContains(response, 'Trop de demandes')
        self.assertEqual(len(mail.outbox), 5)

    def test_mot_de_passe_oublie_n_annonce_que_l_email(self):
        response = self.client.get(reverse('password_reset'))
        self.assertNotContains(response, "nom d'utilisateur")
        self.assertContains(response, "adresse email de ton compte")


class EmailUniqueEtInvitationLieeAuCompteTest(TestCase):
    """Une invitation de foyer est adressée à un compte précis, et non à
    quiconque déclare le même email (ni vérifié, ni unique auparavant)."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
        self.alex = User.objects.create_user(username='alex', email='alex@example.com', password='motdepasse123')
        self.sam = User.objects.create_user(username='sam', email='Sam.Durand@example.com', password='motdepasse123')

    def _inscrire(self, **donnees):
        return self.client.post(reverse('accueil:inscription'), {
            'username': 'intrus', 'password1': 'un-mot-de-passe-solide-42',
            'password2': 'un-mot-de-passe-solide-42', **donnees,
        })

    def test_inscription_refusee_avec_l_email_d_un_compte_existant(self):
        for email in ('Sam.Durand@example.com', 'sam.durand@EXAMPLE.com'):
            with self.subTest(email=email):
                response = self._inscrire(email=email)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Un compte existe déjà avec cet email.')
                self.assertFalse(User.objects.filter(username='intrus').exists())

    def test_invitation_insensible_a_la_casse_et_rattachee_au_compte(self):
        self.client.login(username='alex', password='motdepasse123')
        self.client.post(reverse('accueil:partage_inviter'), {'email': 'sam.durand@example.com'})
        invitation = InvitationFoyer.objects.get()
        self.assertEqual(invitation.invite, self.sam)

        self.client.login(username='sam', password='motdepasse123')
        response = self.client.get(reverse('accueil:partage_compte'))
        self.assertContains(response, reverse('accueil:partage_accepter', args=[invitation.token]))

    def test_un_compte_de_meme_email_ne_voit_ni_n_accepte_l_invitation(self):
        """Doublon d'email hérité (créé avant le contrôle d'unicité) : il ne
        donne aucun droit sur l'invitation adressée à l'autre compte."""
        invitation = InvitationFoyer.objects.create(
            foyer=Foyer.objects.create(), invite_par=self.alex, email_invite=self.sam.email, invite=self.sam,
        )
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=invitation.foyer)
        User.objects.create_user(username='usurpateur', email=self.sam.email, password='motdepasse123')

        self.client.login(username='usurpateur', password='motdepasse123')
        response = self.client.get(reverse('accueil:partage_compte'))
        self.assertNotContains(response, invitation.token)
        for action in ('accueil:partage_accepter', 'accueil:partage_refuser'):
            response = self.client.post(reverse(action, args=[invitation.token]))
            self.assertEqual(response.status_code, 404)
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.EN_ATTENTE)
        self.assertFalse(MembreFoyer.objects.filter(utilisateur__username='usurpateur').exists())

    def test_email_en_doublon_herite_impossible_a_inviter(self):
        User.objects.create_user(username='doublon', email='sam.durand@example.com', password='motdepasse123')
        self.client.login(username='alex', password='motdepasse123')
        self.client.post(reverse('accueil:partage_inviter'), {'email': 'sam.durand@example.com'})
        self.assertFalse(InvitationFoyer.objects.exists())

    def test_la_migration_annule_les_invitations_en_attente_sans_invite(self):
        import importlib

        from django.apps import apps

        foyer = Foyer.objects.create()
        ancienne = InvitationFoyer.objects.create(foyer=foyer, invite_par=self.alex, email_invite='x@example.com')
        liee = InvitationFoyer.objects.create(
            foyer=foyer, invite_par=self.alex, email_invite=self.sam.email, invite=self.sam,
        )
        migration = importlib.import_module('accueil.migrations.0005_invitationfoyer_invite')
        migration.annuler_invitations_sans_invite(apps, None)
        ancienne.refresh_from_db()
        liee.refresh_from_db()
        self.assertEqual(ancienne.statut, InvitationFoyer.Statut.ANNULEE)
        self.assertEqual(liee.statut, InvitationFoyer.Statut.EN_ATTENTE)

    def test_resolution_des_notifications_insensible_a_la_casse(self):
        from notifications.utils import resoudre_utilisateur

        self.assertEqual(resoudre_utilisateur('sam.durand@example.com'), self.sam)
        self.assertIsNone(resoudre_utilisateur('inconnu@example.com'))

    def test_echec_smtp_invitation_enregistree_sans_erreur_500(self):
        from unittest import mock

        from notifications.models import Notification

        self.client.login(username='alex', password='motdepasse123')
        with mock.patch('accueil.views.envoyer_email', side_effect=OSError('SMTP injoignable')):
            with self.assertLogs('accueil.views', level='ERROR'):
                response = self.client.post(
                    reverse('accueil:partage_inviter'), {'email': self.sam.email}, follow=True,
                )
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        self.assertContains(response, "pas pu être envoyé")
        self.assertTrue(InvitationFoyer.objects.filter(invite=self.sam).exists())
        # L'invité est tout de même prévenu dans l'application.
        self.assertTrue(Notification.objects.filter(utilisateur=self.sam, type='INVITATION_FOYER').exists())


class RetraitReserveAuFondateurTest(TestCase):
    """Décision produit : seul le fondateur du foyer peut retirer un membre
    (avoir invité quelqu'un ne suffit plus) ; chacun peut toujours quitter le
    foyer ; le fondateur ne peut pas être retiré ; s'il quitte le foyer, le
    plus ancien membre restant devient fondateur."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex', email='alex@example.com', password='p')
        self.sam = User.objects.create_user(username='sam', email='sam@example.com', password='p')
        self.tiers = User.objects.create_user(username='tiers', email='tiers@example.com', password='p')
        self.foyer = Foyer.objects.create()
        # Alex fonde le foyer et invite Sam, qui invite Tiers.
        self.membre_alex = MembreFoyer.objects.create(utilisateur=self.alex, foyer=self.foyer, invite_par=None)
        self.membre_sam = MembreFoyer.objects.create(utilisateur=self.sam, foyer=self.foyer, invite_par=self.alex)
        self.membre_tiers = MembreFoyer.objects.create(utilisateur=self.tiers, foyer=self.foyer, invite_par=self.sam)

    def _retirer(self, auteur, membre):
        self.client.login(username=auteur, password='p')
        return self.client.post(reverse('accueil:partage_retirer_membre', args=[membre.pk]))

    def _boutons_retirer(self, auteur):
        self.client.login(username=auteur, password='p')
        contenu = self.client.get(reverse('accueil:partage_compte')).content.decode()
        return re.findall(r'action="(/[^"]*retirer[^"]*)"', contenu)

    def test_fondateur_identifie(self):
        self.assertEqual(self.foyer.membre_fondateur(), self.membre_alex)
        self.assertTrue(self.membre_alex.est_fondateur())
        self.assertFalse(self.membre_sam.est_fondateur())

    def test_l_inviteur_non_fondateur_ne_peut_plus_retirer_son_invite(self):
        response = self._retirer('sam', self.membre_tiers)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(MembreFoyer.objects.filter(pk=self.membre_tiers.pk).exists())

    def test_le_fondateur_retire_un_membre_qu_il_n_a_pas_invite(self):
        response = self._retirer('alex', self.membre_tiers)
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        self.assertFalse(MembreFoyer.objects.filter(pk=self.membre_tiers.pk).exists())
        self.assertTrue(MembreFoyer.objects.filter(pk=self.membre_sam.pk).exists())

    def test_le_fondateur_ne_peut_etre_retire_par_personne(self):
        for auteur in ('sam', 'tiers', 'alex'):
            self.assertEqual(self._retirer(auteur, self.membre_alex).status_code, 404, auteur)
        self.assertTrue(MembreFoyer.objects.filter(pk=self.membre_alex.pk).exists())

    def test_invite_par_vide_ne_fait_pas_un_fondateur(self):
        """`invite_par` est vidé (SET_NULL) quand le compte de l'inviteur est
        supprimé : cela ne doit donner aucun droit de retrait."""
        MembreFoyer.objects.filter(pk=self.membre_tiers.pk).update(invite_par=None)
        self.assertEqual(self._retirer('tiers', self.membre_sam).status_code, 404)
        self.assertTrue(MembreFoyer.objects.filter(pk=self.membre_sam.pk).exists())

    def test_le_fondateur_ne_retire_pas_un_membre_d_un_autre_foyer(self):
        etranger = User.objects.create_user(username='etranger', password='p')
        autre = User.objects.create_user(username='autre', password='p')
        autre_foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=autre, foyer=autre_foyer)
        membre_etranger = MembreFoyer.objects.create(utilisateur=etranger, foyer=autre_foyer, invite_par=autre)
        self.assertEqual(self._retirer('alex', membre_etranger).status_code, 404)
        self.assertTrue(MembreFoyer.objects.filter(pk=membre_etranger.pk).exists())

    def test_compte_sans_foyer_ne_retire_personne(self):
        User.objects.create_user(username='solo', password='p')
        self.assertEqual(self._retirer('solo', self.membre_tiers).status_code, 404)

    def test_bouton_retirer_reserve_au_fondateur(self):
        self.assertEqual(len(self._boutons_retirer('alex')), 2)
        self.assertEqual(self._boutons_retirer('sam'), [])
        self.assertEqual(self._boutons_retirer('tiers'), [])
        self.client.login(username='sam', password='p')
        response = self.client.get(reverse('accueil:partage_compte'))
        self.assertContains(response, 'Seul le fondateur du foyer peut retirer un membre')
        self.assertContains(response, '(fondateur du foyer)')

    def test_chacun_peut_toujours_quitter_le_foyer(self):
        for nom, utilisateur in (('tiers', self.tiers), ('sam', self.sam)):
            self.client.login(username=nom, password='p')
            response = self.client.post(reverse('accueil:partage_quitter'))
            self.assertRedirects(response, reverse('accueil:partage_compte'))
            self.assertFalse(MembreFoyer.objects.filter(utilisateur=utilisateur).exists())

    def test_si_le_fondateur_quitte_le_plus_ancien_membre_restant_devient_fondateur(self):
        self.client.login(username='alex', password='p')
        self.client.post(reverse('accueil:partage_quitter'))
        self.assertFalse(MembreFoyer.objects.filter(utilisateur=self.alex).exists())

        self.assertEqual(self.foyer.membre_fondateur(), self.membre_sam)
        # Tiers, plus récent, n'a toujours aucun droit de retrait…
        self.assertEqual(self._retirer('tiers', self.membre_sam).status_code, 404)
        self.assertEqual(self._boutons_retirer('tiers'), [])
        # … Sam, nouveau fondateur, voit le bouton et peut retirer Tiers.
        self.assertEqual(len(self._boutons_retirer('sam')), 1)
        self.assertRedirects(self._retirer('sam', self.membre_tiers), reverse('accueil:partage_compte'))
        self.assertFalse(MembreFoyer.objects.filter(pk=self.membre_tiers.pk).exists())

    def test_un_ancien_fondateur_revenu_n_est_plus_fondateur(self):
        self.client.login(username='alex', password='p')
        self.client.post(reverse('accueil:partage_quitter'))
        revenu = MembreFoyer.objects.create(utilisateur=self.alex, foyer=self.foyer, invite_par=self.sam)
        self.assertFalse(revenu.est_fondateur())
        self.assertEqual(self._retirer('alex', self.membre_tiers).status_code, 404)


class FoyerSoloEtInvitationsPerimeesTest(TestCase):
    def setUp(self):
        self.dominique = User.objects.create_user(username='dominique', email='do@example.com', password='p')
        self.alex = User.objects.create_user(username='alex', email='alex@example.com', password='p')
        self.sam = User.objects.create_user(username='sam', email='sam@example.com', password='p')

    def _inviter(self, auteur, email):
        self.client.login(username=auteur, password='p')
        self.client.post(reverse('accueil:partage_inviter'), {'email': email})
        return InvitationFoyer.objects.filter(email_invite=email).latest('pk')

    def _foyer_dominique_alex(self):
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.dominique, foyer=foyer)
        return MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=self.dominique)

    def test_quitter_le_foyer_annule_ses_invitations_en_attente(self):
        self._foyer_dominique_alex()
        invitation = self._inviter('alex', 'sam@example.com')
        self.client.post(reverse('accueil:partage_quitter'))
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.ANNULEE)

        self.client.login(username='sam', password='p')
        response = self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(MembreFoyer.objects.filter(utilisateur=self.sam).exists())

    def test_retirer_un_membre_annule_ses_invitations_en_attente(self):
        membre_alex = self._foyer_dominique_alex()
        invitation = self._inviter('alex', 'sam@example.com')
        self.client.login(username='dominique', password='p')
        self.client.post(reverse('accueil:partage_retirer_membre', args=[membre_alex.pk]))
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.ANNULEE)

    def test_acceptation_refusee_si_l_auteur_n_est_plus_dans_le_foyer(self):
        """Garde-fou même si l'invitation n'a pas été annulée au départ de son
        auteur (ex. membre supprimé hors des vues)."""
        membre_alex = self._foyer_dominique_alex()
        invitation = self._inviter('alex', 'sam@example.com')
        membre_alex.delete()

        self.client.login(username='sam', password='p')
        response = self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]), follow=True)
        self.assertContains(response, "plus valable")
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.ANNULEE)
        self.assertFalse(MembreFoyer.objects.filter(utilisateur=self.sam).exists())

    def test_un_foyer_solo_n_empeche_pas_d_etre_invite_puis_disparait_a_l_acceptation(self):
        # Sam invite puis annule : il reste seul dans un foyer créé à la volée.
        invitation_sam = self._inviter('sam', 'do@example.com')
        self.client.post(reverse('accueil:partage_annuler', args=[invitation_sam.pk]))
        foyer_solo = MembreFoyer.objects.get(utilisateur=self.sam).foyer

        invitation = self._inviter('alex', 'sam@example.com')
        self.assertEqual(invitation.invite, self.sam)

        self.client.login(username='sam', password='p')
        self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]))
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationFoyer.Statut.ACCEPTEE)
        self.assertEqual(MembreFoyer.objects.get(utilisateur=self.sam).foyer, invitation.foyer)
        self.assertFalse(Foyer.objects.filter(pk=foyer_solo.pk).exists())

    def test_quitter_et_retirer_ne_remplacent_que_le_contenu_principal(self):
        """hx-boost sans cible remplaçait tout <body>, scripts compris."""
        self._foyer_dominique_alex()
        self.client.login(username='dominique', password='p')
        contenu = self.client.get(reverse('accueil:partage_compte')).content.decode()
        formulaires = re.findall(r'<form[^>]*hx-boost="true"[^>]*>', contenu)
        self.assertEqual(len(formulaires), 2)
        for formulaire in formulaires:
            self.assertIn('hx-target="#contenu-principal"', formulaire)
            self.assertIn('hx-select="#contenu-principal"', formulaire)
        self.assertIn('<title>Partage de compte - vos animaux de compagnie</title>', contenu)


class PreferencesVisiteurReprisesALInscriptionTest(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user(username='existant', password='p')
        # Le visiteur règle le panneau avant d'avoir un compte (cookie signé).
        self.client.post(reverse('accueil:preferences_accessibilite'), {
            'taille_texte': 'tres-grand', 'contraste_eleve': 'on',
        })

    def _inscrire(self, **cases):
        self.client.post(reverse('accueil:inscription'), {
            'username': 'nouveau', 'email': 'nouveau@example.com',
            'password1': 'un-mot-de-passe-solide-42', 'password2': 'un-mot-de-passe-solide-42', **cases,
        })
        return PreferenceAccessibilite.objects.get(utilisateur__username='nouveau')

    def test_cases_precochees_d_apres_les_reglages_du_visiteur(self):
        formulaire = self.client.get(reverse('accueil:inscription')).context['form']
        self.assertTrue(formulaire.initial['texte_agrandi'])
        self.assertTrue(formulaire.initial['contraste_eleve'])
        self.assertFalse(formulaire.initial['mode_sombre'])
        self.assertIn('checked', str(formulaire['contraste_eleve']))

    def test_tres_grand_conserve_a_la_creation_du_compte(self):
        preferences = self._inscrire(texte_agrandi='on', contraste_eleve='on')
        self.assertEqual(preferences.taille_texte, PreferenceAccessibilite.Taille.TRES_GRAND)
        self.assertTrue(preferences.contraste_eleve)

    def test_cases_decochees_le_visiteur_garde_le_dernier_mot(self):
        preferences = self._inscrire()
        self.assertEqual(preferences.taille_texte, PreferenceAccessibilite.Taille.NORMAL)
        self.assertFalse(preferences.contraste_eleve)


class NotificationsEnPostTest(TestCase):
    """notifications/ n'a pas de suite de tests propre (cf. pytest.ini)."""

    def setUp(self):
        from notifications.models import Notification

        self.utilisateur = User.objects.create_user(username='alex', password='p')
        self.autre = User.objects.create_user(username='sam', password='p')
        self.notification = Notification.objects.create(
            utilisateur=self.utilisateur, type='NOUVEAU_DOCUMENT', titre='Nouveau document', message='m',
            lien='/documents/1/',
        )
        self.client.login(username='alex', password='p')

    def test_un_simple_get_ne_modifie_rien(self):
        from notifications.models import Notification

        for url in (
            reverse('notifications:marquer_lue', args=[self.notification.pk]),
            reverse('notifications:marquer_toutes_lues'),
            reverse('notifications:supprimer_notification', args=[self.notification.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(Notification.objects.filter(pk=self.notification.pk, lue=False).exists())

    def test_actions_en_post(self):
        from notifications.models import Notification

        liste = reverse('notifications:notification_list')
        response = self.client.post(reverse('notifications:marquer_lue', args=[self.notification.pk]))
        self.assertRedirects(response, liste)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.lue)

        seconde = Notification.objects.create(utilisateur=self.utilisateur, type='NOUVEAU_DOCUMENT', titre='t', message='m')
        self.assertRedirects(self.client.post(reverse('notifications:marquer_toutes_lues')), liste)
        seconde.refresh_from_db()
        self.assertTrue(seconde.lue)

        self.assertRedirects(
            self.client.post(reverse('notifications:supprimer_notification', args=[seconde.pk])), liste,
        )
        self.assertFalse(Notification.objects.filter(pk=seconde.pk).exists())

    def test_notification_d_un_autre_compte_intouchable(self):
        self.client.login(username='sam', password='p')
        response = self.client.post(reverse('notifications:supprimer_notification', args=[self.notification.pk]))
        self.assertEqual(response.status_code, 404)

    def test_la_page_propose_des_formulaires_et_plus_de_liens_modifiants(self):
        contenu = self.client.get(reverse('notifications:notification_list')).content.decode()
        for url in (
            reverse('notifications:marquer_lue', args=[self.notification.pk]),
            reverse('notifications:marquer_toutes_lues'),
            reverse('notifications:supprimer_notification', args=[self.notification.pk]),
        ):
            with self.subTest(url=url):
                self.assertNotIn(f'href="{url}"', contenu)
                self.assertRegex(contenu, rf'<form method="post" action="{re.escape(url)}"')
        # Ouvrir la notification reste un simple lien vers son objet.
        self.assertIn('<a href="/documents/1/">', contenu)
        # Non lue : plus de fond bleu (« active ») sous un titre lui-même bleu.
        self.assertNotIn('list-group-item active', contenu)
        self.assertIn('<title>Mes notifications - vos animaux de compagnie</title>', contenu)


class SessionExpireeHtmxTest(TestCase):
    """Projet_veto.middleware.ConnexionRequiseHtmxMiddleware."""

    def test_requete_htmx_sans_session_vraie_navigation_vers_la_connexion(self):
        response = self.client.get(reverse('animaux:animal_list'), {'tri': 'nom'}, headers={
            'HX-Request': 'true', 'HX-Current-URL': 'http://testserver/animaux/?q=rex&page=2#zoneListe',
        })
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['HX-Redirect'], reverse('login') + '?next=/animaux/%3Fq%3Drex%26page%3D2')

    def test_next_est_la_page_courante_pas_le_point_d_entree_post(self):
        response = self.client.post(reverse('factures:facture_ventilation'), {}, headers={
            'HX-Request': 'true', 'HX-Current-URL': 'http://testserver/factures/ajouter/',
        })
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['HX-Redirect'], reverse('login') + '?next=/factures/ajouter/')

    def test_jamais_d_adresse_externe_dans_next(self):
        for courante in ('https://exemple.invalid/piege', '', '//exemple.invalid/x'):
            with self.subTest(courante=courante):
                response = self.client.get(reverse('consultations:calendrier'), headers={
                    'HX-Request': 'true', 'HX-Current-URL': courante,
                })
                self.assertEqual(response.status_code, 204)
                self.assertEqual(
                    response['HX-Redirect'], reverse('login') + '?next=' + reverse('animaux:animal_list'),
                )

    def test_requete_ordinaire_toujours_redirigee(self):
        response = self.client.get(reverse('animaux:animal_list'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('HX-Redirect', response)

    def test_requete_htmx_connectee_inchangee(self):
        User.objects.create_user(username='alex', password='p')
        self.client.login(username='alex', password='p')
        response = self.client.get(reverse('animaux:animal_list'), headers={
            'HX-Request': 'true', 'HX-Current-URL': 'http://testserver/animaux/',
        })
        self.assertEqual(response.status_code, 200)
        # Une redirection qui ne mène pas à la connexion n'est pas touchée.
        response = self.client.post(reverse('accueil:partage_quitter'), headers={'HX-Request': 'true'})
        self.assertEqual(response.status_code, 404)

    def test_formulaire_booste_sans_session(self):
        response = self.client.post(reverse('accueil:partage_quitter'), headers={
            'HX-Request': 'true', 'HX-Current-URL': 'http://testserver/partage/',
        })
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['HX-Redirect'], reverse('login') + '?next=/partage/')


class ListesRechercheTest(TestCase):
    def setUp(self):
        User.objects.create_user(username='alex', password='p')
        self.client.login(username='alex', password='p')

    def test_octet_nul_dans_la_recherche_sans_erreur_500(self):
        response = self.client.get(reverse('consultations:veterinaire_list') + '?q=a%00b')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['q'], 'ab')

    def test_la_frappe_remplace_l_url_sans_empiler_l_historique(self):
        contenu = self.client.get(reverse('consultations:veterinaire_list')).content.decode()
        champ = re.search(r'<input type="search"[^>]*>', contenu).group(0)
        self.assertIn('hx-replace-url="true"', champ)
        self.assertNotIn('hx-push-url', champ)


class PagesErreurTest(TestCase):
    def test_404_en_francais_avec_lien_de_retour(self):
        response = self.client.get('/cette-page-n-existe-pas/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page introuvable', status_code=404)
        self.assertContains(response, reverse('accueil:accueil'), status_code=404)
        self.assertNotContains(response, '<script', status_code=404)

    def test_404_connecte_lien_vers_ses_animaux(self):
        User.objects.create_user(username='alex', password='p')
        self.client.login(username='alex', password='p')
        response = self.client.get(reverse('documents:document_detail', args=[999999]))
        self.assertContains(response, reverse('animaux:animal_list'), status_code=404)

    def test_403(self):
        from django.contrib.auth.models import AnonymousUser
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory
        from django.views.defaults import permission_denied

        requete = RequestFactory().get('/')
        requete.user = AnonymousUser()
        response = permission_denied(requete, PermissionDenied())
        self.assertEqual(response.status_code, 403)
        self.assertIn('Accès refusé', response.content.decode())

    def test_500_statique_sans_aucune_balise_de_gabarit(self):
        from pathlib import Path

        from django.conf import settings
        from django.test import RequestFactory
        from django.views.defaults import server_error

        response = server_error(RequestFactory().get('/'))
        self.assertEqual(response.status_code, 500)
        self.assertIn('Une erreur est survenue', response.content.decode())
        for nom in ('500.html', '403_csrf.html'):
            source = (Path(settings.BASE_DIR) / 'templates' / nom).read_text(encoding='utf-8')
            self.assertNotIn('{%', source, nom)
            self.assertNotIn('{{', source, nom)

    def test_echec_csrf_en_francais(self):
        from django.test import Client

        response = Client(enforce_csrf_checks=True).post(reverse('login'), {'username': 'a', 'password': 'b'})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Session expirée', status_code=403)


class ReglagesCeleryTest(SimpleTestCase):
    def test_delai_de_visibilite_superieur_aux_rappels_lointains(self):
        """Sans lui (1 h par défaut avec Redis), un rappel planifié à
        plusieurs jours était redélivré toutes les heures, donc envoyé en
        plusieurs exemplaires."""
        from Projet_veto.celery import app

        delai = app.conf.broker_transport_options['visibility_timeout']
        self.assertGreaterEqual(delai, 366 * 24 * 3600)


class AdminCataloguesParCompteTest(TestCase):
    """Le compte créateur d'une entrée de catalogue est visible et filtrable
    dans l'administration."""

    def test_colonne_et_filtre_compte(self):
        from django.contrib import admin
        from consultations.models import Veterinaire
        from documents.models import TypeDocument
        from factures.models import Designation
        from vaccins.models import Traitement, Vaccin

        for model in (Veterinaire, Vaccin, Traitement, Designation, TypeDocument):
            with self.subTest(modele=model.__name__):
                reglages = admin.site._registry[model]
                self.assertIn('utilisateur', reglages.list_display)
                self.assertIn('utilisateur', reglages.list_filter)

    def test_listes_de_l_administration(self):
        from vaccins.models import Vaccin
        admin_ = User.objects.create_superuser(username='admin_cat', password='p', email='admin_cat@example.com')
        Vaccin.objects.create(nom='TEST_TEMP_admin', utilisateur=admin_)
        self.client.login(username='admin_cat', password='p')
        for nom in ('consultations_veterinaire', 'vaccins_vaccin', 'vaccins_traitement',
                    'factures_designation', 'documents_typedocument'):
            with self.subTest(liste=nom):
                self.assertEqual(self.client.get(reverse(f'admin:{nom}_changelist')).status_code, 200)


def _fonction_de_reprise():
    from importlib import import_module
    return import_module('accueil.migrations.0007_rattacher_catalogues_aux_comptes').rattacher_catalogues


class RepriseCataloguesTest(TestCase):
    """Fonction de reprise des catalogues jusque-là communs (migration
    accueil.0007), appelée directement sur les catalogues dont le compte
    reste facultatif (Vaccin, Traitement, TypeDocument). Veterinaire et
    Designation, dont le compte est obligatoire une fois les migrations
    passées, sont couverts par RepriseCataloguesMigrationTest."""

    def setUp(self):
        from datetime import date, timedelta
        from django.utils import timezone
        from animaux.models import Animal, Espece, Proprietaire, Race, Robe

        maintenant = timezone.now()

        def compte(nom, jours, **options):
            utilisateur = User.objects.create_user(username=nom, password='p', **options)
            User.objects.filter(pk=utilisateur.pk).update(date_joined=maintenant - timedelta(days=jours))
            return utilisateur

        # Du plus ancien au plus récent : alex, sam (même foyer), tiers, puis
        # l'administrateur — plus récent que tous, pour vérifier qu'une entrée
        # inutilisée va au superutilisateur et non au plus ancien compte.
        self.alex = compte('alex_rep', 40)
        self.sam = compte('sam_rep', 30)
        self.tiers = compte('tiers_rep', 20)
        self.admin = compte('admin_rep', 10, is_superuser=True)
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)

        chien = Espece.objects.get(code='CHIEN')

        def animal(utilisateur):
            proprietaire = Proprietaire.objects.create(
                nom='TEST_TEMP', email=f'{utilisateur.username}@example.com', utilisateur=utilisateur,
            )
            return Animal.objects.create(
                nom=f'TEST_TEMP_{utilisateur.username}', race=Race.objects.filter(espece=chien).first(),
                espece=chien, date_naissance=date(2020, 1, 1), robe=Robe.objects.get(code='AUTRE'),
                proprietaire=proprietaire, utilisateur=utilisateur,
            )

        self.animaux = {u: animal(u) for u in (self.alex, self.sam, self.tiers)}

    def _suivi(self, utilisateur, **entree):
        from datetime import date
        from vaccins.models import SuiviVaccinTraitement
        return SuiviVaccinTraitement.objects.create(
            animal=self.animaux[utilisateur], date=date(2026, 1, 1), numero_lot='TEST_TEMP_LOT', **entree,
        )

    def _reprendre(self):
        from django.apps import apps
        return _fonction_de_reprise()(apps)

    def test_base_sans_entree_a_reprendre(self):
        """Seules restent sans compte les entrées de référence : rien n'est
        rattaché, rien n'est dupliqué (cas d'une base neuve)."""
        from vaccins.models import Traitement, Vaccin
        nombres = Vaccin.objects.count(), Traitement.objects.count()
        bilan = self._reprendre()
        self.assertEqual((Vaccin.objects.count(), Traitement.objects.count()), nombres)
        self.assertFalse(Vaccin.objects.filter(utilisateur__isnull=False).exists())
        self.assertEqual(bilan['Vaccin']['reference'], nombres[0])
        self.assertEqual(bilan['Traitement']['reference'], nombres[1])
        for compteurs in bilan.values():
            self.assertEqual(
                (compteurs['rattachees'], compteurs['dupliquees'], compteurs['copies'], compteurs['inutilisees']),
                (0, 0, 0, 0),
            )

    def test_entree_de_reference_laissee_sans_compte_meme_utilisee(self):
        from documents.models import TypeDocument
        from vaccins.models import Traitement, Vaccin
        rage = Vaccin.objects.get(nom='Rage')
        suivi = self._suivi(self.tiers, vaccin=rage)
        self._reprendre()
        rage.refresh_from_db()
        suivi.refresh_from_db()
        self.assertIsNone(rage.utilisateur)
        self.assertEqual(suivi.vaccin, rage)
        self.assertEqual(Vaccin.objects.filter(nom='Rage').count(), 1)
        # Toutes les entrées créées par les migrations « seed » sont reconnues.
        for model in (Vaccin, Traitement, TypeDocument):
            self.assertFalse(model.objects.filter(utilisateur__isnull=False).exists(), model.__name__)

    def test_entree_utilisee_par_un_seul_compte(self):
        from vaccins.models import Vaccin
        vaccin = Vaccin.objects.create(nom='TEST_TEMP_mono', description='TEST_TEMP description')
        suivi = self._suivi(self.tiers, vaccin=vaccin)
        bilan = self._reprendre()
        vaccin.refresh_from_db()
        suivi.refresh_from_db()
        self.assertEqual(vaccin.utilisateur, self.tiers)
        self.assertEqual(suivi.vaccin, vaccin)
        self.assertEqual(Vaccin.objects.filter(nom='TEST_TEMP_mono').count(), 1)
        self.assertEqual(bilan['Vaccin']['rattachees'], 1)

    def test_entree_utilisee_par_un_seul_foyer(self):
        """Deux membres du même foyer : une seule entrée, rattachée au compte
        qui l'utilise le plus ; le plus ancien à égalité."""
        from vaccins.models import Traitement
        majoritaire = Traitement.objects.create(nom='TEST_TEMP_majoritaire', classe=Traitement.Classe.GEL)
        self._suivi(self.alex, traitement=majoritaire)
        self._suivi(self.sam, traitement=majoritaire)
        self._suivi(self.sam, traitement=majoritaire)
        egalite = Traitement.objects.create(nom='TEST_TEMP_egalite', classe=Traitement.Classe.GEL)
        self._suivi(self.sam, traitement=egalite)
        self._suivi(self.alex, traitement=egalite)
        bilan = self._reprendre()
        majoritaire.refresh_from_db()
        egalite.refresh_from_db()
        self.assertEqual(majoritaire.utilisateur, self.sam)
        self.assertEqual(egalite.utilisateur, self.alex)
        self.assertEqual(Traitement.objects.filter(nom__startswith='TEST_TEMP_').count(), 2)
        self.assertEqual(majoritaire.suivi_animaux.count(), 3)
        self.assertEqual(bilan['Traitement']['rattachees'], 2)
        self.assertEqual(bilan['Traitement']['copies'], 0)

    def test_entree_utilisee_par_plusieurs_foyers_dupliquee(self):
        """Une copie par foyer, à l'identique, et chaque suivi repointé vers
        la copie de son foyer — aucun suivi perdu ni modifié."""
        from vaccins.models import SuiviVaccinTraitement, Vaccin
        vaccin = Vaccin.objects.create(
            nom='TEST_TEMP_multi', description='TEST_TEMP description', categorie='ESSENTIEL',
            rappel_interval='Annuel',
        )
        suivis = {
            self.alex: self._suivi(self.alex, vaccin=vaccin),
            self.sam: self._suivi(self.sam, vaccin=vaccin),
            self.tiers: self._suivi(self.tiers, vaccin=vaccin),
        }
        bilan = self._reprendre()

        copies = Vaccin.objects.filter(nom='TEST_TEMP_multi')
        self.assertEqual(copies.count(), 2)
        du_foyer = copies.get(utilisateur=self.alex)
        du_tiers = copies.get(utilisateur=self.tiers)
        # Le foyer du plus ancien compte garde la ligne d'origine.
        self.assertEqual(du_foyer.pk, vaccin.pk)
        for copie in (du_foyer, du_tiers):
            self.assertEqual(
                (copie.description, copie.categorie, copie.rappel_interval),
                ('TEST_TEMP description', 'ESSENTIEL', 'Annuel'),
            )
        for utilisateur, attendu in ((self.alex, du_foyer), (self.sam, du_foyer), (self.tiers, du_tiers)):
            suivi = SuiviVaccinTraitement.objects.get(pk=suivis[utilisateur].pk)
            self.assertEqual(suivi.vaccin, attendu)
            self.assertEqual(suivi.numero_lot, 'TEST_TEMP_LOT')
            self.assertEqual(suivi.animal, self.animaux[utilisateur])
        self.assertEqual(SuiviVaccinTraitement.objects.filter(vaccin__nom='TEST_TEMP_multi').count(), 3)
        self.assertEqual((bilan['Vaccin']['dupliquees'], bilan['Vaccin']['copies']), (1, 1))

    def test_type_de_document_multi_foyers(self):
        """Même reprise pour un autre catalogue et un autre modèle référent."""
        from documents.models import Document, TypeDocument
        type_document = TypeDocument.objects.create(nom='TEST_TEMP_type')
        # bulk_create : ni fichier écrit sur le disque, ni notification.
        Document.objects.bulk_create([
            Document(animal=self.animaux[utilisateur], type_document=type_document,
                     titre=f'TEST_TEMP_{utilisateur.username}', fichier='documents/test_temp_absent.pdf')
            for utilisateur in (self.sam, self.tiers)
        ])
        self._reprendre()
        self.assertEqual(Document.objects.get(titre='TEST_TEMP_sam_rep').type_document.utilisateur, self.sam)
        self.assertEqual(Document.objects.get(titre='TEST_TEMP_tiers_rep').type_document.utilisateur, self.tiers)
        self.assertEqual(TypeDocument.objects.filter(nom='TEST_TEMP_type').count(), 2)

    def test_entree_inutilisee_rattachee_au_plus_ancien_superutilisateur(self):
        from vaccins.models import Vaccin
        vaccin = Vaccin.objects.create(nom='TEST_TEMP_inutilise')
        bilan = self._reprendre()
        vaccin.refresh_from_db()
        self.assertEqual(vaccin.utilisateur, self.admin)
        self.assertEqual(bilan['Vaccin']['inutilisees'], 1)

    def test_entree_inutilisee_sans_superutilisateur_va_au_plus_ancien_compte(self):
        from vaccins.models import Vaccin
        User.objects.filter(pk=self.admin.pk).update(is_superuser=False)
        vaccin = Vaccin.objects.create(nom='TEST_TEMP_inutilise')
        self._reprendre()
        vaccin.refresh_from_db()
        self.assertEqual(vaccin.utilisateur, self.alex)

    def test_reprise_relancee_sans_effet(self):
        from vaccins.models import Vaccin
        vaccin = Vaccin.objects.create(nom='TEST_TEMP_multi')
        self._suivi(self.alex, vaccin=vaccin)
        self._suivi(self.tiers, vaccin=vaccin)
        self._reprendre()
        avant = sorted(Vaccin.objects.values_list('pk', 'utilisateur'))
        bilan = self._reprendre()
        self.assertEqual(sorted(Vaccin.objects.values_list('pk', 'utilisateur')), avant)
        self.assertEqual((bilan['Vaccin']['rattachees'], bilan['Vaccin']['copies']), (0, 0))


class RepriseCataloguesMigrationTest(TransactionTestCase):
    """La chaîne de migrations elle-même, rejouée sur des données antérieures
    au rattachement : champ `utilisateur` encore vide et nom de désignation
    encore unique dans toute l'installation. Couvre les deux catalogues dont
    le compte devient obligatoire (Veterinaire, Designation)."""

    # Les catalogues de référence (espèces, races, vaccins...) créés par les
    # migrations sont restaurés avant le test, puisqu'il vide la base.
    serialized_rollback = True

    AVANT = [
        ('accueil', '0006_alter_membrefoyer_invite_par'),
        ('animaux', '0043_proprietaire_email_unique_parmi_les_actifs'),
        ('consultations', '0008_utilisateur_catalogue'),
        ('vaccins', '0013_utilisateur_catalogue'),
        ('factures', '0009_utilisateur_catalogue'),
        ('documents', '0004_utilisateur_catalogue'),
    ]

    def _migrer(self, cibles):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        executor.migrate(cibles)
        return MigrationExecutor(connection).loader

    def _a_jour(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_veterinaires_et_designations_repris_puis_obligatoires(self):
        from datetime import date, timedelta
        from django.db import IntegrityError, transaction
        from django.utils import timezone

        # Quoi qu'il arrive, la base de test revient au dernier schéma.
        self.addCleanup(self._a_jour)
        apps = self._migrer(self.AVANT).project_state(self.AVANT).apps

        UserH = apps.get_model('auth', 'User')
        maintenant = timezone.now()

        def compte(nom, jours, **options):
            return UserH.objects.create(
                username=nom, password='!', date_joined=maintenant - timedelta(days=jours), **options,
            )

        alex, sam, tiers = compte('alex_mig', 40), compte('sam_mig', 30), compte('tiers_mig', 20)
        admin = compte('admin_mig', 10, is_superuser=True)
        foyer = apps.get_model('accueil', 'Foyer').objects.create()
        MembreFoyerH = apps.get_model('accueil', 'MembreFoyer')
        MembreFoyerH.objects.create(utilisateur=alex, foyer=foyer)
        MembreFoyerH.objects.create(utilisateur=sam, foyer=foyer, invite_par=alex)

        chien = apps.get_model('animaux', 'Espece').objects.get(code='CHIEN')
        race = apps.get_model('animaux', 'Race').objects.filter(espece=chien).first()
        robe = apps.get_model('animaux', 'Robe').objects.get(code='AUTRE')
        ProprietaireH = apps.get_model('animaux', 'Proprietaire')
        AnimalH = apps.get_model('animaux', 'Animal')

        def animal(utilisateur):
            proprietaire = ProprietaireH.objects.create(
                nom='TEST_TEMP', email=f'{utilisateur.username}@example.com', utilisateur=utilisateur,
            )
            return AnimalH.objects.create(
                nom=f'TEST_TEMP_{utilisateur.username}', race=race, espece=chien, robe=robe,
                date_naissance=date(2020, 1, 1), proprietaire=proprietaire, utilisateur=utilisateur,
            )

        animaux = {compte_.pk: animal(compte_) for compte_ in (alex, sam, tiers)}

        VeterinaireH = apps.get_model('consultations', 'Veterinaire')
        ConsultationH = apps.get_model('consultations', 'Consultation')
        vet_commun = VeterinaireH.objects.create(
            nom='TEST_TEMP_commun', prenom='Camille', telephone='0102030405', email='commun@example.com',
        )
        vet_seul = VeterinaireH.objects.create(nom='TEST_TEMP_seul')
        vet_inutilise = VeterinaireH.objects.create(nom='TEST_TEMP_inutilise', actif=False)
        consultations = {}
        for compte_, veterinaire in ((alex, vet_commun), (sam, vet_commun), (tiers, vet_commun), (sam, vet_seul)):
            consultations[(compte_.username, veterinaire.nom)] = ConsultationH.objects.create(
                animal=animaux[compte_.pk], date=maintenant - timedelta(days=5),
                motif=f'TEST_TEMP {compte_.username}', veterinaire=veterinaire,
            ).pk

        DesignationH = apps.get_model('factures', 'Designation')
        FactureH = apps.get_model('factures', 'Facture')
        LigneH = apps.get_model('factures', 'LigneFacture')
        des_commune = DesignationH.objects.create(nom='TEST_TEMP_commune')
        des_seule = DesignationH.objects.create(nom='TEST_TEMP_seule')
        des_inutilisee = DesignationH.objects.create(nom='TEST_TEMP_inutilisee')
        lignes = {}
        for compte_, designation, prix in (
            (alex, des_commune, '10.00'), (tiers, des_commune, '99.90'), (tiers, des_seule, '5.00'),
        ):
            facture = FactureH.objects.create(
                utilisateur=compte_, type_depense='ALIMENTAIRE', titre=f'TEST_TEMP {compte_.username}',
                montant=Decimal(prix), date=date(2026, 7, 1), fichier='factures/test_temp_absent.pdf',
            )
            lignes[(compte_.username, designation.nom)] = LigneH.objects.create(
                facture=facture, designation=designation, quantite=Decimal('1'),
                prix_unitaire=Decimal(prix), prix_total=Decimal(prix), pour_tous_les_animaux=True,
            ).pk

        self._a_jour()

        from consultations.models import Consultation, Veterinaire
        from factures.models import Designation, LigneFacture

        # --- Vétérinaires
        communs = Veterinaire.objects.filter(nom='TEST_TEMP_commun')
        self.assertEqual(sorted(communs.values_list('utilisateur__username', flat=True)), ['alex_mig', 'tiers_mig'])
        du_foyer, du_tiers = communs.get(utilisateur=alex.pk), communs.get(utilisateur=tiers.pk)
        self.assertEqual(du_foyer.pk, vet_commun.pk)
        self.assertEqual(
            (du_tiers.prenom, du_tiers.telephone, du_tiers.email, du_tiers.actif),
            ('Camille', '0102030405', 'commun@example.com', True),
        )
        for username, attendu in (('alex_mig', du_foyer), ('sam_mig', du_foyer), ('tiers_mig', du_tiers)):
            consultation = Consultation.objects.get(pk=consultations[(username, 'TEST_TEMP_commun')])
            self.assertEqual(consultation.veterinaire, attendu)
            self.assertEqual(consultation.motif, f'TEST_TEMP {username}')
        self.assertEqual(Veterinaire.objects.get(nom='TEST_TEMP_seul').utilisateur_id, sam.pk)
        inutilise = Veterinaire.objects.get(nom='TEST_TEMP_inutilise')
        self.assertEqual(inutilise.utilisateur_id, admin.pk)
        self.assertFalse(inutilise.actif)
        self.assertEqual(Consultation.objects.filter(motif__startswith='TEST_TEMP').count(), 4)

        # --- Désignations
        communes = Designation.objects.filter(nom='TEST_TEMP_commune')
        self.assertEqual(sorted(communes.values_list('utilisateur__username', flat=True)), ['alex_mig', 'tiers_mig'])
        for username, prix in (('alex_mig', '10.00'), ('tiers_mig', '99.90')):
            ligne = LigneFacture.objects.get(pk=lignes[(username, 'TEST_TEMP_commune')])
            self.assertEqual(ligne.designation.utilisateur.username, username)
            self.assertEqual((ligne.prix_unitaire, ligne.prix_total), (Decimal(prix), Decimal(prix)))
            self.assertEqual(ligne.facture.utilisateur.username, username)
        self.assertEqual(Designation.objects.get(nom='TEST_TEMP_seule').utilisateur_id, tiers.pk)
        self.assertEqual(Designation.objects.get(nom='TEST_TEMP_inutilisee').utilisateur_id, admin.pk)
        self.assertEqual(LigneFacture.objects.filter(facture__titre__startswith='TEST_TEMP').count(), 3)

        # --- Le compte est désormais obligatoire, le nom unique par compte.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Veterinaire.objects.create(nom='TEST_TEMP_sans_compte')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Designation.objects.create(nom='TEST_TEMP_commune', utilisateur_id=alex.pk)
