from django.apps import AppConfig


class BulletsshopConfig(AppConfig):
    name = 'bulletsshop'
    def ready(self):
        import bulletsshop.signals


