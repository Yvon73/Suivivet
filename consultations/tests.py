from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
from accueil.models import Foyer, MembreFoyer
from animaux.models import Animal, AnimalIdentification, Espece, Robe, Race, Proprietaire
from .models import Consultation, Veterinaire
from .forms import ConsultationForm
from notifications.models import Notification


def _creer_animal_test(nom, identification, proprietaire_email, date_naissance=date(2020, 1, 1), utilisateur=None):
    """Crée un Animal de test rattaché à un chien du catalogue de référence,
    pour `utilisateur` (ou un utilisateur de test créé à la volée si non
    fourni) — cf. Animal.utilisateur."""
    if utilisateur is None:
        utilisateur = User.objects.create_user(username=f'u_{User.objects.count()}', password='p')
    chien = Espece.objects.get(code='CHIEN')
    robe = Robe.objects.get(code='AUTRE')
    race = Race.objects.filter(espece=chien).first()
    proprietaire, _ = Proprietaire.objects.get_or_create(
        utilisateur=utilisateur, email=proprietaire_email, defaults={'nom': 'Test'},
    )
    animal = Animal.objects.create(
        nom=nom,
        race=race,
        espece=chien,
        date_naissance=date_naissance,
        proprietaire=proprietaire,
        robe=robe,
        utilisateur=utilisateur,
    )
    if identification:
        AnimalIdentification.objects.create(animal=animal, identification=identification)
    return animal


def _creer_veterinaire_test(utilisateur, nom='Martin'):
    """Crée un Veterinaire de test rattaché au compte `utilisateur` (cf.
    Veterinaire.utilisateur)."""
    veterinaire, _ = Veterinaire.objects.get_or_create(nom=nom, utilisateur=utilisateur)
    return veterinaire


class ConsultationModelTest(TestCase):
    """Tests pour le modèle Consultation."""

    def setUp(self):
        self.animal = _creer_animal_test("Test", "000000", "test@example.com")  # Email pour les tests de rappel
        self.consultation = Consultation.objects.create(
            animal=self.animal,
            date=timezone.now() + timedelta(days=5),
            motif="Vaccination",
            veterinaire=_creer_veterinaire_test(self.animal.utilisateur),
        )

    def test_str_method(self):
        """Test de la méthode __str__."""
        self.assertIn("Test", str(self.consultation))
        self.assertIn("Vaccination", str(self.consultation))

class ConsultationFormTest(TestCase):
    """Tests pour le formulaire ConsultationForm."""

    def test_valid_form(self):
        """Test d'un formulaire valide."""
        user = User.objects.create_user(username='form_valid_user', password='p')
        animal = _creer_animal_test("Test", "000000", "test.user@example.com", utilisateur=user)
        form_data = {
            'animal': animal.pk,
            'date': timezone.now() + timedelta(days=1),
            'motif': 'Vaccination',
            'veterinaire': _creer_veterinaire_test(user).pk,
        }
        form = ConsultationForm(data=form_data, user=user)
        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        """Test d'un formulaire invalide (date dans le passé)."""
        user = User.objects.create_user(username='form_invalid_user', password='p')
        animal = _creer_animal_test("Test", "000000", "test.user@example.com", utilisateur=user)
        form_data = {
            'animal': animal.pk,
            'date': timezone.now() - timedelta(days=1),  # Date dans le passé
            'motif': 'Vaccination',
            'veterinaire': _creer_veterinaire_test(user).pk,
        }
        form = ConsultationForm(data=form_data, user=user)
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
        self.animal = _creer_animal_test("Test", "000000", "test@example.com", utilisateur=self.user)
        self.consultation = Consultation.objects.create(
            animal=self.animal,
            date=timezone.now() + timedelta(days=5),
            motif="Vaccination",
            veterinaire=_creer_veterinaire_test(self.user),
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
            'veterinaire': _creer_veterinaire_test(self.user, 'Dupont').pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Consultation.objects.filter(motif='Nouvelle consultation').exists())

    def test_calendrier_view(self):
        """Test de la vue calendrier."""
        response = self.client.get(reverse('consultations:calendrier'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consultations/calendrier.html')

    def test_calendrier_rendu_par_le_serveur(self):
        """Plus de FullCalendar : la consultation à venir est dans la page."""
        local = timezone.localtime(self.consultation.date)
        response = self.client.get(reverse('consultations:calendrier'), {'annee': local.year, 'mois': local.month})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'fullcalendar')
        self.assertNotContains(response, 'FullCalendar')
        self.assertContains(response, 'class="calendrier-evenement evenement-consultation"')
        self.assertContains(response, 'Test - Vaccination')
        self.assertContains(response, reverse('consultations:consultation_detail', args=[self.consultation.pk]))
        # Grille (grand écran) et planning (téléphone) sont tous deux rendus.
        self.assertContains(response, 'Test - Vaccination', count=3)  # 2 liens + 1 infobulle (title)

    def test_calendrier_navigation_entre_les_mois(self):
        response = self.client.get(reverse('consultations:calendrier'), {'annee': 2026, 'mois': 12, 'vue': 'planning'})
        self.assertEqual(response.context['mois_affiche'], date(2026, 12, 1))
        self.assertContains(response, 'href="?annee=2026&amp;mois=11&amp;vue=planning"')
        self.assertContains(response, 'href="?annee=2027&amp;mois=1&amp;vue=planning"')
        self.assertContains(response, 'décembre 2026')
        # Semaines complètes, du lundi 30 novembre au dimanche 3 janvier.
        semaines = response.context['semaines']
        self.assertEqual(semaines[0][0]['date'], date(2026, 11, 30))
        self.assertEqual(semaines[-1][-1]['date'], date(2027, 1, 3))
        self.assertTrue(semaines[0][0]['hors_mois'])

    def test_calendrier_parametres_illisibles(self):
        response = self.client.get(reverse('consultations:calendrier'), {'annee': 'abc', 'mois': '99', 'vue': 'x'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['mois_affiche'], timezone.localdate().replace(day=1))
        self.assertEqual(response.context['vue'], '')

    def test_calendrier_rappels(self):
        """Rappel de consultation (2 jours avant, si elle est imminente) et
        rappel de vaccin (date de la prochaine dose)."""
        from vaccins.models import SuiviVaccinTraitement, Vaccin
        from .calendrier import evenements
        imminente = Consultation.objects.create(
            animal=self.animal, date=timezone.now() + timedelta(days=1), motif="TEST_TEMP imminente",
            veterinaire=_creer_veterinaire_test(self.user),
        )
        aujourdhui = timezone.localdate()
        SuiviVaccinTraitement.objects.create(
            animal=self.animal, vaccin=Vaccin.objects.create(nom='TEST_TEMP_vaccin'),
            date=aujourdhui, date_prochaine_dose=aujourdhui + timedelta(days=10),
        )
        liste = evenements(self.user, aujourdhui - timedelta(days=5), aujourdhui + timedelta(days=30))
        par_classe = {}
        for evenement in liste:
            par_classe.setdefault(evenement['classe'], []).append(evenement)
        self.assertEqual(len(par_classe['evenement-consultation']), 2)
        rappel, = par_classe['evenement-rappel-consultation']
        self.assertEqual(rappel['date'], timezone.localtime(imminente.date - timedelta(days=2)).date())
        vaccin, = par_classe['evenement-rappel-vaccin']
        self.assertEqual(vaccin['date'], aujourdhui + timedelta(days=10))
        self.assertIsNone(vaccin['heure'])
        self.assertEqual(liste, sorted(liste, key=lambda e: (e['date'], str(e['heure'] or ''), e['titre'])))

    def test_calendrier_isole_par_compte(self):
        from .calendrier import evenements
        autre = User.objects.create_user(username='u_calendrier_autre', password='p')
        aujourdhui = timezone.localdate()
        self.assertEqual(evenements(autre, aujourdhui, aujourdhui + timedelta(days=60)), [])

    def test_formulaire_sans_script_propre(self):
        """Le formulaire n'embarque plus de JavaScript : l'ajout rapide d'un
        vétérinaire passe par htmx."""
        response = self.client.get(reverse('consultations:consultation_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-post="%s"' % reverse('consultations:veterinaire_ajout_rapide'))
        self.assertNotContains(response, 'fetch(')

    def test_ajout_rapide_veterinaire(self):
        """Le panneau « + » crée le vétérinaire et renvoie le menu déroulant
        où il est sélectionné."""
        response = self.client.post(reverse('consultations:veterinaire_ajout_rapide'), {
            'nouveau_veterinaire-nom': 'TEST_TEMP_Dupont',
            'nouveau_veterinaire-telephone': '0102030405',
        })
        self.assertEqual(response.status_code, 200)
        veterinaire = Veterinaire.objects.get(nom='TEST_TEMP_Dupont')
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertContains(response, '<option value="%d" selected>' % veterinaire.pk)

    def test_ajout_rapide_veterinaire_invalide(self):
        """Sans nom, rien n'est créé : le panneau revient ouvert avec l'erreur,
        sans toucher au menu déroulant."""
        nombre = Veterinaire.objects.count()
        response = self.client.post(reverse('consultations:veterinaire_ajout_rapide'), {
            'nouveau_veterinaire-nom': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Veterinaire.objects.count(), nombre)
        self.assertContains(response, 'collapse show')
        self.assertContains(response, 'text-danger')
        self.assertNotContains(response, 'hx-swap-oob')


class ConsultationPartageFoyerTest(TestCase):
    """Un membre du foyer voit les consultations des autres membres ; un
    compte tiers, hors foyer, reste sans accès (régression de sécurité)."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex', password='p')
        self.tiers = User.objects.create_user(username='tiers', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        self.sam = User.objects.create_user(username='sam', password='p')
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)

        self.animal = _creer_animal_test("AnimalAlex", "111111", "alex.p@example.com", utilisateur=self.alex)
        self.consultation = Consultation.objects.create(
            animal=self.animal,
            date=timezone.now() + timedelta(days=5),
            motif="Vaccination",
            veterinaire=_creer_veterinaire_test(self.alex),
        )

    def test_membre_du_foyer_voit_la_consultation(self):
        self.client.login(username='sam', password='p')
        response = self.client.get(reverse('consultations:consultation_detail', args=[self.consultation.pk]))
        self.assertEqual(response.status_code, 200)

    def test_compte_tiers_hors_foyer_ne_voit_pas_la_consultation(self):
        self.client.login(username='tiers', password='p')
        response = self.client.get(reverse('consultations:consultation_detail', args=[self.consultation.pk]))
        self.assertEqual(response.status_code, 404)


class ConsultationHeureLocaleTest(TestCase):
    """Les textes construits côté Python (rappel, notification, __str__)
    affichent l'heure de Paris, pas l'heure UTC relue en base."""

    def setUp(self):
        from zoneinfo import ZoneInfo
        self.user = User.objects.create_user(username='u_heure', password='p', email='heure@example.com')
        self.animal = _creer_animal_test("Rex", "222222", "heure@example.com", utilisateur=self.user)
        dans_un_an = timezone.localdate().year + 1
        # Juillet : heure d'été, 2 h d'écart avec UTC (13:30 UTC).
        moment = timezone.datetime(dans_un_an, 7, 15, 15, 30, tzinfo=ZoneInfo('Europe/Paris'))
        pk = Consultation.objects.create(
            animal=self.animal, date=moment, motif="TEST_TEMP heure", veterinaire=_creer_veterinaire_test(self.user),
        ).pk
        # Relue en base, comme dans la tâche Celery : la date revient en UTC.
        self.consultation = Consultation.objects.get(pk=pk)

    def test_str_en_heure_locale(self):
        self.assertIn('à 15:30', str(self.consultation))
        self.assertNotIn('13:30', str(self.consultation))

    def test_notification_de_creation_en_heure_locale(self):
        from notifications.models import Notification
        notification = Notification.objects.get(utilisateur=self.user, titre__startswith='Nouvelle consultation')
        self.assertIn('à 15:30', notification.message)

    def test_rappel_en_heure_locale(self):
        from unittest import mock
        from notifications.models import Notification
        with mock.patch('consultations.models.envoyer_email') as envoyer_email:
            self.consultation.envoyer_rappel()
        contexte = envoyer_email.call_args.args[1]
        self.assertTrue(contexte['date_consultation'].endswith('à 15:30'), contexte['date_consultation'])
        notification = Notification.objects.get(utilisateur=self.user, titre__startswith='Rappel')
        self.assertIn('à 15:30', notification.message)


class ConsultationPasseeModifiableTest(TestCase):
    """Une consultation passée reste modifiable (compte rendu, motif…) tant
    que sa date n'est pas déplacée vers une autre date passée."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_passee', password='p')
        self.client.login(username='u_passee', password='p')
        self.animal = _creer_animal_test("Test", "333333", "passee@example.com", utilisateur=self.user)
        # Avec des secondes : le champ datetime-local ne les renverra pas.
        self.date = (timezone.now() - timedelta(days=2)).replace(second=42, microsecond=7)
        self.consultation = Consultation.objects.create(
            animal=self.animal, date=self.date, motif="TEST_TEMP passée", veterinaire=_creer_veterinaire_test(self.user),
        )
        self.url = reverse('consultations:consultation_update', args=[self.consultation.pk])

    def _donnees(self, moment, **autres):
        return {
            'animal': self.animal.pk,
            'date': timezone.localtime(moment).strftime('%Y-%m-%dT%H:%M'),
            'motif': 'TEST_TEMP passée',
            'veterinaire': self.consultation.veterinaire_id,
            **autres,
        }

    def test_compte_rendu_saisi_apres_la_consultation(self):
        response = self.client.post(self.url, self._donnees(self.date, compte_rendu='Tout va bien.'))
        self.assertEqual(response.status_code, 302)
        self.consultation.refresh_from_db()
        self.assertEqual(self.consultation.compte_rendu, 'Tout va bien.')

    def test_date_deplacee_vers_une_autre_date_passee_refusee(self):
        response = self.client.post(self.url, self._donnees(self.date - timedelta(days=1), compte_rendu='x'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "doit être dans le futur")
        self.consultation.refresh_from_db()
        self.assertEqual(self.consultation.compte_rendu, '')

    def test_date_deplacee_vers_le_futur_acceptee(self):
        response = self.client.post(self.url, self._donnees(timezone.now() + timedelta(days=1)))
        self.assertEqual(response.status_code, 302)


class VeterinaireCloisonnementTest(TestCase):
    """La fiche d'un vétérinaire appartient au compte qui l'a créée : elle
    n'est visible, avec ses consultations, que de ce compte et de son foyer."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex_v', password='p')
        self.sam = User.objects.create_user(username='sam_v', password='p')
        self.tiers = User.objects.create_user(username='tiers_v', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)
        self.veterinaire = _creer_veterinaire_test(self.alex, 'TEST_TEMP_Cloison')
        animal = _creer_animal_test("AnimalSecretAlex", "444444", "alex.v@example.com", utilisateur=self.alex)
        Consultation.objects.create(
            animal=animal, date=timezone.now() + timedelta(days=5), motif="Vaccination", veterinaire=self.veterinaire,
        )
        self.url_fiche = reverse('consultations:veterinaire_detail', args=[self.veterinaire.pk])
        self.url_liste = reverse('consultations:veterinaire_list')

    def _nb_consultations(self, response):
        return {v.pk: v.nb_consultations for v in response.context['veterinaires']}[self.veterinaire.pk]

    def test_compte_tiers_ne_voit_ni_la_fiche_ni_ses_consultations(self):
        # Avant le rattachement des fiches à leur compte créateur, le tiers
        # voyait la fiche (commune), vide de consultations : il ne la voit plus.
        self.client.login(username='tiers_v', password='p')
        self.assertEqual(self.client.get(self.url_fiche).status_code, 404)
        response = self.client.get(self.url_liste)
        self.assertNotContains(response, 'TEST_TEMP_Cloison')
        self.assertNotIn(self.veterinaire, response.context['veterinaires'])

    def test_proprietaire_et_membre_du_foyer_les_voient(self):
        for nom in ('alex_v', 'sam_v'):
            self.client.login(username=nom, password='p')
            self.assertContains(self.client.get(self.url_fiche), 'AnimalSecretAlex')
            self.assertEqual(self._nb_consultations(self.client.get(self.url_liste)), 1)


class RappelCourtierInjoignableTest(TestCase):
    """Courtier Celery (Redis) injoignable : la consultation reste enregistrée
    ou supprimée, sans erreur 500 ; l'erreur est journalisée."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_courtier', password='p')
        self.client.login(username='u_courtier', password='p')
        self.animal = _creer_animal_test("Test", "555555", "courtier@example.com", utilisateur=self.user)

    def test_creation_sans_courtier(self):
        from unittest import mock
        with mock.patch(
            'consultations.tasks.envoyer_rappel_consultation.apply_async', side_effect=RuntimeError('Redis injoignable'),
        ), self.assertLogs('consultations.models', level='ERROR'):
            response = self.client.post(reverse('consultations:consultation_create'), {
                'animal': self.animal.pk,
                'date': (timezone.now() + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M'),
                'motif': 'TEST_TEMP sans courtier',
                'veterinaire': _creer_veterinaire_test(self.user).pk,
            }, follow=True)
        self.assertEqual(response.status_code, 200)
        consultation = Consultation.objects.get(motif='TEST_TEMP sans courtier')
        self.assertIsNone(consultation.rappel_task_id)
        self.assertContains(response, "le rappel par email n&#x27;a pas pu être programmé")

    def test_creation_avec_courtier_sans_avertissement(self):
        response = self.client.post(reverse('consultations:consultation_create'), {
            'animal': self.animal.pk,
            'date': (timezone.now() + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M'),
            'motif': 'TEST_TEMP avec courtier',
            'veterinaire': _creer_veterinaire_test(self.user).pk,
        }, follow=True)
        self.assertTrue(Consultation.objects.get(motif='TEST_TEMP avec courtier').rappel_task_id)
        self.assertNotContains(response, "pas pu être programmé")

    def test_suppression_sans_courtier(self):
        from unittest import mock
        consultation = Consultation.objects.create(
            animal=self.animal, date=timezone.now() + timedelta(days=10), motif="TEST_TEMP à supprimer",
            veterinaire=_creer_veterinaire_test(self.user),
        )
        self.assertTrue(consultation.rappel_task_id)
        with mock.patch(
            'celery.result.AsyncResult.revoke', side_effect=RuntimeError('Redis injoignable'),
        ), self.assertLogs('consultations.models', level='ERROR'):
            response = self.client.post(reverse('consultations:consultation_delete', args=[consultation.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Consultation.objects.filter(pk=consultation.pk).exists())


class CalendrierBornesTest(TestCase):
    """Paramètres annee/mois extrêmes : repli sur le mois courant, jamais de 500."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_bornes', password='p')
        self.client.login(username='u_bornes', password='p')
        self.url = reverse('consultations:calendrier')

    def test_parametres_extremes(self):
        mois_courant = timezone.localdate().replace(day=1)
        for annee, mois in (('9999', '12'), ('100000000000000000000', '1'), ('1', '1'), ('-5', '3')):
            with self.subTest(annee=annee, mois=mois):
                response = self.client.get(self.url, {'annee': annee, 'mois': mois})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['mois_affiche'], mois_courant)

    def test_pas_de_lien_au_dela_des_bornes(self):
        from .calendrier import ANNEE_MAX, ANNEE_MIN
        response = self.client.get(self.url, {'annee': ANNEE_MAX, 'mois': 12})
        self.assertEqual(response.context['mois_affiche'], date(ANNEE_MAX, 12, 1))
        self.assertEqual(response.context['url_mois_suivant'], '')
        self.assertTrue(response.context['url_mois_precedent'])
        response = self.client.get(self.url, {'annee': ANNEE_MIN, 'mois': 1})
        self.assertEqual(response.context['url_mois_precedent'], '')

    def test_navigation_non_abandonnee_pendant_le_rafraichissement(self):
        """Le hx-sync « drop » de la zone ne doit pas être hérité par les
        liens de navigation (premier clic perdu au retour sur la fenêtre)."""
        response = self.client.get(self.url)
        self.assertContains(response, 'hx-boost="true" hx-sync="#zoneCalendrier:replace"')
        self.assertContains(response, 'hx-trigger="focus from:window delay:400ms" hx-sync="this:drop"')


class VeterinairePrenomTest(TestCase):
    """Le prénom affiché dans la liste des vétérinaires est saisissable."""

    def setUp(self):
        User.objects.create_user(username='u_prenom', password='p')
        self.client.login(username='u_prenom', password='p')

    def test_prenom_dans_le_formulaire(self):
        response = self.client.get(reverse('consultations:veterinaire_create'))
        self.assertContains(response, 'name="prenom"')
        response = self.client.post(reverse('consultations:veterinaire_create'), {
            'nom': 'TEST_TEMP_Prenom', 'prenom': 'Camille',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Veterinaire.objects.get(nom='TEST_TEMP_Prenom').prenom, 'Camille')

    def test_prenom_dans_l_ajout_rapide(self):
        self.client.post(reverse('consultations:veterinaire_ajout_rapide'), {
            'nouveau_veterinaire-nom': 'TEST_TEMP_Rapide', 'nouveau_veterinaire-prenom': 'Dominique',
        })
        self.assertEqual(Veterinaire.objects.get(nom='TEST_TEMP_Rapide').prenom, 'Dominique')


class ConsultationRechercheParDateTest(TestCase):
    """La colonne « Date » de la liste se cherche telle qu'elle est
    affichée (jj/mm/aaaa hh:mm, heure de Paris)."""

    def setUp(self):
        from zoneinfo import ZoneInfo
        self.user = User.objects.create_user(username='u_date', password='p')
        self.client.login(username='u_date', password='p')
        animal = _creer_animal_test("Rex", "333333", "date@example.com", utilisateur=self.user)
        # 00:30 à Paris le 15 = 23:30 UTC le 14 : la recherche suit l'affichage.
        Consultation.objects.create(
            animal=animal, date=timezone.datetime(2025, 1, 15, 0, 30, tzinfo=ZoneInfo('Europe/Paris')),
            motif="TEST_TEMP date", veterinaire=_creer_veterinaire_test(self.user),
        )

    def test_recherches(self):
        for recherche, attendu in (
            ('15/01/2025', 1), ('01/2025', 1), ('00:30', 1), ('2025', 1),
            ('14/01/2025', 0), ('23:30', 0), ('02/2025', 0),
        ):
            with self.subTest(recherche=recherche):
                response = self.client.get(reverse('consultations:consultation_list'), {'q': recherche})
                self.assertEqual(len(response.context['consultations']), attendu)


class ConsultationNotificationCloisonneeTest(TestCase):
    """L'email d'une fiche propriétaire est une saisie libre : un compte
    sans lien avec celui de l'animal ne reçoit aucune notification."""

    def test_pas_de_notification_a_un_compte_etranger_au_foyer(self):
        from unittest import mock
        from zoneinfo import ZoneInfo
        from notifications.models import Notification
        auteur = User.objects.create_user(username='u_auteur', password='p', email='auteur@example.com')
        tiers = User.objects.create_user(username='u_tiers_notif', password='p', email='bob.notif@example.com')
        animal = _creer_animal_test("Rex", "444444", "bob.notif@example.com", utilisateur=auteur)
        consultation = Consultation.objects.create(
            animal=animal, date=timezone.datetime(2025, 1, 15, 10, 0, tzinfo=ZoneInfo('Europe/Paris')),
            motif="TEST_TEMP cloisonnement", veterinaire=_creer_veterinaire_test(auteur),
        )
        with mock.patch('consultations.models.envoyer_email'):
            consultation.envoyer_rappel()
        self.assertFalse(Notification.objects.filter(utilisateur=tiers).exists())


class RappelPrisDeFaconAtomiqueTest(TestCase):
    """Décision produit : un rappel annulé ne doit jamais partir. La tâche
    n'envoie que si son propre identifiant est encore celui enregistré sur la
    consultation, et le vide en le prenant — une révocation perdue ou une
    double livraison n'envoie donc ni à l'ancienne date, ni deux fois."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_rappel', email='rappel@example.com', password='p')
        self.animal = _creer_animal_test("TEST_TEMP_RAPPEL", "777777", "rappel@example.com", utilisateur=self.user)
        self.consultation = Consultation.objects.create(
            animal=self.animal, date=timezone.now() + timedelta(days=10), motif="TEST_TEMP rappel",
            veterinaire=_creer_veterinaire_test(self.user),
        )

    def _livrer(self, task_id, consultation_id=None):
        """Exécute la tâche comme un worker le ferait pour le message
        d'identifiant `task_id` ; renvoie (rappel envoyé ?, mock d'envoi)."""
        from unittest import mock
        from .tasks import envoyer_rappel_consultation
        with mock.patch('consultations.models.envoyer_email') as envoyer_email:
            resultat = envoyer_rappel_consultation.apply(
                args=(consultation_id or self.consultation.pk,), task_id=task_id,
            )
        return resultat.result, envoyer_email

    def test_tache_liee_et_resultat_ignore(self):
        from .tasks import envoyer_rappel_consultation
        self.assertTrue(envoyer_rappel_consultation.ignore_result)

    def test_identifiant_enregistre_avant_la_publication(self):
        from unittest import mock
        vus = []

        def publier(args, eta=None, task_id=None):
            vus.append((task_id, Consultation.objects.get(pk=args[0]).rappel_task_id))

        with mock.patch('consultations.tasks.envoyer_rappel_consultation.apply_async', side_effect=publier):
            consultation = Consultation.objects.create(
                animal=self.animal, date=timezone.now() + timedelta(days=20), motif="TEST_TEMP ordre",
                veterinaire=_creer_veterinaire_test(self.user),
            )
        (task_id, en_base), = vus
        self.assertTrue(task_id)
        self.assertEqual(en_base, task_id)
        self.assertEqual(consultation.rappel_task_id, task_id)

    def test_rappel_envoye_une_seule_fois(self):
        task_id = self.consultation.rappel_task_id
        self.assertTrue(task_id)
        envoye, envoyer_email = self._livrer(task_id)
        self.assertTrue(envoye)
        envoyer_email.assert_called_once()
        self.consultation.refresh_from_db()
        self.assertIsNone(self.consultation.rappel_task_id)
        self.assertEqual(Notification.objects.filter(titre__startswith='Rappel').count(), 1)

        # Seconde livraison du même message : rien ne repart.
        envoye, envoyer_email = self._livrer(task_id)
        self.assertFalse(envoye)
        envoyer_email.assert_not_called()
        self.assertEqual(Notification.objects.filter(titre__startswith='Rappel').count(), 1)

    def test_consultation_replanifiee_l_ancienne_tache_n_envoie_rien(self):
        """Révocation perdue : la tâche calée sur l'ancienne date s'exécute
        quand même, mais ne trouve plus son identifiant."""
        from unittest import mock
        ancien_id = self.consultation.rappel_task_id
        with mock.patch('celery.result.AsyncResult.revoke', side_effect=RuntimeError('révocation perdue')), \
                self.assertLogs('consultations.models', level='ERROR'):
            self.consultation.date = timezone.now() + timedelta(days=30)
            self.consultation.save()
        nouvel_id = self.consultation.rappel_task_id
        self.assertTrue(nouvel_id)
        self.assertNotEqual(nouvel_id, ancien_id)

        envoye, envoyer_email = self._livrer(ancien_id)
        self.assertFalse(envoye)
        envoyer_email.assert_not_called()
        # Le nouveau rappel n'a pas été consommé par la tâche périmée.
        self.consultation.refresh_from_db()
        self.assertEqual(self.consultation.rappel_task_id, nouvel_id)

        envoye, envoyer_email = self._livrer(nouvel_id)
        self.assertTrue(envoye)
        envoyer_email.assert_called_once()

    def test_rappel_annule_ne_part_pas(self):
        """Consultation ramenée à moins de 2 jours : plus aucun rappel prévu."""
        ancien_id = self.consultation.rappel_task_id
        self.consultation.date = timezone.now() + timedelta(days=1)
        self.consultation.save()
        self.assertIsNone(self.consultation.rappel_task_id)
        envoye, envoyer_email = self._livrer(ancien_id)
        self.assertFalse(envoye)
        envoyer_email.assert_not_called()
        self.assertFalse(Notification.objects.filter(titre__startswith='Rappel').exists())

    def test_consultation_supprimee_ne_plante_pas(self):
        task_id, pk = self.consultation.rappel_task_id, self.consultation.pk
        self.consultation.delete()
        envoye, envoyer_email = self._livrer(task_id, consultation_id=pk)
        self.assertFalse(envoye)
        envoyer_email.assert_not_called()

    def test_tache_sans_identifiant_n_envoie_rien(self):
        """Une consultation sans rappel en attente (identifiant vide) ne doit
        pas être prise par une tâche elle-même sans identifiant."""
        from unittest import mock
        from .tasks import envoyer_rappel_consultation
        Consultation.objects.filter(pk=self.consultation.pk).update(rappel_task_id=None)
        with mock.patch('consultations.models.envoyer_email') as envoyer_email, \
                self.assertLogs('consultations.tasks', level='WARNING'):
            self.assertFalse(envoyer_rappel_consultation(self.consultation.pk))
        envoyer_email.assert_not_called()

    def test_echec_d_envoi_journalise_sans_nouvelle_tentative(self):
        from unittest import mock
        from .tasks import envoyer_rappel_consultation
        task_id = self.consultation.rappel_task_id
        with mock.patch('consultations.models.envoyer_email', side_effect=RuntimeError('SMTP injoignable')), \
                mock.patch.object(envoyer_rappel_consultation, 'retry') as retry, \
                self.assertLogs('consultations.tasks', level='ERROR'):
            resultat = envoyer_rappel_consultation.apply(args=(self.consultation.pk,), task_id=task_id)
        self.assertTrue(resultat.successful())
        self.assertFalse(resultat.result)
        retry.assert_not_called()
        # La notification dans l'application, créée avant l'email, reste acquise.
        self.assertEqual(Notification.objects.filter(titre__startswith='Rappel').count(), 1)
        # Le rappel reste pris : une relivraison ne renvoie rien.
        envoye, envoyer_email = self._livrer(task_id)
        self.assertFalse(envoye)
        envoyer_email.assert_not_called()


class VeterinaireRattacheAuCompteTest(TestCase):
    """Une fiche vétérinaire appartient au compte qui l'a créée : seuls ce
    compte et son foyer la voient, la choisissent, la modifient, la suppriment."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex_vc', password='p')
        self.sam = User.objects.create_user(username='sam_vc', password='p')
        self.tiers = User.objects.create_user(username='tiers_vc', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)
        self.veterinaire = _creer_veterinaire_test(self.alex, 'TEST_TEMP_VetAlex')
        self.animal_sam = _creer_animal_test("TEST_TEMP_VC_SAM", "910001", "sam.vc@example.com", utilisateur=self.sam)
        self.animal_tiers = _creer_animal_test("TEST_TEMP_VC_TIERS", "910002", "tiers.vc@example.com", utilisateur=self.tiers)
        self.pk = [self.veterinaire.pk]

    def _donnees(self, animal, **autres):
        return {
            'animal': animal.pk, 'date': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
            'motif': 'TEST_TEMP cloisonnement vétérinaire', 'veterinaire': self.veterinaire.pk, **autres,
        }

    def test_un_autre_compte_ne_voit_pas_la_fiche(self):
        self.client.login(username='tiers_vc', password='p')
        self.assertNotContains(self.client.get(reverse('consultations:veterinaire_list')), 'TEST_TEMP_VetAlex')
        self.assertNotContains(self.client.get(reverse('consultations:consultation_create')), 'TEST_TEMP_VetAlex')
        for nom in ('veterinaire_detail', 'veterinaire_update', 'veterinaire_delete'):
            with self.subTest(vue=nom):
                self.assertEqual(self.client.get(reverse(f'consultations:{nom}', args=self.pk)).status_code, 404)

    def test_un_autre_compte_ne_peut_ni_modifier_ni_supprimer(self):
        self.client.login(username='tiers_vc', password='p')
        response = self.client.post(reverse('consultations:veterinaire_update', args=self.pk), {'nom': 'TEST_TEMP_Pirate'})
        self.assertEqual(response.status_code, 404)
        response = self.client.post(reverse('consultations:veterinaire_delete', args=self.pk))
        self.assertEqual(response.status_code, 404)
        self.veterinaire.refresh_from_db()
        self.assertEqual(self.veterinaire.nom, 'TEST_TEMP_VetAlex')
        self.assertTrue(self.veterinaire.actif)

    def test_selection_forgee_refusee(self):
        self.client.login(username='tiers_vc', password='p')
        response = self.client.post(reverse('consultations:consultation_create'), self._donnees(self.animal_tiers))
        self.assertEqual(response.status_code, 200)
        self.assertIn('veterinaire', response.context['form'].errors)
        self.assertFalse(Consultation.objects.filter(animal=self.animal_tiers).exists())

    def test_un_membre_du_foyer_partage_la_fiche(self):
        self.client.login(username='sam_vc', password='p')
        self.assertContains(self.client.get(reverse('consultations:veterinaire_list')), 'TEST_TEMP_VetAlex')
        self.assertEqual(self.client.get(reverse('consultations:veterinaire_detail', args=self.pk)).status_code, 200)
        response = self.client.post(reverse('consultations:consultation_create'), self._donnees(self.animal_sam))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Consultation.objects.get(animal=self.animal_sam).veterinaire, self.veterinaire)
        # Modifiée par un autre membre du foyer, la fiche ne change pas de compte.
        response = self.client.post(
            reverse('consultations:veterinaire_update', args=self.pk), {'nom': 'TEST_TEMP_VetAlex', 'prenom': 'Camille'},
        )
        self.assertEqual(response.status_code, 302)
        self.veterinaire.refresh_from_db()
        self.assertEqual(self.veterinaire.prenom, 'Camille')
        self.assertEqual(self.veterinaire.utilisateur, self.alex)
        response = self.client.post(reverse('consultations:veterinaire_delete', args=self.pk))
        self.assertEqual(response.status_code, 302)
        self.veterinaire.refresh_from_db()
        self.assertFalse(self.veterinaire.actif)

    def test_creation_et_ajout_rapide_rattaches_au_createur(self):
        self.client.login(username='tiers_vc', password='p')
        self.client.post(reverse('consultations:veterinaire_create'), {'nom': 'TEST_TEMP_Page'})
        self.client.post(reverse('consultations:veterinaire_ajout_rapide'), {'nouveau_veterinaire-nom': 'TEST_TEMP_Rapide2'})
        self.assertEqual(Veterinaire.objects.get(nom='TEST_TEMP_Page').utilisateur, self.tiers)
        self.assertEqual(Veterinaire.objects.get(nom='TEST_TEMP_Rapide2').utilisateur, self.tiers)

    def test_deux_comptes_peuvent_creer_le_meme_nom(self):
        self.client.login(username='tiers_vc', password='p')
        response = self.client.post(reverse('consultations:veterinaire_create'), {'nom': 'TEST_TEMP_VetAlex'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(Veterinaire.objects.filter(nom='TEST_TEMP_VetAlex').values_list('utilisateur', flat=True)),
            {self.alex.pk, self.tiers.pk},
        )
        # Chacun ne voit que la sienne dans le menu du formulaire consultation.
        form = ConsultationForm(user=self.tiers)
        self.assertEqual(list(form.fields['veterinaire'].queryset.values_list('utilisateur', flat=True)), [self.tiers.pk])

    def test_fiche_deja_referencee_conservee_a_la_modification(self):
        """Consultation qui référence une fiche sortie du filtre (ancien
        membre du foyer, par exemple) : la fiche reste sélectionnée et
        consultable, sans pouvoir être modifiée."""
        consultation = Consultation.objects.create(
            animal=self.animal_tiers, date=timezone.now() + timedelta(days=4), motif='TEST_TEMP ancienne',
            veterinaire=self.veterinaire,
        )
        self.client.login(username='tiers_vc', password='p')
        url = reverse('consultations:consultation_update', args=[consultation.pk])
        self.assertContains(self.client.get(url), '<option value="%d" selected>' % self.veterinaire.pk)
        response = self.client.post(url, self._donnees(self.animal_tiers, motif='TEST_TEMP relue'))
        self.assertEqual(response.status_code, 302)
        consultation.refresh_from_db()
        self.assertEqual(consultation.motif, 'TEST_TEMP relue')
        self.assertEqual(consultation.veterinaire, self.veterinaire)

        response = self.client.get(reverse('consultations:veterinaire_detail', args=self.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('consultations:veterinaire_update', args=self.pk))
        self.assertEqual(self.client.get(reverse('consultations:veterinaire_update', args=self.pk)).status_code, 404)
        self.assertNotContains(self.client.get(reverse('consultations:veterinaire_list')), 'TEST_TEMP_VetAlex')

