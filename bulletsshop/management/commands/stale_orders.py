from django.core.management.base import BaseCommand, CommandError
from bulletsshop.models import Order
from django.conf import settings
import datetime
from django.utils import timezone
from bulletsweb.utils import send_bullet_mail, build_absolute_uri
from django.urls import reverse



class Command(BaseCommand):
    help = 'Manage stale orders (unpaid after a time)'

    def handle(self, *args, **options):
        self.stdout.write("Managing stale orders")

# if it has been more than an hour since we saw an order get created, but there's no associated payment, then we email the person reminding them of need to pay
        now = timezone.now()
        hour_ago = now - datetime.timedelta(hours=1)
        week_ago = now - datetime.timedelta(days=21)	# TODO - reduce

        self.stdout.write("Filtering between " + str(hour_ago) + " and " + str(week_ago))

        recent_orders = Order.objects.filter(created__gt=week_ago).filter(created__lt=hour_ago)

        self.stdout.write("Going to chase the following orders:")

        for order in recent_orders.filter(email_chase=False):
            if order.fully_paid != True and order.email != "" and order.email_chase == False:
                self.stdout.write(" emailing : " + str(order.email) + " about order " + str(order))

                url = build_absolute_uri(reverse('shop:view-order', args=[order.unique_ref]))
                send_bullet_mail("emails/order-chase", [order.email], {'order':order, 'url':url})

                order.email_chase = True
                order.save()




