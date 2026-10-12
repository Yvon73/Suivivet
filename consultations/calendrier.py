"""Calendrier des consultations rendu côté serveur.

Remplace FullCalendar : la grille du mois et la liste « planning » sont de
simples pages HTML calculées ici, et la navigation (mois précédent/suivant,
aujourd'hui, grille/planning) de simples liens `?annee=…&mois=…&vue=…` —
htmx ne fait qu'éviter de recharger toute la page (cf.
consultations/partials/calendrier.html).

Trois sortes d'événements, comme auparavant : les consultations à venir,
leur rappel deux jours avant quand elles sont imminentes, et les rappels de
vaccin (date de la prochaine dose).
"""
import calendar
from datetime import date, datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone

from accueil.utils import comptes_accessibles
from vaccins.models import SuiviVaccinTraitement
from .models import Consultation

VUES = ('grille', 'planning')
DELAI_RAPPEL = timedelta(days=2)
# Années navigables. Bien en deçà de date.max : la grille déborde sur les mois
# voisins (décembre 9999 demanderait le 1er janvier 10000).
ANNEE_MIN, ANNEE_MAX = 1900, 2200


def mois_demande(request):
    """Premier jour du mois demandé dans l'URL (`annee`, `mois`), ou du mois
    en cours si ces paramètres sont absents, illisibles ou hors de la plage
    ANNEE_MIN..ANNEE_MAX."""
    aujourdhui = timezone.localdate()
    try:
        premier_jour = date(int(request.GET.get('annee', '')), int(request.GET.get('mois', '')), 1)
    except (TypeError, ValueError, OverflowError):
        return aujourdhui.replace(day=1)
    if not ANNEE_MIN <= premier_jour.year <= ANNEE_MAX:
        return aujourdhui.replace(day=1)
    return premier_jour


def _decaler(premier_jour, nombre_de_mois):
    """Premier jour du mois situé `nombre_de_mois` plus tard (ou plus tôt),
    None si l'on sort de la plage ANNEE_MIN..ANNEE_MAX."""
    indice = premier_jour.year * 12 + (premier_jour.month - 1) + nombre_de_mois
    annee, mois = divmod(indice, 12)
    if not ANNEE_MIN <= annee <= ANNEE_MAX:
        return None
    return date(annee, mois + 1, 1)


def evenements(utilisateur, debut, fin):
    """Événements du calendrier de `utilisateur` entre les dates `debut` et
    `fin` incluses, triés par date puis par heure."""
    comptes = comptes_accessibles(utilisateur)
    maintenant = timezone.now()
    fuseau = timezone.get_current_timezone()
    debut_dt = timezone.make_aware(datetime.combine(debut, time.min), fuseau)
    fin_dt = timezone.make_aware(datetime.combine(fin + timedelta(days=1), time.min), fuseau)
    resultat = []

    def ajouter(moment, titre, url, classe):
        """`moment` : date seule (événement sur la journée) ou date et heure."""
        if isinstance(moment, datetime):
            moment = timezone.localtime(moment)
            jour, heure = moment.date(), moment.time()
        else:
            jour, heure = moment, None
        if debut <= jour <= fin:
            resultat.append({'date': jour, 'heure': heure, 'titre': titre, 'url': url, 'classe': classe})

    # Consultations à venir.
    consultations = Consultation.objects.filter(
        animal__utilisateur__in=comptes, date__gte=max(maintenant, debut_dt), date__lt=fin_dt,
    ).select_related('animal')
    for consultation in consultations:
        ajouter(
            consultation.date, f"{consultation.animal.nom} - {consultation.motif}",
            reverse('consultations:consultation_detail', args=[consultation.pk]), 'evenement-consultation',
        )

    # Rappels : consultations prévues dans les deux jours, affichées deux jours avant.
    rappels = Consultation.objects.filter(
        animal__utilisateur__in=comptes, date__gte=maintenant, date__lte=maintenant + DELAI_RAPPEL,
    ).select_related('animal')
    for rappel in rappels:
        ajouter(
            rappel.date - DELAI_RAPPEL, f"⚠️ Rappel: {rappel.animal.nom} - {rappel.motif}",
            reverse('consultations:consultation_detail', args=[rappel.pk]), 'evenement-rappel-consultation',
        )

    # Rappels de vaccin (date de la prochaine dose).
    suivis = SuiviVaccinTraitement.objects.filter(
        animal__utilisateur__in=comptes, vaccin__isnull=False,
        date_prochaine_dose__gte=debut, date_prochaine_dose__lte=fin,
    ).select_related('animal', 'vaccin')
    for suivi in suivis:
        ajouter(
            suivi.date_prochaine_dose, f"💉 Rappel vaccin : {suivi.animal.nom} - {suivi.vaccin.nom}",
            reverse('animaux:animal_detail', args=[suivi.animal.pk]), 'evenement-rappel-vaccin',
        )

    # Sur une même journée : les événements sans heure d'abord, puis par heure.
    resultat.sort(key=lambda evenement: (evenement['date'], evenement['heure'] or time.min, evenement['titre']))
    return resultat


def contexte(request):
    """Contexte du gabarit consultations/partials/calendrier.html."""
    premier_jour = mois_demande(request)
    vue = request.GET.get('vue', '')
    if vue not in VUES:
        vue = ''
    aujourdhui = timezone.localdate()

    # Grille : semaines complètes, du lundi au dimanche, couvrant le mois.
    semaines_dates = calendar.Calendar(firstweekday=calendar.MONDAY).monthdatescalendar(
        premier_jour.year, premier_jour.month,
    )
    par_jour = {}
    for evenement in evenements(request.user, semaines_dates[0][0], semaines_dates[-1][-1]):
        par_jour.setdefault(evenement['date'], []).append(evenement)

    semaines = [
        [
            {
                'date': jour,
                'hors_mois': jour.month != premier_jour.month,
                'aujourdhui': jour == aujourdhui,
                'evenements': par_jour.get(jour, []),
            }
            for jour in semaine
        ]
        for semaine in semaines_dates
    ]
    # Planning : les seules journées du mois qui ont au moins un événement.
    planning = [
        {'date': jour, 'aujourdhui': jour == aujourdhui, 'evenements': liste}
        for jour, liste in sorted(par_jour.items()) if jour.month == premier_jour.month
    ]

    def url(mois, vue_voulue=vue):
        if mois is None:
            return ''
        parametres = f'?annee={mois.year}&mois={mois.month}'
        return parametres + (f'&vue={vue_voulue}' if vue_voulue else '')

    return {
        'mois_affiche': premier_jour,
        'semaines': semaines,
        'planning': planning,
        'vue': vue,
        'jours_semaine': ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'],
        'url_mois_precedent': url(_decaler(premier_jour, -1)),
        'url_mois_suivant': url(_decaler(premier_jour, 1)),
        'url_aujourdhui': url(aujourdhui.replace(day=1)),
        'url_grille': url(premier_jour, 'grille'),
        'url_planning': url(premier_jour, 'planning'),
        'url_courante': url(premier_jour),
        'est_mois_courant': premier_jour == aujourdhui.replace(day=1),
    }
