from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from animaux.models import Animal, Espece, Robe, Race, Proprietaire
from .models import Facture, Designation, LigneFacture


def _fichier_test():
    return SimpleUploadedFile('facture.pdf', b'%PDF-1.4 test', content_type='application/pdf')


class VentilationFactureTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u_test', password='p')
        self.client = Client()
        self.client.login(username='u_test', password='p')

        chien = Espece.objects.get(code='CHIEN')
        robe = Robe.objects.filter(code='AUTRE').first() or Robe.objects.first()
        race = Race.objects.filter(espece=chien).first()
        proprietaire = Proprietaire.objects.create(nom='TEST_TEMP', email='test_temp2@example.com', utilisateur=self.user)
        self.animal1 = Animal.objects.create(
            nom='TEST_TEMP_1', race=race, espece=chien,
            date_naissance=date(2020, 1, 1), robe=robe, proprietaire=proprietaire, utilisateur=self.user,
        )
        self.animal2 = Animal.objects.create(
            nom='TEST_TEMP_2', race=race, espece=chien,
            date_naissance=date(2020, 1, 1), robe=robe, proprietaire=proprietaire, utilisateur=self.user,
        )
        self.designation = Designation.objects.create(nom='TEST_Consultation')

    def test_get_create_form(self):
        response = self.client.get(reverse('factures:facture_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'factures/form.html')

    def test_get_update_form_facture_simple(self):
        """Édition d'une facture non ventilée : formulaire pleinement
        éditable (pas de verrouillage)."""
        facture = Facture.objects.create(
            animal=self.animal1, type_depense='VETERINAIRE', titre='Simple',
            montant=Decimal('30.00'), date=date(2026, 8, 1), fichier=_fichier_test(),
        )
        response = self.client.get(reverse('factures:facture_update', args=[facture.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['verrouillee'])
        self.assertFalse(response.context['form'].fields['titre'].disabled)

    def test_detail_facture_ventilee_affiche_les_lignes(self):
        facture = self._creer_facture_ventilee()
        response = self.client.get(reverse('factures:facture_detail', args=[facture.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TEST_Consultation')
        self.assertContains(response, 'Tous les animaux')

    def test_creation_facture_simple_sans_ventilation(self):
        response = self.client.post(reverse('factures:facture_create'), {
            'numero': 'F001',
            'animal': self.animal1.pk,
            'type_depense': 'VETERINAIRE',
            'titre': 'Titre simple',
            'montant': '42.50',
            'date': '2026-08-01',
            'fichier': _fichier_test(),
            'description': '',
            'ventiler': '0',
            'lignes-TOTAL_FORMS': '0',
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.status_code == 200 else '')
        facture = Facture.objects.get(titre='Titre simple')
        self.assertEqual(facture.montant, Decimal('42.50'))
        self.assertFalse(facture.est_ventilee())

    def _creer_facture_ventilee(self):
        """Crée (via une requête POST réelle) une facture ventilée de 2
        lignes, réutilisée comme fixture par plusieurs tests ci-dessous."""
        data = {
            'numero': 'F002',
            'animal': '',
            'type_depense': 'VETERINAIRE',
            'titre': 'Titre ventilee',
            'montant': '',
            'date': '2026-08-01',
            'fichier': _fichier_test(),
            'description': '',
            'ventiler': '1',
            'lignes-TOTAL_FORMS': '2',
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-designation': self.designation.pk,
            'lignes-0-quantite': '2',
            'lignes-0-prix_unitaire': '10.00',
            'lignes-0-cible': str(self.animal1.pk),
            'lignes-1-designation': self.designation.pk,
            'lignes-1-quantite': '1',
            'lignes-1-prix_unitaire': '5.00',
            'lignes-1-cible': 'TOUS',
        }
        response = self.client.post(reverse('factures:facture_create'), data)
        assert response.status_code == 302, (
            (response.context['form'].errors, response.context['formset'].errors)
            if response.status_code == 200 else ''
        )
        return Facture.objects.get(titre='Titre ventilee')

    def test_creation_facture_ventilee(self):
        facture = self._creer_facture_ventilee()
        self.assertTrue(facture.est_ventilee())
        # 2*10 + 1*5 = 25
        self.assertEqual(facture.montant, Decimal('25.00'))
        lignes = list(facture.lignes.all())
        self.assertEqual(len(lignes), 2)
        ligne_animal = facture.lignes.get(pour_tous_les_animaux=False)
        self.assertEqual(ligne_animal.animal, self.animal1)
        self.assertEqual(ligne_animal.prix_total, Decimal('20.00'))
        ligne_partagee = facture.lignes.get(pour_tous_les_animaux=True)
        self.assertIsNone(ligne_partagee.animal)
        self.assertEqual(ligne_partagee.prix_total, Decimal('5.00'))

    def test_verrouillage_apres_ventilation(self):
        facture = self._creer_facture_ventilee()
        response = self.client.get(reverse('factures:facture_update', args=[facture.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['verrouillee'])
        self.assertTrue(response.context['form'].fields['titre'].disabled)

        ligne_existante = facture.lignes.get(pour_tous_les_animaux=False)
        data = {
            'numero': 'CHANGE_INTERDIT',  # doit être ignoré (champ disabled)
            'animal': '',
            'type_depense': 'VETERINAIRE',
            'titre': 'CHANGE_INTERDIT',   # doit être ignoré (champ disabled)
            'montant': '999.99',          # doit être ignoré (champ disabled)
            'date': '2026-08-01',
            'description': '',
            'ventiler': '1',
            'lignes-TOTAL_FORMS': '2',
            'lignes-INITIAL_FORMS': '1',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-id': ligne_existante.pk,
            'lignes-0-designation': 'CHANGE_INTERDIT_IGNORE',  # sera ignoré (disabled)
            'lignes-0-quantite': '99',  # ignoré (disabled)
            'lignes-0-prix_unitaire': '99',  # ignoré (disabled)
            'lignes-0-cible': str(self.animal2.pk),  # SEUL champ modifiable sur une ligne existante
            'lignes-1-designation': self.designation.pk,
            'lignes-1-quantite': '3',
            'lignes-1-prix_unitaire': '4.00',
            'lignes-1-cible': str(self.animal2.pk),
        }
        response = self.client.post(reverse('factures:facture_update', args=[facture.pk]), data)
        self.assertEqual(response.status_code, 302, (response.context['form'].errors, response.context['formset'].errors) if response.status_code == 200 else '')
        facture.refresh_from_db()
        self.assertEqual(facture.titre, 'Titre ventilee')  # inchangé
        self.assertEqual(facture.numero, 'F002')  # inchangé

        ligne_existante.refresh_from_db()
        self.assertEqual(ligne_existante.animal, self.animal2)  # rattribution OK
        self.assertEqual(ligne_existante.quantite, Decimal('2.00'))  # quantité inchangée
        self.assertEqual(ligne_existante.designation, self.designation)  # désignation inchangée

        self.assertEqual(facture.lignes.count(), 3)  # nouvelle ligne ajoutée
        # 20 (ligne1 inchangée) + 5 (ligne2 tous animaux) + 12 (nouvelle) = 37
        self.assertEqual(facture.montant, Decimal('37.00'))

    def test_suppression_ligne_existante_autorisee(self):
        facture = self._creer_facture_ventilee()
        ligne_a_supprimer = facture.lignes.get(pour_tous_les_animaux=False)
        ligne_restante = facture.lignes.get(pour_tous_les_animaux=True)
        data = {
            'numero': 'F002',
            'animal': '',
            'type_depense': 'VETERINAIRE',
            'titre': 'Titre ventilee',
            'montant': '25.00',
            'date': '2026-08-01',
            'description': '',
            'ventiler': '1',
            'lignes-TOTAL_FORMS': '1',
            'lignes-INITIAL_FORMS': '1',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-id': ligne_a_supprimer.pk,
            'lignes-0-cible': str(self.animal1.pk),
            'lignes-0-DELETE': 'on',
        }
        response = self.client.post(reverse('factures:facture_update', args=[facture.pk]), data)
        self.assertEqual(response.status_code, 302, (response.context['form'].errors, response.context['formset'].errors) if response.status_code == 200 else '')
        self.assertFalse(LigneFacture.objects.filter(pk=ligne_a_supprimer.pk).exists())
        facture.refresh_from_db()
        self.assertEqual(facture.montant, ligne_restante.prix_total)

    def test_cout_revient_animal(self):
        facture = self._creer_facture_ventilee()
        annee = facture.date.year
        # animal1 a une ligne à 20€ direct + une part de la ligne partagée (5€ / 2 animaux = 2.5€)
        cout1 = Facture.cout_revient_animal(self.animal1, annee)
        self.assertEqual(cout1, Decimal('22.50'))
        cout2 = Facture.cout_revient_animal(self.animal2, annee)
        self.assertEqual(cout2, Decimal('2.50'))

        couts = Facture.couts_revient_annuels(self.user, annee)
        self.assertEqual(couts[self.animal1.pk], Decimal('22.50'))
        self.assertEqual(couts[self.animal2.pk], Decimal('2.50'))

    def test_facture_non_ventilee_avec_animal_compte_100_pour_cent(self):
        Facture.objects.create(
            animal=self.animal1, type_depense='VETERINAIRE', titre='Simple',
            montant=Decimal('30.00'), date=date(2026, 8, 1), fichier=_fichier_test(),
        )
        cout1 = Facture.cout_revient_animal(self.animal1, 2026)
        cout2 = Facture.cout_revient_animal(self.animal2, 2026)
        self.assertEqual(cout1, Decimal('30.00'))
        self.assertEqual(cout2, Decimal('0'))

    def test_cout_revient_isole_par_compte(self):
        """Le cout de revient d'un animal ne doit jamais inclure les factures
        (ni la part de facture partagee) d'un autre compte."""
        autre_user = User.objects.create_user(username='autre_facture_user', password='p')
        chien = Espece.objects.get(code='CHIEN')
        robe = Robe.objects.filter(code='AUTRE').first() or Robe.objects.first()
        race = Race.objects.filter(espece=chien).first()
        autre_proprietaire = Proprietaire.objects.create(
            nom='AUTRE', email='autre_facture@example.com', utilisateur=autre_user,
        )
        autre_animal = Animal.objects.create(
            nom='AUTRE_ANIMAL', race=race, espece=chien,
            date_naissance=date(2020, 1, 1), robe=robe, proprietaire=autre_proprietaire,
            utilisateur=autre_user,
        )
        # Grosse facture partagee (sans animal) chez l'autre compte : ne doit
        # jamais impacter le cout de revient de self.animal1.
        Facture.objects.create(
            animal=None, utilisateur=autre_user, type_depense='ALIMENTAIRE', titre='Fuite',
            montant=Decimal('1000.00'), date=date(2026, 8, 1), fichier=_fichier_test(),
        )
        Facture.objects.create(
            animal=self.animal1, type_depense='VETERINAIRE', titre='Simple',
            montant=Decimal('30.00'), date=date(2026, 8, 1), fichier=_fichier_test(),
        )
        self.assertEqual(Facture.cout_revient_animal(self.animal1, 2026), Decimal('30.00'))
        self.assertEqual(Facture.cout_revient_animal(autre_animal, 2026), Decimal('1000.00'))
        couts = Facture.couts_revient_annuels(self.user, 2026)
        self.assertNotIn(autre_animal.pk, couts)

    def test_facture_non_ventilee_sans_animal_partagee(self):
        Facture.objects.create(
            animal=None, utilisateur=self.user, type_depense='ALIMENTAIRE', titre='Generale',
            montant=Decimal('10.00'), date=date(2026, 8, 1), fichier=_fichier_test(),
        )
        cout1 = Facture.cout_revient_animal(self.animal1, 2026)
        cout2 = Facture.cout_revient_animal(self.animal2, 2026)
        self.assertEqual(cout1, Decimal('5.00'))
        self.assertEqual(cout2, Decimal('5.00'))
