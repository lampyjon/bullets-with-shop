from django.db.models.signals import pre_save
from django.dispatch import receiver
from payments import PaymentStatus

from .models import Payment, OrderHistory, Order, ProductItem
from django.db.models import F

from bulletsweb.utils import send_bullet_mail, build_absolute_uri, send_manager_email
from django.urls import reverse


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
        #print("Payment status changed from " + str(old_status) + " to " + str(payment.status))
        m = "Payment of £" + str(payment.total) + " (" + str(payment.variant) + ") status: " + str(payment.status)
 
        if payment.status == PaymentStatus.ERROR:
            m = ": message = " + str(payment.message)

        oh = OrderHistory(order=order, comment=m)
        oh.save()

        if payment.status == PaymentStatus.CONFIRMED:
           # print("Payment is now Confirmed!")
            update_order_after_payment(order)
            # Now send the customer an email to confirm we've received their payment

            url = build_absolute_uri(reverse('shop:view-order', args=[order.unique_ref]))
            send_bullet_mail("emails/order-confirmed", [order.email], {'order':order, 'url':url})

            url = build_absolute_uri(reverse('dashboard:order', args=[order.id]))
            send_manager_email("emails/manager-order-confirmed", {'order':order, 'url':url})

     


# When an order becomes fully paid, try and allocate some stock to it.
def update_order_after_payment(order):
    # mark any associated voucher as being used to the value of this order
    if order.voucher:			
        if order.voucher.is_valid:
            order.voucher.used_count = F('used_count') + 1
            order.voucher.save()
        else:
            # This is a problem - the voucher has become invalid during the payment flow. We'll make a note of this, and remove the voucher from the order.
            oh = OrderHistory(order=order, comment="!!! " + str(order.voucher) + " - was used on this order. It has been automatically removed during the payment process, so there is still money owing on this order. !!!")
            oh.save()

            order.voucher = None
            order.save()

	    #  send a manager email here, advising of the issue.
            url = build_absolute_uri(reverse('dashboard:order', args=[order.id]))
            send_manager_email("emails/manager-order-problem", {'order':order, 'url':url, 'problem': "A voucher was used which is no longer valid"})


    for orderitem in order.items.all():
        (status, to_allocate_stock, to_allocate_from_order, to_order) = orderitem.item.order_or_allocate(orderitem.quantity_ordered)

        if status == ProductItem.CANNOT_BUY:
		# This is a big problem, as between the customer starting the order, and us getting the payment confirmed, we've run low/out of stock
 		# Rather than try and allocate any remaining stock (e.g. we have 2 items left, this order is for 5, could possibly allocate 3), 
 		# we will simply flag a problem, and let the shop admin figure out the best course of action
            oh = OrderHistory(order=order, comment="!!! Insufficient Stock !!! Cannot allocate " + str(orderitem.quantity_ordered) + " x " + str(orderitem.item_name))
            oh.save()
	    # send a manager email here if this situation occurs.
            url = build_absolute_uri(reverse('dashboard:order', args=[order.id]))
            send_manager_email("emails/manager-order-problem", {'order':order, 'url':url, 'problem': "There is insufficient stock for a purchase that was just paid for. Cannot allocate an item for this purchase."})



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


