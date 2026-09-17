import io
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Animal, AnimalIdentification, Poids, Espece, Robe, Race, Proprietaire
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
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('Nom,Espèce,Race', response.content.decode('utf-8'))

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
