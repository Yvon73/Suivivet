from django.shortcuts import redirect, get_object_or_404
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Notification

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/liste.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        return Notification.objects.filter(utilisateur=self.request.user).order_by('-date_creation')

@login_required
def marquer_comme_lue(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, utilisateur=request.user)
    notification.lue = True
    notification.save()
    return redirect('notifications:notification_list')

@login_required
def marquer_toutes_comme_lues(request):
    Notification.objects.filter(utilisateur=request.user, lue=False).update(lue=True)
    return redirect('notifications:notification_list')

@login_required
def supprimer_notification(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, utilisateur=request.user)
    notification.delete()
    return redirect('notifications:notification_list')
