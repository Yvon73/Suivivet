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
