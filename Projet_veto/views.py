from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

from . import throttling


class LoginThrottleView(auth_views.LoginView):
    """Bloque la connexion après 3 échecs consécutifs depuis la même adresse
    — 15 min la 1ère fois, 1h en cas de récidive, définitivement à partir de
    la 3e (cf. Projet_veto.throttling) — protection basique contre les
    robots qui testent des mots de passe en masse."""

    def post(self, request, *args, **kwargs):
        if throttling.est_bloque('login', request):
            messages.error(request, throttling.message_blocage('login', request))
            return redirect('login')
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        throttling.enregistrer_tentative('login', self.request)
        return super().form_invalid(form)

    def form_valid(self, form):
        throttling.reinitialiser_tentatives('login', self.request)
        return super().form_valid(form)


class PasswordResetThrottleView(auth_views.PasswordResetView):
    """« Mot de passe oublié » : formulaire public dont chaque envoi visant
    un email inscrit déclenche un vrai email — limité à
    MAX_DEMANDES_REINITIALISATION demandes par heure et par adresse, pour
    qu'un script ne puisse pas noyer la boîte d'un utilisateur ni entamer le
    quota du compte SMTP (dont dépendent aussi les rappels de consultation).
    Simple compteur en cache, sans l'escalade jusqu'au blocage définitif de
    la connexion/inscription : redemander un lien plusieurs fois est un usage
    légitime."""

    MAX_DEMANDES_REINITIALISATION = 5
    FENETRE_SECONDES = 60 * 60

    def post(self, request, *args, **kwargs):
        if throttling.limite_simple_atteinte(
            'reinitialisation', request, self.MAX_DEMANDES_REINITIALISATION, self.FENETRE_SECONDES,
        ):
            messages.error(request, "Trop de demandes depuis cette adresse. Réessaie dans 1 heure.")
            return redirect('password_reset')
        return super().post(request, *args, **kwargs)
