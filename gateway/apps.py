from django.apps import AppConfig


class GatewayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gateway'

    def ready(self):
        from corsheaders.signals import check_request_enabled
        
        from .cors import allow_registered_client_origins

        check_request_enabled.connect(allow_registered_client_origins, dispatch_uid="gateway_cors")