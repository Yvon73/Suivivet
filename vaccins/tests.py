from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accueil.models import Foyer, MembreFoyer
from animaux.models import Animal, Espece, Robe, Race, Proprietaire
from .models import SuiviVaccinTraitement, Traitement, Vaccin


class FormulaireSuiviHtmxTest(TestCase):
    """Formulaire de suivi vaccin/traitement : plus de JavaScript propre, les
    blocs et les ajouts rapides au catalogue sont pilotés par htmx."""

    def setUp(self):
        self.user = User.objects.create_user(username='u_test', password='p')
        self.client.login(username='u_test', password='p')
        chien = Espece.objects.get(code='CHIEN')
        proprietaire = Proprietaire.objects.create(
            nom='TEST_TEMP', email='test_temp_vaccins@example.com', utilisateur=self.user,
        )
        self.animal = Animal.objects.create(
            nom='TEST_TEMP', race=Race.objects.filter(espece=chien).first(), espece=chien,
            date_naissance=date(2020, 1, 1), robe=Robe.objects.get(code='AUTRE'),
            proprietaire=proprietaire, utilisateur=self.user,
        )
        self.vaccin = Vaccin.objects.create(nom='TEST_TEMP_vaccin')
        self.comprime = Traitement.objects.create(nom='TEST_TEMP_comprime', classe=Traitement.Classe.COMPRIME)
        self.collier = Traitement.objects.create(nom='TEST_TEMP_collier', classe=Traitement.Classe.COLLIER)

    def _champ(self, response, nom):
        """Portion de la réponse correspondant au menu `nom`."""
        contenu = response.content.decode()
        debut = contenu.index('id="champ-%s"' % nom)
        return contenu[debut:contenu.index('</select>', debut)]

    def test_formulaire_sans_script_propre(self):
        response = self.client.get(reverse('vaccins:suivi_create', args=[self.animal.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-post="%s"' % reverse('vaccins:suivi_choix'))
        self.assertNotContains(response, 'fetch(')
        self.assertNotContains(response, 'addEventListener')
        # Rien de choisi : aucune liste grisée, bloc « Dose » masqué.
        self.assertNotIn('disabled', self._champ(response, 'vaccins'))
        self.assertNotIn('disabled', self._champ(response, 'traitement'))
        self.assertContains(response, 'id="blocDose" class="col-sm-8 d-none"')

    def test_choix_vaccin_grise_le_traitement(self):
        response = self.client.post(
            reverse('vaccins:suivi_choix'), {'vaccins': [str(self.vaccin.pk)]}, headers={'HX-Trigger': 'zone-vaccins'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('disabled', self._champ(response, 'traitement'))
        # La liste dans laquelle on vient de choisir n'est pas redessinée.
        self.assertNotContains(response, 'id="champ-vaccins"')

    def test_choix_traitement_grise_les_vaccins_et_regle_la_dose(self):
        url = reverse('vaccins:suivi_choix')
        response = self.client.post(url, {'traitement': str(self.comprime.pk)}, headers={'HX-Trigger': 'zone-traitement'})
        self.assertIn('disabled', self._champ(response, 'vaccins'))
        self.assertContains(response, 'id="blocDose" class="col-sm-8" hx-swap-oob="true"')

        response = self.client.post(url, {'traitement': str(self.collier.pk)}, headers={'HX-Trigger': 'zone-traitement'})
        self.assertContains(response, 'id="blocDose" class="col-sm-8 d-none" hx-swap-oob="true"')

    def test_ajout_rapide_vaccin_conserve_la_selection(self):
        response = self.client.post(reverse('vaccins:vaccin_ajout_rapide'), {
            'vaccins': [str(self.vaccin.pk)],
            'nouveau_vaccin-nom': 'TEST_TEMP_nouveau',
        })
        self.assertEqual(response.status_code, 200)
        nouveau = Vaccin.objects.get(nom='TEST_TEMP_nouveau')
        champ = self._champ(response, 'vaccins')
        self.assertIn('<option value="%d" selected>' % nouveau.pk, champ)
        self.assertIn('<option value="%d" selected>' % self.vaccin.pk, champ)

    def test_ajout_rapide_vaccin_invalide(self):
        response = self.client.post(reverse('vaccins:vaccin_ajout_rapide'), {'nouveau_vaccin-nom': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'collapse show')
        self.assertContains(response, 'text-danger')
        self.assertNotContains(response, 'hx-swap-oob')

    def test_ajout_rapide_traitement(self):
        response = self.client.post(reverse('vaccins:traitement_ajout_rapide'), {
            'nouveau_traitement-nom': 'TEST_TEMP_sirop',
            'nouveau_traitement-classe': Traitement.Classe.SOLUTION_BUVABLE,
        })
        self.assertEqual(response.status_code, 200)
        nouveau = Traitement.objects.get(nom='TEST_TEMP_sirop')
        self.assertIn('<option value="%d" selected>' % nouveau.pk, self._champ(response, 'traitement'))
        self.assertIn('disabled', self._champ(response, 'vaccins'))
        self.assertContains(response, 'id="blocDose" class="col-sm-8" hx-swap-oob="true"')

    def test_enregistrement_du_suivi(self):
        """Le formulaire complet s'enregistre toujours par un POST classique."""
        response = self.client.post(reverse('vaccins:suivi_create', args=[self.animal.pk]), {
            'animal': self.animal.pk, 'date': '2026-08-01', 'vaccins': [str(self.vaccin.pk)],
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SuiviVaccinTraitement.objects.filter(animal=self.animal, vaccin=self.vaccin).exists())

    def test_modification_suivi_traitement(self):
        suivi = SuiviVaccinTraitement.objects.create(animal=self.animal, traitement=self.comprime, date=date(2026, 8, 1))
        response = self.client.get(reverse('vaccins:suivi_update', args=[suivi.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('disabled', self._champ(response, 'vaccins'))
        self.assertContains(response, 'id="blocDose" class="col-sm-8"')

    # --- Non-régressions de l'audit ---

    def test_ajout_rapide_vaccin_vide_le_traitement_selectionne(self):
        """Le dernier ajout l'emporte : jamais vaccin ET traitement à la fois."""
        response = self.client.post(reverse('vaccins:vaccin_ajout_rapide'), {
            'traitement': str(self.comprime.pk),
            'nouveau_vaccin-nom': 'TEST_TEMP_nouveau',
        })
        nouveau = Vaccin.objects.get(nom='TEST_TEMP_nouveau')
        self.assertIn('<option value="%d" selected>' % nouveau.pk, self._champ(response, 'vaccins'))
        traitement = self._champ(response, 'traitement')
        self.assertNotIn('<option value="%d" selected>' % self.comprime.pk, traitement)
        self.assertIn('disabled', traitement)
        self.assertContains(response, 'id="blocDose" class="col-sm-8 d-none" hx-swap-oob="true"')

    def test_ajout_rapide_traitement_vide_les_vaccins_selectionnes(self):
        response = self.client.post(reverse('vaccins:traitement_ajout_rapide'), {
            'vaccins': [str(self.vaccin.pk)],
            'nouveau_traitement-nom': 'TEST_TEMP_sirop',
            'nouveau_traitement-classe': Traitement.Classe.SOLUTION_BUVABLE,
        })
        vaccins = self._champ(response, 'vaccins')
        self.assertNotIn('<option value="%d" selected>' % self.vaccin.pk, vaccins)
        self.assertIn('disabled', vaccins)

    def test_rappel_anterieur_a_l_administration_refuse(self):
        url = reverse('vaccins:suivi_create', args=[self.animal.pk])
        donnees = {'animal': self.animal.pk, 'date': '2026-10-09', 'vaccins': [str(self.vaccin.pk)]}
        response = self.client.post(url, {**donnees, 'date_prochaine_dose': '2025-10-09'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ne peut pas être antérieure")
        self.assertFalse(SuiviVaccinTraitement.objects.filter(animal=self.animal).exists())
        response = self.client.post(url, {**donnees, 'date_prochaine_dose': '2027-10-09'})
        self.assertEqual(response.status_code, 302)

    def test_suivi_orphelin_dans_la_liste(self):
        """Vaccin retiré du catalogue (SET_NULL) : ni « Traitement », ni nom vide."""
        SuiviVaccinTraitement.objects.create(animal=self.animal, vaccin=self.vaccin, date=date(2026, 8, 1))
        self.vaccin.delete()
        response = self.client.get(reverse('vaccins:suivi_list'))
        self.assertContains(response, '(supprimé du catalogue)')
        ligne = response.content.decode().split('<tbody', 1)[1]
        self.assertNotIn('Traitement', ligne.split('(supprimé du catalogue)')[0])

    def test_textes_d_aide_references_par_aria_describedby(self):
        response = self.client.get(reverse('vaccins:suivi_create', args=[self.animal.pk]))
        for nom in ('vaccins', 'duree_traitement'):
            self.assertContains(response, 'aria-describedby="id_%s_helptext"' % nom)
            self.assertContains(response, 'id="id_%s_helptext"' % nom, count=1)

    def test_bloc_dose_visible_sans_javascript(self):
        response = self.client.get(reverse('vaccins:suivi_create', args=[self.animal.pk]))
        self.assertContains(response, '<noscript><style>#blocDose { display: block !important; }</style></noscript>')

    def test_catalogues_sans_renvoi_a_l_administrateur(self):
        for nom in ('vaccins:vaccin_list', 'vaccins:traitement_list'):
            response = self.client.get(reverse(nom))
            self.assertNotContains(response, "administrateur")
            # Le catalogue n'est plus commun à tous les comptes (entrées
            # rattachées à leur compte créateur) : le texte l'annonçant a disparu.
            self.assertNotContains(response, 'Catalogue commun à tous les comptes')
            self.assertContains(response, 'visibles que de ton compte et de ton foyer')


def _animal_de(utilisateur, nom):
    chien = Espece.objects.get(code='CHIEN')
    proprietaire = Proprietaire.objects.create(
        nom='TEST_TEMP', email=f'{nom.lower()}@example.com', utilisateur=utilisateur,
    )
    return Animal.objects.create(
        nom=nom, race=Race.objects.filter(espece=chien).first(), espece=chien,
        date_naissance=date(2020, 1, 1), robe=Robe.objects.get(code='AUTRE'),
        proprietaire=proprietaire, utilisateur=utilisateur,
    )


class CataloguesVaccinsTraitementsParCompteTest(TestCase):
    """Un vaccin ou un traitement ajouté par un compte lui est rattaché : il
    n'est visible et sélectionnable que de ce compte et de son foyer. Les
    entrées de référence (sans compte) restent proposées à tous."""

    def setUp(self):
        self.alex = User.objects.create_user(username='alex_cat', password='p')
        self.sam = User.objects.create_user(username='sam_cat', password='p')
        self.tiers = User.objects.create_user(username='tiers_cat', password='p')
        foyer = Foyer.objects.create()
        MembreFoyer.objects.create(utilisateur=self.alex, foyer=foyer, invite_par=None)
        MembreFoyer.objects.create(utilisateur=self.sam, foyer=foyer, invite_par=self.alex)
        self.animal_sam = _animal_de(self.sam, 'TEST_TEMP_CAT_SAM')
        self.animal_tiers = _animal_de(self.tiers, 'TEST_TEMP_CAT_TIERS')
        self.vaccin = Vaccin.objects.create(nom='TEST_TEMP_vaccin_alex', utilisateur=self.alex)
        self.traitement = Traitement.objects.create(
            nom='TEST_TEMP_traitement_alex', classe=Traitement.Classe.COMPRIME, utilisateur=self.alex,
        )
        self.reference = Vaccin.objects.create(nom='TEST_TEMP_vaccin_reference')
        self.traitement_reference = Traitement.objects.create(nom='TEST_TEMP_traitement_reference')

    def test_entree_de_reference(self):
        self.assertTrue(self.reference.est_reference)
        self.assertFalse(self.vaccin.est_reference)
        # Les vaccins livrés par les migrations du projet sont des références.
        self.assertTrue(Vaccin.objects.get(nom='Rage').est_reference)

    def test_un_autre_compte_ne_voit_pas_l_entree(self):
        self.client.login(username='tiers_cat', password='p')
        for url in (
            reverse('vaccins:vaccin_list'), reverse('vaccins:traitement_list'),
            reverse('vaccins:suivi_create', args=[self.animal_tiers.pk]), reverse('consultations:calendrier'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'TEST_TEMP_vaccin_alex')
                self.assertNotContains(response, 'TEST_TEMP_traitement_alex')
        # Fragment htmx des listes (redessinées à chaque changement de sélection).
        response = self.client.post(reverse('vaccins:suivi_choix'), {'vaccins': [str(self.vaccin.pk)]})
        self.assertNotContains(response, 'TEST_TEMP_vaccin_alex')
        self.assertNotContains(response, 'TEST_TEMP_traitement_alex')
        response = self.client.post(reverse('vaccins:suivi_choix'), {'traitement': str(self.traitement.pk)})
        self.assertNotContains(response, 'TEST_TEMP_vaccin_alex')
        self.assertNotContains(response, 'TEST_TEMP_traitement_alex')

    def test_les_references_sont_proposees_a_tous(self):
        self.client.login(username='tiers_cat', password='p')
        self.assertContains(self.client.get(reverse('vaccins:vaccin_list')), 'TEST_TEMP_vaccin_reference')
        self.assertContains(self.client.get(reverse('vaccins:traitement_list')), 'TEST_TEMP_traitement_reference')
        response = self.client.get(reverse('vaccins:suivi_create', args=[self.animal_tiers.pk]))
        self.assertContains(response, 'TEST_TEMP_vaccin_reference')
        self.assertContains(response, 'TEST_TEMP_traitement_reference')
        response = self.client.post(reverse('vaccins:suivi_create', args=[self.animal_tiers.pk]), {
            'animal': self.animal_tiers.pk, 'date': '2026-08-01', 'vaccins': [str(self.reference.pk)],
        })
        self.assertEqual(response.status_code, 302)

    def test_selection_forgee_refusee(self):
        """POST forgé avec la clé d'une entrée d'un autre compte : erreur de
        validation, rien n'est enregistré."""
        self.client.login(username='tiers_cat', password='p')
        url = reverse('vaccins:suivi_create', args=[self.animal_tiers.pk])
        for selection in ({'vaccins': [str(self.vaccin.pk)]}, {'traitement': str(self.traitement.pk)}):
            with self.subTest(selection=selection):
                response = self.client.post(url, {'animal': self.animal_tiers.pk, 'date': '2026-08-01', **selection})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.assertFalse(SuiviVaccinTraitement.objects.filter(animal=self.animal_tiers).exists())

    def test_un_membre_du_foyer_partage_les_entrees(self):
        self.client.login(username='sam_cat', password='p')
        self.assertContains(self.client.get(reverse('vaccins:vaccin_list')), 'TEST_TEMP_vaccin_alex')
        self.assertContains(self.client.get(reverse('vaccins:traitement_list')), 'TEST_TEMP_traitement_alex')
        url = reverse('vaccins:suivi_create', args=[self.animal_sam.pk])
        response = self.client.get(url)
        self.assertContains(response, 'TEST_TEMP_vaccin_alex')
        self.assertContains(response, 'TEST_TEMP_traitement_alex')
        response = self.client.post(url, {
            'animal': self.animal_sam.pk, 'date': '2026-08-01', 'vaccins': [str(self.vaccin.pk)],
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.post(url, {
            'animal': self.animal_sam.pk, 'date': '2026-08-02', 'traitement': str(self.traitement.pk),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SuiviVaccinTraitement.objects.filter(animal=self.animal_sam).count(), 2)

    def test_ajout_rapide_rattache_au_createur(self):
        self.client.login(username='tiers_cat', password='p')
        self.client.post(reverse('vaccins:vaccin_ajout_rapide'), {'nouveau_vaccin-nom': 'TEST_TEMP_ajout'})
        self.client.post(reverse('vaccins:traitement_ajout_rapide'), {
            'nouveau_traitement-nom': 'TEST_TEMP_ajout', 'nouveau_traitement-classe': Traitement.Classe.GEL,
        })
        self.assertEqual(Vaccin.objects.get(nom='TEST_TEMP_ajout').utilisateur, self.tiers)
        self.assertEqual(Traitement.objects.get(nom='TEST_TEMP_ajout').utilisateur, self.tiers)

    def test_deux_comptes_peuvent_creer_le_meme_nom(self):
        self.client.login(username='tiers_cat', password='p')
        response = self.client.post(reverse('vaccins:vaccin_ajout_rapide'), {'nouveau_vaccin-nom': 'TEST_TEMP_vaccin_alex'})
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('vaccins:traitement_ajout_rapide'), {
            'nouveau_traitement-nom': 'TEST_TEMP_traitement_alex',
            'nouveau_traitement-classe': Traitement.Classe.COMPRIME,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(Vaccin.objects.filter(nom='TEST_TEMP_vaccin_alex').values_list('utilisateur', flat=True)),
            {self.alex.pk, self.tiers.pk},
        )
        self.assertEqual(
            set(Traitement.objects.filter(nom='TEST_TEMP_traitement_alex').values_list('utilisateur', flat=True)),
            {self.alex.pk, self.tiers.pk},
        )

    def test_entree_deja_referencee_conservee_a_la_modification(self):
        """Suivi qui référence une entrée sortie du filtre (ancien membre du
        foyer, par exemple) : elle reste proposée et l'enregistrement ne la
        vide pas."""
        self.client.login(username='tiers_cat', password='p')
        for champ, entree, selection in (
            ('vaccin', self.vaccin, {'vaccins': [str(self.vaccin.pk)]}),
            ('traitement', self.traitement, {'traitement': str(self.traitement.pk)}),
        ):
            with self.subTest(champ=champ):
                suivi = SuiviVaccinTraitement.objects.create(
                    animal=self.animal_tiers, date=date(2026, 8, 1), **{champ: entree},
                )
                url = reverse('vaccins:suivi_update', args=[suivi.pk])
                self.assertContains(self.client.get(url), '<option value="%d" selected>' % entree.pk)
                response = self.client.post(url, {
                    'animal': self.animal_tiers.pk, 'date': '2026-08-03', 'notes': 'TEST_TEMP relu', **selection,
                })
                self.assertEqual(response.status_code, 302)
                suivi.refresh_from_db()
                self.assertEqual(getattr(suivi, champ), entree)
                self.assertEqual(suivi.notes, 'TEST_TEMP relu')


class FragmentsSuiviEnModificationTest(TestCase):
    """Fragments htmx du formulaire de suivi en modification : ils connaissent
    le suivi (clé dans l'URL) et gardent dans les listes redessinées le vaccin
    / traitement qu'il référence déjà, même sorti du catalogue visible (entrée
    créée par un ancien membre du foyer) — sinon la liste renvoyée en
    hx-swap-oob le perdait, et le suivi avec elle à l'enregistrement."""

    def setUp(self):
        self.ancien = User.objects.create_user(username='ancien_frag', password='p')
        self.sam = User.objects.create_user(username='sam_frag', password='p')
        self.tiers = User.objects.create_user(username='tiers_frag', password='p')
        self.animal = _animal_de(self.sam, 'TEST_TEMP_FRAG_SAM')
        animal_tiers = _animal_de(self.tiers, 'TEST_TEMP_FRAG_TIERS')
        # Entrées d'un compte qui ne partage plus (ou pas) le foyer de Sam.
        self.vaccin = Vaccin.objects.create(nom='TEST_TEMP_vaccin_ancien', utilisateur=self.ancien)
        self.traitement = Traitement.objects.create(
            nom='TEST_TEMP_traitement_ancien', classe=Traitement.Classe.COMPRIME, utilisateur=self.ancien,
        )
        self.suivi_vaccin = SuiviVaccinTraitement.objects.create(
            animal=self.animal, vaccin=self.vaccin, date=date(2026, 8, 1),
        )
        self.suivi_traitement = SuiviVaccinTraitement.objects.create(
            animal=self.animal, traitement=self.traitement, date=date(2026, 8, 2),
        )
        self.suivi_tiers = SuiviVaccinTraitement.objects.create(
            animal=animal_tiers, vaccin=self.vaccin, date=date(2026, 8, 3),
        )
        self.client.login(username='sam_frag', password='p')

    def _champ(self, response, nom):
        contenu = response.content.decode()
        debut = contenu.index('id="champ-%s"' % nom)
        return contenu[debut:contenu.index('</select>', debut)]

    def test_le_formulaire_de_modification_appelle_les_fragments_du_suivi(self):
        pk = self.suivi_vaccin.pk
        response = self.client.get(reverse('vaccins:suivi_update', args=[pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-post="%s"' % reverse('vaccins:suivi_choix', args=[pk]), count=2)
        self.assertContains(response, 'hx-post="%s"' % reverse('vaccins:vaccin_ajout_rapide', args=[pk]))
        self.assertContains(response, 'hx-post="%s"' % reverse('vaccins:traitement_ajout_rapide', args=[pk]))
        # En création, rien ne change : URL sans clé.
        response = self.client.get(reverse('vaccins:suivi_create', args=[self.animal.pk]))
        self.assertContains(response, 'hx-post="%s"' % reverse('vaccins:suivi_choix'), count=2)
        self.assertContains(response, 'hx-post="%s"' % reverse('vaccins:vaccin_ajout_rapide'))
        self.assertContains(response, 'hx-post="%s"' % reverse('vaccins:traitement_ajout_rapide'))

    def test_la_liste_redessinee_garde_le_vaccin_du_suivi(self):
        url = reverse('vaccins:suivi_choix', args=[self.suivi_vaccin.pk])
        # Sélection inchangée, puis vaccin désélectionné : il reste proposé.
        response = self.client.post(url, {'vaccins': [str(self.vaccin.pk)]})
        self.assertIn('<option value="%d" selected>' % self.vaccin.pk, self._champ(response, 'vaccins'))
        response = self.client.post(url, {'vaccins': ['']}, headers={'HX-Trigger': 'zone-traitement'})
        champ = self._champ(response, 'vaccins')
        self.assertIn('<option value="%d">TEST_TEMP_vaccin_ancien</option>' % self.vaccin.pk, champ)
        # Sans la clé du suivi (création), l'entrée d'un autre compte n'est
        # toujours pas proposée.
        response = self.client.post(reverse('vaccins:suivi_choix'), {'vaccins': [str(self.vaccin.pk)]})
        self.assertNotContains(response, 'TEST_TEMP_vaccin_ancien')

    def test_la_liste_redessinee_garde_le_traitement_du_suivi(self):
        url = reverse('vaccins:suivi_choix', args=[self.suivi_traitement.pk])
        response = self.client.post(url, {'traitement': str(self.traitement.pk)})
        self.assertIn('<option value="%d" selected>' % self.traitement.pk, self._champ(response, 'traitement'))
        # Comprimé : le bloc « Dose » reste affiché.
        self.assertContains(response, 'id="blocDose" class="col-sm-8"')
        response = self.client.post(url, {'traitement': ''}, headers={'HX-Trigger': 'zone-vaccins'})
        self.assertIn(
            '<option value="%d">TEST_TEMP_traitement_ancien</option>' % self.traitement.pk,
            self._champ(response, 'traitement'),
        )
        # Le vaccin de l'autre suivi n'est gardé que pour son propre suivi.
        self.assertNotContains(self.client.post(url, {'traitement': ''}), 'TEST_TEMP_vaccin_ancien')

    def test_ajout_rapide_de_vaccin_garde_celui_du_suivi(self):
        url = reverse('vaccins:vaccin_ajout_rapide', args=[self.suivi_vaccin.pk])
        response = self.client.post(url, {
            'vaccins': [str(self.vaccin.pk)], 'nouveau_vaccin-nom': 'TEST_TEMP_vaccin_ajoute',
        })
        self.assertEqual(response.status_code, 200)
        ajoute = Vaccin.objects.get(nom='TEST_TEMP_vaccin_ajoute')
        champ = self._champ(response, 'vaccins')
        self.assertIn('<option value="%d" selected>' % self.vaccin.pk, champ)
        self.assertIn('<option value="%d" selected>' % ajoute.pk, champ)
        # Ajout refusé (nom vide) : le panneau revient avec son erreur.
        response = self.client.post(url, {'vaccins': [str(self.vaccin.pk)], 'nouveau_vaccin-nom': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Vaccin.objects.filter(utilisateur=self.sam).count(), 1)

    def test_ajout_rapide_de_traitement_garde_celui_du_suivi(self):
        url = reverse('vaccins:traitement_ajout_rapide', args=[self.suivi_traitement.pk])
        response = self.client.post(url, {
            'traitement': str(self.traitement.pk), 'nouveau_traitement-nom': 'TEST_TEMP_traitement_ajoute',
            'nouveau_traitement-classe': Traitement.Classe.GEL,
        })
        self.assertEqual(response.status_code, 200)
        ajoute = Traitement.objects.get(nom='TEST_TEMP_traitement_ajoute')
        champ = self._champ(response, 'traitement')
        self.assertIn('<option value="%d" selected>' % ajoute.pk, champ)
        # L'ancien traitement reste proposé : on peut encore y revenir.
        self.assertIn('<option value="%d">TEST_TEMP_traitement_ancien</option>' % self.traitement.pk, champ)

    def test_enregistrement_apres_un_aller_retour_conserve_le_vaccin(self):
        """Le scénario complet : la liste revenue du fragment contient
        toujours le vaccin, que le formulaire complet accepte ensuite."""
        url = reverse('vaccins:suivi_choix', args=[self.suivi_vaccin.pk])
        response = self.client.post(url, {'vaccins': ['']}, headers={'HX-Trigger': 'zone-traitement'})
        self.assertIn('value="%d"' % self.vaccin.pk, self._champ(response, 'vaccins'))
        response = self.client.post(reverse('vaccins:suivi_update', args=[self.suivi_vaccin.pk]), {
            'animal': self.animal.pk, 'date': '2026-08-05', 'vaccins': [str(self.vaccin.pk)],
        })
        self.assertEqual(response.status_code, 302)
        self.suivi_vaccin.refresh_from_db()
        self.assertEqual(self.suivi_vaccin.vaccin, self.vaccin)

    def test_suivi_d_un_autre_compte_introuvable(self):
        """Même contrôle d'accès que la vue de modification : 404, et aucune
        entrée créée par l'ajout rapide."""
        pk = self.suivi_tiers.pk
        self.assertEqual(self.client.get(reverse('vaccins:suivi_update', args=[pk])).status_code, 404)
        for nom, data in (
            ('vaccins:suivi_choix', {'vaccins': [str(self.vaccin.pk)]}),
            ('vaccins:vaccin_ajout_rapide', {'nouveau_vaccin-nom': 'TEST_TEMP_interdit'}),
            ('vaccins:traitement_ajout_rapide', {
                'nouveau_traitement-nom': 'TEST_TEMP_interdit', 'nouveau_traitement-classe': Traitement.Classe.GEL,
            }),
        ):
            with self.subTest(url=nom):
                response = self.client.post(reverse(nom, args=[pk]), data)
                self.assertEqual(response.status_code, 404)
        self.assertFalse(Vaccin.objects.filter(nom='TEST_TEMP_interdit').exists())
        self.assertFalse(Traitement.objects.filter(nom='TEST_TEMP_interdit').exists())
        # Suivi inexistant, et requête non connectée.
        self.assertEqual(self.client.post(reverse('vaccins:suivi_choix', args=[999999999])).status_code, 404)
        self.client.logout()
        response = self.client.post(reverse('vaccins:suivi_choix', args=[self.suivi_vaccin.pk]))
        self.assertEqual(response.status_code, 302)
