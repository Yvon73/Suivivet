import shutil
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from accueil.models import Foyer, MembreFoyer
from animaux.models import Animal, Espece, Robe, Race, Proprietaire
from documents.models import Document, TypeDocument
from notifications.models import Notification
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
        self.designation = Designation.objects.create(nom='TEST_Consultation', utilisateur=self.user)

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

    def test_liste_totaux_depenses_sans_facture(self):
        """Sans aucune facture, les totaux restent des montants à deux
        décimales (0.00), pas l'entier 0."""
        response = self.client.get(reverse('factures:facture_list'))
        self.assertEqual(response.status_code, 200)
        for cle in ('depenses_mensuelles_total', 'depenses_annuelles_total'):
            self.assertEqual(str(response.context[cle]), '0.00')

    def test_liste_totaux_depenses_conservent_les_centimes(self):
        aujourdhui = date.today()
        for type_depense, montant in (('VETERINAIRE', '12.50'), ('ALIMENTAIRE', '3.25')):
            Facture.objects.create(
                animal=self.animal1, utilisateur=self.user, type_depense=type_depense, titre='TEST_TEMP',
                montant=Decimal(montant), date=aujourdhui, fichier=_fichier_test(),
            )
        response = self.client.get(reverse('factures:facture_list'))
        self.assertEqual(response.context['depenses_mensuelles_total'], Decimal('15.75'))
        self.assertEqual(response.context['depenses_annuelles_total'], Decimal('15.75'))


class FacturePartageFoyerTest(TestCase):
    """Un membre du foyer voit les factures des autres membres, et le coût de
    revient se répartit sur tout le foyer ; un compte tiers, hors foyer,
    reste sans accès ni impact sur le calcul (régression de sécurité)."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex', password='p')
        self.sam = User.objects.create_user(username='sam', password='p')
        self.tiers = User.objects.create_user(username='tiers', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)

        chien = Espece.objects.get(code='CHIEN')
        robe = Robe.objects.filter(code='AUTRE').first() or Robe.objects.first()
        race = Race.objects.filter(espece=chien).first()
        proprietaire_alex = Proprietaire.objects.create(nom='Alex', email='alex.f@example.com', utilisateur=self.alex)
        self.animal_alex = Animal.objects.create(
            nom='AnimalAlex', race=race, espece=chien,
            date_naissance=date(2020, 1, 1), robe=robe, proprietaire=proprietaire_alex, utilisateur=self.alex,
        )
        self.facture = Facture.objects.create(
            animal=self.animal_alex, type_depense='VETERINAIRE', titre='Vaccin',
            montant=Decimal('40.00'), date=date(2026, 8, 1), fichier=_fichier_test(),
        )

    def test_membre_du_foyer_voit_la_facture(self):
        self.client.login(username='sam', password='p')
        response = self.client.get(reverse('factures:facture_detail', args=[self.facture.pk]))
        self.assertEqual(response.status_code, 200)

    def test_compte_tiers_hors_foyer_ne_voit_pas_la_facture(self):
        self.client.login(username='tiers', password='p')
        response = self.client.get(reverse('factures:facture_detail', args=[self.facture.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cout_de_revient_se_repartit_sur_tout_le_foyer(self):
        """Le compte de Sam (sans animal propre) doit quand même retrouver le
        coût de revient de l'animal d'Alex, puisqu'ils partagent un foyer."""
        couts = Facture.couts_revient_annuels(self.sam, 2026)
        self.assertEqual(couts.get(self.animal_alex.pk), Decimal('40.00'))

    def test_cout_de_revient_ignore_un_compte_tiers_hors_foyer(self):
        couts = Facture.couts_revient_annuels(self.tiers, 2026)
        self.assertNotIn(self.animal_alex.pk, couts)


class VentilationHtmxTest(TestCase):
    """Point d'entrée HTMX du formulaire de ventilation
    (views.ventilation_facture) : tous les calculs auparavant faits en
    JavaScript dans la page le sont désormais ici."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_htmx', password='p')
        self.client.login(username='u_htmx', password='p')
        chien = Espece.objects.get(code='CHIEN')
        robe = Robe.objects.filter(code='AUTRE').first() or Robe.objects.first()
        race = Race.objects.filter(espece=chien).first()
        proprietaire = Proprietaire.objects.create(nom='TEST_HTMX', email='test_htmx@example.com', utilisateur=self.user)
        self.animal = Animal.objects.create(
            nom='TEST_HTMX_1', race=race, espece=chien,
            date_naissance=date(2020, 1, 1), robe=robe, proprietaire=proprietaire, utilisateur=self.user,
        )
        self.designation = Designation.objects.create(nom='TEST_Croquettes', utilisateur=self.user)
        self.url = reverse('factures:facture_ventilation')

    def _lignes(self, *lignes, **extra):
        data = {
            'ventiler': '1',
            'lignes-TOTAL_FORMS': str(len(lignes)),
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
        }
        for index, ligne in enumerate(lignes):
            for champ, valeur in ligne.items():
                data[f'lignes-{index}-{champ}'] = valeur
        data.update(extra)
        return data

    def test_formulaire_sans_script_inline(self):
        response = self.client.get(reverse('factures:facture_create'))
        self.assertContains(response, 'vendor/htmx/htmx.min.js')
        self.assertContains(response, 'hx-post="%s"' % self.url)
        self.assertNotContains(response, 'addEventListener')

    def test_connexion_requise(self):
        self.client.logout()
        response = self.client.post(self.url, self._lignes())
        self.assertEqual(response.status_code, 302)

    def test_ventiler_affiche_une_premiere_ligne(self):
        response = self.client.post(self.url, {'ventiler': '0', 'action': 'ventiler'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="lignes-0-quantite"')
        self.assertContains(response, 'name="ventiler" id="id_ventiler" value="1"')
        self.assertContains(response, 'name="lignes-TOTAL_FORMS" value="1"')

    def test_recalcul_conserve_les_decimales(self):
        """Régression : le total perdait ses décimales (« 12,50 » lu 12)."""
        response = self.client.post(self.url, self._lignes(
            {'designation': self.designation.pk, 'quantite': '2', 'prix_unitaire': '12,50', 'cible': 'TOUS'},
            {'designation': self.designation.pk, 'quantite': '1.5', 'prix_unitaire': '3.33', 'cible': 'TOUS'},
        ))
        self.assertEqual(response.context['total'], Decimal('30.00'))
        self.assertEqual(response.context['lignes'][1]['prix_total'], Decimal('5.00'))
        self.assertContains(response, 'id="prixTotal-0" hx-swap-oob="true">25,00<')
        self.assertContains(response, 'value="30.00"')
        # Simple recalcul : les champs en cours de saisie ne sont pas renvoyés.
        self.assertNotContains(response, 'name="lignes-0-quantite"')

    def test_recalcul_tolere_une_saisie_incomplete(self):
        response = self.client.post(self.url, self._lignes(
            {'designation': '', 'quantite': 'abc', 'prix_unitaire': '', 'cible': 'TOUS'},
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], Decimal('0'))

    def test_ajouter_une_ligne_reprend_l_animal_precedent(self):
        response = self.client.post(self.url, self._lignes(
            {'designation': self.designation.pk, 'quantite': '2', 'prix_unitaire': '10', 'cible': str(self.animal.pk)},
            action='ajouter',
        ))
        self.assertContains(response, 'name="lignes-TOTAL_FORMS" value="2"')
        lignes = response.context['lignes']
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[1]['form']['cible'].value(), str(self.animal.pk))
        self.assertEqual(lignes[0]['form']['quantite'].value(), '2')

    def test_retirer_une_ligne_renumerote_les_suivantes(self):
        response = self.client.post(self.url, self._lignes(
            {'designation': self.designation.pk, 'quantite': '1', 'prix_unitaire': '1', 'cible': 'TOUS'},
            {'designation': self.designation.pk, 'quantite': '1', 'prix_unitaire': '2', 'cible': 'TOUS'},
            {'designation': self.designation.pk, 'quantite': '1', 'prix_unitaire': '4', 'cible': 'TOUS'},
            action='retirer', ligne='1',
        ))
        lignes = response.context['lignes']
        self.assertEqual([ligne['prix_total'] for ligne in lignes], [Decimal('1.00'), Decimal('4.00')])
        self.assertEqual(response.context['total'], Decimal('5.00'))
        self.assertContains(response, 'name="lignes-TOTAL_FORMS" value="2"')

    def test_nouvelle_designation_creee_et_selectionnee(self):
        data = self._lignes(
            {'designation': '', 'quantite': '1', 'prix_unitaire': '', 'cible': 'TOUS'},
            action='designation', ligne='0',
        )
        data['nouvelle_designation-0'] = '  TEST_Vermifuge  '
        response = self.client.post(self.url, data)
        designation = Designation.objects.get(nom='TEST_Vermifuge')
        self.assertEqual(response.context['lignes'][0]['form']['designation'].value(), str(designation.pk))
        self.assertContains(response, '<option value="%d" selected>TEST_Vermifuge</option>' % designation.pk)

    def test_nouvelle_designation_en_double_ou_vide_signalee(self):
        data = self._lignes(
            {'designation': '', 'quantite': '1', 'prix_unitaire': '', 'cible': 'TOUS'},
            action='designation', ligne='0',
        )
        data['nouvelle_designation-0'] = 'TEST_Croquettes'
        response = self.client.post(self.url, data)
        self.assertEqual(Designation.objects.filter(nom='TEST_Croquettes').count(), 1)
        self.assertTrue(response.context['lignes'][0]['erreurs_designation'])
        self.assertContains(response, 'value="TEST_Croquettes"')

        data['nouvelle_designation-0'] = ''
        response = self.client.post(self.url, data)
        self.assertContains(response, 'La désignation est obligatoire.')

    def test_dernier_prix_compare_au_prix_saisi(self):
        facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='Ancienne', montant=Decimal('0.01'),
            date=date(2026, 7, 1), fichier=_fichier_test(), utilisateur=self.user,
        )
        LigneFacture.objects.create(
            facture=facture, designation=self.designation, quantite=Decimal('1'),
            prix_unitaire=Decimal('20.00'), pour_tous_les_animaux=True,
        )
        response = self.client.post(self.url, self._lignes(
            {'designation': self.designation.pk, 'quantite': '1', 'prix_unitaire': '22,5', 'cible': 'TOUS'},
        ))
        self.assertEqual(response.context['lignes'][0]['comparaison'], 'plus')
        self.assertContains(response, 'Prix précédent : 20,00 €')
        self.assertContains(response, 'plus élevé')

    def test_facture_existante_ligne_cochee_suppr_exclue_du_total(self):
        facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='Ventilée', montant=Decimal('0.01'),
            date=date(2026, 7, 1), fichier=_fichier_test(), utilisateur=self.user,
        )
        ligne = LigneFacture.objects.create(
            facture=facture, designation=self.designation, quantite=Decimal('2'),
            prix_unitaire=Decimal('7.25'), pour_tous_les_animaux=True,
        )
        url = reverse('factures:facture_ventilation', args=[facture.pk])
        data = self._lignes({'id': ligne.pk, 'cible': 'TOUS'})
        data['lignes-INITIAL_FORMS'] = '1'
        response = self.client.post(url, data)
        self.assertEqual(response.context['total'], Decimal('14.50'))
        self.assertTrue(response.context['verrouillee'])

        # Une ligne enregistrée ne se retire pas par l'action « retirer ».
        response = self.client.post(url, {**data, 'action': 'retirer', 'ligne': '0'})
        self.assertEqual(len(response.context['lignes']), 1)

        data['lignes-0-DELETE'] = 'on'
        response = self.client.post(url, data)
        self.assertEqual(response.context['total'], Decimal('0'))
        self.assertTrue(LigneFacture.objects.filter(pk=ligne.pk).exists())

    def test_facture_d_un_autre_compte_inaccessible(self):
        autre = User.objects.create_user(username='u_htmx_autre', password='p')
        facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='Privée', montant=Decimal('10.00'),
            date=date(2026, 7, 1), fichier=_fichier_test(), utilisateur=autre,
        )
        response = self.client.post(reverse('factures:facture_ventilation', args=[facture.pk]), self._lignes())
        self.assertEqual(response.status_code, 404)


def _animal_test(utilisateur, nom, email_proprietaire):
    chien = Espece.objects.get(code='CHIEN')
    robe = Robe.objects.filter(code='AUTRE').first() or Robe.objects.first()
    proprietaire = Proprietaire.objects.create(nom=f'P_{nom}', email=email_proprietaire, utilisateur=utilisateur)
    return Animal.objects.create(
        nom=nom, race=Race.objects.filter(espece=chien).first(), espece=chien,
        date_naissance=date(2020, 1, 1), robe=robe, proprietaire=proprietaire, utilisateur=utilisateur,
    )


class MediaTemporaireMixin:
    """Fichiers téléversés dans un dossier temporaire : ces tests suppriment
    des fichiers du stockage, jamais dans le vrai media/."""

    @classmethod
    def setUpClass(cls):
        cls.dossier_media = tempfile.mkdtemp(prefix='test_media_')
        cls.reglages_media = override_settings(MEDIA_ROOT=cls.dossier_media)
        cls.reglages_media.enable()
        cls.addClassCleanup(shutil.rmtree, cls.dossier_media, ignore_errors=True)
        cls.addClassCleanup(cls.reglages_media.disable)
        super().setUpClass()


class MontantFactureVentileeTest(TestCase):
    """Le montant d'une facture ventilée vient de ses lignes, jamais de la
    valeur postée (périmée dès que le formulaire part avant la réponse du
    recalcul HTMX), et la dernière ligne d'une facture ventilée se supprime."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_montant', password='p')
        self.client.login(username='u_montant', password='p')
        self.animal = _animal_test(self.user, 'TEST_MONTANT', 'montant@example.com')
        self.designation = Designation.objects.create(nom='TEST_Montant', utilisateur=self.user)

    def _donnees(self, *lignes, **extra):
        data = {
            'numero': '', 'animal': '', 'type_depense': 'ALIMENTAIRE', 'titre': 'Montant ventilé',
            'montant': '0.00', 'date': '2026-08-01', 'description': '', 'ventiler': '1',
            'lignes-TOTAL_FORMS': str(len(lignes)), 'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
        }
        for index, ligne in enumerate(lignes):
            for champ, valeur in ligne.items():
                data[f'lignes-{index}-{champ}'] = valeur
        data.update(extra)
        return data

    def _ligne(self, prix):
        return {'designation': self.designation.pk, 'quantite': '2', 'prix_unitaire': prix, 'cible': 'TOUS'}

    def test_montant_poste_a_zero_remplace_par_le_total_des_lignes(self):
        """« 0.00 » est la valeur du champ juste après le clic sur « Ventiler »."""
        response = self.client.post(
            reverse('factures:facture_create'), self._donnees(self._ligne('12.50'), fichier=_fichier_test()),
        )
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.context else '')
        self.assertEqual(Facture.objects.get(titre='Montant ventilé').montant, Decimal('25.00'))

    def test_montant_poste_perime_ignore(self):
        response = self.client.post(
            reverse('factures:facture_create'),
            self._donnees(self._ligne('12.50'), fichier=_fichier_test(), montant='999.00'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Facture.objects.get(titre='Montant ventilé').montant, Decimal('25.00'))

    def test_erreur_reaffiche_le_total_des_lignes(self):
        """Autre champ en erreur (fichier manquant) : le champ Montant
        réaffiche le total des lignes, pas la valeur périmée postée."""
        response = self.client.post(reverse('factures:facture_create'), self._donnees(self._ligne('12.50')))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form']['montant'].value(), '25.00')
        self.assertFalse(response.context['form']['montant'].errors)

    def test_lignes_de_total_nul_refusees_avec_un_message_clair(self):
        for lignes in ((), (self._ligne('0'),)):
            with self.subTest(lignes=lignes):
                response = self.client.post(
                    reverse('factures:facture_create'), self._donnees(*lignes, fichier=_fichier_test()),
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context['form'].errors['montant'],
                    ["Ajoute au moins une ligne de ventilation d'un montant non nul."],
                )
                self.assertFalse(Facture.objects.filter(titre='Montant ventilé').exists())

    def test_suppression_de_toutes_les_lignes_d_une_facture_ventilee(self):
        facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='À dé-ventiler', montant=Decimal('0.01'),
            date=date(2026, 7, 1), fichier=_fichier_test(), utilisateur=self.user,
        )
        ligne = LigneFacture.objects.create(
            facture=facture, designation=self.designation, quantite=Decimal('1'),
            prix_unitaire=Decimal('30.00'), pour_tous_les_animaux=True,
        )
        url = reverse('factures:facture_update', args=[facture.pk])
        # Facture verrouillée : ses champs sont `disabled`, donc non postés.
        response = self.client.post(url, {
            'ventiler': '1',
            'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '1',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-id': ligne.pk, 'lignes-0-cible': 'TOUS', 'lignes-0-DELETE': 'on',
        })
        # Retour sur le formulaire, redevenu modifiable, pour saisir le montant.
        self.assertRedirects(response, url, fetch_redirect_response=False)
        facture.refresh_from_db()
        self.assertFalse(facture.est_ventilee())
        self.assertEqual(facture.montant, Decimal('0'))
        response = self.client.get(url)
        self.assertFalse(response.context['verrouillee'])
        self.assertContains(response, "n&#x27;est plus ventilée")


class FactureProprietaireConserveTest(TestCase):
    """Modifier la facture d'un autre membre du foyer ne la réattribue pas
    au compte qui modifie."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex_p', password='p')
        self.sam = User.objects.create_user(username='sam_p', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)
        self.animal = _animal_test(self.alex, 'AnimalAlexP', 'alex.p@example.com')
        self.designation = Designation.objects.create(nom='TEST_Proprietaire', utilisateur=self.alex)
        self.client.login(username='sam_p', password='p')

    def test_modification_par_un_autre_membre(self):
        facture = Facture.objects.create(
            animal=self.animal, type_depense='VETERINAIRE', titre='Vaccin', utilisateur=self.alex,
            montant=Decimal('40.00'), date=date(2026, 8, 1), fichier=_fichier_test(),
        )
        response = self.client.post(reverse('factures:facture_update', args=[facture.pk]), {
            'numero': '', 'animal': self.animal.pk, 'type_depense': 'VETERINAIRE', 'titre': 'Vaccin corrigé',
            'montant': '40.00', 'date': '2026-08-01', 'description': '', 'ventiler': '0',
        })
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.context else '')
        facture.refresh_from_db()
        self.assertEqual(facture.titre, 'Vaccin corrigé')
        self.assertEqual(facture.utilisateur, self.alex)

    def test_modification_d_une_facture_verrouillee_par_un_autre_membre(self):
        facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='Ventilée', montant=Decimal('0.01'),
            date=date(2026, 7, 1), fichier=_fichier_test(), utilisateur=self.alex,
        )
        ligne = LigneFacture.objects.create(
            facture=facture, designation=self.designation, quantite=Decimal('1'),
            prix_unitaire=Decimal('30.00'), pour_tous_les_animaux=True,
        )
        response = self.client.post(reverse('factures:facture_update', args=[facture.pk]), {
            'ventiler': '1',
            'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '1',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-id': ligne.pk, 'lignes-0-cible': str(self.animal.pk),
        })
        self.assertEqual(response.status_code, 302)
        facture.refresh_from_db()
        self.assertEqual(facture.utilisateur, self.alex)
        self.assertEqual(facture.lignes.get().animal, self.animal)

    def test_creation_rattachee_au_compte_connecte(self):
        response = self.client.post(reverse('factures:facture_create'), {
            'numero': '', 'animal': '', 'type_depense': 'ALIMENTAIRE', 'titre': 'Partagée de Sam',
            'montant': '12.00', 'date': '2026-08-01', 'description': '', 'ventiler': '0',
            'fichier': _fichier_test(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Facture.objects.get(titre='Partagée de Sam').utilisateur, self.sam)


class LigneAnimalSupprimeTest(TestCase):
    """Une ligne dont l'animal a été supprimé ne devient pas, sans le dire,
    une ligne « Tous les animaux » au prochain enregistrement."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_orpheline', password='p')
        self.client.login(username='u_orpheline', password='p')
        self.animal = _animal_test(self.user, 'TEST_RESTANT', 'orpheline@example.com')
        disparu = _animal_test(self.user, 'TEST_DISPARU', 'orpheline2@example.com')
        self.facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='Ligne orpheline', montant=Decimal('0.01'),
            date=date(2026, 7, 1), fichier=_fichier_test(), utilisateur=self.user,
        )
        self.ligne = LigneFacture.objects.create(
            facture=self.facture, designation=Designation.objects.create(nom='TEST_Orpheline', utilisateur=self.user),
            quantite=Decimal('1'), prix_unitaire=Decimal('30.00'), animal=disparu,
        )
        # Donnée héritée : avant la décision « supprimer avec l'animal », la
        # suppression d'un animal laissait ses lignes sans animal (SET_NULL).
        # Elle les supprime désormais (cf. SuppressionAnimalEmporteSesFacturesTest) :
        # l'état hérité est donc reproduit directement en base.
        LigneFacture.objects.filter(pk=self.ligne.pk).update(animal=None)
        self.ligne.refresh_from_db()
        self.url = reverse('factures:facture_update', args=[self.facture.pk])

    def _donnees(self, cible):
        return {
            'ventiler': '1',
            'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '1',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-id': self.ligne.pk, 'lignes-0-cible': cible,
        }

    def test_option_explicite_selectionnee(self):
        response = self.client.get(self.url)
        self.assertContains(response, '<option value="" selected>— Animal supprimé : à réattribuer —</option>', html=True)

    def test_enregistrement_sans_choix_refuse(self):
        response = self.client.post(self.url, self._donnees(''))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['formset'].forms[0].errors['cible'])
        self.ligne.refresh_from_db()
        self.assertFalse(self.ligne.pour_tous_les_animaux)

    def test_reattribution_possible(self):
        response = self.client.post(self.url, self._donnees(str(self.animal.pk)))
        self.assertEqual(response.status_code, 302)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.animal, self.animal)

    def test_ligne_ordinaire_sans_option_vide(self):
        self.ligne.animal = self.animal
        self.ligne.save()
        response = self.client.get(self.url)
        self.assertNotContains(response, 'Animal supprimé')


class PrixPrecedentCloisonneTest(TestCase):
    """Le « prix précédent » d'une désignation n'est lu que dans les
    factures du compte et de son foyer."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex_prix', password='p')
        self.sam = User.objects.create_user(username='sam_prix', password='p')
        self.tiers = User.objects.create_user(username='tiers_prix', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)
        self.designation = Designation.objects.create(nom='TEST_Prix', utilisateur=self.alex)
        facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='Facture Alex', montant=Decimal('0.01'),
            date=date(2026, 7, 1), fichier=_fichier_test(), utilisateur=self.alex,
        )
        LigneFacture.objects.create(
            facture=facture, designation=self.designation, quantite=Decimal('1'),
            prix_unitaire=Decimal('54.90'), pour_tous_les_animaux=True,
        )

    def _recalcul(self, username):
        self.client.login(username=username, password='p')
        return self.client.post(reverse('factures:facture_ventilation'), {
            'ventiler': '1',
            'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-designation': self.designation.pk, 'lignes-0-quantite': '1',
            'lignes-0-prix_unitaire': '60', 'lignes-0-cible': 'TOUS',
        })

    def test_methode_du_modele(self):
        self.assertEqual(self.designation.dernier_prix_unitaire(self.alex), Decimal('54.90'))
        self.assertEqual(self.designation.dernier_prix_unitaire(self.sam), Decimal('54.90'))
        self.assertIsNone(self.designation.dernier_prix_unitaire(self.tiers))

    def test_membre_du_foyer_voit_le_prix(self):
        response = self._recalcul('sam_prix')
        self.assertContains(response, 'Prix précédent : 54,90 €')

    def test_compte_tiers_ne_voit_pas_le_prix(self):
        response = self._recalcul('tiers_prix')
        self.assertIsNone(response.context['lignes'][0]['dernier_prix'])
        self.assertNotContains(response, 'Prix précédent')
        self.assertNotContains(response, '54,90')

    def test_formulaire_de_creation_du_compte_tiers(self):
        """Même cloisonnement au réaffichage du formulaire complet."""
        self.client.login(username='tiers_prix', password='p')
        response = self.client.post(reverse('factures:facture_create'), {
            'numero': '', 'animal': '', 'type_depense': 'ALIMENTAIRE', 'titre': '', 'montant': '',
            'date': '2026-08-01', 'description': '', 'ventiler': '1',
            'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-designation': self.designation.pk, 'lignes-0-quantite': '1',
            'lignes-0-prix_unitaire': '60', 'lignes-0-cible': 'TOUS',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Prix précédent')


class NouvelleDesignationParEntreeTest(TestCase):
    """Entrée dans « Nouvelle désignation » d'une ligne envoie le bouton
    « Ajouter » de la première ligne non enregistrée : pas d'erreur
    « obligatoire » sur cette autre ligne."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_entree', password='p')
        self.client.login(username='u_entree', password='p')

    def test_pas_d_erreur_sur_une_autre_ligne(self):
        response = self.client.post(reverse('factures:facture_ventilation'), {
            'ventiler': '1', 'action': 'designation', 'ligne': '0',
            'lignes-TOTAL_FORMS': '2', 'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-designation': '', 'lignes-0-quantite': '1', 'lignes-0-prix_unitaire': '', 'lignes-0-cible': 'TOUS',
            'lignes-1-designation': '', 'lignes-1-quantite': '1', 'lignes-1-prix_unitaire': '', 'lignes-1-cible': 'TOUS',
            'nouvelle_designation-0': '', 'nouvelle_designation-1': 'TEST_Vermifuge_Entree',
        })
        designation = Designation.objects.get(nom='TEST_Vermifuge_Entree')
        self.assertEqual(response.context['lignes'][1]['form']['designation'].value(), str(designation.pk))
        self.assertEqual(response.context['lignes'][0]['erreurs_designation'], [])
        self.assertNotContains(response, 'La désignation est obligatoire.')


class RechercheListeFacturesTest(TestCase):
    """Toutes les colonnes affichées se cherchent : type de dépense (libellé
    accentué ou non), date et montant tels qu'affichés."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_recherche', password='p')
        self.client.login(username='u_recherche', password='p')
        Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='Croquettes', montant=Decimal('45.90'),
            date=date(2026, 3, 15), fichier=_fichier_test(), utilisateur=self.user,
        )
        Facture.objects.create(
            type_depense='VETERINAIRE', titre='Rappel', montant=Decimal('120.00'),
            date=date(2025, 11, 2), fichier=_fichier_test(), utilisateur=self.user,
        )

    def _titres(self, recherche):
        response = self.client.get(reverse('factures:facture_list'), {'q': recherche})
        self.assertEqual(response.status_code, 200)
        return sorted(facture.titre for facture in response.context['factures'])

    def test_recherches(self):
        attendus = {
            'alimentaire': ['Croquettes'],
            'Vétérinaire': ['Rappel'],
            'veterinaire': ['Rappel'],
            '03/2026': ['Croquettes'],
            '15/03/2026': ['Croquettes'],
            '2025': ['Rappel'],
            '45,90': ['Croquettes'],
            '45.90': ['Croquettes'],
            '120': ['Rappel'],
            'croquettes 2026': ['Croquettes'],
            'croquettes 2025': [],
            'introuvable': [],
        }
        for recherche, titres in attendus.items():
            with self.subTest(recherche=recherche):
                self.assertEqual(self._titres(recherche), titres)

    def test_recherche_combinee_au_tri(self):
        response = self.client.get(reverse('factures:facture_list'), {'q': '20', 'tri': 'montant', 'sens': 'desc'})
        self.assertEqual([f.titre for f in response.context['factures']], ['Rappel', 'Croquettes'])


class FichierAbsentDuDisqueTest(MediaTemporaireMixin, TestCase):
    """Ligne en base mais fichier absent de media/ (base restaurée sans son
    dossier media, par exemple) : 404 à l'ouverture, et le document reste
    modifiable sans retéléverser de fichier."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_absent', password='p')
        self.client.login(username='u_absent', password='p')
        self.animal = _animal_test(self.user, 'TEST_ABSENT', 'absent@example.com')
        self.facture = Facture.objects.create(
            animal=self.animal, type_depense='VETERINAIRE', titre='Sans fichier', montant=Decimal('10.00'),
            date=date(2026, 8, 1), fichier=_fichier_test(), utilisateur=self.user,
        )
        self.type_document = TypeDocument.objects.create(nom='TEST_Type')
        self.document = Document.objects.create(
            animal=self.animal, type_document=self.type_document, titre='Sans fichier', fichier=_fichier_test(),
        )
        for objet in (self.facture, self.document):
            objet.fichier.storage.delete(objet.fichier.name)

    def test_fichier_de_facture_absent_404(self):
        response = self.client.get(reverse('factures:facture_fichier', args=[self.facture.pk]))
        self.assertEqual(response.status_code, 404)

    def test_fichier_de_document_absent_404(self):
        response = self.client.get(reverse('documents:document_fichier', args=[self.document.pk]))
        self.assertEqual(response.status_code, 404)

    def test_document_modifiable_sans_reteleverser(self):
        response = self.client.post(reverse('documents:document_update', args=[self.document.pk]), {
            'animal': self.animal.pk, 'type_document': self.type_document.pk,
            'nouveau_type_document': '', 'titre': 'Titre corrigé', 'description': '',
        })
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.context else '')
        self.document.refresh_from_db()
        self.assertEqual(self.document.titre, 'Titre corrigé')

    def test_facture_modifiable_sans_reteleverser(self):
        response = self.client.post(reverse('factures:facture_update', args=[self.facture.pk]), {
            'numero': '', 'animal': self.animal.pk, 'type_depense': 'VETERINAIRE', 'titre': 'Titre corrigé',
            'montant': '10.00', 'date': '2026-08-01', 'description': '', 'ventiler': '0',
        })
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.context else '')

    def test_fichier_trop_gros_toujours_refuse_au_televersement(self):
        from Projet_veto.validators import MAX_UPLOAD_SIZE_BYTES
        gros = SimpleUploadedFile('gros.pdf', b'0' * (MAX_UPLOAD_SIZE_BYTES + 1), content_type='application/pdf')
        response = self.client.post(reverse('documents:document_update', args=[self.document.pk]), {
            'animal': self.animal.pk, 'type_document': self.type_document.pk,
            'nouveau_type_document': '', 'titre': 'Trop gros', 'description': '', 'fichier': gros,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors['fichier'])


class MenageFichiersTest(MediaTemporaireMixin, TestCase):
    """Le fichier d'un document ou d'une facture quitte le disque quand sa
    ligne est supprimée ou quand il est remplacé — après validation de la
    transaction, et jamais s'il est encore référencé par une autre ligne."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_menage', password='p')
        self.client.login(username='u_menage', password='p')
        self.animal = _animal_test(self.user, 'TEST_MENAGE', 'menage@example.com')
        self.type_document = TypeDocument.objects.create(nom='TEST_Menage')
        self.document = Document.objects.create(
            animal=self.animal, type_document=self.type_document, titre='À supprimer', fichier=_fichier_test(),
        )
        self.facture = Facture.objects.create(
            animal=self.animal, type_depense='VETERINAIRE', titre='À supprimer', montant=Decimal('10.00'),
            date=date(2026, 8, 1), fichier=_fichier_test(), utilisateur=self.user,
        )
        self.stockage = self.document.fichier.storage

    def test_suppression_d_un_document(self):
        nom = self.document.fichier.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('documents:document_delete', args=[self.document.pk]))
            self.assertEqual(response.status_code, 302)
            # Rien n'est supprimé avant la validation de la transaction.
            self.assertTrue(self.stockage.exists(nom))
        self.assertFalse(self.stockage.exists(nom))

    def test_suppression_d_une_facture(self):
        nom = self.facture.fichier.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('factures:facture_delete', args=[self.facture.pk]))
            self.assertEqual(response.status_code, 302)
        self.assertFalse(self.stockage.exists(nom))

    def test_suppression_en_cascade_avec_l_animal(self):
        nom = self.document.fichier.name
        with self.captureOnCommitCallbacks(execute=True):
            self.animal.delete()
        self.assertFalse(Document.objects.filter(pk=self.document.pk).exists())
        self.assertFalse(self.stockage.exists(nom))
        # La facture non ventilée de l'animal part avec lui (décision
        # produit), son fichier scanné aussi.
        self.assertFalse(Facture.objects.filter(pk=self.facture.pk).exists())
        self.assertFalse(self.stockage.exists(self.facture.fichier.name))

    def test_remplacement_du_fichier_d_un_document(self):
        ancien = self.document.fichier.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('documents:document_update', args=[self.document.pk]), {
                'animal': self.animal.pk, 'type_document': self.type_document.pk,
                'nouveau_type_document': '', 'titre': 'Remplacé', 'description': '',
                'fichier': SimpleUploadedFile('nouveau.pdf', b'%PDF-1.4 nouveau', content_type='application/pdf'),
            })
            self.assertEqual(response.status_code, 302, response.context['form'].errors if response.context else '')
        self.document.refresh_from_db()
        self.assertNotEqual(self.document.fichier.name, ancien)
        self.assertFalse(self.stockage.exists(ancien))
        self.assertTrue(self.stockage.exists(self.document.fichier.name))

    def test_remplacement_du_fichier_d_une_facture(self):
        ancien = self.facture.fichier.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('factures:facture_update', args=[self.facture.pk]), {
                'numero': '', 'animal': self.animal.pk, 'type_depense': 'VETERINAIRE', 'titre': 'Remplacée',
                'montant': '10.00', 'date': '2026-08-01', 'description': '', 'ventiler': '0',
                'fichier': SimpleUploadedFile('nouveau.pdf', b'%PDF-1.4 nouveau', content_type='application/pdf'),
            })
            self.assertEqual(response.status_code, 302, response.context['form'].errors if response.context else '')
        self.facture.refresh_from_db()
        self.assertFalse(self.stockage.exists(ancien))
        self.assertTrue(self.stockage.exists(self.facture.fichier.name))

    def test_modification_sans_nouveau_fichier_conserve_le_fichier(self):
        nom = self.document.fichier.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('documents:document_update', args=[self.document.pk]), {
                'animal': self.animal.pk, 'type_document': self.type_document.pk,
                'nouveau_type_document': '', 'titre': 'Renommé', 'description': '',
            })
        self.document.refresh_from_db()
        self.assertEqual(self.document.titre, 'Renommé')
        self.assertEqual(self.document.fichier.name, nom)
        self.assertTrue(self.stockage.exists(nom))

    def test_fichier_encore_reference_par_une_autre_ligne_conserve(self):
        nom = self.document.fichier.name
        jumeau = Document.objects.create(
            animal=self.animal, type_document=self.type_document, titre='Jumeau', fichier=nom,
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.document.delete()
        self.assertTrue(self.stockage.exists(nom))
        with self.captureOnCommitCallbacks(execute=True):
            jumeau.delete()
        self.assertFalse(self.stockage.exists(nom))

    def test_transaction_annulee_conserve_le_fichier(self):
        pk, nom = self.document.pk, self.document.fichier.name
        with self.captureOnCommitCallbacks(execute=True) as rappels:
            try:
                with transaction.atomic():
                    self.document.delete()
                    raise RuntimeError('annulation')
            except RuntimeError:
                pass
        self.assertEqual(rappels, [])
        self.assertTrue(Document.objects.filter(pk=pk).exists())
        self.assertTrue(self.stockage.exists(nom))


class DocumentsDiversTest(MediaTemporaireMixin, TestCase):
    """Régressions de l'app documents (son tests.py n'est pas dans
    pytest.ini) : type en double à la casse près, notification cloisonnée,
    recherche par date d'ajout."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_docs', password='p', email='docs@example.com')
        self.client.login(username='u_docs', password='p')
        self.animal = _animal_test(self.user, 'TEST_DOCS', 'docs@example.com')
        self.type_document = TypeDocument.objects.create(nom='TEST_Radio')

    def _poster(self, **extra):
        data = {
            'animal': self.animal.pk, 'type_document': '', 'nouveau_type_document': '',
            'titre': 'Cliché', 'description': '', 'fichier': _fichier_test(),
        }
        data.update(extra)
        return self.client.post(reverse('documents:document_create'), data)

    def test_types_en_double_a_la_casse_pres(self):
        TypeDocument.objects.create(nom='test_radio')
        response = self._poster(nouveau_type_document='TEST_RADIO')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.get(titre='Cliché').type_document, self.type_document)
        self.assertEqual(TypeDocument.objects.filter(nom__iexact='test_radio').count(), 2)

    def test_nouveau_type_cree_ou_reutilise(self):
        self.assertEqual(self._poster(nouveau_type_document='TEST_Échographie').status_code, 302)
        self.assertEqual(self._poster(nouveau_type_document='test_échographie', titre='Second').status_code, 302)
        self.assertEqual(TypeDocument.objects.filter(nom__iexact='test_échographie').count(), 1)

    def test_notification_au_proprietaire_du_meme_compte(self):
        Document.objects.create(
            animal=self.animal, type_document=self.type_document, titre='Résultats', fichier=_fichier_test(),
        )
        self.assertTrue(Notification.objects.filter(utilisateur=self.user, type='NOUVEAU_DOCUMENT').exists())

    def test_pas_de_notification_a_un_compte_etranger_au_foyer(self):
        """L'email d'une fiche propriétaire est une saisie libre : celui
        d'un compte sans lien ne doit rien recevoir."""
        tiers = User.objects.create_user(username='u_docs_tiers', password='p', email='bob@example.com')
        animal = _animal_test(self.user, 'TEST_DOCS_BOB', 'bob@example.com')
        Document.objects.create(
            animal=animal, type_document=self.type_document, titre='Résultats biopsie', fichier=_fichier_test(),
        )
        Facture.objects.create(
            animal=animal, type_depense='VETERINAIRE', titre='Biopsie', montant=Decimal('80.00'),
            date=date(2026, 8, 1), fichier=_fichier_test(),
        )
        self.assertFalse(Notification.objects.filter(utilisateur=tiers).exists())

    def test_notification_a_un_membre_du_foyer(self):
        membre = User.objects.create_user(username='u_docs_membre', password='p', email='membre@example.com')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.user, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=membre, foyer=foyer, invite_par=self.user)
        animal = _animal_test(self.user, 'TEST_DOCS_MEMBRE', 'membre@example.com')
        Document.objects.create(
            animal=animal, type_document=self.type_document, titre='Résultats', fichier=_fichier_test(),
        )
        Facture.objects.create(
            animal=animal, type_depense='VETERINAIRE', titre='Soin', montant=Decimal('80.00'),
            date=date(2026, 8, 1), fichier=_fichier_test(),
        )
        self.assertEqual(
            sorted(Notification.objects.filter(utilisateur=membre).values_list('type', flat=True)),
            ['FACTURE_A_PAYER', 'NOUVEAU_DOCUMENT'],
        )

    def test_recherche_par_date_d_ajout(self):
        document = Document.objects.create(
            animal=self.animal, type_document=self.type_document, titre='Daté', fichier=_fichier_test(),
        )
        Document.objects.filter(pk=document.pk).update(date_ajout=date(2026, 3, 15))
        for recherche, attendu in (('03/2026', 1), ('15/03/2026', 1), ('2026', 1), ('04/2026', 0)):
            with self.subTest(recherche=recherche):
                response = self.client.get(reverse('documents:document_list'), {'q': recherche})
                self.assertEqual(len(response.context['documents']), attendu)


class SuppressionAnimalEmporteSesFacturesTest(MediaTemporaireMixin, TestCase):
    """Décision produit « supprimer avec l'animal » : supprimer un animal
    supprime ses lignes de facture ventilées (montant recalculé, facture
    supprimée si elle n'a plus de ligne) et ses factures non ventilées — quel
    que soit le chemin de suppression. Les coûts partagés ne bougent pas."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_suppr_animal', password='p')
        self.client.login(username='u_suppr_animal', password='p')
        self.animal = _animal_test(self.user, 'TEST_SUPPR_A', 'suppr@example.com')
        self.autre = _animal_test(self.user, 'TEST_SUPPR_B', 'suppr2@example.com')
        self.designation = Designation.objects.create(nom='TEST_Suppr', utilisateur=self.user)

        self.simple = self._facture('Simple animal', animal=self.animal, montant='40.00')
        self.simple_autre = self._facture('Simple autre', animal=self.autre, montant='7.00')
        self.sans_animal = self._facture('Sans animal', montant='30.00')
        # Ventilée, partagée entre l'animal, l'autre et tous.
        self.mixte = self._facture('Mixte', animal=self.animal)
        self._ligne(self.mixte, '10.00', animal=self.animal)
        self.ligne_autre = self._ligne(self.mixte, '20.00', animal=self.autre)
        self.ligne_tous = self._ligne(self.mixte, '5.00', pour_tous_les_animaux=True)
        # Ventilée, entièrement sur l'animal.
        self.entiere = self._facture('Entière')
        self._ligne(self.entiere, '12.00', animal=self.animal)
        self._ligne(self.entiere, '3.00', animal=self.animal)

    def _facture(self, titre, animal=None, montant='1.00'):
        return Facture.objects.create(
            animal=animal, type_depense='VETERINAIRE', titre=titre, montant=Decimal(montant),
            date=date(2026, 8, 1), fichier=_fichier_test(), utilisateur=self.user,
        )

    def _ligne(self, facture, prix, **champs):
        return LigneFacture.objects.create(
            facture=facture, designation=self.designation, quantite=Decimal('1'),
            prix_unitaire=Decimal(prix), **champs,
        )

    def _verifier_apres_suppression(self):
        self.assertFalse(Animal.objects.filter(nom='TEST_SUPPR_A').exists())
        # Facture non ventilée de l'animal et facture ventilée vidée : supprimées.
        self.assertFalse(Facture.objects.filter(pk__in=[self.simple.pk, self.entiere.pk]).exists())
        # Facture ventilée gardant d'autres lignes : conservée, montant recalculé.
        self.mixte.refresh_from_db()
        self.assertEqual(self.mixte.montant, Decimal('25.00'))
        self.assertIsNone(self.mixte.animal)
        self.assertEqual(
            set(self.mixte.lignes.values_list('pk', flat=True)), {self.ligne_autre.pk, self.ligne_tous.pk},
        )
        # Plus aucune ligne orpheline (ni animal, ni « tous les animaux »).
        self.assertFalse(LigneFacture.objects.filter(animal__isnull=True, pour_tous_les_animaux=False).exists())
        # Ce qui ne concerne pas l'animal n'est pas touché.
        self.sans_animal.refresh_from_db()
        self.assertEqual(self.sans_animal.montant, Decimal('30.00'))
        self.simple_autre.refresh_from_db()
        self.assertEqual(self.simple_autre.animal, self.autre)
        # Coût de revient de l'animal restant : ses lignes (20) + sa facture
        # (7) + les coûts partagés (5 + 30), désormais à lui seul — et rien
        # des 40 € de la facture de l'animal supprimé.
        self.assertEqual(Facture.cout_revient_animal(self.autre, 2026), Decimal('62.00'))
        self.assertEqual(Facture.depenses_annuelles(self.user, 2026), Decimal('62.00'))

    def test_suppression_par_la_vue(self):
        fichiers_supprimes = [self.simple.fichier.name, self.entiere.fichier.name]
        fichiers_gardes = [self.mixte.fichier.name, self.sans_animal.fichier.name, self.simple_autre.fichier.name]
        stockage = self.simple.fichier.storage
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('animaux:animal_delete', args=[self.animal.pk]))
            self.assertEqual(response.status_code, 302)
            # Rien ne quitte le disque avant la validation de la transaction.
            self.assertTrue(stockage.exists(fichiers_supprimes[0]))
        self._verifier_apres_suppression()
        for nom in fichiers_supprimes:
            self.assertFalse(stockage.exists(nom), nom)
        for nom in fichiers_gardes:
            self.assertTrue(stockage.exists(nom), nom)

    def test_suppression_hors_vue_par_instance(self):
        self.animal.delete()
        self._verifier_apres_suppression()

    def test_suppression_hors_vue_par_queryset(self):
        """Chemin de l'action « supprimer la sélection » de l'admin."""
        Animal.objects.filter(pk=self.animal.pk).delete()
        self._verifier_apres_suppression()

    def test_page_de_confirmation_annonce_les_nombres_reels(self):
        response = self.client.get(reverse('animaux:animal_delete', args=[self.animal.pk]))
        self.assertEqual(response.context['suppressions']['lignes_facture'], 3)
        # « Simple animal » + « Entière » ; « Mixte » est conservée.
        self.assertEqual(response.context['suppressions']['factures'], 2)
        self.assertContains(response, '<strong>2 factures</strong>', html=True)
        self.assertContains(response, '3 lignes')
        self.assertContains(response, 'Tous les animaux')


class DesignationParCompteTest(MediaTemporaireMixin, TestCase):
    """Une désignation appartient au compte qui l'a créée : seuls ce compte
    et son foyer la voient et la choisissent ; un autre compte peut créer la
    sienne sous le même nom."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex_des', password='p')
        self.sam = User.objects.create_user(username='sam_des', password='p')
        self.tiers = User.objects.create_user(username='tiers_des', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)
        self.designation = Designation.objects.create(nom='TEST_DesAlex', utilisateur=self.alex)
        self.url = reverse('factures:facture_ventilation')

    def _lignes(self, **extra):
        data = {
            'ventiler': '1', 'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-designation': self.designation.pk, 'lignes-0-quantite': '2',
            'lignes-0-prix_unitaire': '12.50', 'lignes-0-cible': 'TOUS',
        }
        data.update(extra)
        return data

    def _facture(self, **extra):
        return self._lignes(
            numero='', animal='', type_depense='ALIMENTAIRE', titre='TEST_DesFacture', montant='0.00',
            date='2026-08-01', description='', fichier=_fichier_test(), **extra,
        )

    def test_un_autre_compte_ne_voit_pas_la_designation(self):
        self.client.login(username='tiers_des', password='p')
        # Zone de ventilation redessinée (htmx) puis formulaire complet.
        response = self.client.post(self.url, self._lignes(action='ajouter'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'TEST_DesAlex')
        response = self.client.post(self.url, {'ventiler': '0', 'action': 'ventiler'})
        self.assertNotContains(response, 'TEST_DesAlex')

    def test_selection_forgee_refusee(self):
        self.client.login(username='tiers_des', password='p')
        response = self.client.post(reverse('factures:facture_create'), self._facture())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Facture.objects.filter(titre='TEST_DesFacture').exists())
        self.assertFalse(LigneFacture.objects.filter(designation=self.designation).exists())
        self.assertNotContains(response, 'TEST_DesAlex')

    def test_un_membre_du_foyer_partage_la_designation(self):
        self.client.login(username='sam_des', password='p')
        self.assertContains(self.client.post(self.url, self._lignes(action='ajouter')), 'TEST_DesAlex')
        response = self.client.post(reverse('factures:facture_create'), self._facture())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LigneFacture.objects.get(facture__titre='TEST_DesFacture').designation, self.designation)

    def test_creation_rattachee_au_createur_et_meme_nom_possible(self):
        self.client.login(username='tiers_des', password='p')
        data = self._lignes(action='designation', ligne='0', **{'lignes-0-designation': ''})
        data['nouvelle_designation-0'] = 'TEST_DesAlex'
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['lignes'][0]['erreurs_designation'])
        la_sienne = Designation.objects.get(nom='TEST_DesAlex', utilisateur=self.tiers)
        self.assertContains(response, '<option value="%d" selected>' % la_sienne.pk)
        self.assertEqual(Designation.objects.filter(nom='TEST_DesAlex').count(), 2)

    def test_doublon_refuse_dans_le_foyer(self):
        """Message clair, jamais d'IntegrityError : la désignation d'un membre
        du foyer est déjà proposée dans la liste."""
        for username in ('sam_des', 'alex_des'):
            with self.subTest(compte=username):
                self.client.login(username=username, password='p')
                data = self._lignes(action='designation', ligne='0', **{'lignes-0-designation': ''})
                data['nouvelle_designation-0'] = 'TEST_DesAlex'
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Cette désignation existe déjà dans ton catalogue')
                self.assertEqual(Designation.objects.filter(nom='TEST_DesAlex').count(), 1)

    def test_unicite_par_compte_en_base(self):
        from django.db import IntegrityError
        Designation.objects.create(nom='TEST_DesAlex', utilisateur=self.tiers)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Designation.objects.create(nom='TEST_DesAlex', utilisateur=self.alex)

    def test_designation_deja_referencee_conservee_a_la_modification(self):
        """Ligne enregistrée dont la désignation est sortie du filtre (ancien
        membre du foyer, par exemple) : elle reste affichée et n'est pas
        vidée quand on réattribue la ligne."""
        facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre='TEST_DesAncienne', montant=Decimal('0.01'),
            date=date(2026, 7, 1), fichier=_fichier_test(), utilisateur=self.tiers,
        )
        ligne = LigneFacture.objects.create(
            facture=facture, designation=self.designation, quantite=Decimal('1'),
            prix_unitaire=Decimal('9.00'), pour_tous_les_animaux=True,
        )
        animal = _animal_test(self.tiers, 'TEST_DES_TIERS', 'tiers.des@example.com')
        self.client.login(username='tiers_des', password='p')
        url = reverse('factures:facture_update', args=[facture.pk])
        self.assertContains(self.client.get(url), '<option value="%d" selected>' % self.designation.pk)
        response = self.client.post(url, {
            'ventiler': '1', 'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '1',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-id': ligne.pk, 'lignes-0-facture': facture.pk, 'lignes-0-cible': str(animal.pk),
        })
        self.assertEqual(response.status_code, 302)
        ligne.refresh_from_db()
        self.assertEqual(ligne.animal, animal)
        self.assertEqual(ligne.designation, self.designation)


class TypeDocumentParCompteTest(MediaTemporaireMixin, TestCase):
    """Un type de document ajouté par un compte lui est rattaché (visible de
    son seul foyer) ; les types de référence restent proposés à tous."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex_td', password='p')
        self.sam = User.objects.create_user(username='sam_td', password='p')
        self.tiers = User.objects.create_user(username='tiers_td', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)
        self.animaux = {
            'sam_td': _animal_test(self.sam, 'TEST_TD_SAM', 'sam.td@example.com'),
            'tiers_td': _animal_test(self.tiers, 'TEST_TD_TIERS', 'tiers.td@example.com'),
        }
        self.type_alex = TypeDocument.objects.create(nom='TEST_TypeAlex', utilisateur=self.alex)
        self.url = reverse('documents:document_create')

    def _poster(self, username, **extra):
        self.client.login(username=username, password='p')
        data = {
            'animal': self.animaux[username].pk, 'type_document': '', 'nouveau_type_document': '',
            'titre': 'TEST_TD_Doc', 'description': '', 'fichier': _fichier_test(),
        }
        data.update(extra)
        return self.client.post(self.url, data)

    def test_un_autre_compte_ne_voit_pas_le_type(self):
        self.client.login(username='tiers_td', password='p')
        response = self.client.get(self.url)
        self.assertNotContains(response, 'TEST_TypeAlex')
        # Les types de référence (livrés par les migrations) restent proposés.
        self.assertContains(response, 'Analyse de sang')
        self.assertTrue(TypeDocument.objects.get(nom='Analyse de sang').est_reference)

    def test_selection_forgee_refusee(self):
        response = self._poster('tiers_td', type_document=self.type_alex.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('type_document', response.context['form'].errors)
        self.assertFalse(Document.objects.filter(titre='TEST_TD_Doc').exists())

    def test_un_membre_du_foyer_partage_le_type(self):
        self.client.login(username='sam_td', password='p')
        self.assertContains(self.client.get(self.url), 'TEST_TypeAlex')
        self.assertEqual(self._poster('sam_td', type_document=self.type_alex.pk).status_code, 302)
        # Même nom saisi comme « nouveau type » : celui du foyer est repris.
        response = self._poster('sam_td', nouveau_type_document='test_typealex', titre='TEST_TD_Doc2')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.get(titre='TEST_TD_Doc2').type_document, self.type_alex)
        self.assertEqual(TypeDocument.objects.filter(nom__iexact='TEST_TypeAlex').count(), 1)

    def test_nouveau_type_rattache_au_createur_et_meme_nom_possible(self):
        response = self._poster('tiers_td', nouveau_type_document='TEST_TypeAlex')
        self.assertEqual(response.status_code, 302)
        le_sien = Document.objects.get(titre='TEST_TD_Doc').type_document
        self.assertNotEqual(le_sien, self.type_alex)
        self.assertEqual(le_sien.utilisateur, self.tiers)
        self.assertEqual(TypeDocument.objects.filter(nom='TEST_TypeAlex').count(), 2)

    def test_nouveau_type_du_nom_d_une_reference_reprend_la_reference(self):
        response = self._poster('tiers_td', nouveau_type_document='analyse de sang')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Document.objects.get(titre='TEST_TD_Doc').type_document.est_reference)
        self.assertEqual(TypeDocument.objects.filter(nom__iexact='analyse de sang').count(), 1)

    def test_type_deja_reference_conserve_a_la_modification(self):
        document = Document.objects.create(
            animal=self.animaux['tiers_td'], type_document=self.type_alex, titre='TEST_TD_Ancien',
            fichier=_fichier_test(),
        )
        self.client.login(username='tiers_td', password='p')
        url = reverse('documents:document_update', args=[document.pk])
        self.assertContains(self.client.get(url), '<option value="%d" selected>' % self.type_alex.pk)
        response = self.client.post(url, {
            'animal': self.animaux['tiers_td'].pk, 'type_document': self.type_alex.pk,
            'nouveau_type_document': '', 'titre': 'TEST_TD_Relu', 'description': '',
        })
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.titre, 'TEST_TD_Relu')
        self.assertEqual(document.type_document, self.type_alex)


class SuppressionCompteCataloguesTest(MediaTemporaireMixin, TestCase):
    """Supprimer un compte ne retire pas du catalogue les entrées qu'il a
    créées et qu'un autre compte utilise encore : elles sont réattribuées à
    ce compte-là (cf. accueil/catalogues.py), au lieu de laisser un suivi
    sans vaccin, une ligne sans désignation ou un document sans type."""

    def setUp(self):
        # Alex : compte supprimé, sans animal ni fiche propriétaire (sauf
        # dans les tests qui lui en créent).
        self.alex = User.objects.create_user(username='alex_sup', password='p')
        self.sam = User.objects.create_user(username='sam_sup', password='p')
        self.lou = User.objects.create_user(username='lou_sup', password='p')
        foyer = Foyer.objects.create()
        for compte in (self.alex, self.sam, self.lou):
            MembreFoyer.objects.create(utilisateur=compte, foyer=foyer)
        self.animal_sam = _animal_test(self.sam, 'TEST_SUP_SAM', 'sam.sup@example.com')
        self.animal_lou = _animal_test(self.lou, 'TEST_SUP_LOU', 'lou.sup@example.com')

    def _facture(self, utilisateur, titre='TEST_SUP_Facture'):
        return Facture.objects.create(
            type_depense='ALIMENTAIRE', titre=titre, montant=Decimal('0.01'), date=date(2026, 7, 1),
            fichier=_fichier_test(), utilisateur=utilisateur,
        )

    def _ligne(self, facture, designation):
        return LigneFacture.objects.create(
            facture=facture, designation=designation, quantite=Decimal('1'), prix_unitaire=Decimal('9.00'),
            pour_tous_les_animaux=True,
        )

    def test_vaccin_et_traitement_utilises_par_un_autre_compte(self):
        from vaccins.models import SuiviVaccinTraitement, Traitement, Vaccin
        vaccin = Vaccin.objects.create(nom='TEST_SUP_vaccin', utilisateur=self.alex)
        traitement = Traitement.objects.create(nom='TEST_SUP_traitement', utilisateur=self.alex)
        inutilise = Vaccin.objects.create(nom='TEST_SUP_inutilise', utilisateur=self.alex)
        reference = Vaccin.objects.create(nom='TEST_SUP_reference')
        suivi_vaccin = SuiviVaccinTraitement.objects.create(
            animal=self.animal_sam, vaccin=vaccin, date=date(2026, 8, 1),
        )
        suivi_traitement = SuiviVaccinTraitement.objects.create(
            animal=self.animal_sam, traitement=traitement, date=date(2026, 8, 2),
        )

        self.alex.delete()

        suivi_vaccin.refresh_from_db()
        suivi_traitement.refresh_from_db()
        self.assertEqual(suivi_vaccin.vaccin, vaccin)
        self.assertEqual(suivi_traitement.traitement, traitement)
        # Réattribuée au compte qui l'utilise — jamais « sans compte », ce
        # qui en ferait une entrée de référence visible de tous.
        self.assertEqual(Vaccin.objects.get(pk=vaccin.pk).utilisateur, self.sam)
        self.assertEqual(Traitement.objects.get(pk=traitement.pk).utilisateur, self.sam)
        # Entrée que personne d'autre n'utilise : supprimée avec le compte.
        self.assertFalse(Vaccin.objects.filter(pk=inutilise.pk).exists())
        self.assertTrue(Vaccin.objects.get(pk=reference.pk).est_reference)

    def test_type_de_document_utilise_par_un_autre_compte(self):
        type_document = TypeDocument.objects.create(nom='TEST_SUP_type', utilisateur=self.alex)
        document = Document.objects.create(
            animal=self.animal_sam, type_document=type_document, titre='TEST_SUP_doc', fichier=_fichier_test(),
        )
        self.alex.delete()
        document.refresh_from_db()
        self.assertEqual(document.type_document, type_document)
        self.assertEqual(TypeDocument.objects.get(pk=type_document.pk).utilisateur, self.sam)

    def test_designation_utilisee_par_un_autre_compte(self):
        designation = Designation.objects.create(nom='TEST_SUP_des', utilisateur=self.alex)
        propre = Designation.objects.create(nom='TEST_SUP_propre', utilisateur=self.alex)
        ligne = self._ligne(self._facture(self.sam), designation)
        # Désignation utilisée par les seules factures du compte supprimé :
        # elle part avec lui, comme ses factures.
        facture_alex = self._facture(self.alex, 'TEST_SUP_FactureAlex')
        self._ligne(facture_alex, propre)

        self.alex.delete()

        ligne.refresh_from_db()
        self.assertEqual(ligne.designation, designation)
        self.assertEqual(Designation.objects.get(pk=designation.pk).utilisateur, self.sam)
        self.assertFalse(Designation.objects.filter(pk=propre.pk).exists())
        self.assertFalse(Facture.objects.filter(pk=facture_alex.pk).exists())

    def test_designation_homonyme_chez_le_repreneur(self):
        """Le repreneur a déjà une désignation du même nom (l'unicité par
        compte interdit la réattribution) : ses lignes sont repointées vers
        la sienne."""
        designation = Designation.objects.create(nom='TEST_SUP_des', utilisateur=self.alex)
        la_sienne = Designation.objects.create(nom='TEST_SUP_des', utilisateur=self.sam)
        ligne = self._ligne(self._facture(self.sam), designation)
        ligne_lou = self._ligne(self._facture(self.lou, 'TEST_SUP_FactureLou'), designation)
        self._ligne(self._facture(self.sam, 'TEST_SUP_Facture2'), designation)

        self.alex.delete()

        ligne.refresh_from_db()
        ligne_lou.refresh_from_db()
        self.assertEqual(ligne.designation, la_sienne)
        self.assertEqual(ligne_lou.designation, la_sienne)
        self.assertFalse(Designation.objects.filter(pk=designation.pk).exists())
        self.assertFalse(LigneFacture.objects.filter(designation__isnull=True).exists())

    def test_repreneur_le_plus_gros_utilisateur_puis_le_plus_ancien(self):
        from vaccins.models import SuiviVaccinTraitement, Vaccin
        # Lou est le compte le plus ancien des deux.
        User.objects.filter(pk=self.lou.pk).update(date_joined=self.sam.date_joined.replace(year=2020))
        majoritaire = Vaccin.objects.create(nom='TEST_SUP_majoritaire', utilisateur=self.alex)
        egalite = Vaccin.objects.create(nom='TEST_SUP_egalite', utilisateur=self.alex)
        for animal, vaccin in (
            (self.animal_sam, majoritaire), (self.animal_sam, majoritaire), (self.animal_lou, majoritaire),
            (self.animal_sam, egalite), (self.animal_lou, egalite),
        ):
            SuiviVaccinTraitement.objects.create(animal=animal, vaccin=vaccin, date=date(2026, 8, 1))

        # Même règle par QuerySet.delete() (action « supprimer » de l'administration).
        User.objects.filter(pk=self.alex.pk).delete()

        self.assertEqual(Vaccin.objects.get(pk=majoritaire.pk).utilisateur, self.sam)
        self.assertEqual(Vaccin.objects.get(pk=egalite.pk).utilisateur, self.lou)
        self.assertEqual(SuiviVaccinTraitement.objects.filter(vaccin__isnull=True).count(), 0)

    def test_veterinaire_utilise_par_un_autre_compte(self):
        """Consultation.veterinaire est en RESTRICT : sans réattribution, la
        suppression du compte serait refusée (RestrictedError)."""
        from datetime import timedelta
        from django.utils import timezone
        from consultations.models import Consultation, Veterinaire
        veterinaire = Veterinaire.objects.create(nom='TEST_SUP_veto', utilisateur=self.alex)
        inutilise = Veterinaire.objects.create(nom='TEST_SUP_veto_inutilise', utilisateur=self.alex)
        consultation = Consultation.objects.create(
            animal=self.animal_sam, date=timezone.now() - timedelta(days=400), motif="TEST_SUP",
            veterinaire=veterinaire,
        )

        self.alex.delete()

        consultation.refresh_from_db()
        self.assertEqual(consultation.veterinaire, veterinaire)
        self.assertEqual(Veterinaire.objects.get(pk=veterinaire.pk).utilisateur, self.sam)
        self.assertFalse(Veterinaire.objects.filter(pk=inutilise.pk).exists())

    def test_deux_comptes_supprimes_ensemble_avec_des_designations_homonymes(self):
        """Deux comptes supprimés d'un coup (action de l'administration),
        chacun avec une désignation du même nom que le même compte reprend :
        il n'en reçoit qu'une (unicité par compte), ses lignes y sont toutes
        repointées."""
        celle_d_alex = Designation.objects.create(nom='TEST_SUP_des', utilisateur=self.alex)
        celle_de_lou = Designation.objects.create(nom='TEST_SUP_des', utilisateur=self.lou)
        autre = Designation.objects.create(nom='TEST_SUP_autre', utilisateur=self.lou)
        self.animal_lou.delete()
        ligne_alex = self._ligne(self._facture(self.sam), celle_d_alex)
        ligne_lou = self._ligne(self._facture(self.sam, 'TEST_SUP_Facture2'), celle_de_lou)
        ligne_autre = self._ligne(self._facture(self.sam, 'TEST_SUP_Facture3'), autre)

        User.objects.filter(pk__in=[self.alex.pk, self.lou.pk]).delete()

        for ligne in (ligne_alex, ligne_lou, ligne_autre):
            ligne.refresh_from_db()
        # La plus ancienne des deux est conservée.
        self.assertEqual(ligne_alex.designation, celle_d_alex)
        self.assertEqual(ligne_lou.designation, celle_d_alex)
        self.assertEqual(ligne_autre.designation, autre)
        self.assertEqual(
            list(Designation.objects.filter(nom='TEST_SUP_des').values_list('pk', 'utilisateur')),
            [(celle_d_alex.pk, self.sam.pk)],
        )
        self.assertEqual(Designation.objects.get(pk=autre.pk).utilisateur, self.sam)
        self.assertFalse(LigneFacture.objects.filter(designation__isnull=True).exists())

    def test_trois_comptes_supprimes_ensemble_homonyme_deja_chez_le_repreneur(self):
        """Même cas quand le repreneur a déjà la sienne : c'est elle qui reste."""
        tom = User.objects.create_user(username='tom_sup', password='p')
        la_sienne = Designation.objects.create(nom='TEST_SUP_des', utilisateur=self.sam)
        lignes = [
            self._ligne(
                self._facture(self.sam, 'TEST_SUP_Facture_%s' % compte.username),
                Designation.objects.create(nom='TEST_SUP_des', utilisateur=compte),
            )
            for compte in (self.alex, tom)
        ]

        User.objects.filter(pk__in=[self.alex.pk, tom.pk]).delete()

        for ligne in lignes:
            ligne.refresh_from_db()
            self.assertEqual(ligne.designation, la_sienne)
        self.assertEqual(Designation.objects.filter(nom='TEST_SUP_des').count(), 1)

    def _consultation(self, animal, veterinaire):
        from datetime import timedelta
        from django.utils import timezone
        from consultations.models import Consultation
        return Consultation.objects.create(
            animal=animal, date=timezone.now() - timedelta(days=400), motif="TEST_SUP", veterinaire=veterinaire,
        )

    def test_compte_avec_ses_propres_animaux_et_consultations(self):
        """Un compte se supprime avec tout ce qu'il possède : ses animaux,
        leur fiche propriétaire, ses vétérinaires et les consultations qui
        les relient (clés en RESTRICT, et non PROTECT qui refusait tout)."""
        from animaux.models import Animal, Proprietaire
        from consultations.models import Consultation, Veterinaire
        animal_alex = _animal_test(self.alex, 'TEST_SUP_ALEX', 'alex.sup@example.com')
        veterinaire = Veterinaire.objects.create(nom='TEST_SUP_veto', utilisateur=self.alex)
        partage = Veterinaire.objects.create(nom='TEST_SUP_veto_partage', utilisateur=self.alex)
        self._consultation(animal_alex, veterinaire)
        self._consultation(animal_alex, partage)
        consultation_sam = self._consultation(self.animal_sam, partage)

        self.alex.delete()

        self.assertFalse(Animal.objects.filter(pk=animal_alex.pk).exists())
        self.assertFalse(Proprietaire.objects.filter(utilisateur_id=self.alex.pk).exists())
        self.assertFalse(Veterinaire.objects.filter(pk=veterinaire.pk).exists())
        # Le vétérinaire qui sert aussi à un autre compte lui revient.
        self.assertEqual(Veterinaire.objects.get(pk=partage.pk).utilisateur, self.sam)
        self.assertEqual(list(Consultation.objects.filter(motif="TEST_SUP")), [consultation_sam])

    def test_veterinaire_et_proprietaire_utilises_restent_proteges(self):
        """RESTRICT protège toujours la suppression directe : un vétérinaire
        qui a des consultations, une fiche propriétaire qui a des animaux."""
        from django.db.models import RestrictedError
        from consultations.models import Veterinaire
        veterinaire = Veterinaire.objects.create(nom='TEST_SUP_veto', utilisateur=self.sam)
        self._consultation(self.animal_sam, veterinaire)
        with self.assertRaises(RestrictedError):
            veterinaire.delete()
        with self.assertRaises(RestrictedError):
            self.animal_sam.proprietaire.delete()
        self.assertTrue(Veterinaire.objects.filter(pk=veterinaire.pk).exists())

    def test_page_de_confirmation_de_l_administration_sans_ecriture(self):
        """La page de confirmation de l'administration ne fait que simuler la
        suppression : rien n'est réattribué tant qu'elle n'est pas confirmée."""
        from vaccins.models import SuiviVaccinTraitement, Vaccin
        vaccin = Vaccin.objects.create(nom='TEST_SUP_vaccin', utilisateur=self.alex)
        SuiviVaccinTraitement.objects.create(animal=self.animal_sam, vaccin=vaccin, date=date(2026, 8, 1))
        User.objects.create_superuser(username='admin_sup', password='p')
        self.client.login(username='admin_sup', password='p')
        url = reverse('admin:auth_user_delete', args=[self.alex.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Vaccin.objects.get(pk=vaccin.pk).utilisateur, self.alex)
        self.assertEqual(self.client.post(url, {'post': 'yes'}).status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.alex.pk).exists())
        self.assertEqual(Vaccin.objects.get(pk=vaccin.pk).utilisateur, self.sam)


class DesignationsHomonymesDansUnFoyerTest(MediaTemporaireMixin, TestCase):
    """Deux comptes ont chacun créé « Croquettes » (permis : unicité par
    compte) puis partagent un foyer : le menu ne propose qu'une option par
    nom, et le « prix précédent » couvre les lignes des deux désignations."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex_hom', password='p')
        self.sam = User.objects.create_user(username='sam_hom', password='p')
        self.lou = User.objects.create_user(username='lou_hom', password='p')
        self.tiers = User.objects.create_user(username='tiers_hom', password='p')
        # Créées avant le foyer ; la casse diffère d'un compte à l'autre.
        self.des_alex = Designation.objects.create(nom='TEST_Croquettes', utilisateur=self.alex)
        self.des_sam = Designation.objects.create(nom='test_croquettes', utilisateur=self.sam)
        self.des_tiers = Designation.objects.create(nom='TEST_Croquettes', utilisateur=self.tiers)
        self.autre = Designation.objects.create(nom='TEST_Litiere', utilisateur=self.alex)
        foyer = Foyer.objects.create()
        for compte in (self.alex, self.sam, self.lou):
            MembreFoyer.objects.create(utilisateur=compte, foyer=foyer)
        self.ligne_alex = self._ligne(self.alex, self.des_alex, '10.00', date(2026, 7, 1))
        self.ligne_sam = self._ligne(self.sam, self.des_sam, '12.00', date(2026, 8, 1))
        self._ligne(self.tiers, self.des_tiers, '99.00', date(2026, 9, 1))
        self.url = reverse('factures:facture_ventilation')

    def _ligne(self, utilisateur, designation, prix, jour):
        facture = Facture.objects.create(
            type_depense='ALIMENTAIRE', titre=f'TEST_HOM_{utilisateur.username}', montant=Decimal('0.01'),
            date=jour, fichier=_fichier_test(), utilisateur=utilisateur,
        )
        return LigneFacture.objects.create(
            facture=facture, designation=designation, quantite=Decimal('1'), prix_unitaire=Decimal(prix),
            pour_tous_les_animaux=True,
        )

    def _lignes(self, designation, **extra):
        data = {
            'ventiler': '1', 'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-designation': designation and designation.pk, 'lignes-0-quantite': '1',
            'lignes-0-prix_unitaire': '11.00', 'lignes-0-cible': 'TOUS',
        }
        data.update(extra)
        return data

    def _options(self, form):
        """Clés des désignations proposées par le menu de la ligne `form`."""
        return [valeur for valeur, _libelle in form.fields['designation'].choices if valeur != '']

    def test_prix_precedent_sur_toutes_les_lignes_du_meme_nom(self):
        # La ligne la plus récente du foyer (Sam, 12 €), quelle que soit la
        # désignation interrogée — sans distinction de casse.
        for designation in (self.des_alex, self.des_sam):
            for compte in (self.alex, self.sam, self.lou):
                with self.subTest(designation=designation.pk, compte=compte.username):
                    self.assertEqual(designation.dernier_prix_unitaire(compte), Decimal('12.00'))
        # Toujours cloisonné : ni le prix du compte tiers pour le foyer, ni
        # ceux du foyer pour le compte tiers.
        self.assertEqual(self.des_tiers.dernier_prix_unitaire(self.tiers), Decimal('99.00'))
        self.assertEqual(self.des_alex.dernier_prix_unitaire(self.tiers), Decimal('99.00'))
        self.assertIsNone(self.autre.dernier_prix_unitaire(self.alex))
        self.assertIsNone(self.autre.dernier_prix_unitaire(self.tiers))

    def test_prix_precedent_insensible_aux_espaces_de_bord(self):
        Designation.objects.filter(pk=self.des_sam.pk).update(nom='  TEST_CROQUETTES ')
        self.assertEqual(self.des_alex.dernier_prix_unitaire(self.alex), Decimal('12.00'))

    def test_prix_precedent_identique_dans_la_zone_htmx(self):
        self.client.login(username='sam_hom', password='p')
        for designation in (self.des_sam, self.des_alex):
            with self.subTest(designation=designation.pk):
                response = self.client.post(self.url, self._lignes(designation))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['lignes'][0]['dernier_prix'], Decimal('12.00'))
                self.assertEqual(response.context['lignes'][0]['comparaison'], 'moins')
                self.assertContains(response, 'Prix précédent : 12,00 €')

    def test_une_seule_option_par_nom_celle_du_compte_connecte(self):
        from .forms import LigneFactureForm
        self.assertEqual(self._options(LigneFactureForm(user=self.alex)), [self.des_alex.pk, self.autre.pk])
        self.assertEqual(self._options(LigneFactureForm(user=self.sam)), [self.des_sam.pk, self.autre.pk])
        # Membre sans désignation de ce nom : la plus ancienne du foyer.
        self.assertEqual(self._options(LigneFactureForm(user=self.lou)), [self.des_alex.pk, self.autre.pk])
        self.assertEqual(self._options(LigneFactureForm(user=self.tiers)), [self.des_tiers.pk])
        # À l'écran : une seule option de ce nom dans la zone redessinée.
        self.client.login(username='sam_hom', password='p')
        response = self.client.post(self.url, self._lignes('', action='ventiler'))
        self.assertContains(response, '<option value="%d">test_croquettes</option>' % self.des_sam.pk, html=True)
        self.assertNotContains(response, 'value="%d"' % self.des_alex.pk)
        self.assertNotContains(response, 'value="%d"' % self.des_tiers.pk)

    def test_la_designation_deja_portee_par_la_ligne_est_prioritaire(self):
        from .forms import LigneFactureForm
        # Ligne enregistrée de la facture d'Alex, ouverte par Sam : l'option
        # reste celle d'Alex (et non l'homonyme de Sam).
        form = LigneFactureForm(instance=self.ligne_alex, user=self.sam)
        self.assertEqual(self._options(form), [self.des_alex.pk, self.autre.pk])
        self.client.login(username='sam_hom', password='p')
        response = self.client.get(reverse('factures:facture_update', args=[self.ligne_alex.facture_id]))
        self.assertContains(response, '<option value="%d" selected>' % self.des_alex.pk)
        # Ligne en cours de saisie portant la clé de l'homonyme masqué (page
        # ouverte avant le regroupement) : il reste affiché et sélectionné.
        response = self.client.post(self.url, self._lignes(self.des_alex, action='ajouter'))
        ligne_form = response.context['lignes'][0]['form']
        self.assertEqual(self._options(ligne_form), [self.des_alex.pk, self.autre.pk])
        self.assertContains(response, '<option value="%d" selected>' % self.des_alex.pk)
        # La ligne ajoutée, elle, propose la désignation de Sam.
        self.assertEqual(self._options(response.context['lignes'][1]['form']), [self.des_sam.pk, self.autre.pk])

    def test_poster_la_cle_d_un_homonyme_masque_reste_valide(self):
        self.client.login(username='sam_hom', password='p')
        response = self.client.post(reverse('factures:facture_create'), self._lignes(
            self.des_alex, numero='', animal='', type_depense='ALIMENTAIRE', titre='TEST_HOM_Masque',
            montant='0.00', date='2026-09-15', description='', fichier=_fichier_test(),
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LigneFacture.objects.get(facture__titre='TEST_HOM_Masque').designation, self.des_alex)
        # Celle d'un compte hors foyer reste refusée.
        response = self.client.post(reverse('factures:facture_create'), self._lignes(
            self.des_tiers, numero='', animal='', type_depense='ALIMENTAIRE', titre='TEST_HOM_Refuse',
            montant='0.00', date='2026-09-15', description='', fichier=_fichier_test(),
        ))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Facture.objects.filter(titre='TEST_HOM_Refuse').exists())

    def test_modifier_une_ligne_existante_ne_change_pas_sa_designation(self):
        animal = _animal_test(self.sam, 'TEST_HOM_SAM', 'sam.hom@example.com')
        self.client.login(username='sam_hom', password='p')
        facture = self.ligne_alex.facture
        response = self.client.post(reverse('factures:facture_update', args=[facture.pk]), {
            'ventiler': '1', 'lignes-TOTAL_FORMS': '1', 'lignes-INITIAL_FORMS': '1',
            'lignes-MIN_NUM_FORMS': '0', 'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-id': self.ligne_alex.pk, 'lignes-0-facture': facture.pk, 'lignes-0-cible': str(animal.pk),
        })
        self.assertEqual(response.status_code, 302)
        self.ligne_alex.refresh_from_db()
        self.assertEqual(self.ligne_alex.designation, self.des_alex)
        self.assertEqual(self.ligne_alex.animal, animal)

    def test_creer_un_homonyme_reste_refuse_dans_le_foyer(self):
        """Créer « Croquettes » quand le foyer l'a déjà : refusé comme avant,
        y compris sous une autre casse ou avec des espaces (l'entrée créée
        serait aussitôt masquée par le regroupement)."""
        self.client.login(username='lou_hom', password='p')
        for nom in ('TEST_Croquettes', 'test_croquettes', 'Test_CROQUETTES', '  test_croquettes  '):
            with self.subTest(nom=nom):
                data = self._lignes('', action='designation', ligne='0')
                data['nouvelle_designation-0'] = nom
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Cette désignation existe déjà dans ton catalogue')
        self.assertFalse(Designation.objects.filter(utilisateur=self.lou).exists())
        # Un nom réellement nouveau se crée et se sélectionne toujours.
        data = self._lignes('', action='designation', ligne='0')
        data['nouvelle_designation-0'] = 'TEST_Croquettes chaton'
        response = self.client.post(self.url, data)
        nouvelle = Designation.objects.get(nom='TEST_Croquettes chaton', utilisateur=self.lou)
        self.assertContains(response, '<option value="%d" selected>' % nouvelle.pk)
