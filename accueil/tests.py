from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import Foyer, InvitationFoyer, MembreFoyer, PreferenceAccessibilite
from .utils import comptes_accessibles


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
    """Tests de la mise à jour des préférences d'accessibilité depuis le panneau."""

    def setUp(self):
        self.utilisateur = User.objects.create_user(username='alex', password='motdepasse123')

    def test_necessite_d_etre_connecte(self):
        response = self.client.post(reverse('accueil:preferences_accessibilite'), {
            'champ': 'contraste_eleve', 'valeur': '1',
        })
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(PreferenceAccessibilite.objects.filter(utilisateur=self.utilisateur).exists())

    def test_enregistre_un_reglage_booleen(self):
        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(reverse('accueil:preferences_accessibilite'), {
            'champ': 'palette_daltonisme', 'valeur': '1',
        })
        self.assertEqual(response.status_code, 200)
        prefs = PreferenceAccessibilite.objects.get(utilisateur=self.utilisateur)
        self.assertTrue(prefs.palette_daltonisme)

    def test_enregistre_la_taille_de_texte(self):
        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(reverse('accueil:preferences_accessibilite'), {
            'champ': 'taille_texte', 'valeur': 'tres-grand',
        })
        self.assertEqual(response.status_code, 200)
        prefs = PreferenceAccessibilite.objects.get(utilisateur=self.utilisateur)
        self.assertEqual(prefs.taille_texte, PreferenceAccessibilite.Taille.TRES_GRAND)

    def test_rejette_un_champ_inconnu(self):
        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(reverse('accueil:preferences_accessibilite'), {
            'champ': 'est_admin', 'valeur': '1',
        })
        self.assertEqual(response.status_code, 400)

    def test_mode_sombre_enregistre_puis_applique_sur_les_pages(self):
        self.client.login(username='alex', password='motdepasse123')
        self.assertNotContains(self.client.get(reverse('animaux:animal_list')), 'data-bs-theme="dark"')

        response = self.client.post(reverse('accueil:preferences_accessibilite'), {
            'champ': 'mode_sombre', 'valeur': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PreferenceAccessibilite.objects.get(utilisateur=self.utilisateur).mode_sombre)
        self.assertContains(self.client.get(reverse('animaux:animal_list')), 'data-bs-theme="dark"')

        self.client.post(reverse('accueil:preferences_accessibilite'), {'champ': 'mode_sombre', 'valeur': '0'})
        self.assertNotContains(self.client.get(reverse('animaux:animal_list')), 'data-bs-theme="dark"')

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
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=None)

        self.client.login(username='alex', password='motdepasse123')
        response = self.client.post(reverse('accueil:partage_inviter'), {'email': 'sam@example.com'})
        self.assertRedirects(response, reverse('accueil:partage_compte'))
        self.assertFalse(InvitationFoyer.objects.exists())

    def test_seul_l_inviteur_peut_retirer_le_membre_qu_il_a_invite(self):
        invitation = self._inviter_sam_depuis_alex()
        self.client.login(username='sam', password='motdepasse123')
        self.client.post(reverse('accueil:partage_accepter', args=[invitation.token]))
        membre_sam = MembreFoyer.objects.get(utilisateur=self.sam)

        # Sam n'est l'inviteur de personne : cette action lui est fermée,
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

        autre_foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=autre_foyer, invite_par=None)

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
