from django.db.models.signals import post_save
from django.dispatch import receiver
from payments import PaymentStatus

from .models import Payment, OrderHistory, Order

@receiver(post_save, sender=Payment)
def payment_made(sender, **kwargs):
    payment = kwargs['instance']
 
    order = payment.order
    m = "Payment of £" + str(payment.total) + " (" + str(payment.variant) + ") status: " + str(payment.status)
 
    if payment.status == PaymentStatus.ERROR:
        m = ": message = " + str(payment.message)

    oh = OrderHistory(order=order, comment=m)
    oh.save()
  
 
