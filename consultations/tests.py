from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
from animaux.models import Animal, AnimalIdentification, Espece, Robe, Race, Proprietaire
from .models import Consultation, Veterinaire
from .forms import ConsultationForm


def _creer_animal_test(nom, identification, proprietaire_email, date_naissance=date(2020, 1, 1)):
    """Crée un Animal de test rattaché à un chien du catalogue de référence."""
    chien = Espece.objects.get(code='CHIEN')
    robe = Robe.objects.get(code='AUTRE')
    race = Race.objects.filter(espece=chien).first()
    proprietaire, _ = Proprietaire.objects.get_or_create(
        email=proprietaire_email, defaults={'nom': 'Test'},
    )
    animal = Animal.objects.create(
        nom=nom,
        race=race,
        espece=chien,
        date_naissance=date_naissance,
        proprietaire=proprietaire,
        robe=robe,
    )
    if identification:
        AnimalIdentification.objects.create(animal=animal, identification=identification)
    return animal


def _creer_veterinaire_test(nom='Martin'):
    """Crée un Veterinaire de test (catalogue partagé, cf. Veterinaire)."""
    veterinaire, _ = Veterinaire.objects.get_or_create(nom=nom)
    return veterinaire


class ConsultationModelTest(TestCase):
    """Tests pour le modèle Consultation."""

    def setUp(self):
        self.animal = _creer_animal_test("Test", "000000", "test@example.com")  # Email pour les tests de rappel
        self.consultation = Consultation.objects.create(
            animal=self.animal,
            date=timezone.now() + timedelta(days=5),
            motif="Vaccination",
            veterinaire=_creer_veterinaire_test(),
        )

    def test_str_method(self):
        """Test de la méthode __str__."""
        self.assertIn("Test", str(self.consultation))
        self.assertIn("Vaccination", str(self.consultation))

class ConsultationFormTest(TestCase):
    """Tests pour le formulaire ConsultationForm."""

    def test_valid_form(self):
        """Test d'un formulaire valide."""
        animal = _creer_animal_test("Test", "000000", "test.user@example.com")
        form_data = {
            'animal': animal.pk,
            'date': timezone.now() + timedelta(days=1),
            'motif': 'Vaccination',
            'veterinaire': _creer_veterinaire_test().pk,
        }
        form = ConsultationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        """Test d'un formulaire invalide (date dans le passé)."""
        animal = _creer_animal_test("Test", "000000", "test.user@example.com")
        form_data = {
            'animal': animal.pk,
            'date': timezone.now() - timedelta(days=1),  # Date dans le passé
            'motif': 'Vaccination',
            'veterinaire': _creer_veterinaire_test().pk,
        }
        form = ConsultationForm(data=form_data)
        self.assertFalse(form.is_valid())

class ConsultationViewTest(TestCase):
    """Tests pour les vues de l'application consultations."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        self.client.login(username='testuser', password='testpass123')
        self.animal = _creer_animal_test("Test", "000000", "test@example.com")
        self.consultation = Consultation.objects.create(
            animal=self.animal,
            date=timezone.now() + timedelta(days=5),
            motif="Vaccination",
            veterinaire=_creer_veterinaire_test(),
        )

    def test_consultation_list_view(self):
        """Test de la vue liste des consultations."""
        response = self.client.get(reverse('consultations:consultation_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consultations/liste.html')
        self.assertContains(response, "Vaccination")

    def test_consultation_detail_view(self):
        """Test de la vue détail d'une consultation."""
        response = self.client.get(
            reverse('consultations:consultation_detail', args=[self.consultation.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consultations/detail.html')
        self.assertContains(response, "Vaccination")

    def test_consultation_create_view(self):
        """Test de la vue création d'une consultation."""
        response = self.client.post(reverse('consultations:consultation_create', args=[self.animal.pk]), {
            'animal': self.animal.pk,
            'date': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'motif': 'Nouvelle consultation',
            'veterinaire': _creer_veterinaire_test('Dupont').pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Consultation.objects.filter(motif='Nouvelle consultation').exists())

    def test_calendrier_view(self):
        """Test de la vue calendrier."""
        response = self.client.get(reverse('consultations:calendrier'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consultations/calendrier.html')

    def test_calendrier_json_view(self):
        """Test de la vue JSON du calendrier."""
        response = self.client.get(reverse('consultations:calendrier_json'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')