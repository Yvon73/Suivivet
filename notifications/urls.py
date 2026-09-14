from django.urls import path
from .views import (
    NotificationListView,
    marquer_comme_lue,
    marquer_toutes_comme_lues,
    supprimer_notification,
)

app_name = 'notifications'

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification_list'),
    path('<int:notification_id>/lire/', marquer_comme_lue, name='marquer_lue'),
    path('toutes/lire/', marquer_toutes_comme_lues, name='marquer_toutes_lues'),
    path('<int:notification_id>/supprimer/', supprimer_notification, name='supprimer_notification'),
]