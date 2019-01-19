from django.db import models
from autoslug import AutoSlugField
from datetime import date
from django.core.validators import MinValueValidator
from decimal import Decimal
from versatileimagefield.fields import VersatileImageField
import uuid
from django.db.models import Sum, F
from bulletsweb.utils import build_absolute_uri
from django.urls import reverse

from payments import PurchasedItem, PaymentStatus
from payments.models import BasePayment


### All the models we need for the Bullets Shop ###

################################################ PRODUCT RELATED MODELS ################################################


# give the products a bit of structure
class ProductCategory(models.Model):
    name = models.CharField("Category Name", max_length=128)
    hidden = models.BooleanField("Hide on shop display", default=False)

    def __str__(self):
        return self.name
  

## The suppliers we have to order things from
class Supplier(models.Model):
    name = models.CharField(max_length=128)
    
    def __str__(self):
        return self.name


# Postage
class Postage(models.Model):
    name = models.CharField("Name", max_length=500)				# name of Postage
    price = models.DecimalField("Price", max_digits=5, decimal_places=2)	# Postage price

    def __str__(self):
        return self.name

# Products
class Product(models.Model):
    POSTAGE_NEEDED = "P"
    POSTAGE_OPTIONAL = "O"
    POSTAGE_NOT_ALLOWED = "X"
   
    POSTAGE_STATUS_CHOICES = (
        (POSTAGE_NEEDED, "Postage required"),
        (POSTAGE_OPTIONAL, "Postage optional"),
        (POSTAGE_NOT_ALLOWED, "Postage not permitted"),
        )
   

    name = models.CharField("Product Name", max_length=500)						# name of product
    description = models.TextField("Product Description", blank=True)					# HTML
    price = models.DecimalField("Price", max_digits=5, decimal_places=2)				# price
    hidden = models.BooleanField("Hide on shop display", default=False)					# do not display (but can buy)
    available_from = models.DateField("Available on or after this date", default=date.today)		# only purchase after this date
    available_until = models.DateField("Available until this date", blank=True, null=True)		# stop purchases after this date
    category = models.ManyToManyField(ProductCategory, related_name='products') 			# what categories is this product in
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='products')		# supplier of this product
    allow_supplier_orders = models.BooleanField("Allow orders even when no stock?", default=False)	# allow ordering when not in stock
    postage_option = models.CharField("Postage", max_length=1, choices=POSTAGE_STATUS_CHOICES, default=POSTAGE_OPTIONAL)  # what type of postage
    postage_amount = models.ForeignKey(Postage, on_delete=models.SET_NULL, blank=True, null=True, default=None, related_name='products')   # What level of postage?
    only_buy_one = models.BooleanField("Limit to single purchases?", default=False)			# can only put one in the basket + order
    slug = AutoSlugField(populate_from='name', unique=True, editable=False)				# For nice URLs

    @property
    def postage_required(self):
        return (self.postage_option == self.POSTAGE_NEEDED)

    @property
    def postage_price(self):
        if (self.postage_option == self.POSTAGE_NOT_ALLOWED):
            return 0
        else:
            if self.postage_amount: 
                return self.postage_amount.price
            else:
                return 0


    @property
    def is_visible(self):
        if self.hidden:				# This product is explicitly hidden
            return False

        today = date.today()
        if (today < self.available_from):
            return False			# This product doesn't appear for a while 
        
        if self.available_until:
            if (self.available_until < today):
                return False			# This product appeared in the past

        return True

    @property
    def display_price(self):
        return "£" + str(self.price)


    @property
    def no_options(self):			# return true if there's only the fake underlying item
        y = self.items        
#print("no options for " + str(self) + " = " + str(self.items.all.count))
        if (self.items.count() == 1):
            item = self.items.first()
            return item.extra_text == None	# if it's blank
        return False

    def picture_url(self):
        x = self.pictures.first()
        if x == None:
            return "https://via.placeholder.com/200x150.png?text=Boldmere+Bullets"
        else:
            return x.image.url

    def __str__(self):
        return self.name

    def get_history(self): 	# TODO: date range filter?
        return ProductHistory.objects.filter(item__product=self)

    @property
    def items_for_sale(self):	# 	return all the ProductItems for this Product which can be sold (in stock or for order)
        if self.allow_supplier_orders:
            return self.items.all()
        else:
            return self.items.filter(quantity_in_stock__gt=0) 	# TODO: could sell stuff that's not allocated but is on order too

    @property
    def no_options_stock(self):
        if self.no_options:
            return self.items.first().quantity_in_stock
        else:
            return 0

    @property
    def anything_to_buy(self):
        return self.items_for_sale.exists()



# create at least one of these per product, this is stock keeping unit
class ProductItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='items')
    extra_text = models.CharField("Item Name", max_length=500, blank=True, null=True)	# this is where sizes, colours, variations on the main Product go

#   TODO: display_order??

    quantity_in_stock = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(1))		# amount we physically have available to sell
#    quantity_allocated = models.IntegerField(
#        validators=[MinValueValidator(0)], default=Decimal(0))		# what we have, but have sold
    quantity_to_order = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))		# qty paid for but not yet ordered from supplier
    quantity_on_order = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))		# qty on order from suppliers
    quantity_allocated_on_order = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))		# qty on order from suppliers which are already sold

    # TODO - allow deep linking to just a productitem (eg. to just large t-shirts) - slug/id maybe? or slug/slug ???

    OK_TO_BUY_NOW = 1
    OK_TO_BUY_OR_ORDER = 2
    CANNOT_BUY = 3

    # work out whether we can allocate this many items, or whether we can order them, or what
    # returns (STATUS, <to_allocate_stock>, <to_allocate_from_order> <how many we can order>)
        # status =  ProductItem.OK_TO_BUY_NOW, ProductItem.OK_TO_BUY_OR_ORDER, ProductItem.CANNOT_BUY
        # to_allocate_stock = amount we can allocate from stock,
        # to_allocate_from_order = amount we can allocate from spare stock in a coming order
        # to_order = amount we need to put in a future order

    def order_or_allocate(self, quantity):
        if quantity <= self.quantity_in_stock:				# we can just allocate this many items - Easy!
            return (self.OK_TO_BUY_NOW, quantity, 0, 0)
        
        if quantity <= (self.quantity_in_stock + self.spare_in_order):   # we can allocate from a mixture of on order and spare items
            from_stock = self.quantity_in_stock				 # allocate all of the stock first
            from_order = (quantity - from_stock)        		 # what's left comes from the on-order stuff
            return (self.OK_TO_BUY_OR_ORDER, from_stock, from_order, 0)

        # if we get here, we have to make up the rest of the order by ordering more from a supplier
        if self.product.allow_supplier_orders != True:		# more than are in stock or on order, and can't order more
            return (self.CANNOT_BUY, 0, 0, 0)

        from_stock = self.quantity_in_stock	
        from_order = self.spare_in_order
        to_order = (quantity - from_stock - from_order)
        return (self.OK_TO_BUY_OR_ORDER, from_stock, from_order, to_order)
 
    def ok_to_add_to_basket(self, quantity):
        (status, a, b, c) = self.order_or_allocate(quantity)
        print(str(status))
        return (status != self.CANNOT_BUY)

    @property
    def quantity_allocated(self):
        # sum all of the qty allocated for all orderitems for this item
        x = self.ordered_items.aggregate(Sum('quantity_allocated'))
        if x['quantity_allocated__sum']:
            return x['quantity_allocated__sum']
        else:
            return 0

    @property
    def spare_in_order(self):
        return max(0, self.quantity_on_order - self.quantity_allocated_on_order)

    def __str__(self):
        if self.product.no_options:
            x = str(self.product)
        else:
            x = str(self.product) + " - " + str(self.extra_text)
        if (self.quantity_in_stock) == 0 and self.product.allow_supplier_orders:
            x = x + " (*)"
        return x


    def stock_returned(self, quantity_ordered, quantity_allocated):	# an order is being cancelled, and this many items have just been freed up.
	# returns how many items have been ordered from the supplier that will be problematic now
	# quantity_ordered = how many items were in the original order
	# quantity_allocated = how much stock we'd assigned to this order (difference between two = stuff that is potentially on order from supplier)
	# can only change quantity_to_order (as order has not yet been made with supplier) 
	#  and quantity_allocated_on_order (to show fewer items allocated in the order). 
	# Do quantity_to_order first, then deducted any left from quantity_allocated_on_order (and return this difference as a problem)

        # qto = 1, qao = 0, qbo = 1      qto -> 0, qao = 0, problem = 0    			nqto = 0, rqoo = 0
        # qto = 1, qao = 1, qbo = 1      qto -> 0, qao = 1, problem = 0				nqto = 0, rqoo = 0
        # qto = 2, qao = 0, qbo = 1      qto -> 1, qao = 0, problem = 0				nqto = 1, rqoo = 0
        # qto = 1, qao = 0, qbo = 2      qto -> 0, qao = 0, problem = 1   (can't happen???)	nqto = 0, rqoo = 1
        # qto = 0, qao = 1, qbo = 1      qto = 0, qao -> 0, problem = 1				
        # qto = 0, qao = 2, qbo = 1      qto = 0, qao -> 1, problem = 1
        # qto = 1, qao = 1, qbo = 2      qto -> 0, qao -> 0, problem = 1  ('problem' is whatever qao should change by)
        # qto = 3, qao = 5, qbo = 4      qto -> 0, qao -> 4, problem = 1			nqto = 0, rqoo = 1

        self.quantity_in_stock += quantity_allocated

        quantity_being_ordered = quantity_ordered - quantity_allocated			# what must be on order (or to go on order) from a supplier

        new_quantity_to_order = max(0, self.quantity_to_order - quantity_being_ordered)	# take stuff off of future orders first
        reduce_quantity_on_order_by = max(0, quantity_being_ordered - self.quantity_to_order)
        new_quantity_allocated_on_order = max(0, self.quantity_allocated_on_order - reduce_quantity_on_order_by)

        self.quantity_allocated_on_order = new_quantity_allocated_on_order
        self.quantity_to_order = new_quantity_to_order
        self.save()

	# now distribute stock to existing orders
        self.allocate_stock_to_orders()
        return reduce_quantity_on_order_by



    def stock_arrived(self, qty_arrived):
        # add stock into the inventory and then try and distribute to existing orders

        to_allocate = min(qty_arrived, self.quantity_allocated_on_order) 			# how many do we have to allocate?
        spare = max(0, qty_arrived - to_allocate)						# what's left from the order after allocations?

        self.quantity_on_order = max(0, self.quantity_on_order - qty_arrived)			# can't go below zero on this
        self.quantity_allocated_on_order = self.quantity_allocated_on_order - to_allocate  	# this can't be above the amount we are tracking
        self.quantity_in_stock = self.quantity_in_stock + qty_arrived				# Push stock up by the amount that just arrived
                
        self.save()		
	
	# Now distribute stock to existing orders
        return self.allocate_stock_to_orders()



    def allocate_stock_to_orders(self):		# When stock arrives, try to allocate as much as possible to orders, oldest first
        allocations = [] 
       	# Step 1: sort OrderItems by oldest to newest, filtered on this Item 
        orderitems_for_item = self.ordered_items.order_by('order__created').filter(quantity_ordered__gt=F('quantity_delivered')+F('quantity_allocated')+F('quantity_refunded'))

	# TODO: I think this might allocate stock to unpaid orders. Might need sanity check in here.
	# TODO: need to check above for refunded items confusing things.

        for orderitem in orderitems_for_item:
	    # Step 2: go over each of these until we've got rid of all of the items that arrived in the order.
            remaining_for_item = orderitem.quantity_ordered - (orderitem.quantity_delivered + orderitem.quantity_allocated + orderitem.quantity_refunded)
            oi_to_allocate = min(remaining_for_item, self.quantity_in_stock)
            if oi_to_allocate > 0:
                orderitem.quantity_allocated = orderitem.quantity_allocated + oi_to_allocate
                orderitem.save()

                oh = OrderHistory(order=orderitem.order, comment=str(oi_to_allocate) + " x " + str(orderitem.item_name) + " - allocated")
                oh.save()

                self.quantity_in_stock -= oi_to_allocate
                self.save()
                 
                allocations.append({'orderitem':orderitem, 'just_allocated':oi_to_allocate})
         
        return allocations




# Pictures of products - associated with product-level things
class ProductPicture(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='pictures')
    image = VersatileImageField(
        'Product Image',
        upload_to='product_images/'
    )


# track the history of sales and stock on particular products
class ProductHistory(models.Model):
    created = models.DateTimeField("Date Time", auto_now_add=True)
    item = models.ForeignKey(ProductItem, on_delete=models.CASCADE, related_name='history')
    
    CREATED = 'c'
    DISPATCHED = 'd'
    ORDERED = 'o'
    RECEIVED = 'r'
    REFUNDED = 'x'

    EVENT_CHOICES = (
        (CREATED, "Created"),
        (DISPATCHED, "Dispatched to customer"),
        (ORDERED, "Ordered from supplier"),
        (RECEIVED, "Received from supplier"), 
        (REFUNDED, "Refunded"),
        )

    event = models.CharField("Event",
        max_length=1,
        choices=EVENT_CHOICES,
        default=CREATED,
        )
    quantity = models.IntegerField(default=0)
	
    	# what events could occur? 
   	# 	Product created (with x in stock)
	#	Product given to customer (x to customer)
	# 	Product ordered from supplier (x ordered)
	# 	Product received from supplier (x received)
	#	Product returned (x returned)
    
    class Meta:
        ordering = ['-created']

    def __str__(self):
        return str(self.item) + " " + self.get_event_display() + " (" + str(self.quantity) + ")"


################################################ ORDER RELATED MODELS ################################################

class Order(models.Model):
    billing_name = models.CharField("Billing Name", max_length=500)				# billing name for order
    billing_address = models.TextField("Billing Address", blank=True)				# billing address 
    billing_postcode = models.CharField("Billing Postcode", max_length=8)			# billing postcode

    delivery_name = models.CharField("Delivery Name", max_length=500)				# name of person to deliver to
    delivery_address = models.TextField("Delivery Address", blank=True)				# delivery
    delivery_postcode = models.CharField("Delivery Postcode", max_length=8)			# delivery postcode

    email = models.EmailField("Email")								# required email address
 
    postage_amount = models.DecimalField("Postage", max_digits=5, decimal_places=2)		# amount paid for postage
     
    customer_notes = models.TextField("Notes", blank=True)					# any note from the customer

    created = models.DateTimeField("Order created", auto_now_add=True)				# When created
    updated = models.DateTimeField("Order last updated", auto_now=True)				# When changed

    unique_ref =  models.UUIDField("random uuid for email links", default=uuid.uuid4, editable=False) # random UUID for emails

    cancelled = models.BooleanField("Cancelled?", default=False)					# Is this order cancelled? 

    def __str__(self):
        return "Purchase #" + str(self.pk) + " for " + str(self.name)

    @property
    def name(self):
        if self.delivery_name:
            return self.delivery_name
        else:
            return self.billing_name

    @property
    def grand_total(self):					# grand total (inc. postage)
        return self.total + self.postage_amount

    @property			
    def total(self):						# subtotal (without any postage)
        total = Decimal(0)
        for item in self.items.all():
            total = total + item.line_price
        return total

    @property
    def items_in_order(self):					# total number of items that have been purchased
        x = self.items.aggregate(Sum('quantity_ordered'))
        return x['quantity_ordered__sum'] 

    @property
    def postage_required(self):
        return self.items.filter(item_postage_required=True).exists()

    @property
    def amount_owing(self):					# what is left to pay on this order?
        return self.grand_total - self.amount_paid()

    def amount_paid(self):					# How much money has been paid on this order?
        total = 0
        for payment in self.confirmed_payments():
            total = total + payment.total

        return total
 
    @property							# Is this order completely paid for?
    def fully_paid(self):
        return self.amount_paid() == self.grand_total

    @property
    def items_ready_to_dispatch(self):		# How many items can we give out right now
        items = self.dispatch_items()
        qty_to_dispatch = items.aggregate(Sum('quantity_allocated'))['quantity_allocated__sum']
        return qty_to_dispatch or 0

    @property				# How many items are left to give out on this order?		
    def outstanding_item_count(self):
        ordered = self.items.aggregate(Sum('quantity_ordered'))
        delivered = self.items.aggregate(Sum('quantity_delivered'))

        ordered_qty = ordered['quantity_ordered__sum']
        delivered_qty = delivered['quantity_delivered__sum']
        return (ordered_qty - delivered_qty)		# TODO - take off refunded items too?

    @property				# How many items are we waiting for stock on?
    def total_waiting_for_stock(self):
        on_order = self.on_order_items().aggregate(total=Sum(F('quantity_ordered') - F('quantity_allocated') - F('quantity_delivered') - F('quantity_refunded')))
        waiting_for_stock = on_order['total']        
        return waiting_for_stock or 0
 
      
    @property
    def can_cancel(self):		# Can we cancel this order? Yes, if fully paid and no items dispatched / refunded
        if self.fully_paid and (self.dispatched_items().count() == 0) and (self.refunded_items().count() == 0):
            return True
        else:
            return False


    @property
    def status(self):
        if self.cancelled:
            return "Cancelled"
        elif self.fully_paid != True:
            return "Waiting payment"
        elif self.items_ready_to_dispatch > 0:
            return "Items ready to dispatch"
        elif self.total_waiting_for_stock > 0:
            return "Waiting for stock"
        elif self.outstanding_item_count > 0:
            return "Processing"
        else:
            return "Complete"
    

# some helper methods to return filtered querysets 
    def dispatch_items(self):				# All items waiting to be given out / dispatched
        if self.fully_paid:
            return self.items.filter(quantity_ordered__gt=F('quantity_delivered'), quantity_allocated__gt=0)
        else:
            return self.items.none()

    def on_order_items(self):				# All items we are waiting on stock for
        if self.fully_paid:
            return self.items.filter(quantity_allocated__lt=F('quantity_ordered')-F('quantity_delivered')-F('quantity_refunded'))
        else:
            return self.items.none()

    def dispatched_items(self):				# All items we have given out to the purchaser
        return self.items.filter(quantity_delivered__gt=0)

    def refunded_items(self):				# All items we have returned & refunded
        return self.items.filter(quantity_refunded__gt=0)

    def confirmed_payments(self):			# All confirmed payments (only ones that can be refunded)
        return self.payments.filter(status=PaymentStatus.CONFIRMED)







class OrderItem(models.Model):
    item = models.ForeignKey(ProductItem, on_delete=models.SET_NULL, blank=True, null=True, related_name='ordered_items')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')

    # These fields are copied when we create the order
    item_name = models.CharField("Name", max_length=1000)
    item_price = models.DecimalField("Price", max_digits=5, decimal_places=2)
    item_postage_required = models.BooleanField("Must be posted to buyer?", default=False) 		# must pay for postage  

    quantity_ordered = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))					# what was ordered originally
    quantity_allocated= models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))					# what is physically allocated, but not yet delivered
    quantity_delivered = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))					# what was supplied to customer
    quantity_refunded = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))					# what has been refunded
 
    def __str__(self):
        return "Order #" + str(self.order.pk) + " " + str(self.quantity_ordered) + " x " + str(self.item_name)

    @property
    def line_price(self):
        return (self.item_price * self.quantity_ordered)

    # helper to adjust status when we ship stuff
    @property
    def status(self):
        if self.quantity_ordered == 0:
            return "Cancelled"
        elif self.quantity_refunded == 0:
            if self.quantity_ordered == self.quantity_delivered:
                return "Fully dispatched"
            elif self.order.fully_paid != True:		# this feels most natural place to display that order isn't fully paid
                return "Awaiting payment"
            elif self.quantity_delivered > 0:
                return "Partially dispatched"
            elif self.quantity_allocated > 0:
                return "Ready to dispatch"
            else:
                return "Waiting for stock"
        elif self.quantity_refunded == self.quantity_ordered:
            return "Fully refunded"
        else:
            return "Partially refunded"
        
    @property
    def need_to_order(self):					# ONLY use in the email to customer - otherwise use status()
        return self.quantity_allocated != self.quantity_ordered

    @property
    def left_to_deliver(self):
        return self.quantity_ordered - (self.quantity_delivered + self.quantity_refunded)


    @property
    def unallocated(self):
        return self.quantity_ordered - self.quantity_delivered - self.quantity_allocated - self.quantity_refunded


    def dispatch(self, quantity):    # mark this many of the item as dispatched (move them from allocated to delivered)
        if (quantity > 0) and (quantity <= self.left_to_deliver):
            self.quantity_delivered = F('quantity_delivered') + quantity
            self.quantity_allocated = F('quantity_allocated') - quantity
            self.save()

            m = str(quantity) + " x " + str(self.item_name) + " - dispatched"
            oh = OrderHistory(order=self.order, comment=m)		# Create a history entry for this item
            oh.save()
            ph = ProductHistory(item=self.item, quantity=quantity, event=ProductHistory.DISPATCHED)
            ph.save()


    # cancel this order item and return allocated items to stock etc (before items are delivered to customer)
    def cancel(self):
        amount = self.quantity_allocated
        m = str(self.quantity_ordered) + " x " + str(self.item_name) + " - cancelled "
        
        if self.item:
            problem_items = self.item.stock_returned(self.quantity_ordered, self.quantity_allocated)	
            m = m + "and " + str(amount) + " returned to stock"
        else:
            m = m + ", " + str(amount) + " NOT returned to stock (item no longer exists!)"
            problem_items = 0
       
        self.quantity_allocated = 0
 #       self.quantity_ordered = 0	
        self.save()

        oh = OrderHistory(order=self.order, comment=m)
        oh.save()
 
        if problem_items > 0:
            oh = OrderHistory(order=self.order, comment="!!! Items on order !!! " + str(problem_items) + " are already on order from the supplier")
            oh.save()

        return (problem_items > 0)


    def refund(self, amount=None):		# mark <amount> of item as refunded & return items to stock (all if amount is unset)
        if amount == None or amount > self.quantity_ordered:
            amount = self.quantity_ordered

        self.quantity_delivered = self.quantity_delivered - amount		# Change allocation of items on this order item
        self.quantity_refunded = self.quantity_refunded + amount
        self.save()

	# also return the item into stock

        m = str(amount) + " x " + str(self.item_name) + " - refunded "

        if self.item:
            self.item.quantity_in_stock = self.item.quantity_in_stock + amount
            self.item.save()
            m = m + "and returned to stock"
        else:
            m = m + "NOT returned to stock (item no longer exists!)"
       
        oh = OrderHistory(order=self.order, comment=m)
        oh.save()
        ph = ProductHistory(item=self.item, quantity=amount, event=ProductHistory.REFUNDED)
        ph.save()
  

class OrderHistory(models.Model):
    created = models.DateTimeField("Date Time", auto_now_add=True)
    comment = models.CharField("Comment", max_length=500, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='comments')

    class Meta:
        ordering = ['-created']


################################################ BASKET RELATED MODELS ################################################

class Basket(models.Model):
    created = models.DateTimeField("Basket created", auto_now_add=True)

# fill these items in during order creation before we actually create an order
    billing_name = models.CharField("Billing Name", max_length=500, blank=True)					# name of person buying
    billing_address = models.TextField("Billing Address", blank=True)						# address of purchaser
    billing_postcode = models.CharField("Billing Postcode", max_length=8, blank=True)				# required postcode

    delivery_name = models.CharField("Delivery Name", max_length=500, blank=True)				# delivery name
    delivery_address = models.TextField("Delivery Address", blank=True)						# delivery address    
    delivery_postcode = models.CharField("Delivery Postcode", max_length=8, blank=True)				# delivery postcode
    email = models.EmailField("Email", blank=True)								# contact email address\

    postage_amount = models.DecimalField("Postage", max_digits=5, decimal_places=2, default=Decimal(0))		# amount paid for postage


    @property
    def has_items(self):
        return self.items.exists()

    @property
    def item_count(self):
        x = self.items.aggregate(Sum('quantity'))
        if x['quantity__sum']:
            return x['quantity__sum']
        else:
            return 0

    @property
    def basket_total(self):
        total = 0
        for item in self.items.all():
            total = total + item.total
        return total

    @property
    def grand_total(self):
        return self.basket_total + self.postage_amount

    @property
    def must_not_post(self):  # return true if all item in the basket do not allow posting
        for basket_item in self.items.all():
            if basket_item.item.product.postage_option != Product.POSTAGE_NOT_ALLOWED:
                return False  # if any item can have postage then return early
        return True 

    @property
    def must_post(self):  # return true if any item in the basket requires posting
        for basket_item in self.items.all():
            if basket_item.item.product.postage_required:
                return True  # if any item can must have postage then return early
        return False 


    def max_postage(self):	# return the highest postage object in this basket
        price = 0
        postage = None
        for basket_item in self.items.all():
            if basket_item.item.product.postage_price > price:
                price = basket_item.item.product.postage_price 
                postage = basket_item.item.product.postage_amount

        return postage



class BasketItem(models.Model):
    basket = models.ForeignKey(Basket, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(ProductItem, on_delete=models.CASCADE, related_name='basket_items')
    quantity = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))			
    
    @property
    def price(self):
        return self.item.product.price


    @property
    def total(self):
        return self.price * self.quantity



################################################ PAYMENT RELATED MODELS ################################################

class Payment(BasePayment):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')

    def get_failure_url(self):
        return build_absolute_uri(reverse('shop:home'))			# TODO: what to do if failed

    def get_success_url(self):
        return build_absolute_uri(reverse('shop:payment-success', kwargs={'uuid': self.order.unique_ref}))


    def get_purchased_items(self):
        items = []
        for item in order.ordered_items.all():
            x = PurchasedItem(name=item.item_name, sku='SKU',
                            quantity=item.quantity_ordered, price=item.item_price, currency='GBP')
            items.append(x)
        return items




################################################ DISCOUNT CODE RELATED MODELS ################################################


#class DiscountCode
#code name
#percentage_off
#fixed_amount_off
#applies_to_product
#applies_to_postage

