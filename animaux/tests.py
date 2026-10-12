import io
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from accueil.models import Foyer, MembreFoyer
from .models import Animal, AnimalIdentification, Organisme, Poids, Espece, Robe, Race, Proprietaire
from datetime import date
from .forms import AnimalForm, ProprietaireForm


def _creer_proprietaire_test(email, nom='Test', prenom='', utilisateur=None):
    """Crée un Proprietaire de test, rattaché à `utilisateur` (ou à un
    utilisateur de test créé à la volée si non fourni) — cf.
    Proprietaire.utilisateur."""
    if utilisateur is None:
        utilisateur = User.objects.create_user(username=f'u_{User.objects.count()}', password='p')
    return Proprietaire.objects.create(nom=nom, prenom=prenom, email=email, utilisateur=utilisateur)

class AnimalModelTest(TestCase):
    """Tests pour le modèle Animal."""

    def setUp(self):
        """Créer des données de test."""
        self.user = User.objects.create_user(username='testuser_model', password='p')
        self.chien = Espece.objects.get(code='CHIEN')
        self.noir = Robe.objects.get(code='NOIR')
        self.race_chien = Race.objects.filter(espece=self.chien).first()
        self.proprietaire = _creer_proprietaire_test("jean.dupont@example.com", nom="Dupont", prenom="Jean", utilisateur=self.user)
        self.animal = Animal.objects.create(
            nom="Rex",
            race=self.race_chien,
            espece=self.chien,
            date_naissance=date(2020, 1, 1),
            proprietaire=self.proprietaire,
            robe=self.noir,
            utilisateur=self.user,
        )
        AnimalIdentification.objects.create(animal=self.animal, identification="123456")

    def test_age_calcul(self):
        """Test du calcul de l'âge."""
        # Âge aujourd'hui
        today = date.today()
        expected_age = today.year - self.animal.date_naissance.year
        if (today.month, today.day) < (self.animal.date_naissance.month, self.animal.date_naissance.day):
            expected_age -= 1
        self.assertEqual(self.animal.age(), expected_age)

        # Âge avec date de décès
        self.animal.date_deces = date(2025, 1, 1)
        self.animal.save()
        expected_age = (
            self.animal.date_deces.year - self.animal.date_naissance.year -
            ((self.animal.date_deces.month, self.animal.date_deces.day) <
             (self.animal.date_naissance.month, self.animal.date_naissance.day))
        )
        self.assertEqual(self.animal.age(), expected_age)

    def test_str_method(self):
        """Test de la méthode __str__."""
        self.assertEqual(str(self.animal), "Rex (Chien)")

    def test_unique_identification(self):
        """Test de l'unicité de l'identification."""
        max = Animal.objects.create(
            nom="Max",
            race=self.race_chien,
            espece=self.chien,
            date_naissance=date(2021, 1, 1),
            proprietaire=_creer_proprietaire_test("marie.martin@example.com", nom="Martin", prenom="Marie", utilisateur=self.user),
            robe=self.noir,
            utilisateur=self.user,
        )
        with self.assertRaises(Exception):
            AnimalIdentification.objects.create(
                animal=max,
                identification="123456",  # Même identification que Rex
            )

class PoidsModelTest(TestCase):
    """Tests pour le modèle Poids."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser_poids', password='p')
        chat = Espece.objects.get(code='CHAT')
        robe = Robe.objects.get(code='AUTRE')
        race_chat = Race.objects.filter(espece=chat).first()
        self.animal = Animal.objects.create(
            nom="Moustache",
            race=race_chat,
            espece=chat,
            date_naissance=date(2019, 5, 15),
            proprietaire=_creer_proprietaire_test("pierre.martin@example.com", nom="Martin", prenom="Pierre", utilisateur=self.user),
            robe=robe,
            utilisateur=self.user,
        )
        self.poids = Poids.objects.create(
            animal=self.animal,
            date=date(2023, 1, 1),
            valeur=4.5,
        )

    def test_str_method(self):
        """Test de la méthode __str__."""
        self.assertEqual(str(self.poids), "Moustache - 4.5 kg (2023-01-01)")

    def test_unique_poids_par_animal_et_date(self):
        """Test de l'unicité du poids par animal et date."""
        with self.assertRaises(Exception):
            Poids.objects.create(
                animal=self.animal,
                date=date(2023, 1, 1),  # Même date
                valeur=5.0,
            )

class AnimalFormTest(TestCase):
    """Tests pour le formulaire AnimalForm."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser_form', password='p')
        self.chat = Espece.objects.get(code='CHAT')
        self.blanc = Robe.objects.get(code='BLANC')
        self.race_chat = Race.objects.filter(espece=self.chat).first()
        self.proprietaire = _creer_proprietaire_test("sophie.laurent@example.com", nom="Laurent", prenom="Sophie", utilisateur=self.user)

    def test_valid_form(self):
        """Test d'un formulaire valide."""
        form_data = {
            'nom': 'Bella',
            'race': self.race_chat.pk,
            'espece': self.chat.pk,
            'date_naissance': date(2021, 3, 10),
            'proprietaire': self.proprietaire.pk,
            'robe': self.blanc.pk,
        }
        form = AnimalForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        """Test d'un formulaire invalide (champ requis manquant)."""
        form_data = {
            'nom': '',  # Nom vide
            'race': self.race_chat.pk,
            'espece': self.chat.pk,
            'date_naissance': date(2021, 3, 10),
        }
        form = AnimalForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('nom', form.errors)

class ProprietaireFormTest(TestCase):
    """Tests pour le formulaire ProprietaireForm, notamment l'unicité de
    l'email par compte (cf. Proprietaire.Meta.constraints)."""

    def setUp(self):
        self.user = User.objects.create_user(username='proprio_user', password='p')
        self.autre_user = User.objects.create_user(username='proprio_autre', password='p')
        _creer_proprietaire_test('deja.pris@example.com', utilisateur=self.user)

    def test_email_deja_utilise_par_le_meme_compte_est_refuse(self):
        form = ProprietaireForm(data={'nom': 'Doublon', 'email': 'deja.pris@example.com'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_meme_email_autorise_pour_un_autre_compte(self):
        form = ProprietaireForm(data={'nom': 'Doublon', 'email': 'deja.pris@example.com'}, user=self.autre_user)
        self.assertTrue(form.is_valid())

    def test_email_deja_utilise_par_un_membre_du_foyer_est_refuse(self):
        """Pas de fusion automatique (cf. décision produit) : la création
        d'un doublon inter-foyer est bloquée, pas fusionnée."""
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.user, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.autre_user, foyer=foyer, invite_par=self.user)

        form = ProprietaireForm(data={'nom': 'Doublon', 'email': 'deja.pris@example.com'}, user=self.autre_user)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class AnimalViewTest(TestCase):
    """Tests pour les vues de l'application animaux."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        self.client.login(username='testuser', password='testpass123')
        self.chien = Espece.objects.get(code='CHIEN')
        self.chat = Espece.objects.get(code='CHAT')
        self.noir = Robe.objects.get(code='NOIR')
        self.race_chien = Race.objects.filter(espece=self.chien).first()
        self.race_chat = Race.objects.filter(espece=self.chat).first()
        self.proprietaire = _creer_proprietaire_test("test.user@example.com", utilisateur=self.user)
        self.animal = Animal.objects.create(
            nom="Test",
            race=self.race_chien,
            espece=self.chien,
            date_naissance=date(2020, 1, 1),
            proprietaire=self.proprietaire,
            robe=self.noir,
            utilisateur=self.user,
        )
        AnimalIdentification.objects.create(animal=self.animal, identification="000000")

        # Données de management form du formset identifications, requises par
        # les vues de création/modification (cf. AnimalIdentificationFormSet).
        self.identifications_management_data = {
            'identifications-TOTAL_FORMS': '0',
            'identifications-INITIAL_FORMS': '0',
            'identifications-MIN_NUM_FORMS': '0',
            'identifications-MAX_NUM_FORMS': '1000',
        }

    def test_animal_list_view(self):
        """Test de la vue liste des animaux."""
        response = self.client.get(reverse('animaux:animal_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'animaux/liste.html')
        self.assertContains(response, "Test")

    def test_animal_detail_view(self):
        """Test de la vue détail d'un animal."""
        response = self.client.get(reverse('animaux:animal_detail', args=[self.animal.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'animaux/detail.html')
        self.assertContains(response, "Test")

    def test_animal_detail_view_cout_revient(self):
        """La case « Coût de revient » (Statistiques) reprend le total d'une
        facture non ventilée attribuée à l'animal (cf. factures.Facture)."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from factures.models import Facture

        Facture.objects.create(
            animal=self.animal, type_depense='VETERINAIRE', titre='Facture test',
            montant='50.00', date=date.today(),
            fichier=SimpleUploadedFile('f.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

        response = self.client.get(reverse('animaux:animal_detail', args=[self.animal.pk]))
        self.assertEqual(response.context['cout_revient_annuel'], 50)
        self.assertEqual(response.context['cout_revient_mensuel'], 50)

        response_liste = self.client.get(reverse('animaux:animal_list'))
        animaux_page = list(response_liste.context['animaux'])
        animal_affiche = next(a for a in animaux_page if a.pk == self.animal.pk)
        self.assertEqual(animal_affiche.cout_revient_annuel, 50)

    def test_animal_create_view(self):
        """Test de la vue création d'un animal."""
        response = self.client.post(reverse('animaux:animal_create'), {
            'nom': 'Nouveau',
            'race': self.race_chien.pk,
            'espece': self.chien.pk,
            'date_naissance': '2022-01-01',
            'proprietaire': self.proprietaire.pk,
            'robe': self.noir.pk,
            **self.identifications_management_data,
        })
        self.assertEqual(response.status_code, 302)  # Redirection après création
        self.assertTrue(Animal.objects.filter(nom='Nouveau').exists())

    def test_animal_update_view(self):
        """Test de la vue modification d'un animal."""
        response = self.client.post(
            reverse('animaux:animal_update', args=[self.animal.pk]),
            {
                'nom': 'Test Modifié',
                'race': self.race_chien.pk,
                'espece': self.chien.pk,
                'date_naissance': '2020-01-01',
                'proprietaire': self.proprietaire.pk,
                'robe': self.noir.pk,
                **self.identifications_management_data,
            }
        )
        self.assertEqual(response.status_code, 302)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.nom, 'Test Modifié')

    def test_animal_delete_view(self):
        """Test de la vue suppression d'un animal."""
        response = self.client.post(reverse('animaux:animal_delete', args=[self.animal.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Animal.objects.filter(pk=self.animal.pk).exists())

    def test_pdf_generation(self):
        """Test de la génération du PDF."""
        response = self.client.get(reverse('animaux:pdf_fiche_animal', args=[self.animal.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_search_view(self):
        """Test de la recherche d'animaux."""
        # Ajouter un deuxième animal
        autre = Animal.objects.create(
            nom="Autre",
            race=self.race_chat,
            espece=self.chat,
            date_naissance=date(2021, 1, 1),
            proprietaire=_creer_proprietaire_test("autre.user@example.com", utilisateur=self.user),
            robe=self.noir,
            utilisateur=self.user,
        )
        AnimalIdentification.objects.create(animal=autre, identification="222222")
        # Recherche par nom
        response = self.client.get(reverse('animaux:animal_list'), {'nom': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test")
        self.assertNotContains(response, "222222")  # identification de l'animal "Autre"

        # Recherche par espèce
        response = self.client.get(reverse('animaux:animal_list'), {'espece': self.chien.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test")
        self.assertNotContains(response, "222222")

    def test_unauthenticated_access(self):
        """Test de l'accès non autorisé."""
        self.client.logout()
        response = self.client.get(reverse('animaux:animal_list'))
        self.assertEqual(response.status_code, 302)  # Redirection vers la page de login.

    def test_export_csv(self):
        """Test de l'export CSV des animaux."""
        response = self.client.get(reverse('animaux:exporter_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment', response['Content-Disposition'])
        # Marque d'ordre des octets en tête, pour qu'Excel lise les accents.
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        self.assertIn('Nom,Espèce,Race', response.content.decode('utf-8-sig'))

    def test_export_excel(self):
        """Test de l'export Excel des animaux."""
        response = self.client.get(reverse('animaux:exporter_excel'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('attachment', response['Content-Disposition'])

    def test_animal_liste_isole_par_compte(self):
        """Un compte ne voit jamais les animaux d'un autre compte (cf.
        Animal.utilisateur)."""
        autre_user = User.objects.create_user(username='autre_compte', password='p')
        autre_proprietaire = _creer_proprietaire_test("autre.compte@example.com", utilisateur=autre_user)
        Animal.objects.create(
            nom="PasVisible", race=self.race_chien, espece=self.chien,
            date_naissance=date(2020, 1, 1), proprietaire=autre_proprietaire,
            robe=self.noir, utilisateur=autre_user,
        )
        response = self.client.get(reverse('animaux:animal_list'))
        self.assertContains(response, "Test")
        self.assertNotContains(response, "PasVisible")

    def test_animal_detail_isole_par_compte(self):
        """Accéder à la fiche d'un animal d'un autre compte renvoie 404, pas
        les données de cet animal."""
        autre_user = User.objects.create_user(username='autre_compte2', password='p')
        autre_proprietaire = _creer_proprietaire_test("autre.compte2@example.com", utilisateur=autre_user)
        autre_animal = Animal.objects.create(
            nom="InterditAcces", race=self.race_chien, espece=self.chien,
            date_naissance=date(2020, 1, 1), proprietaire=autre_proprietaire,
            robe=self.noir, utilisateur=autre_user,
        )
        response = self.client.get(reverse('animaux:animal_detail', args=[autre_animal.pk]))
        self.assertEqual(response.status_code, 404)

    def test_import_csv(self):
        """Test de l'import CSV des animaux."""
        # Créer un fichier CSV valide
        csv_content = (
            "Nom,Espèce,Race,Identification,Date de Naissance,Propriétaire,LOF,Robe\n"
            "NouvelAnimal,CHIEN,Berger,999999,2022-01-01,Nouveau Propriétaire,Oui,NOIR\n"
        )
        csv_file = io.StringIO(csv_content)
        csv_file.name = 'test.csv'

        # Test de l'import
        response = self.client.post(
            reverse('animaux:importer_csv'),
            {'csv_file': csv_file},
            format='multipart',
        )
        self.assertEqual(response.status_code, 302)  # Redirection après import
        self.assertTrue(Animal.objects.filter(nom='NouvelAnimal').exists())


class ListeAnimauxTriableTest(TestCase):
    """Liste des animaux : recherche, tri et pagination côté serveur (cf.
    Projet_veto/listes.py), sans DataTables."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_liste', password='p')
        self.client.login(username='u_liste', password='p')
        chien = Espece.objects.get(code='CHIEN')
        race = Race.objects.filter(espece=chien).first()
        robe = Robe.objects.get(code='NOIR')
        proprietaire = _creer_proprietaire_test("liste@example.com", nom='Durand', utilisateur=self.user)
        for numero in range(12):
            Animal.objects.create(
                nom='TEST_TEMP_%02d' % numero, race=race, espece=chien, robe=robe, proprietaire=proprietaire,
                date_naissance=date(2010 + numero, 1, 1), utilisateur=self.user,
            )
        self.url = reverse('animaux:animal_list')

    def _noms(self, response):
        return [animal.nom for animal in response.context['animaux']]

    def test_liste_sans_datatables(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'DataTable')
        self.assertNotContains(response, 'jquery')
        self.assertContains(response, 'id="zoneListe"')
        self.assertContains(response, 'Affichage de 1 à 10')
        self.assertContains(response, 'sur 12 éléments')

    def test_pagination(self):
        response = self.client.get(self.url, {'page': 2})
        self.assertEqual(self._noms(response), ['TEST_TEMP_10', 'TEST_TEMP_11'])
        # Une page qui n'existe plus ramène à la dernière au lieu d'une 404.
        response = self.client.get(self.url, {'page': 99})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 2)

    def test_tri_par_colonne(self):
        response = self.client.get(self.url, {'tri': 'nom', 'sens': 'desc'})
        self.assertEqual(self._noms(response)[0], 'TEST_TEMP_11')
        # Âge croissant : le plus jeune (né en 2021) d'abord.
        response = self.client.get(self.url, {'tri': 'age'})
        self.assertEqual(self._noms(response)[0], 'TEST_TEMP_11')
        response = self.client.get(self.url, {'tri': 'age', 'sens': 'desc'})
        self.assertEqual(self._noms(response)[0], 'TEST_TEMP_00')
        # Une colonne inconnue retombe sur le tri par défaut.
        response = self.client.get(self.url, {'tri': 'inconnue'})
        self.assertEqual(self._noms(response)[0], 'TEST_TEMP_00')

    def test_liens_de_tri_et_de_page_conservent_la_recherche(self):
        response = self.client.get(self.url, {'q': 'TEST_TEMP', 'tri': 'nom', 'sens': 'asc'})
        self.assertContains(response, 'href="?q=TEST_TEMP&amp;tri=nom&amp;sens=desc"')
        self.assertContains(response, 'href="?q=TEST_TEMP&amp;tri=nom&amp;sens=asc&amp;page=2"')
        self.assertContains(response, 'aria-sort="ascending"')

    def test_recherche(self):
        response = self.client.get(self.url, {'q': 'temp_07'})
        self.assertEqual(self._noms(response), ['TEST_TEMP_07'])
        # Chaque mot doit correspondre, quel que soit le champ (nom, propriétaire...).
        response = self.client.get(self.url, {'q': 'durand _03'})
        self.assertEqual(self._noms(response), ['TEST_TEMP_03'])
        response = self.client.get(self.url, {'q': 'introuvable'})
        self.assertEqual(self._noms(response), [])
        self.assertContains(response, 'Aucun élément ne correspond à « introuvable »')

    def test_recherche_par_identification_sans_doublon(self):
        animal = Animal.objects.get(nom='TEST_TEMP_05')
        AnimalIdentification.objects.create(animal=animal, identification='TEST_TEMP_250A')
        AnimalIdentification.objects.create(animal=animal, identification='TEST_TEMP_250B')
        response = self.client.get(self.url, {'q': 'TEST_TEMP_250'})
        self.assertEqual(self._noms(response), ['TEST_TEMP_05'])

    def test_recherche_combinee_a_la_recherche_avancee(self):
        response = self.client.get(self.url, {'q': 'TEST_TEMP_1', 'nom': '11'})
        self.assertEqual(self._noms(response), ['TEST_TEMP_11'])

    def test_liste_des_proprietaires_triable(self):
        response = self.client.get(reverse('animaux:proprietaire_list'), {'tri': 'animaux', 'sens': 'desc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['proprietaires'][0].nb_animaux, 12)
        self.assertContains(response, 'data-label="Animaux">12</td>')


class FormulaireAnimalHtmxTest(TestCase):
    """Formulaire animal : plus de JavaScript propre ni de Tom Select, tout
    est piloté par htmx (cf. animaux/formulaire.py)."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_htmx', password='p')
        self.client.login(username='u_htmx', password='p')
        self.chien = Espece.objects.get(code='CHIEN')
        self.chat = Espece.objects.get(code='CHAT')
        self.race_chien = Race.objects.filter(espece=self.chien).first()
        self.persan = Race.objects.get(espece=self.chat, nom='Persan')
        self.proprietaire = _creer_proprietaire_test("htmx@example.com", utilisateur=self.user)
        self.animal = Animal.objects.create(
            nom="TEST_TEMP", race=self.race_chien, espece=self.chien, date_naissance=date(2020, 1, 1),
            robe=Robe.objects.get(code='NOIR'), proprietaire=self.proprietaire, utilisateur=self.user,
        )
        self.url_choix = reverse('animaux:animal_choix_race')

    def _menu(self, response, nom):
        contenu = response.content.decode()
        debut = contenu.index('id="champ-%s"' % nom)
        return contenu[debut:contenu.index('</select>', debut)]

    def test_formulaire_sans_script_propre(self):
        for url in (reverse('animaux:animal_create'), reverse('animaux:animal_update', args=[self.animal.pk])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'fetch(')
            self.assertNotContains(response, 'addEventListener')
            self.assertNotContains(response, 'tom-select')
            self.assertNotContains(response, 'class="modal')
            self.assertContains(response, 'hx-post="%s"' % self.url_choix)

    def test_creation_propose_toutes_les_races(self):
        response = self.client.get(reverse('animaux:animal_create'))
        menu = self._menu(response, 'race')
        self.assertIn('>%s</option>' % self.race_chien.nom, menu)
        self.assertIn('>Persan</option>', menu)

    def test_modification_limite_les_races_a_l_espece(self):
        response = self.client.get(reverse('animaux:animal_update', args=[self.animal.pk]))
        menu = self._menu(response, 'race')
        self.assertIn('<option value="%d" selected>' % self.race_chien.pk, menu)
        self.assertNotIn('>Persan</option>', menu)

    def test_changement_d_espece_filtre_et_deselectionne_la_race(self):
        response = self.client.post(
            self.url_choix, {'espece': self.chat.pk, 'race': self.race_chien.pk}, headers={'HX-Trigger': 'zone-espece'},
        )
        self.assertEqual(response.status_code, 200)
        menu = self._menu(response, 'race')
        self.assertIn('>Persan</option>', menu)
        self.assertNotIn('>%s</option>' % self.race_chien.nom, menu)
        self.assertNotIn('selected', menu.split('---------')[1])
        # Le menu « Espèce », dans lequel on vient de choisir, n'est pas redessiné.
        self.assertNotContains(response, 'id="champ-espece"')
        # L'espèce proposée dans le panneau « Ajouter une race » suit.
        self.assertContains(response, 'id="id_nouveau_race-espece"')

    def test_race_choisie_avant_l_espece_renseigne_l_espece(self):
        response = self.client.post(self.url_choix, {'espece': '', 'race': self.persan.pk}, headers={'HX-Trigger': 'zone-race'})
        self.assertIn('<option value="%d" selected>' % self.chat.pk, self._menu(response, 'espece'))
        self.assertIn('<option value="%d" selected>' % self.persan.pk, self._menu(response, 'race'))
        # Fiche de la race affichée (le Persan a une dangerosité cataloguée).
        self.assertContains(response, 'alert-dangerosite-1')

    def test_race_choisie_avec_espece_ne_redessine_que_la_fiche(self):
        response = self.client.post(
            self.url_choix, {'espece': self.chat.pk, 'race': self.persan.pk}, headers={'HX-Trigger': 'zone-race'},
        )
        self.assertNotContains(response, 'id="champ-race"')
        self.assertNotContains(response, 'id="champ-espece"')
        self.assertContains(response, 'id="ficheRace" class="col-12 mb-3" hx-swap-oob="true"')

    def test_filtre_des_races_sans_accents_ni_majuscules(self):
        Race.objects.create(espece=self.chat, nom='TEST_TEMP Élégant')
        response = self.client.post(
            self.url_choix, {'espece': self.chat.pk, 'race': '', 'recherche_race': 'elegan'},
            headers={'HX-Trigger': 'recherche_race'},
        )
        menu = self._menu(response, 'race')
        self.assertIn('>TEST_TEMP Élégant</option>', menu)
        self.assertNotIn('>Persan</option>', menu)

    def test_filtre_conserve_la_race_selectionnee(self):
        response = self.client.post(
            self.url_choix, {'espece': self.chat.pk, 'race': self.persan.pk, 'recherche_race': 'zzzz'},
            headers={'HX-Trigger': 'recherche_race'},
        )
        self.assertIn('<option value="%d" selected>Persan</option>' % self.persan.pk, self._menu(response, 'race'))

    def test_filtre_sans_resultat(self):
        response = self.client.post(
            self.url_choix, {'espece': self.chat.pk, 'race': '', 'recherche_race': 'zzzz'},
            headers={'HX-Trigger': 'recherche_race'},
        )
        self.assertContains(response, 'Aucune race ne correspond à ce filtre')

    def test_ajout_rapide_espece(self):
        response = self.client.post(reverse('animaux:espece_ajout_rapide'), {
            'nouveau_espece-nom': 'TEST_TEMP Furet', 'nouveau_espece-nom_race': '',
        })
        self.assertEqual(response.status_code, 200)
        espece = Espece.objects.get(nom='TEST_TEMP Furet')
        race = Race.objects.get(espece=espece)
        self.assertEqual(race.nom, 'Autre')
        self.assertIn('<option value="%d" selected>' % espece.pk, self._menu(response, 'espece'))
        self.assertIn('<option value="%d" selected>' % race.pk, self._menu(response, 'race'))

    def test_ajout_rapide_robe_et_proprietaire(self):
        response = self.client.post(reverse('animaux:robe_ajout_rapide'), {'nouveau_robe-nom': 'TEST_TEMP Bringé'})
        robe = Robe.objects.get(nom='TEST_TEMP Bringé')
        self.assertIn('<option value="%d" selected>' % robe.pk, self._menu(response, 'robe'))

        response = self.client.post(reverse('animaux:proprietaire_ajout_rapide'), {
            'nouveau_proprietaire-nom': 'TEST_TEMP', 'nouveau_proprietaire-email': 'test_temp_ajout@example.com',
        })
        proprietaire = Proprietaire.objects.get(email='test_temp_ajout@example.com')
        self.assertEqual(proprietaire.utilisateur, self.user)
        self.assertIn('<option value="%d" selected>' % proprietaire.pk, self._menu(response, 'proprietaire'))

    def test_ajout_rapide_proprietaire_en_double_refuse(self):
        response = self.client.post(reverse('animaux:proprietaire_ajout_rapide'), {
            'nouveau_proprietaire-nom': 'TEST_TEMP', 'nouveau_proprietaire-email': 'htmx@example.com',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'collapse show')
        self.assertContains(response, 'existe déjà')
        self.assertEqual(Proprietaire.objects.filter(email='htmx@example.com').count(), 1)

    def _donnees_identifications(self, total=1, **champs):
        donnees = {
            'identifications-TOTAL_FORMS': str(total), 'identifications-INITIAL_FORMS': '0',
            'identifications-MIN_NUM_FORMS': '0', 'identifications-MAX_NUM_FORMS': '1000',
        }
        donnees.update(champs)
        return donnees

    def test_identifications_ajouter_puis_retirer_une_ligne(self):
        url = reverse('animaux:animal_identifications')
        response = self.client.post(url, self._donnees_identifications(
            action='ajouter', **{'identifications-0-identification': 'TEST_TEMP_123'},
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="identifications-TOTAL_FORMS" value="2"')
        self.assertContains(response, 'name="identifications-1-identification"')
        # La saisie en cours est conservée.
        self.assertContains(response, 'value="TEST_TEMP_123"')

        response = self.client.post(url, self._donnees_identifications(total=2, action='retirer', ligne='1'))
        self.assertContains(response, 'identification-row row gx-2 align-items-start mb-2 d-none')
        self.assertContains(response, 'name="identifications-1-DELETE" id="id_identifications-1-DELETE" checked')

    def test_identifications_d_un_animal_d_un_autre_compte_refusees(self):
        User.objects.create_user(username='u_autre', password='p')
        self.client.login(username='u_autre', password='p')
        url = reverse('animaux:animal_identifications', args=[self.animal.pk])
        self.assertEqual(self.client.post(url, self._donnees_identifications(action='ajouter')).status_code, 404)

    def test_ajout_rapide_organisme_selectionne_sur_la_ligne_vide(self):
        response = self.client.post(reverse('animaux:organisme_ajout_rapide'), self._donnees_identifications(**{
            'nouveau_organisme-nom': 'TEST_TEMP Registre', 'nouveau_organisme-nom_court': 'TEST_TEMP',
            'nouveau_organisme-espece': Organisme.Espece.choices[0][0],
        }))
        self.assertEqual(response.status_code, 200, response.content.decode()[:2000])
        organisme = Organisme.objects.get(nom_court='TEST_TEMP')
        self.assertContains(response, 'id="zoneIdentifications" class="col-12" hx-swap-oob="true"')
        self.assertContains(response, '<option value="%d" selected>TEST_TEMP</option>' % organisme.pk)

    def test_apercu_photo(self):
        from PIL import Image
        tampon = io.BytesIO()
        Image.new('RGB', (1200, 800), 'red').save(tampon, format='PNG')
        photo = SimpleUploadedFile('photo.png', tampon.getvalue(), content_type='image/png')
        response = self.client.post(reverse('animaux:animal_apercu_photo'), {'photo': photo})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'src="data:image/jpeg;base64,')

    def test_apercu_photo_fichier_illisible(self):
        faux = SimpleUploadedFile('photo.png', b'pas une image', content_type='image/png')
        response = self.client.post(reverse('animaux:animal_apercu_photo'), {'photo': faux})
        self.assertEqual(response.status_code, 204)

    def test_enregistrement_complet_avec_identifications(self):
        """Le formulaire complet s'enregistre toujours par un POST classique."""
        response = self.client.post(reverse('animaux:animal_create'), {
            'nom': 'TEST_TEMP_2', 'espece': self.chat.pk, 'race': self.persan.pk,
            'robe': Robe.objects.get(code='NOIR').pk, 'date_naissance': '2021-01-01',
            'proprietaire': self.proprietaire.pk,
            **self._donnees_identifications(total=2, **{
                'identifications-0-identification': 'TEST_TEMP_A',
                'identifications-1-identification': 'TEST_TEMP_B', 'identifications-1-DELETE': 'on',
            }),
        })
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['form'].errors)
        animal = Animal.objects.get(nom='TEST_TEMP_2')
        self.assertEqual(list(animal.identifications.values_list('identification', flat=True)), ['TEST_TEMP_A'])


class PartageFoyerVisibiliteTest(TestCase):
    """Un membre du foyer voit et modifie les animaux des autres membres ; un
    compte tiers, hors foyer, n'y a toujours pas accès (cf.
    accueil.utils.comptes_accessibles)."""

    def setUp(self):
        self.chien = Espece.objects.get(code='CHIEN')
        self.noir = Robe.objects.get(code='NOIR')
        self.race_chien = Race.objects.filter(espece=self.chien).first()

        self.alex = User.objects.create_user(username='alex', password='p')
        self.sam = User.objects.create_user(username='sam', password='p')
        self.tiers = User.objects.create_user(username='tiers', password='p')

        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)

        self.proprietaire_alex = _creer_proprietaire_test("alex.animal@example.com", utilisateur=self.alex)
        self.animal_alex = Animal.objects.create(
            nom="AnimalDAlex", race=self.race_chien, espece=self.chien,
            date_naissance=date(2020, 1, 1), proprietaire=self.proprietaire_alex,
            robe=self.noir, utilisateur=self.alex,
        )

    def test_membre_du_foyer_voit_l_animal_de_l_autre_membre(self):
        self.client.login(username='sam', password='p')
        response = self.client.get(reverse('animaux:animal_detail', args=[self.animal_alex.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AnimalDAlex")

    def test_membre_du_foyer_peut_modifier_l_animal_de_l_autre_membre(self):
        self.client.login(username='sam', password='p')
        response = self.client.post(
            reverse('animaux:animal_update', args=[self.animal_alex.pk]),
            {
                'nom': 'AnimalRenommeParSam', 'espece': self.chien.pk, 'race': self.race_chien.pk,
                'date_naissance': '2020-01-01', 'robe': self.noir.pk, 'proprietaire': self.proprietaire_alex.pk,
                'identifications-TOTAL_FORMS': '0', 'identifications-INITIAL_FORMS': '0',
                'identifications-MIN_NUM_FORMS': '0', 'identifications-MAX_NUM_FORMS': '1000',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.animal_alex.refresh_from_db()
        self.assertEqual(self.animal_alex.nom, 'AnimalRenommeParSam')

    def test_compte_tiers_hors_foyer_ne_voit_toujours_pas_l_animal(self):
        """Régression de sécurité : un compte qui ne partage aucun foyer reste
        invisible, même après l'introduction du partage de compte."""
        self.client.login(username='tiers', password='p')
        response = self.client.get(reverse('animaux:animal_detail', args=[self.animal_alex.pk]))
        self.assertEqual(response.status_code, 404)

    def test_compte_tiers_hors_foyer_absent_de_la_liste(self):
        self.client.login(username='tiers', password='p')
        response = self.client.get(reverse('animaux:animal_list'))
        self.assertNotContains(response, "AnimalDAlex")


class CatalogueRacesChats2Tests(TestCase):
    """Catalogue static/data/races_chats2.json (migration 0040) et champs
    correspondants du panneau « Ajouter une race »."""

    def setUp(self):
        self.user = User.objects.create_user(username='catalogue', password='motdepasse')
        self.client.login(username='catalogue', password='motdepasse')
        self.chat = Espece.objects.get(code='CHAT')

    def test_catalogue_importe(self):
        persan = Race.objects.get(espece=self.chat, nom='Persan')
        self.assertEqual(persan.echelle_dangerosite, 1)
        self.assertEqual(persan.classe_bootstrap_dangerosite(), 'dangerosite-1')
        self.assertIs(persan.certificat_detention, False)
        self.assertTrue(persan.comportement)
        self.assertTrue(persan.note)

    def test_couleur_suit_l_echelle(self):
        savannah = Race.objects.get(espece=self.chat, nom='Savannah')
        self.assertEqual(savannah.echelle_dangerosite, 4)
        self.assertEqual(savannah.classe_bootstrap_dangerosite(), 'dangerosite-4')
        self.assertIs(savannah.certificat_detention, True)
        chausie = Race.objects.get(espece=self.chat, nom='Chausie')
        self.assertEqual(chausie.echelle_dangerosite, 5)
        self.assertEqual(chausie.classe_bootstrap_dangerosite(), 'dangerosite-5')
        self.assertIn('niveau 5/5', chausie.dangerosite_affichee())

    def test_noms_nettoyes_et_sans_doublon(self):
        races = Race.objects.filter(espece=self.chat)
        self.assertFalse(races.filter(nom__startswith=' ').exists())
        # « Turc d'Angora » du fichier complète la race « Angora Turc » existante.
        self.assertFalse(races.filter(nom="Turc d'Angora").exists())
        self.assertEqual(races.get(nom='Angora Turc').echelle_dangerosite, 2)

    def test_ajout_rapide_avec_champs_du_catalogue(self):
        """La race créée est sélectionnée et sa fiche s'affiche aussitôt."""
        response = self.client.post(reverse('animaux:race_ajout_rapide'), {
            'nouveau_race-espece': self.chat.pk, 'nouveau_race-nom': 'Race de test',
            'nouveau_race-echelle_dangerosite': '4', 'nouveau_race-certificat_detention': 'true',
            'nouveau_race-comportement': 'Vif.', 'nouveau_race-note': 'À surveiller.',
        })
        self.assertEqual(response.status_code, 200)
        race = Race.objects.get(nom='Race de test')
        self.assertEqual(race.echelle_dangerosite, 4)
        self.assertIs(race.certificat_detention, True)
        self.assertContains(response, '<option value="%d" selected>Race de test</option>' % race.pk)
        self.assertContains(response, '<option value="%d" selected>%s</option>' % (self.chat.pk, self.chat.nom))
        self.assertContains(response, 'alert-dangerosite-4')
        self.assertContains(response, 'Élevé — niveau 4/5')
        self.assertContains(response, '<strong>Certificat de détention :</strong> Requis')
        self.assertContains(response, '<strong>Comportement :</strong> Vif.')

    def test_ajout_rapide_sans_champs_du_catalogue(self):
        response = self.client.post(reverse('animaux:race_ajout_rapide'), {
            'nouveau_race-espece': self.chat.pk, 'nouveau_race-nom': 'Race minimale',
        })
        self.assertEqual(response.status_code, 200)
        race = Race.objects.get(nom='Race minimale')
        self.assertIsNone(race.echelle_dangerosite)
        self.assertIsNone(race.certificat_detention)
        # Rien d'autre que son nom à afficher : la fiche reste masquée.
        self.assertContains(response, 'id="ficheRace" class="col-12 d-none"')

    def test_ajout_rapide_invalide(self):
        response = self.client.post(reverse('animaux:race_ajout_rapide'), {'nouveau_race-espece': self.chat.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'collapse show')
        self.assertContains(response, 'text-danger')
        self.assertNotContains(response, 'hx-swap-oob')

    def test_formulaire_animal_affiche_les_champs_du_catalogue(self):
        response = self.client.get(reverse('animaux:animal_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ficheRace"')
        self.assertContains(response, 'id="id_nouveau_race-echelle_dangerosite"')
        self.assertContains(response, '5 — Extrême')

class CataloguesInsectesReptilesArachnidesTests(TestCase):
    """Catalogues insectes.json / reptiles.json / arachnides.json et passage
    de la dangerosité sur une seule échelle à 5 niveaux (migration 0041)."""

    def test_insectes_importes(self):
        frelon = Race.objects.get(espece__code='INSECTE', nom='Vespa crabro (Frelon Européen)')
        self.assertEqual(frelon.echelle_dangerosite, 4)
        self.assertEqual(frelon.categorie, 'Hyménoptère')
        self.assertEqual(frelon.esperance_vie, 'Colonie: 1 an / Reine: 1 an')
        self.assertIn('Venin puissant', frelon.dangerosite_affichee())

    def test_arachnides_importes(self):
        veuve = Race.objects.get(espece__code='ARACHNIDE', nom__startswith='Latrodectus mactans')
        self.assertEqual(veuve.echelle_dangerosite, 4)
        self.assertIs(veuve.certificat_detention, True)
        self.assertTrue(veuve.certificat_detention_affiche().startswith('Requis — Recommandé'))

    def test_reptiles_importes(self):
        cobra = Race.objects.get(espece__code='REPTILE', nom__startswith='Cobra Royal')
        self.assertEqual(cobra.echelle_dangerosite, 5)
        self.assertEqual(cobra.classe_bootstrap_dangerosite(), 'dangerosite-5')
        self.assertEqual(cobra.categorie, 'Serpent')
        self.assertEqual(cobra.sous_categorie, 'Elapidae')
        self.assertEqual(cobra.nom_scientifique, 'Ophiophagus hannah')

    def test_amphibiens_ranges_sous_batracien(self):
        self.assertTrue(Race.objects.filter(espece__code='BATRACIEN', nom__startswith='Triton Palmé').exists())
        self.assertFalse(Race.objects.filter(espece__code='REPTILE', nom__startswith='Triton Palmé').exists())

    def test_race_existante_completee_sans_doublon(self):
        # « Boa Constrictor (Boa imperator) » complète « Boa constrictor ».
        boas = Race.objects.filter(espece__code='REPTILE', nom__istartswith='boa constrictor')
        self.assertEqual(boas.count(), 1)
        self.assertEqual(boas.get().echelle_dangerosite, 2)
        self.assertEqual(boas.get().classe_bootstrap_dangerosite(), 'dangerosite-2')

    def test_ancien_niveau_converti_en_echelle(self):
        chiens = Race.objects.filter(espece__code='CHIEN')
        self.assertFalse(chiens.filter(echelle_dangerosite__isnull=True).exists())
        rottweiler = chiens.get(nom='Rottweiler')
        self.assertEqual(rottweiler.echelle_dangerosite, 4)
        # Pas de légende propre aux chiens : seulement le libellé du niveau.
        self.assertEqual(rottweiler.dangerosite_affichee(), 'Élevé — niveau 4/5')
        self.assertEqual(chiens.get(nom='Berger Allemand').echelle_dangerosite, 3)


class _BaseAuditTest(TestCase):
    """Données communes aux tests de non-régression de l'audit ci-dessous."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_audit', password='p')
        self.client.login(username='u_audit', password='p')
        self.chien = Espece.objects.get(code='CHIEN')
        self.noir = Robe.objects.get(code='NOIR')
        self.race_chien = Race.objects.filter(espece=self.chien).first()
        self.proprietaire = _creer_proprietaire_test(
            "audit@example.com", nom="Audit", prenom="Jeanne", utilisateur=self.user,
        )
        self.animal = self._animal("TEST_TEMP_AUDIT")

    def _animal(self, nom, naissance=date(2020, 1, 1), **champs):
        champs.setdefault('utilisateur', self.user)
        champs.setdefault('proprietaire', self.proprietaire)
        return Animal.objects.create(
            nom=nom, race=self.race_chien, espece=self.chien, date_naissance=naissance, robe=self.noir, **champs,
        )

    def _donnees_animal(self, **champs):
        donnees = {
            'nom': self.animal.nom, 'espece': self.chien.pk, 'race': self.race_chien.pk,
            'date_naissance': '2020-01-01', 'robe': self.noir.pk, 'proprietaire': self.proprietaire.pk,
            'identifications-TOTAL_FORMS': '0', 'identifications-INITIAL_FORMS': '0',
            'identifications-MIN_NUM_FORMS': '0', 'identifications-MAX_NUM_FORMS': '1000',
        }
        donnees.update(champs)
        return donnees

    def _importer(self, contenu):
        fichier = SimpleUploadedFile('animaux.csv', contenu.encode('utf-8'), content_type='text/csv')
        return self.client.post(reverse('animaux:importer_csv'), {'csv_file': fichier}, follow=True)

    def _messages(self, response):
        return [str(message) for message in response.context['messages']]


class IdentificationsAuditTest(_BaseAuditTest):
    """Zone des identifications du formulaire animal."""

    def setUp(self):
        super().setUp()
        self.ident = AnimalIdentification.objects.create(
            animal=self.animal, identification='TEST_TEMP_999', organisme_autre='Club du Berger',
        )
        self.url = reverse('animaux:animal_update', args=[self.animal.pk])

    def _ligne_existante(self, **champs):
        donnees = {
            'identifications-TOTAL_FORMS': '1', 'identifications-INITIAL_FORMS': '1',
            'identifications-0-id': self.ident.pk, 'identifications-0-animal': self.animal.pk,
            'identifications-0-organisme': '', 'identifications-0-identification': 'TEST_TEMP_999',
        }
        donnees.update(champs)
        return self._donnees_animal(**donnees)

    def test_organisme_libre_conserve_a_la_modification(self):
        """Enregistrer la fiche sans toucher à la ligne n'efface plus
        l'organisme saisi librement (importé par CSV)."""
        response = self.client.get(self.url)
        self.assertContains(response, 'Organisme importé, hors liste : Club du Berger')
        self.assertNotContains(response, 'identifications-0-organisme_autre')

        response = self.client.post(self.url, self._ligne_existante(nom='TEST_TEMP_AUDIT2'))
        self.assertEqual(response.status_code, 302)
        self.ident.refresh_from_db()
        self.assertEqual(self.ident.organisme_autre, 'Club du Berger')
        self.assertEqual(self.ident.identification, 'TEST_TEMP_999')

    def test_organisme_du_catalogue_remplace_l_organisme_libre(self):
        organisme = Organisme.objects.create(
            nom='TEST_TEMP Registre', nom_court='TEST_TEMP_ORG', espece=Organisme.Espece.choices[0][0],
        )
        response = self.client.post(self.url, self._ligne_existante(**{'identifications-0-organisme': organisme.pk}))
        self.assertEqual(response.status_code, 302)
        self.ident.refresh_from_db()
        self.assertEqual(self.ident.organisme, organisme)
        self.assertEqual(self.ident.organisme_autre, '')

    def test_meme_numero_sur_deux_lignes_affiche_l_erreur(self):
        response = self.client.post(reverse('animaux:animal_create'), self._donnees_animal(**{
            'nom': 'TEST_TEMP_DOUBLON', 'identifications-TOTAL_FORMS': '2',
            'identifications-0-identification': 'TEST_TEMP_DUP', 'identifications-1-identification': 'TEST_TEMP_DUP',
        }))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Animal.objects.filter(nom='TEST_TEMP_DOUBLON').exists())
        self.assertContains(response, 'Corrigez les données en double')
        self.assertContains(response, 'Corrigez les valeurs en double')

    def test_premiere_ligne_enregistree_retirable(self):
        """La première ligne se retire aussi (elle ne le pouvait jamais), et
        les libellés passent alors sur la première ligne encore visible."""
        url = reverse('animaux:animal_identifications', args=[self.animal.pk])
        donnees = self._ligne_existante(**{'identifications-TOTAL_FORMS': '2'})
        response = self.client.post(url, {**donnees, 'action': 'ajouter'})
        self.assertContains(response, 'hx-vals=\'{"action": "retirer", "ligne": "0"}\'')

        response = self.client.post(url, {**donnees, 'action': 'retirer', 'ligne': '0'})
        self.assertContains(response, 'name="identifications-0-DELETE" id="id_identifications-0-DELETE" checked')
        self.assertContains(response, '<label for="id_identifications-1-organisme"')
        self.assertNotContains(response, '<label for="id_identifications-0-organisme"')

        response = self.client.post(self.url, self._ligne_existante(**{'identifications-0-DELETE': 'on'}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.animal.identifications.exists())

    def test_ligne_vierge_seule_sans_bouton_retirer(self):
        response = self.client.get(reverse('animaux:animal_create'))
        self.assertNotContains(response, '"action": "retirer"')

    def test_ligne_enregistree_videe_est_supprimee(self):
        self.ident.organisme_autre = ''
        self.ident.save()
        response = self.client.post(self.url, self._ligne_existante(**{'identifications-0-identification': ''}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.animal.identifications.exists())

    def test_ligne_videe_avec_organisme_libre_est_conservee(self):
        response = self.client.post(self.url, self._ligne_existante(**{'identifications-0-identification': ''}))
        self.assertEqual(response.status_code, 302)
        self.ident.refresh_from_db()
        self.assertEqual(self.ident.organisme_autre, 'Club du Berger')

    def test_nouvel_organisme_selectionne_sur_la_ligne_vierge_pas_sur_la_puce(self):
        """Une puce saisie sans organisme n'est pas rattachée d'office à
        l'organisme que l'on vient de créer pour une autre ligne."""
        donnees = {
            'identifications-TOTAL_FORMS': '2', 'identifications-INITIAL_FORMS': '0',
            'identifications-MIN_NUM_FORMS': '0', 'identifications-MAX_NUM_FORMS': '1000',
            'identifications-0-identification': 'TEST_TEMP_PUCE', 'identifications-0-organisme': '',
            'nouveau_organisme-nom': 'TEST_TEMP Registre', 'nouveau_organisme-nom_court': 'TEST_TEMP_ORG',
            'nouveau_organisme-espece': Organisme.Espece.choices[0][0],
        }
        response = self.client.post(reverse('animaux:organisme_ajout_rapide'), donnees)
        self.assertEqual(response.status_code, 200)
        organisme = Organisme.objects.get(nom_court='TEST_TEMP_ORG')
        contenu = response.content.decode()
        ligne_1 = contenu.index('name="identifications-1-organisme"')
        option = '<option value="%d" selected>' % organisme.pk
        self.assertNotIn(option, contenu[:ligne_1])
        self.assertIn(option, contenu[ligne_1:])

        # Aucune ligne vierge : rien n'est présélectionné.
        donnees.update({'identifications-TOTAL_FORMS': '1', 'nouveau_organisme-nom_court': 'TEST_TEMP_ORG2'})
        response = self.client.post(reverse('animaux:organisme_ajout_rapide'), donnees)
        organisme = Organisme.objects.get(nom_court='TEST_TEMP_ORG2')
        self.assertNotContains(response, '<option value="%d" selected>' % organisme.pk)
        self.assertContains(response, '<option value="%d">' % organisme.pk)

    def test_recherche_rapide_par_organisme(self):
        organisme = Organisme.objects.create(
            nom='TEST_TEMP Registre', nom_court='TEST_TEMP_ORG', espece=Organisme.Espece.choices[0][0],
        )
        autre = self._animal('TEST_TEMP_SANS_ORG')
        AnimalIdentification.objects.create(animal=autre, identification='TEST_TEMP_1', organisme=organisme)
        url = reverse('animaux:animal_list')
        self.assertEqual([a.pk for a in self.client.get(url, {'q': 'TEST_TEMP_ORG'}).context['animaux']], [autre.pk])
        self.assertEqual(
            [a.pk for a in self.client.get(url, {'q': 'club du berger'}).context['animaux']], [self.animal.pk],
        )


class PoidsAuditTest(_BaseAuditTest):
    """Pesées : doublon de date, modification, suppression."""

    def setUp(self):
        super().setUp()
        self.poids = Poids.objects.create(animal=self.animal, date=date(2024, 3, 1), valeur=35)

    def test_deuxieme_pesee_a_la_meme_date_refusee_sans_erreur_500(self):
        url = reverse('animaux:poids_create', args=[self.animal.pk])
        response = self.client.post(url, {'date': '2024-03-01', 'valeur': '3.5'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Une pesée existe déjà à cette date')
        self.assertEqual(self.animal.poids.count(), 1)

        response = self.client.post(url, {'date': '2024-03-02', 'valeur': '3.5'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.animal.poids.count(), 2)

    def test_boutons_de_la_fiche_actifs(self):
        response = self.client.get(reverse('animaux:animal_detail', args=[self.animal.pk]))
        self.assertContains(response, reverse('animaux:poids_update', args=[self.poids.pk]))
        self.assertContains(response, reverse('animaux:poids_delete', args=[self.poids.pk]))
        self.assertNotContains(response, 'href="#" class="btn btn-sm btn-outline-')

    def test_modification_d_une_pesee(self):
        url = reverse('animaux:poids_update', args=[self.poids.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Modifier une pesée')
        # Champ date HTML5 prérempli au format ISO.
        self.assertContains(response, 'value="2024-03-01"')
        response = self.client.post(url, {'date': '2024-03-01', 'valeur': '3.5'})
        self.assertRedirects(response, reverse('animaux:animal_detail', args=[self.animal.pk]))
        self.poids.refresh_from_db()
        self.assertEqual(self.poids.valeur, 3.5)

        # Déplacée sur une date déjà prise : refusée.
        Poids.objects.create(animal=self.animal, date=date(2024, 4, 1), valeur=4)
        response = self.client.post(url, {'date': '2024-04-01', 'valeur': '3.5'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Une pesée existe déjà à cette date')

    def test_suppression_d_une_pesee(self):
        url = reverse('animaux:poids_delete', args=[self.poids.pk])
        self.assertContains(self.client.get(url), '01/03/2024')
        self.assertRedirects(self.client.post(url), reverse('animaux:animal_detail', args=[self.animal.pk]))
        self.assertFalse(Poids.objects.filter(pk=self.poids.pk).exists())

    def test_pesee_d_un_autre_compte_inaccessible(self):
        User.objects.create_user(username='u_audit_tiers', password='p')
        self.client.login(username='u_audit_tiers', password='p')
        for nom in ('animaux:poids_update', 'animaux:poids_delete'):
            self.assertEqual(self.client.post(reverse(nom, args=[self.poids.pk]), {
                'date': '2024-03-01', 'valeur': '1',
            }).status_code, 404)
        self.assertEqual(self.client.post(
            reverse('animaux:poids_create', args=[self.animal.pk]), {'date': '2024-05-01', 'valeur': '1'},
        ).status_code, 404)
        self.poids.refresh_from_db()
        self.assertEqual(self.poids.valeur, 35)


class AjoutRapideCatalogueAuditTest(_BaseAuditTest):
    """Ajout rapide d'une espèce / d'une robe dont le code dérivé existe déjà."""

    def test_code_derive_sans_accents(self):
        from .forms import generer_code
        self.assertEqual(generer_code('Élan'), 'ELAN')
        self.assertEqual(generer_code('Tigré'), 'TIGRE')
        self.assertEqual(generer_code('???'), 'AUTRE')

    def test_robe_sans_accent_reutilise_la_robe_existante(self):
        tigre = Robe.objects.get(code='TIGRE')
        nombre = Robe.objects.count()
        response = self.client.post(reverse('animaux:robe_ajout_rapide'), {'nouveau_robe-nom': 'Tigre'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Robe.objects.count(), nombre)
        self.assertContains(response, '<option value="%d" selected>' % tigre.pk)

    def test_espece_sans_accent_reutilise_l_espece_existante(self):
        equide, _ = Espece.objects.get_or_create(code='EQUIDE', defaults={'nom': 'Équidé'})
        nombre = Espece.objects.count()
        response = self.client.post(reverse('animaux:espece_ajout_rapide'), {
            'nouveau_espece-nom': 'Equide', 'nouveau_espece-nom_race': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Espece.objects.count(), nombre)
        self.assertContains(response, '<option value="%d" selected>' % equide.pk)

    def test_nom_sans_lettre_ni_chiffre_refuse(self):
        for url, champ in (('animaux:robe_ajout_rapide', 'nouveau_robe-nom'),
                           ('animaux:espece_ajout_rapide', 'nouveau_espece-nom')):
            response = self.client.post(reverse(url), {champ: '???'})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'au moins une lettre ou un chiffre')
        self.assertFalse(Robe.objects.filter(nom='???').exists())
        self.assertFalse(Espece.objects.filter(nom='???').exists())

    def test_race_de_l_espece_autre_garde_l_espece_selectionnee(self):
        """Le menu « Espèce » redessiné par htmx propose l'espèce « Autre »
        quand c'est celle de la race que l'on vient de choisir."""
        autre = Espece.objects.get(code='AUTRE')
        race = Race.objects.create(espece=autre, nom='TEST_TEMP Furet')
        response = self.client.post(
            reverse('animaux:animal_choix_race'), {'espece': '', 'race': race.pk}, HTTP_HX_TRIGGER='zone-race',
        )
        contenu = response.content.decode()
        debut = contenu.index('id="champ-espece"')
        self.assertIn('<option value="%d" selected>' % autre.pk, contenu[debut:contenu.index('</select>', debut)])
        # ... et le formulaire complet l'accepte à l'enregistrement.
        response = self.client.post(reverse('animaux:animal_create'), self._donnees_animal(
            nom='TEST_TEMP_FURET', espece=autre.pk, race=race.pk,
        ))
        self.assertEqual(response.status_code, 302)
        # Sans cela, « Autre » reste masquée du menu.
        contenu = self.client.get(reverse('animaux:animal_create')).content.decode()
        debut = contenu.index('id="champ-espece"')
        self.assertNotIn('<option value="%d"' % autre.pk, contenu[debut:contenu.index('</select>', debut)])


class RechercheAvanceeAuditTest(_BaseAuditTest):
    """Recherche avancée par âge : bornes en années révolues."""

    def setUp(self):
        super().setUp()
        from dateutil.relativedelta import relativedelta
        # Deux ans et quelques mois : affiché « 2 ans ».
        self.deux_ans = self._animal('TEST_TEMP_2ANS', naissance=date.today() - relativedelta(years=2, months=6))
        self.url = reverse('animaux:animal_list')

    def _trouve(self, **filtres):
        return self.deux_ans.pk in [a.pk for a in self.client.get(self.url, filtres).context['animaux']]

    def test_bornes_d_age(self):
        self.assertEqual(self.deux_ans.age(), 2)
        self.assertTrue(self._trouve(min_age=2))
        self.assertTrue(self._trouve(max_age=2))
        self.assertTrue(self._trouve(min_age=2, max_age=2))
        self.assertTrue(self._trouve(min_age=0))
        self.assertFalse(self._trouve(min_age=3))
        self.assertFalse(self._trouve(max_age=1))

    def test_age_demesure_sans_erreur_500(self):
        for filtres in ({'min_age': 3000}, {'max_age': 3000}, {'min_age': 10 ** 30}):
            response = self.client.get(self.url, filtres)
            self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'inférieure ou égale à 150')

    def test_29_fevrier(self):
        from .views import _il_y_a
        self.assertEqual(_il_y_a(date(2024, 2, 29), 1), date(2023, 2, 28))
        self.assertEqual(_il_y_a(date(2024, 2, 29), 4), date(2020, 2, 29))

    def test_reinitialiser_est_une_navigation_ordinaire(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'aria-label="Réinitialiser la recherche" hx-boost="false"')


class ExportImportAuditTest(_BaseAuditTest):
    """Exports CSV / Excel et import CSV."""

    def test_export_excel_sans_animal(self):
        Animal.objects.all().delete()
        response = self.client.get(reverse('animaux:exporter_excel'))
        self.assertEqual(response.status_code, 200)
        import pandas as pd
        self.assertEqual(list(pd.read_excel(io.BytesIO(response.content)).columns), [
            'ID', 'Nom', 'Espèce', 'Race', 'Identifications', 'Date de Naissance', 'Âge', 'Propriétaire', 'Robe',
        ])

    def test_export_excel_avec_animaux(self):
        import pandas as pd
        df = pd.read_excel(io.BytesIO(self.client.get(reverse('animaux:exporter_excel')).content))
        self.assertEqual(list(df['Nom']), ['TEST_TEMP_AUDIT'])
        self.assertEqual(list(df['Âge']), [self.animal.age()])

    def test_import_conserve_les_identifications_numeriques(self):
        """Zéros de tête conservés, pas de « .0 » quand une ligne n'a pas de numéro."""
        response = self._importer(
            "Nom,Espèce,Race,Identification,Date de Naissance\n"
            "TEST_TEMP_A,CHIEN,Berger,0123456,2022-01-01\n"
            "TEST_TEMP_B,CHIEN,Berger,,2024-01-01\n"
            "TEST_TEMP_C,CHIEN,Berger,250269812345678,2021-01-01\n"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(AnimalIdentification.objects.filter(animal__nom__startswith='TEST_TEMP_').values_list(
                'identification', flat=True)),
            ['0123456', '250269812345678'],
        )
        animal_b = Animal.objects.get(nom='TEST_TEMP_B')
        self.assertFalse(animal_b.identifications.exists())
        # Colonnes optionnelles absentes : valeurs par défaut à la création.
        self.assertEqual(animal_b.robe.code, 'AUTRE')
        self.assertEqual(animal_b.proprietaire.email, 'inconnu@exemple.invalid')
        self.assertFalse(Race.objects.filter(nom__iexact='nan').exists())

    def test_reimport_ne_modifie_que_les_colonnes_presentes(self):
        """Mise à jour par identification : propriétaire, robe et compte de
        l'animal sont conservés si le fichier n'en dit rien."""
        membre = User.objects.create_user(username='u_audit_membre', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.user, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=membre, foyer=foyer, invite_par=self.user)
        AnimalIdentification.objects.create(animal=self.animal, identification='TEST_TEMP_777')
        self.client.login(username='u_audit_membre', password='p')

        response = self._importer(
            "Nom,Espèce,Race,Identification,Date de Naissance\n"
            "TEST_TEMP_RENOMME,CHIEN,%s,TEST_TEMP_777,2019-06-01\n" % self.race_chien.nom
        )
        self.assertIn('Animal TEST_TEMP_RENOMME déjà existant (mis à jour).', self._messages(response))
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.nom, 'TEST_TEMP_RENOMME')
        self.assertEqual(self.animal.date_naissance, date(2019, 6, 1))
        self.assertEqual(self.animal.proprietaire, self.proprietaire)
        self.assertEqual(self.animal.robe, self.noir)
        self.assertEqual(self.animal.utilisateur, self.user)
        self.assertFalse(Proprietaire.objects.filter(email='inconnu@exemple.invalid').exists())
        self.assertEqual(Animal.objects.count(), 1)

    def test_import_proprietaire_par_nom(self):
        """Un nom dans la colonne « Propriétaire » n'est jamais rangé dans le
        champ email : fiche existante retrouvée par son nom, créée sinon."""
        self._importer(
            "Nom,Espèce,Race,Date de Naissance,Propriétaire\n"
            "TEST_TEMP_A,CHIEN,Berger,2022-01-01,jeanne audit\n"
            "TEST_TEMP_B,CHIEN,Berger,2022-01-01,Marie Martin\n"
            "TEST_TEMP_C,CHIEN,Berger,2022-01-01,Marie Martin\n"
            "TEST_TEMP_D,CHIEN,Berger,2022-01-01,paul.durand@example.com\n"
        )
        self.assertEqual(Animal.objects.get(nom='TEST_TEMP_A').proprietaire, self.proprietaire)
        marie = Animal.objects.get(nom='TEST_TEMP_B').proprietaire
        self.assertEqual((marie.nom, marie.email), ('Marie Martin', 'marie.martin@exemple.invalid'))
        self.assertEqual(Animal.objects.get(nom='TEST_TEMP_C').proprietaire, marie)
        paul = Animal.objects.get(nom='TEST_TEMP_D').proprietaire
        self.assertEqual((paul.nom, paul.email), ('Paul Durand', 'paul.durand@example.com'))
        self.assertFalse(Proprietaire.objects.filter(email__icontains=' ').exists())

    def test_import_tout_ou_rien(self):
        nombre = Animal.objects.count()
        proprietaires = Proprietaire.objects.count()
        response = self._importer(
            "Nom,Espèce,Race,Date de Naissance,Propriétaire\n"
            "TEST_TEMP_A,CHIEN,Berger,2022-01-01,nouveau@example.com\n"
            "TEST_TEMP_B,CHIEN,Berger,inconnue,\n"
            "TEST_TEMP_C,CHIEN,Berger,2022-01-01,\n"
        )
        self.assertEqual(Animal.objects.count(), nombre)
        self.assertEqual(Proprietaire.objects.count(), proprietaires)
        messages_affiches = self._messages(response)
        self.assertEqual(len(messages_affiches), 1)
        self.assertIn('Erreur à la ligne 3', messages_affiches[0])
        self.assertIn("aucun animal n'a été importé", messages_affiches[0])

    def test_import_numero_d_un_compte_hors_foyer(self):
        tiers = User.objects.create_user(username='u_audit_tiers', password='p')
        animal_tiers = self._animal(
            'TEST_TEMP_TIERS', utilisateur=tiers,
            proprietaire=_creer_proprietaire_test('tiers@example.com', utilisateur=tiers),
        )
        AnimalIdentification.objects.create(animal=animal_tiers, identification='TEST_TEMP_555')
        response = self._importer(
            "Nom,Espèce,Race,Identification,Date de Naissance\n"
            "TEST_TEMP_PIRATE,CHIEN,Berger,TEST_TEMP_555,2022-01-01\n"
        )
        self.assertIn('Erreur à la ligne 2', self._messages(response)[0])
        animal_tiers.refresh_from_db()
        self.assertEqual(animal_tiers.nom, 'TEST_TEMP_TIERS')
        self.assertFalse(Animal.objects.filter(nom='TEST_TEMP_PIRATE').exists())

    def test_export_csv_reimportable_sans_doublon(self):
        """Aller-retour export -> import : chaque animal identifié est
        retrouvé (colonne « Identifications », propriétaire en nom complet,
        marque d'ordre des octets) et rien n'est recréé."""
        organisme = Organisme.objects.create(
            nom='TEST_TEMP Registre', nom_court='TEST_TEMP_ORG', espece=Organisme.Espece.choices[0][0],
        )
        AnimalIdentification.objects.create(animal=self.animal, identification='0012345', organisme=organisme)
        AnimalIdentification.objects.create(animal=self.animal, identification='TEST_TEMP_2')
        export = self.client.get(reverse('animaux:exporter_csv')).content
        self.assertIn('0012345 (TEST_TEMP_ORG); TEST_TEMP_2', export.decode('utf-8-sig'))

        fichier = SimpleUploadedFile('animaux.csv', export, content_type='text/csv')
        response = self.client.post(reverse('animaux:importer_csv'), {'csv_file': fichier}, follow=True)
        self.assertEqual(self._messages(response), ['Animal TEST_TEMP_AUDIT déjà existant (mis à jour).'])
        self.assertEqual(Animal.objects.count(), 1)
        self.assertEqual(Proprietaire.objects.count(), 1)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.proprietaire, self.proprietaire)
        self.assertEqual(self.animal.robe, self.noir)
        self.assertEqual(self.animal.race, self.race_chien)
        self.assertEqual(self.animal.identifications.count(), 2)

    def test_notice_d_import(self):
        response = self.client.get(reverse('animaux:importer_csv'))
        self.assertContains(response, 'jean.dupont@exemple.fr')
        self.assertContains(response, 'aucun animal')


class ProprietaireAuditTest(_BaseAuditTest):
    """Fiche propriétaire : compte de rattachement, fiche supprimée."""

    def test_modification_par_un_membre_du_foyer_ne_transfere_pas_la_fiche(self):
        membre = User.objects.create_user(username='u_audit_membre', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.user, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=membre, foyer=foyer, invite_par=self.user)
        self.client.login(username='u_audit_membre', password='p')
        response = self.client.post(reverse('animaux:proprietaire_update', args=[self.proprietaire.pk]), {
            'nom': 'Audit', 'prenom': 'Jeanne', 'email': 'audit@example.com', 'telephone': '0102030405',
        })
        self.assertEqual(response.status_code, 302)
        self.proprietaire.refresh_from_db()
        self.assertEqual(self.proprietaire.telephone, '0102030405')
        self.assertEqual(self.proprietaire.utilisateur, self.user)

    def test_creation_rattachee_au_compte_connecte(self):
        self.client.post(reverse('animaux:proprietaire_create'), {'nom': 'Neuf', 'email': 'neuf@example.com'})
        self.assertEqual(Proprietaire.objects.get(email='neuf@example.com').utilisateur, self.user)

    def test_recreer_un_proprietaire_supprime_donne_une_fiche_neuve(self):
        """Décision produit : la recréation ne réactive plus l'ancienne fiche
        et n'en reprend rien (ni coordonnées, ni animaux)."""
        Proprietaire.objects.filter(pk=self.proprietaire.pk).update(
            telephone='0102030405', adresse='1 rue Ancienne', code_postal='69000', ville='Lyon',
        )
        self.client.post(reverse('animaux:proprietaire_delete', args=[self.proprietaire.pk]))
        self.proprietaire.refresh_from_db()
        self.assertFalse(self.proprietaire.actif)

        response = self.client.post(reverse('animaux:proprietaire_create'), {
            'nom': 'Nouveau', 'email': 'audit@example.com',
        })
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.context else '')
        self.assertEqual(Proprietaire.objects.filter(email='audit@example.com').count(), 2)
        neuve = Proprietaire.objects.get(email='audit@example.com', actif=True)
        self.assertNotEqual(neuve.pk, self.proprietaire.pk)
        # Seules les valeurs saisies comptent : rien n'est repris de l'ancienne.
        self.assertEqual(
            (neuve.nom, neuve.prenom, neuve.telephone, neuve.adresse, neuve.code_postal, neuve.ville),
            ('Nouveau', '', '', '', '', ''),
        )
        self.assertEqual(neuve.utilisateur, self.user)
        self.assertEqual(neuve.animaux.count(), 0)
        # L'ancienne fiche reste archivée, inchangée, sur ses animaux.
        self.proprietaire.refresh_from_db()
        self.assertFalse(self.proprietaire.actif)
        self.assertEqual((self.proprietaire.nom, self.proprietaire.prenom, self.proprietaire.ville),
                         ('Audit', 'Jeanne', 'Lyon'))
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.proprietaire, self.proprietaire)
        # La liste ne montre que la fiche neuve.
        self.assertEqual(list(self.client.get(reverse('animaux:proprietaire_list')).context['proprietaires']), [neuve])

    def test_recreation_par_le_panneau_d_ajout_rapide_du_formulaire_animal(self):
        """Même formulaire (ProprietaireForm) : même règle."""
        self.proprietaire.actif = False
        self.proprietaire.save()
        form = ProprietaireForm(data={'nom': 'Rapide', 'email': 'AUDIT@example.com'}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        neuve = form.save()
        self.assertNotEqual(neuve.pk, self.proprietaire.pk)
        self.assertTrue(neuve.actif)
        self.assertEqual(neuve.prenom, '')

    def test_doublon_d_email_toujours_refuse_parmi_les_fiches_actives(self):
        form = ProprietaireForm(data={'nom': 'Doublon', 'email': 'AUDIT@example.com'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('existe déjà', form.errors['email'][0])
        # Et en base : la contrainte tient pour les fiches actives…
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Proprietaire.objects.create(nom='Doublon', email='audit@example.com', utilisateur=self.user)
        # … mais plus pour une fiche supprimée.
        Proprietaire.objects.filter(pk=self.proprietaire.pk).update(actif=False)
        Proprietaire.objects.create(nom='Neuve', email='audit@example.com', utilisateur=self.user)

    def test_email_d_une_fiche_supprimee_accepte_en_modification(self):
        """L'email d'une fiche supprimée est libre : une autre fiche peut le
        prendre (l'ancien message invitait à « recréer pour réactiver »)."""
        supprimee = _creer_proprietaire_test('supprimee@example.com', utilisateur=self.user)
        supprimee.actif = False
        supprimee.save()
        form = ProprietaireForm(
            data={'nom': 'Audit', 'email': 'supprimee@example.com'}, instance=self.proprietaire, user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        supprimee.refresh_from_db()
        self.assertFalse(supprimee.actif)

    def test_import_csv_ne_reprend_pas_une_fiche_supprimee(self):
        """Import par email ou par nom : même règle que le formulaire."""
        from .views import _proprietaire_depuis_import
        Proprietaire.objects.filter(pk=self.proprietaire.pk).update(actif=False, ville='Lyon')
        par_email = _proprietaire_depuis_import('audit@example.com', self.user)
        self.assertNotEqual(par_email.pk, self.proprietaire.pk)
        self.assertTrue(par_email.actif)
        self.assertEqual((par_email.email, par_email.ville, par_email.prenom), ('audit@example.com', '', ''))
        # Un second import retrouve la fiche neuve, sans en recréer une.
        self.assertEqual(_proprietaire_depuis_import('AUDIT@example.com', self.user), par_email)

        par_email.actif = False
        par_email.save()
        par_nom = _proprietaire_depuis_import('Jeanne Audit', self.user)
        self.assertNotIn(par_nom.pk, (self.proprietaire.pk, par_email.pk))
        self.assertTrue(par_nom.actif)
        self.assertEqual(_proprietaire_depuis_import('jeanne audit', self.user), par_nom)

    def test_fiche_proprietaire_liste_ses_animaux(self):
        response = self.client.get(reverse('animaux:proprietaire_detail', args=[self.proprietaire.pk]))
        self.assertContains(response, 'TEST_TEMP_AUDIT')


class FicheAnimalAuditTest(_BaseAuditTest):
    """Fiche animal, page de suppression, champs fichier."""

    def test_confirmation_de_suppression_annonce_ce_qui_sera_supprime(self):
        """Décision produit : les factures de l'animal sont supprimées avec
        lui (elles étaient auparavant conservées, sans animal). La page de
        confirmation donne les nombres réels."""
        from factures.models import Facture
        facture = Facture.objects.create(
            animal=self.animal, type_depense='VETERINAIRE', titre='TEST_TEMP facture', montant='50.00',
            date=date.today(), fichier=SimpleUploadedFile('f.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        Poids.objects.create(animal=self.animal, date=date(2024, 1, 1), valeur=10)
        Poids.objects.create(animal=self.animal, date=date(2024, 2, 1), valeur=11)
        url = reverse('animaux:animal_delete', args=[self.animal.pk])
        response = self.client.get(url)
        self.assertEqual(response.context['suppressions'], {
            'identifications': 0, 'poids': 2, 'suivis': 0, 'consultations': 0, 'documents': 0,
            'lignes_facture': 0, 'factures': 1,
        })
        self.assertContains(response, '<strong>1 facture</strong>', html=True)
        self.assertContains(response, '2 pesées')
        self.assertNotContains(response, 'factures sont conservées')
        self.client.post(url)
        self.assertFalse(Facture.objects.filter(pk=facture.pk).exists())

    def test_colonne_dose_des_traitements(self):
        from vaccins.models import SuiviVaccinTraitement, Traitement
        traitement = Traitement.objects.create(nom='TEST_TEMP Antibiotique', classe='COMPRIME')
        SuiviVaccinTraitement.objects.create(
            animal=self.animal, traitement=traitement, date=date(2024, 1, 1), dose_valeur=2, dose_unite='KG',
        )
        SuiviVaccinTraitement.objects.create(animal=self.animal, traitement=traitement, date=date(2024, 2, 1))
        response = self.client.get(reverse('animaux:animal_detail', args=[self.animal.pk]))
        # (la cellule porte un data-label, cf. TableauxEmpilablesMiddleware)
        self.assertContains(response, '>2 Dose par Kg</td>')
        html_pdf = __import__('django.template.loader', fromlist=['render_to_string']).render_to_string(
            'animaux/pdf_fiche_animal.html', {
                'animal': self.animal, 'traitements': self.animal.suivi_vaccins_traitements.all(), 'today': date.today(),
            },
        )
        self.assertIn('<td>2 Dose par Kg</td>', html_pdf)
        self.assertIn('<td>-</td>', html_pdf)

    def test_fiche_animal_sans_requete_par_ligne(self):
        """Le nombre de requêtes de la fiche ne dépend pas du nombre de
        documents ni de suivis affichés."""
        from documents.models import Document, TypeDocument
        from vaccins.models import SuiviVaccinTraitement, Vaccin

        def ajouter(numero):
            Document.objects.create(
                animal=self.animal, titre='TEST_TEMP doc %d' % numero,
                type_document=TypeDocument.objects.create(nom='TEST_TEMP type %d' % numero),
                fichier=SimpleUploadedFile('d.pdf', b'%PDF-1.4', content_type='application/pdf'),
            )
            SuiviVaccinTraitement.objects.create(
                animal=self.animal, date=date(2024, 1, numero),
                vaccin=Vaccin.objects.create(nom='TEST_TEMP vaccin %d' % numero),
            )

        def requetes():
            from django.db import connection
            from django.test.utils import CaptureQueriesContext
            with CaptureQueriesContext(connection) as contexte:
                response = self.client.get(reverse('animaux:animal_detail', args=[self.animal.pk]))
            self.assertEqual(response.status_code, 200)
            return len(contexte)

        ajouter(1)
        reference = requetes()
        for numero in range(2, 6):
            ajouter(numero)
        self.assertEqual(requetes(), reference)
        response = self.client.get(reverse('animaux:animal_detail', args=[self.animal.pk]))
        self.assertContains(response, 'TEST_TEMP doc 5')
        self.assertContains(response, 'TEST_TEMP type 5')

    def test_champs_fichier_sans_lien_vers_media(self):
        """« Actuellement : … » n'est plus un lien vers /media/, qui n'est pas
        servi (animal, facture, document)."""
        from documents.forms import DocumentForm
        from documents.models import Document
        from factures.forms import FactureForm
        from factures.models import Facture

        self.animal.photo.name = 'animaux/photos/test_temp_rex.jpg'
        formulaires = [
            AnimalForm(instance=self.animal, user=self.user)['photo'],
            FactureForm(instance=Facture(fichier='factures/test_temp_facture.pdf'), user=self.user)['fichier'],
            DocumentForm(instance=Document(fichier='documents/test_temp_doc.pdf'), user=self.user)['fichier'],
        ]
        for champ, nom in zip(formulaires, ('test_temp_rex.jpg', 'test_temp_facture.pdf', 'test_temp_doc.pdf')):
            rendu = str(champ)
            self.assertNotIn('<a ', rendu)
            self.assertNotIn('/media/', rendu)
            self.assertIn(nom, rendu)
            self.assertIn('type="file"', rendu)
        # La photo, facultative, garde sa case « Effacer ».
        self.assertIn('name="photo-clear"', str(formulaires[0]))

    def test_requetes_du_choix_de_race_coordonnees(self):
        """Espèce, race et filtre des races partagent une même file hx-sync."""
        contenu = self.client.get(reverse('animaux:animal_create')).content.decode()
        self.assertEqual(contenu.count('hx-sync="#zone-race:replace"'), 3)
        self.assertIn('hx-sync="this:replace"', contenu[contenu.index('id="zone-race"'):][:400])
