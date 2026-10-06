from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from accueil.models import Foyer, MembreFoyer
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
        self.designation = Designation.objects.create(nom='TEST_Croquettes')
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
