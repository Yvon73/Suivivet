from django.apps import AppConfig

class ConsultationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'consultations'

    def ready(self):
        # Import nécessaire à son seul effet de bord : enregistrer les
        # @receiver définis dans signals.py (jamais utilisé directement ici).
        import consultations.signals  # noqa: F401