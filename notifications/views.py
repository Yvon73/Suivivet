from django.shortcuts import redirect, get_object_or_404
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from .models import Notification

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/liste.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        return Notification.objects.filter(utilisateur=self.request.user).order_by('-date_creation')

# Actions modifiantes : en POST uniquement (formulaires avec jeton CSRF dans
# notifications/liste.html et dans la cloche de base.html) — un simple lien
# GET pouvait être déclenché par un site tiers ou un préchargement de liens.
@login_required
@require_POST
def marquer_comme_lue(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, utilisateur=request.user)
    notification.lue = True
    notification.save()
    return redirect('notifications:notification_list')

@login_required
@require_POST
def marquer_toutes_comme_lues(request):
    Notification.objects.filter(utilisateur=request.user, lue=False).update(lue=True)
    return redirect('notifications:notification_list')

@login_required
@require_POST
def supprimer_notification(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, utilisateur=request.user)
    notification.delete()
    return redirect('notifications:notification_list')
