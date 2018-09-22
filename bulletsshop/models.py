from django.db import models
from autoslug import AutoSlugField
from datetime import date
from django.core.validators import MinValueValidator
from decimal import Decimal

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
    slug = AutoSlugField(populate_from='name', editable=False)						# For nice URLs


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
#class ProductPictures(models.Model):
# TODO



################################################ ORDER RELATED MODELS ################################################

#class Order(models.Model)
#name
#email
#address
#status
#postage_required
#notes
#datetime created
#guid for linking in emails etc


#class OrderItems(models.Model)
#link to productitem
#copy of name
#copy of price
#quantity
#status - has it been given out or not?


#class OrderHistory
#history_entry



################################################ BASKET RELATED MODELS ################################################
#class Basket
#created datetime (to allow purging once a day)


#class BasketItems
#item
#quantity





################################################ DISCOUNT CODE RELATED MODELS ################################################


#class DiscountCode
#code name
#percentage_off
#fixed_amount_off
#applies_to_product
#applies_to_postage

