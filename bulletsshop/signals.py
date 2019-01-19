from django.db.models.signals import pre_save
from django.dispatch import receiver
from payments import PaymentStatus

from .models import Payment, OrderHistory, Order, ProductItem
from django.db.models import F

from bulletsweb.utils import send_bullet_mail

@receiver(pre_save, sender=Payment)
def payment_made(sender, instance, **kwargs):
    payment = instance
    order = payment.order

    old_status = None

    try:
        old_payment = Payment.objects.get(pk=payment.pk)
        old_status = old_payment.status
    except sender.DoesNotExist:
        pass # Object is new

    if payment.status != old_status:	
        print("Payment status changed from " + str(old_status) + " to " + str(payment.status))
        m = "Payment of £" + str(payment.total) + " (" + str(payment.variant) + ") status: " + str(payment.status)
 
        if payment.status == PaymentStatus.ERROR:
            m = ": message = " + str(payment.message)

        oh = OrderHistory(order=order, comment=m)
        oh.save()

        if payment.status == PaymentStatus.CONFIRMED:
            print("Payment is now Confirmed!")
            update_order_after_payment(order)
            # Now send the customer an email to confirm we've received their payment
            send_bullet_mail("emails/order-confirmed", [order.email], {'order':order})
    else:
        print("Payment status unchanged")
  


# When an order becomes fully paid, try and allocate some stock to it.
def update_order_after_payment(order):
    for orderitem in order.items.all():
        (status, to_allocate_stock, to_allocate_from_order, to_order) = orderitem.item.order_or_allocate(orderitem.quantity_ordered)
        #print("In update_order_after_payment " + str(status) + " - " + str(to_allocate_stock) + " - " + str(to_allocate_from_order) + " - " + str(to_order))

        if status == ProductItem.CANNOT_BUY:
		# This is a big problem, as between the customer starting the order, and us getting the payment confirmed, we've run low/out of stock
 		# Rather than try and allocate any remaining stock (e.g. we have 2 items left, this order is for 5, could possibly allocate 3), 
 		# we will simply flag a problem, and let the shop admin figure out the best course of action
            oh = OrderHistory(order=order, comment="!!! Insufficient Stock !!! Cannot allocate " + str(orderitem.quantity_ordered) + " x " + str(orderitem.item_name))
            oh.save()
	    # TODO: send a manager email here if this situation occurs.

        else: 
            # update the amount of stock allocated to this order item
            orderitem.quantity_allocated=to_allocate_stock
           # print("at this point orderitem.quantity_allocated = " + str(orderitem.quantity_allocated))
            orderitem.save()

            if to_allocate_stock > 0:
                oh = OrderHistory(order=order, comment=str(to_allocate_stock) + " x " + str(orderitem.item_name) + " - allocated")
                oh.save()

            # and also adjust the productItem's stock levels		
            orderitem.item.quantity_in_stock = F('quantity_in_stock') - to_allocate_stock
            orderitem.item.quantity_to_order = F('quantity_to_order') + to_order
            orderitem.item.quantity_allocated_on_order = F('quantity_allocated_on_order') + to_allocate_from_order
            orderitem.item.save()

        #print("leaving signal handler, with qty allocated = " + str(orderitem.quantity_allocated))


