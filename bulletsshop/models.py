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




# create at least one of these per product, this is stock keeping unit
class ProductItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='items')
    extra_text = models.CharField("Item Name", max_length=500, blank=True, null=True)	# this is where sizes, colours, variations on the main Product go

#   TODO: display_order

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
        if quantity <= self.quantity_in_stock:			# we can just allocate this many items - Easy!
            return (self.OK_TO_BUY_NOW, quantity, 0, 0)
        
        if quantity <= (self.quantity_in_stock + self.spare_in_order):   # we can allocate from a mixture of on order and spare items
            from_stock = self.quantity_in_stock		# allocate all of the stock first
            from_order = (quantity - from_stock)        # what's left comes from the on-order stuff
            return (self.OK_TO_BUY_OR_ORDER, from_stock, from_order, 0)

        # if we get here, we have to make up the rest of the order by ordering more from a supplier
        if self.product.allow_supplier_orders != True:		# more than are in stock or on order, and can't order more
            return (self.CANNOT_BUY, 0, 0, 0)

        from_stock = self.quantity_in_stock	
        from_order = self.spare_in_order
        to_order = (quantity - from_stock - from_order)
        return (self.OK_TO_BUY_OR_ORDER, from_stock, from_order, to_order)
 

    @property
    def quantity_allocated(self):
        # sum all of the qty allocated for all orderitems for this item
        x = self.ordered_items.aggregate(Sum('quantity_allocated'))
        print(str(x))
        if x['quantity_allocated__sum']:
            return x['quantity_allocated__sum']
        else:
            return 0


    @property
    def spare_in_order(self):
        return max(0, self.quantity_on_order - self.quantity_allocated_on_order)

    def __str__(self):
        if self.product.no_options:
            return str(self.product)
        else:
            return str(self.product) + " - " + str(self.extra_text)


# Pictures of products - associated with product-level things
class ProductPicture(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='pictures')
    image = VersatileImageField(
        'Product Image',
        upload_to='product_images/'
    )


################################################ ORDER RELATED MODELS ################################################

class Order(models.Model):
    STATUS_UNPAID = "U"
    STATUS_PAID = "P"
    STATUS_COMPLETE = "C"
    STATUS_CANCELLED = "X"
    STATUS_REFUNDED = "R"
   
    ORDER_STATUS_CHOICES = (
        (STATUS_UNPAID, "Not paid"),
        (STATUS_PAID, "Paid"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REFUNDED, "Refunded"),
        )

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

#    status = models.CharField("Status", max_length=1, choices=ORDER_STATUS_CHOICES, default=STATUS_UNPAID)

    def __str__(self):
        return "Order #" + str(self.pk) + " for " + str(self.name)

    @property
    def name(self):
        if self.delivery_name:
            return self.delivery_name
        else:
            return self.billing_name


    @property
    def grand_total(self):
        return self.total + self.postage_amount

    @property
    def total(self):
        total = Decimal(0)
        for item in self.items.all():
            total = total + item.line_price
        return total

    @property
    def items_in_order(self):
        x = self.items.aggregate(Sum('quantity_ordered'))
        return x['quantity_ordered__sum'] 

    @property
    def postage_required(self):
        return self.items.filter(item_postage_requred=True).exists()

    @property
    def amount_owing(self):
        return self.grand_total - self.amount_paid()

    def amount_paid(self):
        total = 0
        for payment in self.payments.filter(status=PaymentStatus.CONFIRMED):
            total = total + payment.total

        return total
 
    @property
    def fully_paid(self):
        return self.amount_paid() == self.grand_total


    @property
    def outstanding_item_count(self):
        ordered = self.items.aggregate(Sum('quantity_ordered'))
        delivered = self.items.aggregate(Sum('quantity_delivered'))

        ordered_qty = ordered['quantity_ordered__sum']
        delivered_qty = delivered['quantity_delivered__sum']
        return (ordered_qty - delivered_qty)


    
# some helper methods to return filtered querysets 
    def despatch_items(self):				# All items waiting to be given out / despatched
        return self.items.filter(quantity_ordered__gt=F('quantity_delivered'), quantity_allocated__gt=0)

    def on_order_items(self):				# All items we are waiting on stock for
        return self.items.filter(quantity_allocated__lt=F('quantity_ordered')-F('quantity_delivered'))

    def despatched_items(self):				# All items we have given out to the purchaser
        return self.items.filter(quantity_delivered__gt=0)



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
        validators=[MinValueValidator(0)], default=Decimal(0))					# what is allocated, but not yet delivered
    quantity_delivered = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))					# what was supplied
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
        if self.quantity_refunded == 0:
            if self.quantity_ordered == self.quantity_delivered:
                return "Fully despatched"
            elif self.quantity_delivered > 0:
                return "Partially despatched"
            elif self.quantity_allocated > 0:
                return "Ready to despatch"
            else:
                return "Waiting for stock"
        elif self.quantity_refunded == self.quantity_ordered:
            return "Fully refunded"
        else:
            return "Partially refunded"
        
    @property
    def left_to_deliver(self):
        return self.quantity_ordered - self.quantity_delivered 

    def despatch(self, quantity):    # mark this many of the item as despatched (move them from allocated to delivered)
        if (quantity > 0) and (quantity <= self.left_to_deliver):
            self.quantity_delivered = self.quantity_delivered + quantity
            self.quantity_allocated = self.quantity_allocated - quantity
            self.save()
	    # TODO: log this as a history item



class OrderHistory(models.Model):
    created = models.DateTimeField("Date Time", auto_now_add=True)
    comment = models.CharField("Comment", max_length=500, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='comments')

    # TODO: maybe create automatically based on post_save signal?


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
    order =  models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')

    def get_failure_url(self):
        return build_absolute_uri(reverse('shop:home'))	# TODO: what to do if failed

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

