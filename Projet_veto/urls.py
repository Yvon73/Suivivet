"""
URL configuration for Projet_veto project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

# L'appli n'a qu'un seul "Admin" (le tout premier compte cree via
# PremierUtilisateurCreateView, is_staff=is_superuser=True) - d'autres comptes
# peuvent recevoir is_staff par la suite sans etre l'Admin ; on restreint donc
# l'acces au site admin Django a is_superuser plutot qu'a is_staff seul, pour
# que le lien "Administration" masque cote template (voir base.html) soit
# aussi une vraie restriction d'acces et pas seulement un masquage visuel.
admin.site.has_permission = lambda request: (
    request.user.is_active and request.user.is_superuser
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
    ), name='password_reset'),
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
    ), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change_form.html',
    ), name='password_change'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='registration/password_change_done.html',
    ), name='password_change_done'),
    path('', include('accueil.urls')),
    path('animaux/', include('animaux.urls')),
    path('vaccins/', include('vaccins.urls')),
    path('consultations/', include('consultations.urls')),
    path('factures/', include('factures.urls')),
    path('documents/', include('documents.urls')),
    path('notifications/', include('notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)