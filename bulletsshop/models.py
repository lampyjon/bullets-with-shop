from django.db import models
from autoslug import AutoSlugField
from datetime import date
from django.core.validators import MinValueValidator
from decimal import Decimal
from versatileimagefield.fields import VersatileImageField
import uuid
from django.db.models import Sum

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




# Products
class Product(models.Model):
    name = models.CharField("Product Name", max_length=500)						# name of product
    description = models.TextField("Product Description", blank=True)					# HTML
    price = models.DecimalField("Price", max_digits=5, decimal_places=2)				# price
    hidden = models.BooleanField("Hide on shop display", default=False)					# do not display (but can buy)
    available_from = models.DateField("Available on or after this date", default=date.today)		# only purchase after this date
    available_until = models.DateField("Available until this date", blank=True, null=True)		# stop purchases after this date
    category = models.ManyToManyField(ProductCategory, related_name='products') 			# what categories is this product in
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='products')		# supplier of this product
    allow_supplier_orders = models.BooleanField("Allow orders even when no stock?", default=False)	# allow ordering when not in stock
    postage_required = models.BooleanField("Must be posted to buyer?", default=False) 			# must pay for postage
    only_buy_one = models.BooleanField("Limit to single purchases?", default=False)			# can only put one in the basket + order
    slug = AutoSlugField(populate_from='name', unique=True, editable=False)						# For nice URLs


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
   

    def __str__(self):
        return self.name




# create at least one of these per product, this is stock keeping unit
class ProductItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='items')
    extra_text = models.CharField("Item Name", max_length=500, blank=True, null=True)	# this is where sizes, colours, variations on the main Product go

#   display_order

    quantity_in_stock = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(1))		# amount we physically have available to sell
    quantity_allocated = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))		# what we have, but have sold
    quantity_to_order = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))		# qty paid for but not yet ordered from supplier
    quantity_on_order = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))		# qty on order from suppliers
    quantity_allocated_on_order = models.IntegerField(
        validators=[MinValueValidator(0)], default=Decimal(0))		# qty on order from suppliers which are already sold

    # TODO - allow deep linking to just a productitem (eg. to just large t-shirts) - slug/id maybe? or slug/slug ???


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

    name = models.CharField("Name", max_length=500)						# name of person buying
    address = models.TextField("Address", blank=True)						# optional address of purchaser
    email = models.EmailField("Email")								# required email address
    postcode = models.CharField("PostCode", max_length=8)					# required postcode
 
    postage_amount = models.DecimalField("Postage", max_digits=5, decimal_places=2)		# amount paid for postage

     
    customer_notes = models.TextField("Notes", blank=True)					# any note from the customer

    created = models.DateTimeField("Order created", auto_now_add=True)				# When created
    updated = models.DateTimeField("Order last updated", auto_now=True)				# When changed

    unique_ref =  models.UUIDField("random uuid for email links", default=uuid.uuid4, editable=False) # random for emails

    status = models.CharField("Status", max_length=1, choices=ORDER_STATUS_CHOICES, default=STATUS_UNPAID)

    def __str__(self):
        return "Order #" + str(self.pk) + " for " + str(self.name)

    @property
    def total(self):
        total = Decimal(0)
        for item in self.items.all():
            total = total + item.line_price
        return total


    @property
    def items_in_order(self):
        x = self.items.aggregate(Sum('quantity_ordered'))
        return x['quantity_ordered__sum'] + self.postage_amount

    @property
    def postage_required(self):
        return self.items.filter(item_postage_requred=True).exists()

    



class OrderItem(models.Model):
    STATUS_WAITING_FOR_STOCK = "W"
    STATUS_READY_TO_DESPATCH = "G"
    STATUS_DESPATCHED = "D"
    STATUS_CANCELLED = "X"
    STATUS_RETURNED_REFUNDED = "R"

    ORDERITEM_STATUS_CHOICES = (
        (STATUS_WAITING_FOR_STOCK, "Waiting for stock"),
        (STATUS_READY_TO_DESPATCH, "Ready to despatch"),
        (STATUS_DESPATCHED, "Despatched"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_RETURNED_REFUNDED, "Returned / Refunded"),
    )

    item = models.ForeignKey(ProductItem, on_delete=models.SET_NULL, blank=True, null=True, related_name='ordered_items')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')

    status = models.CharField("Status", max_length=1, choices=ORDERITEM_STATUS_CHOICES, default=STATUS_READY_TO_DESPATCH)

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
 
    def __str__(self):
        return "Order #" + str(self.order.pk) + " " + str(self.quantity_ordered) + " x " + str(self.item_name)

    @property
    def line_price(self):
        return (self.item_price * self.quantity_ordered)



#class OrderHistory
#history_entry
# maybe create automatically based on post_save signal?


################################################ BASKET RELATED MODELS ################################################

class Basket(models.Model):
    created = models.DateTimeField("Basket created", auto_now_add=True)

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
# TODO: utility methods here to figure out total costs etc


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


################################################ DISCOUNT CODE RELATED MODELS ################################################


#class DiscountCode
#code name
#percentage_off
#fixed_amount_off
#applies_to_product
#applies_to_postage

