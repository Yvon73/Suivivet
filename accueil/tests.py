from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import PreferenceAccessibilite


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
