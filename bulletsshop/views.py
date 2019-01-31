from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
import django.core.exceptions
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.csrf import csrf_exempt
from django.contrib.messages.views import SuccessMessageMixin

from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView

from django.utils import timezone
from django.db.models import Q, Sum, F
from django.urls import reverse_lazy, reverse
from django.contrib.sites.models import Site
from django.forms import formset_factory, inlineformset_factory
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator


# Python imports 
import datetime
import uuid
import random
import os
import calendar


from .models import Product, ProductCategory, Supplier, ProductItem, ProductPicture, Order, OrderItem, Basket, BasketItem, Postage, OrderHistory, ProductHistory
from .forms import ProductForm, ItemForm, ProductPictureForm, OrderHistoryItemForm, ShopProductForm, OrderFormPostage, OrderFormBillingAddress, OrderFormDeliveryAddress, ReturnItemForm, OfflineSaleForm

from payments import PaymentStatus

from bulletsweb.utils import is_shop_team


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[-1]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


########## SHOP VIEWS #####################


# Get into the request and return the basket (or create a new one)
def get_basket(request):
    basket_id = request.session.get('basket', None)
    basket = None
    if basket_id:
        if Basket.objects.filter(id=basket_id).exists():
            basket = Basket.objects.get(pk=basket_id)

    if basket == None:
        basket = Basket()
        basket.save()

    request.session['basket'] = basket.id

    return basket


# get the visible categories into the request
def get_categories():
    return ProductCategory.objects.filter(hidden=False)


def index(request):
    return render(request, "shop/index.html", {})



## Product views
class ShopProductList(ListView):
    template_name="shop/product_list.html"
    context_object_name = 'products'		

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context['basket'] = get_basket(self.request)  # add the basket to the context
        context['categories'] = get_categories()
        return context

    def get_queryset(self):
        today = datetime.date.today()
        qs = Product.objects.filter(hidden=False).filter(available_from__lte=today).filter(Q(available_until__gte=today)|Q(available_until=None))
        return qs


## Product views
class ShopProductCategoryList(ListView):
 #   model = Product
    template_name="shop/product_list.html"
    context_object_name = 'products'

    def get_queryset(self):
        self.category = get_object_or_404(ProductCategory, pk=self.kwargs['category_pk'])
        if self.category.hidden:			
            return None
        today = datetime.date.today()
        qs = Product.objects.filter(category=self.category).filter(hidden=False).filter(available_from__lte=today).filter(Q(available_until__gte=today)|Q(available_until=None))
        return qs

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context['basket'] = get_basket(self.request)  	# add the basket to the context
        context['categories'] = get_categories()
        context['category'] = self.category
        return context


# Main view for looking at a product
def ShopProduct(request, product_pk, slug):
    product = get_object_or_404(Product, pk=product_pk, slug=slug)
    basket = get_basket(request)              

    # TODO: visibilty checks here

    if request.POST:
        product_form = ShopProductForm(request.POST, product=product)
        if product_form.is_valid():
            # add to basket
            item = product_form.cleaned_data['item']
            qty = product_form.cleaned_data['quantity']
            # TODO: so much stuff to do here to keep things sane!
            if item.product.only_buy_one and qty>1:
               qty = 1
               messages.info(request, "You can only buy one of this item at a time")

            if item.ok_to_add_to_basket(qty):            
                basket_item, created = BasketItem.objects.get_or_create(basket=basket, item=item, defaults={'quantity':qty})
                if created:
                    messages.success(request, str(item) + " was added to your basket")
                else:
                    basket_item.quantity = basket_item.quantity + qty
                    basket_item.save()
                    messages.success(request, str(item) + " - quantity updated in basket")       
                return redirect(reverse('shop:basket'))
            else:
                messages.error(request, "This product is not in stock or available to order")
            
    # reset product form 
    product_form = ShopProductForm(product=product)
 
    return render(request, "shop/product_view.html", {'product_form':product_form, 'product':product, 'basket':basket, 'categories':get_categories()})


def ShopBasketUpdate(request):
    basket = get_basket(request)

    if request.POST:
        item_pk = request.POST.get("item_pk", None)
        action = request.POST.get("action", None)

        if basket.items.filter(pk=item_pk).exists():
            item = basket.items.get(pk=item_pk)
            # ok to edit
            if action == "delete":
                messages.success(request, str(item.item) + " has been removed from your basket")
                item.delete()
            elif action == "up":
                # TODO: stock level check
                item.quantity = item.quantity + 1
                item.save()
                messages.success(request, "Added 1 x " + str(item.item) + " to your basket")
            elif action == "down":
                messages.success(request, "Removed 1 x " + str(item.item) + " from your basket")
                if item.quantity > 1:
                    item.quantity = item.quantity - 1
                    item.save()
                else:
                    item.delete()
    return redirect(reverse('shop:basket'))
 


def ShopBasket(request):
    basket = get_basket(request)

    if basket == None:
       return redirect('shop:home')

    return render(request, "shop/basket.html", {'basket':basket, 'categories':get_categories()})




######## ORDERING VIEWS #############

from payments import get_payment_model
from decimal import Decimal



# Create a new order from all the data that's in the basket. Return an error code if one or more items are not in stock (and don't create an order)
def create_order_from_basket(basket, note):
    # step 1 - create order
    # step 2 - add items to order (error if no stock and can't order)
    # step 3 - delete basket
    # if step 2 goes wrong, delete order

    # step 1
    order = Order(billing_name = basket.billing_name, 
                  billing_address = basket.billing_address,
                  billing_postcode = basket.billing_postcode,
                  delivery_name = basket.delivery_name,
                  delivery_address = basket.delivery_address,
                  delivery_postcode = basket.delivery_postcode,
                  email = basket.email,
                  postage_amount = basket.postage_amount,
                  customer_notes = note)

    order.save()
    

    # step 2
    any_problems = False
    for basket_item in basket.items.all():
        (status, to_allocate_stock, to_allocate_from_order, to_order) = basket_item.item.order_or_allocate(basket_item.quantity)
#        print("For item ("+ str(basket_item.quantity) + " x " + str(basket_item.item) + ") = " + str(status) + " to_alloc_from_stock=" + str(to_allocate_stock) + "  to_order=" + str(to_order) + " to_alloc_from_order=" + str(to_allocate_from_order))

        # status =  ProductItem.OK_TO_BUY_NOW, ProductItem.OK_TO_BUY_OR_ORDER, ProductItem.CANNOT_BUY
        # to_allocate_stock = amount we can allocate from stock,
        # to_allocate_from_order = amount we can allocate from spare stock in a coming order
        # to_order = amount we need to put in a future order
       
        if status == ProductItem.CANNOT_BUY:
           any_problems = True

    if any_problems:
        order.delete()
        return None		# TODO: return more info on the problem?

    for basket_item in basket.items.all():
 	# make an order Item for this basket line
        orderitem = OrderItem(item=basket_item.item, 
                              order=order,
                              item_name=str(basket_item.item),
                              item_price=basket_item.item.product.price,
                              item_postage_required=basket_item.item.product.postage_required,
                              quantity_ordered=basket_item.quantity,
                              quantity_allocated=0,
                              quantity_delivered=0)
       
        orderitem.save()

    # STEP 3
    basket.delete()

    return order




# Checkout Step 1 - show a summary of the basket, and postage options (as available)
def CheckoutViewBasket(request):
    basket = get_basket(request)

    if basket == None:
       return redirect('shop:home')

    if request.POST:
        orderform = OrderFormPostage(request.POST, basket=basket)
        if orderform.is_valid(): 
            if basket.must_not_post:
                basket.postage_amount = 0
            else:
                basket.postage_amount = orderform.cleaned_data['postage_amount']
            basket.save()
            
            # we always redirect to...
            return redirect(reverse('shop:checkout-billing'))
    else:
        orderform = OrderFormPostage(basket=basket)
   
    return render(request, "shop/checkout.html", {'basket':basket, 'form':orderform})



# Checkout Step 2 - show billing address entry form, and (if postage is being paid for, an optional 'delivery address is same as billing address' button
def CheckoutBillingAddress(request):
    basket = get_basket(request)

    if basket == None:
       return redirect('shop:home')

    if request.POST:
        orderform = OrderFormBillingAddress(request.POST, basket=basket)
        if orderform.is_valid(): 
            basket.billing_name = orderform.cleaned_data['billing_name']
            basket.billing_address = orderform.cleaned_data['billing_address']
            basket.billing_postcode = orderform.cleaned_data['billing_postcode']
            basket.email = orderform.cleaned_data['email']

            basket.save()

            # we always redirect to...
            if basket.postage_amount != 0:
               if orderform.cleaned_data['same_delivery_address'] == False:
                   return redirect(reverse('shop:checkout-delivery'))
               else:
                   basket.delivery_name = basket.billing_name
                   basket.delivery_address = basket.billing_address
                   basket.delivery_postcode = basket.billing_postcode
                   basket.save()
            return redirect(reverse('shop:checkout-summary'))			# No postage, or we can skip to the summary
    else:
        orderform = OrderFormBillingAddress(basket=basket)
    
    return render(request, "shop/checkout-billing.html", {'basket':basket, 'form':orderform})




# Checkout Step 3 - optionally skipped - get delivery address if different to billing
def CheckoutDeliveryAddress(request):
    basket = get_basket(request)

    if basket == None:
       return redirect('shop:home')

    if basket.postage_amount == 0:
       return redirect(reverse('shop:checkout-summary'))

    if request.POST:
        orderform = OrderFormDeliveryAddress(request.POST)
        if orderform.is_valid(): 
            basket.delivery_name = orderform.cleaned_data['delivery_name']
            basket.delivery_address = orderform.cleaned_data['delivery_address']
            basket.delivery_postcode = orderform.cleaned_data['delivery_postcode']
            basket.save()

            return redirect(reverse('shop:checkout-summary'))			# go to the summary
    else:
        orderform = OrderFormDeliveryAddress()
    
    return render(request, "shop/checkout-delivery.html", {'basket':basket, 'form':orderform})

 

# Checkout Step 4 - summary of all captured details from checkout, final chance to go and change!
def CheckoutSummary(request):
    basket = get_basket(request)

    if basket == None:
       return redirect('shop:home')

    if request.POST:
        orderform = OrderHistoryItemForm(request.POST)
        if orderform.is_valid():
            order = create_order_from_basket(basket=basket, note=orderform.cleaned_data['comment'])

            if order == None: # something went wrong - stock probably
                messages.error(request, "There was a problem creating your order") 
                return redirect('shop:basket')

            return do_payment(request, order)

    else:
        orderform = OrderHistoryItemForm()

    print(str(orderform))
    return render(request, "shop/checkout-summary.html", {'basket':basket, 'form':orderform})



from django.views.decorators.csrf import csrf_exempt
from payments import get_payment_model, RedirectNeeded


def payment_details(request, payment_id):
    payment = get_object_or_404(get_payment_model(), id=payment_id)
    try:
        form = payment.get_form(data=request.POST or None)
    except RedirectNeeded as redirect_to:
        return redirect(str(redirect_to))
    return render(request, 'shop/payment.html', {'form': form, 'payment': payment})


@csrf_exempt
def payment_success(request, uuid):
    order = get_object_or_404(Order, unique_ref=uuid)		# TODO: what to do here?

    print("order " + str(order) + " was paid!")
    print(str(request.POST))

    messages.success(request, "Your payment was received")

    return redirect(reverse('shop:home'))

# TODO: payment_failure page

def do_payment(request, order):					# make a payment and redirect to the payment page
    # made order ok - make payment object for the order
    Payment = get_payment_model()
    payment = Payment.objects.create(
                order=order,
                variant='default',  # this is the variant from PAYMENT_VARIANTS
                description='Boldmere Bullet Shop Purchase',
                total=order.grand_total,
                tax=Decimal(0),
                currency='GBP',
                delivery=order.postage_amount,
                billing_first_name=order.billing_name,
                billing_last_name='',
                billing_address_1=order.billing_address,
                billing_address_2='',
                billing_city='',
                billing_postcode=order.billing_postcode,
                billing_country_code='UK',
                billing_country_area='',
                customer_ip_address=get_client_ip(request))
          
    return redirect(reverse('shop:pay', args=[payment.pk]))		# go to the payment page

def view_order(request, uuid):					# Page to view order details
    order = get_object_or_404(Order, unique_ref=uuid)
    return render(request, 'shop/order.html', {'order':order})

def make_payment(request, uuid):					# Quick redirection to payment page
    order = get_object_or_404(Order, unique_ref=uuid)
    return do_payment(request, order)


######################################## DASHBOARD VIEWS #####################################################################

@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def dashboard(request):			# stuff we see first
    orders = Order.objects.order_by('-created')
    purchases = []
    for order in orders:
        if order.fully_paid:
            purchases.append(order)

    items = ProductItem.objects.filter(quantity_to_order__gt=0).order_by('product__supplier')

    allocations = OrderItem.objects.order_by('order__created').filter(quantity_allocated__gt=0)

    return render(request, "dashboard/index.html", {'allocations':allocations[:10], 'purchases':purchases[:10], 'stock_required':items})


## Product views
class ProductList(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Product
    template_name="dashboard/product_list.html"
    def test_func(self):
        return is_shop_team(self.request.user)

@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def product_create(request, category_pk=None, product_pk=None, supplier_pk=None):
    if category_pk:
        category = get_object_or_404(ProductCategory, pk=category_pk)
    else:
        category = None

    if product_pk:
        product = get_object_or_404(Product, pk=product_pk)
    else:
        product = None

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        product_form = ProductForm(request.POST, instance=product)
        if product_form.is_valid():
             product = product_form.save()
             messages.success(request, str(product) + " was saved")
             if product_pk:
                 return redirect(reverse('dashboard:product-view', args=[product.pk]))		# we are editing, so don't show the item list

             if product_form.cleaned_data.get("create_items", False):
                 return redirect(reverse('dashboard:product-edit-items', args=[product.pk]))
             else:
                 # create a fake item underneath this product
                 item = ProductItem(product=product)				
                 item.save()

             ph = ProductHistory(item=item, quantity=0, event=ProductHistory.CREATED)
             ph.save()

             return redirect(reverse('dashboard:product-view', args=[product.pk]))
    else:  # no data sent to form, prepopulate based on what we got in the URL
        initial = {}
        if category_pk:
            category = get_object_or_404(ProductCategory, pk=category_pk)
            initial={'category':category}
        if supplier_pk:
            supplier = get_object_or_404(Supplier, pk=supplier_pk)
            initial={'supplier':supplier}

        product_form = ProductForm(initial=initial, instance=product)

    return render(request, "dashboard/product_form.html", {'product_form':product_form, 'product':product})



@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def product_edit_ajax(request, product_pk):			# This view allows the product edit page to toggle properties
    product = get_object_or_404(Product, pk=product_pk)

    v = request.POST.get("store_to")
    o = request.POST.get("on_off") == "true"
    if (v == 'hidden'):
        product.hidden = o
    elif (v == 'allow_supplier_orders'):
        product.allow_supplier_orders = o
    elif (v== 'only_buy_one'):
        product.only_buy_one = o

    product.save()
    return JsonResponse({'thank':'you'})



@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def product_view(request, product_pk=None):				# View a product in the dashboard
    product = get_object_or_404(Product, pk=product_pk)
    return render(request, "dashboard/product_view.html", {'product':product})


@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def product_analytics(request, product_pk, year=None):
    product = get_object_or_404(Product, pk=product_pk)
    now = datetime.datetime.now()

    if year == None:
        year = now.year

    monthTotal = {}
    items = {}
    grandTotal = 0
    x = 1
    for item in product.items.all():
        total = 0
        r = {}
        for month in range(1,13):
            month_abr = calendar.month_abbr[month]
            month_start = datetime.datetime(year, month, 1)
            (start_day, days_in_month) = calendar.monthrange(year, month)
            month_end = datetime.datetime(year, month, days_in_month, 23, 59, 59)
            print("Month " + str(month_abr) + " = " + str(month_start) + " - " + str(month_end))
            h = ProductHistory.objects.filter(item=item, event=ProductHistory.DISPATCHED, created__gte=month_start, created__lte=month_end).aggregate(Sum('quantity'))
            if h["quantity__sum"]:
               x = h["quantity__sum"]
            else:
               x = 0
 
            monthTotal[month_abr] = monthTotal.get(month_abr, 0) + x
            r[month_abr] = x
            total += x

        r['total'] = total
        grandTotal += total
        items[item] = r
    monthTotal['total'] = grandTotal
    
    return render(request, "dashboard/product_analytics.html", {'product':product, 'items':items, 'monthTotal':monthTotal, 'lastYear':year-1, 'nextYear':year+1, 'year':year})



@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def product_purchases(request, product_pk):				# a view to show every single purchaser of this product
    product = get_object_or_404(Product, pk=product_pk)

    items = {}
    for pi in product.items.all():
        oi = pi.ordered_items.filter(quantity_ordered__gt=0).filter(quantity_refunded__lt=F('quantity_ordered'))  # TODO: NOT FINISHED HERE!!!!!
        items[pi.pk] = (pi, oi)

    return render(request, "dashboard/product_purchases.html", {'product':product, 'items':items})



## Product Image views
@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def product_picture_create(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    if request.method == 'POST':
        form = ProductPictureForm(request.POST, request.FILES)
        if form.is_valid():
            pp = form.save(commit=False)
            pp.product = product
            pp.save()

            return redirect(reverse('dashboard:product-view', args=[product.pk]))
    else:
        form = ProductPictureForm()

    return render(request, 'dashboard/productpicture_form.html', {'form': form, 'product':product})




## Product Item Views

@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def product_edit_items(request, product_pk):			# edit/add items to an existing product
    product = get_object_or_404(Product, pk=product_pk)
    ItemFormset = inlineformset_factory(Product, ProductItem, fields=['extra_text', 'quantity_in_stock'], extra=5, can_delete=False)

    if request.method == 'POST':
        item_formset = ItemFormset(request.POST, instance=product)
        if item_formset.is_valid():
   	    # save all the items
            items = item_formset.save()					# TODO: think this formset is ending up with extra items saving
            messages.success(request, "Saved " + str(len(items)) + " items on " + str(product))

            return redirect(reverse('dashboard:product-view', args=[product.pk]))

    else:
        item_formset = ItemFormset(instance=product)

    return render(request, "dashboard/product_items_add.html", {'product':product, 'item_formset':item_formset})



@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def product_sell_now(request, item_pk):				# sell an item immediately (ish)
    item = get_object_or_404(ProductItem, pk=item_pk)

    if request.method == 'POST':
        offline_sale_form = OfflineSaleForm(request.POST)
        if offline_sale_form.is_valid():
            qty = offline_sale_form.cleaned_data["quantity"]
            if qty <= item.quantity_in_stock:				# sufficient stock to make sale
                name =  offline_sale_form.cleaned_data.get("name", "")
                if name == "":
                    name = "Offline Sale"
                order = Order(billing_name = name,
                          billing_address = offline_sale_form.cleaned_data["address"],
                          billing_postcode = offline_sale_form.cleaned_data["postcode"],
                          delivery_name = name,
                          delivery_address = offline_sale_form.cleaned_data["address"],
                          delivery_postcode = offline_sale_form.cleaned_data["postcode"],
                          email = offline_sale_form.cleaned_data["email"],
			  postage_amount = Decimal(0.0),
                          customer_notes = "")

                order.save()

                orderitem = OrderItem(item=item, 
                              order=order,
                              item_name=str(item),
                              item_price=item.product.price,
                              quantity_ordered=qty,
                              quantity_allocated=0,
                              quantity_delivered=0)

                orderitem.save()

                oh = OrderHistory(order=order, comment="Offline sale through dashboard")
                oh.save()

                Payment = get_payment_model()
                payment = Payment.objects.create(
                    order=order,
                    variant='cash',  # this is the variant from PAYMENT_VARIANTS
                    status='confirmed', 
                    description='Boldmere Bullet Shop Purchase',
                    total=order.amount_owing,
                    captured_amount=order.amount_owing,
                    tax=Decimal(0),
                    currency='GBP',
                    delivery=order.postage_amount,
                    billing_first_name=name,
                    billing_last_name='',
                    billing_address_1=order.billing_address,
                    billing_address_2='',
                    billing_city='',
                    billing_postcode=order.billing_postcode,
                    billing_country_code='UK',
                    billing_country_area='',
                    customer_ip_address=get_client_ip(request))

                orderitem.dispatch(qty) 
                messages.success(request, "Purchase was recorded")

                return redirect(reverse('dashboard:product-view', args=[item.product.pk]))
            else:
                offline_sale_form.add_error("quantity", "Cannot sell that amount")

    else:
        offline_sale_form = OfflineSaleForm()

    return render(request, "dashboard/product_sell_now.html", {'item':item, 'offline_sale_form':offline_sale_form})


## Product Category views
class CategoryList(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ProductCategory
    template_name="dashboard/productcategory_list.html"
    def test_func(self):
        return is_shop_team(self.request.user)


class CategoryCreate(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = ProductCategory
    template_name="dashboard/productcategory_form.html"
    fields = ['name', 'hidden']
    success_url = reverse_lazy('dashboard:categories')
    success_message = "%(name)s was created successfully"

    def test_func(self):
        return is_shop_team(self.request.user)


class CategoryUpdate(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = ProductCategory
    template_name="dashboard/productcategory_form.html"
    fields = ['name', 'hidden']
    success_url = reverse_lazy('dashboard:categories')
    success_message = "%(name)s was updated successfully"

    def test_func(self):
        return is_shop_team(self.request.user)


class CategoryDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ProductCategory
    template_name="dashboard/productcategory_delete.html"
    success_url = reverse_lazy('dashboard:categories')

    def test_func(self):
        return is_shop_team(self.request.user)



## Product Postage views
class PostageList(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Postage
    context_object_name = 'postage_list'
    template_name="dashboard/postage_list.html"

    def test_func(self):
        return is_shop_team(self.request.user)

class PostageCreate(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = Postage
    context_object_name = 'postage'
    template_name="dashboard/postage_form.html"
    fields = ['name', 'price']
    success_url = reverse_lazy('dashboard:postage')
    success_message = "%(name)s was created successfully"

    def test_func(self):
        return is_shop_team(self.request.user)


class PostageUpdate(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = Postage
    context_object_name = 'postage'
    template_name="dashboard/postage_form.html"
    fields = ['name', 'price']
    success_url = reverse_lazy('dashboard:postage')
    success_message = "%(name)s was updated successfully"

    def test_func(self):
        return is_shop_team(self.request.user)


class PostageDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Postage
    context_object_name = 'postage'
    template_name="dashboard/postage_delete.html"
    success_url = reverse_lazy('dashboard:postage')

    def test_func(self):
        return is_shop_team(self.request.user)





## Supplier views
class SupplierList(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Supplier
    template_name="dashboard/supplier_list.html"

    def test_func(self):
        return is_shop_team(self.request.user)


class SupplierCreate(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = Supplier
    template_name="dashboard/supplier_form.html"
    fields = ['name']
    success_url = reverse_lazy('dashboard:suppliers')
    success_message = "%(name)s was created successfully"

    def test_func(self):
        return is_shop_team(self.request.user)


class SupplierUpdate(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = Supplier
    template_name="dashboard/supplier_form.html"
    fields = ['name']
    success_url = reverse_lazy('dashboard:suppliers')
    success_message = "%(name)s was updated successfully"

    def test_func(self):
        return is_shop_team(self.request.user)


class SupplierDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Supplier
    template_name="dashboard/supplier_delete.html"
    success_url = reverse_lazy('dashboard:suppliers')

    def test_func(self):
        return is_shop_team(self.request.user)


class SupplierDetail(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Supplier
    template_name="dashboard/supplier_view.html"
    context_object_name = 'supplier'

    def test_func(self):
        return is_shop_team(self.request.user)



# receive a delivery from this supplier & update the stock levels
@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def supplier_delivery(request, supplier_pk):
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
 
    items = ProductItem.objects.filter(product__supplier=supplier)

    if request.method == 'POST':
	# validate the delivery & update stock levels
        items_count = 0
        allocations = []

        for key, value in request.POST.items():
            #print(str(key) + " - " + str(value))
            if key.startswith("product_qty_"):
                x = key[12:]
                y = int(x)
                #print(" product = " + str(y) + " qty = " + str(value))
                item = ProductItem.objects.get(pk=y)
                qty_arrived = int(value)

                allocations = item.stock_arrived(qty_arrived)
                ph = ProductHistory(item=item, quantity=qty_arrived, event=ProductHistory.RECEIVED)
                ph.save()

                items_count = items_count + qty_arrived

        messages.success(request, 'Added %d items from delivery' % (items_count,))

        return render(request, 'dashboard/supplier_delivery_allocations.html', {'supplier':supplier, 'allocations':allocations})

    return render(request, 'dashboard/supplier_delivery.html', {'supplier': supplier, 'items': items })


# create a new order for this supplier, and adjust stock levels accordingly
@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def supplier_order(request, supplier_pk):
    supplier = get_object_or_404(Supplier, pk=supplier_pk)

    items = {}
    items_qs = ProductItem.objects.filter(product__supplier=supplier).order_by('quantity_to_order')
    for item in items_qs:
        items[item.pk] = (item, item.quantity_to_order)

    if request.method == 'POST':
        mode = request.POST.get("save", "preview")
        saving = (mode == "save")
        preview = (mode == "preview")
        cancel = (mode == "cancel") 

	# validate the order & update stock levels
        items_count = 0
        preview_items = {}
        for key, value in request.POST.items():    # filter out all the stuff we don't need for this order and just give a preview of what is needed
            print(str(key) + " - " + str(value))
            if key.startswith("product_qty_"):
                x = key[12:]
                y = int(x)
                item = ProductItem.objects.get(pk=y)
                order_quantity = int(value)
                if order_quantity > 0:
                    preview_items[y] = (item, order_quantity)

                if saving:
                    allocated_in_order = min(item.quantity_to_order, order_quantity)
                    item.quantity_allocated_on_order = item.quantity_allocated_on_order + allocated_in_order
                    item.quantity_to_order = max(item.quantity_to_order - order_quantity, 0)
                    item.quantity_on_order = item.quantity_on_order + order_quantity
                    item.save()
                    items_count = items_count + order_quantity

                    ph = ProductHistory(item=item, quantity=order_quantity, event=ProductHistory.ORDERED)
                    ph.save()

        if saving:
            messages.success(request, 'Added %d items to order' % (items_count,))
            return redirect(reverse('dashboard:supplier-view', kwargs={'pk': supplier.pk}))

        elif preview:    # preview mode
            return render(request, 'dashboard/supplier_order_preview.html', {'supplier': supplier, 'items':preview_items, 'visible_boxes': False})

        else:  # must be cancel
           for pk, (item, qty) in preview_items.items():
              items[pk] = (item, qty) # only update those which were in the cancelled order
 
    return render(request, 'dashboard/supplier_order_preview.html', {'supplier': supplier, 'items': items, 'visible_boxes': True})



## Order Views

@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def order_list(request, status='all'):
    orders = Order.objects.all()

    results = []
   
    for order in orders:
        if status == 'all':
            results.append(order)
        elif status == 'paid':
            if order.fully_paid:
                results.append(order)
        elif status == 'unpaid':
            if order.fully_paid != True:
                results.append(order)
        elif status == 'outstanding':
            if order.fully_paid:
                if order.outstanding_item_count > 0:
                   results.append(order)

    orders_all = ''
    orders_unpaid = ''
    orders_paid = ''
    orders_paid_outstanding = ''

    if status == 'all':
        orders_all = 'active'
    elif status == 'paid':
        orders_paid = 'active'
    elif status == 'unpaid':
        orders_unpaid = 'active'
    elif status == 'outstanding':
        orders_paid_outstanding = 'active'
        status = "Paid (with outstanding items)"


    paginator = Paginator(results, per_page=30)
    page = request.GET.get('page')
    results_list = paginator.get_page(page)

    return render(request, 'dashboard/order_list.html', {'orders':results_list, 'order_status':status, 'orders_all':orders_all, 'orders_unpaid':orders_unpaid, 'orders_paid':orders_unpaid, 'orders_paid_outstanding':orders_paid_outstanding})
  

@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def order_comment(request, pk):						# Add a comment to the order
    order = get_object_or_404(Order, pk=pk)
    if request.POST:
        comment_form = OrderHistoryItemForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.cleaned_data["comment"]
            oh = OrderHistory(order=order, comment=comment)		# TODO: annotate with logged in user name
            oh.save()
            messages.success(request, "Comment was added")

    return redirect(reverse('dashboard:order', kwargs={'pk': order.pk}))




class OrderDetail(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Order
    template_name="dashboard/order_view.html"
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super(OrderDetail, self).get_context_data(**kwargs)
        context['form'] = OrderHistoryItemForm()
        return context

    def test_func(self):
        return is_shop_team(self.request.user)



# dispatch some items

@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def order_items_dispatch(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    if request.POST:
        override = request.POST.get("override", False)
        if (order.fully_paid != True) and (override == False):
            # the order isnt fully paid - show a warning page with the items on it, plus the details of what has been paid for
            items = {}
            for key, value in request.POST.items():
                if key.startswith("id-"):
                    orderitem_pk = int(key[3:])
                    orderitem = get_object_or_404(OrderItem, pk=orderitem_pk)
                    qty = int(value)
                    items[orderitem.pk] = qty
  
            return render(request, "dashboard/order_dispatch_unpaid.html", {'items':items, 'order':order})

        # Ok to continue with dispatching items (order is fully paid, or admin has said to override)
        for key, value in request.POST.items():    # get all the items that got sent back to us
           # print(str(key) + " - " + str(value))
            if key.startswith("id-"):
               orderitem_pk = int(key[3:])
               orderitem = get_object_or_404(OrderItem, pk=orderitem_pk)

               orderitem.dispatch(int(value))	# This has got safety checks in it.

    
        messages.success(request, 'Items were dispatched')
    return redirect(reverse('dashboard:order', kwargs={'pk': order.pk}))



# pay an order in cash if there's any balance outstanding on it
@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def order_cash_payment(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    if order.fully_paid:
        messages.info(request, "Order is already fully paid")
        return redirect(reverse('dashboard:order', kwargs={'pk': order.pk}))

    if request.POST:
        Payment = get_payment_model()
        payment = Payment.objects.create(
                order=order,
                variant='cash',  # this is the variant from PAYMENT_VARIANTS
                status='confirmed', 
                description='Boldmere Bullet Shop Purchase',
                total=order.amount_owing,
                captured_amount=order.amount_owing,
                tax=Decimal(0),
                currency='GBP',
                delivery=order.postage_amount,
                billing_first_name=order.billing_name,
                billing_last_name='',
                billing_address_1=order.billing_address,
                billing_address_2='',
                billing_city='',
                billing_postcode=order.billing_postcode,
                billing_country_code='UK',
                billing_country_area='',
                customer_ip_address=get_client_ip(request))
   
        messages.success(request, "Cash payment was added to the order")
        return redirect(reverse('dashboard:order', kwargs={'pk': order.pk}))

    return render(request, "dashboard/order_cash_payment.html", {'order': order})


# Full cancellation of order - all allocated items back to stock, and full refund of money paid in
@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def order_cancel(request, pk):			
    order = get_object_or_404(Order, pk=pk)

    if order.can_cancel != True:
        messages.info(request, "This order cannot be cancelled")
        return redirect(reverse('dashboard:order', kwargs={'pk': order.pk}))

    # also - looks like you have to refund individual payments (or all of them in turn I guess... what to do about cash?)
    if request.POST:
        for payment in order.confirmed_payments().all():
            if payment.variant == 'cash':
                messages.info(request, "You must refund " + str(order.name) + " £" + str(payment.total) + " cash")
                payment.change_status(PaymentStatus.REFUNDED)		# Have to do this manually as there's no cash variant in reality
		# TODO: change captured amount to zero?
            else:
                payment.refund()
 
        any_problems = False
        for orderitem in order.items.all():			# cancel all of the items we have waiting
            y = orderitem.cancel()
            if y:
                any_problems = True				

        order.cancelled = True
        order.save()

        oh = OrderHistory(order=order, comment="Order cancelled")
        oh.save()
      
        if any_problems:
            messages.info(request, "Some items are already on order from a supplier!")
        else:
            messages.success(request, "Order was cancelled")

        return redirect(reverse('dashboard:order', kwargs={'pk': order.pk}))


    return render(request, "dashboard/order_cancel_confirm.html", {'order': order})


@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def order_item_return(request, pk):		# Return an item from an order
    orderitem = get_object_or_404(OrderItem, pk=pk)
    
    if request.POST:	
        rif = ReturnItemForm(request.POST, orderitem=orderitem)
        if rif.is_valid():
		# process the return
            amount = rif.cleaned_data["quantity"]
            if amount > 0 and amount <= orderitem.quantity_delivered:
                refund_amount = (orderitem.item_price * amount)
                print("Need to refund " + str(refund_amount))
                orderitem.refund(amount)		# return the items to stock
		
		# refund the requsite sum (refund_amount) - refund successful payments until we've paid back what we owe
                refunded_amount = Decimal(0.00)
                for payment in orderitem.order.confirmed_payments().all():
                    if refunded_amount >= refund_amount:
                        print("Have refunded enough!")
                        break; # we have refunded enough!

                    x = payment.captured_amount
                    print("Found a payment of " + str(x))
                    left_to_refund = refund_amount - refunded_amount
                    print("there is " + str(left_to_refund) + " left to refund")
                    if left_to_refund < x:
                        x = left_to_refund

                    if payment.variant == 'cash':
                        messages.info(request, "You must refund " + str(orderitem.order.name) + " £" + str(x) + " cash")
                        payment.change_status(PaymentStatus.REFUNDED)		# Have to do this manually as there's no cash variant in reality
                    else:
                        payment.refund(amount=x)		# do genuine refund via Paypal etc.
                        messages.success(request, "£" + str(x) + " was refunded")

                    refunded_amount += x
                    print("Have now refunded " + str(refunded_amount))

                m = str(amount) + " x " + str(orderitem.item_name) + " was successfully returned"
                messages.success(request, m)

                return redirect(reverse('dashboard:order', kwargs={'pk': orderitem.order.pk}))
            else:
                messages.warning(request, "Cannot return " + str(amount) + " of " + str(orderitem.item_name) + " - must be between 1 and " + str(orderitem.quantity_delivered))
    else:
        rif = ReturnItemForm(orderitem=orderitem)

    cash = False
    for payment in orderitem.order.confirmed_payments().all():
        if payment.variant == 'cash':
            cash = True						# BUG: UI vs code inconsistency
    return render(request, "dashboard/order_return_item.html", {'orderitem': orderitem, 'form':rif, 'cash':cash})



# Product allocations
@login_required
@user_passes_test(is_shop_team, login_url="/") # are they in the shop team group?
def allocations(request, order_by='name', item_pk=None):
    ordering = 'pk'	# default for item
    if order_by == 'date':
        ordering = 'order__created'
    elif order_by == 'order':
        ordering = 'order__pk'
    elif order_by == 'name':
        ordering = 'order__delivery_name'

    allocations = OrderItem.objects.order_by(ordering).filter(quantity_allocated__gt=0)

    return render(request, "dashboard/allocations.html", {'allocations':allocations, 'order_by':order_by})


