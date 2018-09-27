from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
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
from django.db.models import Q, Sum
from django.urls import reverse_lazy, reverse

from django.contrib.sites.models import Site

from django.forms import formset_factory
from django.forms import inlineformset_factory

# Python imports 
#from datetime import timedelta
import datetime
import uuid
import random
import os

from .models import Product, ProductCategory, Supplier, ProductItem, ProductPicture, Order, OrderItem, Basket, BasketItem
from .forms import ProductForm, ItemForm, ProductPictureForm, OrderHistoryItemForm, ShopProductForm


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

    request.session['basket'] = basket.id

    return basket




def index(request):
    return render(request, "shop/index.html", {})

# TODO: add basket as extra context to these views
## Product views
class ShopProductList(ListView):
    model = Product
    template_name="shop/product_list.html"
    context_object_name = 'products'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context['basket'] = get_basket(self.request)
        return context



# Main view for looking at a product
def ShopProduct(request, product_pk, slug):
    product = get_object_or_404(Product, pk=product_pk, slug=slug)
    basket = get_basket(request)              

    if request.POST:
        product_form = ShopProductForm(request.POST, product=product)
        if product_form.is_valid():
            # add to basket
            item = product_form.cleaned_data['item']
            qty = product_form.cleaned_data['quantity']
            # TODO: so much stuff to do here to keep things sane!
            basket_item, created = BasketItem.objects.get_or_create(basket=basket, item=item, defaults={'quantity':qty})
            if created:
                messages.success(request, str(item) + " was added to your basket")
            else:
                basket_item.quantity = basket_item.quantity + qty
                basket_item.save()
                messages.success(request, str(item) + " - quantity updated in basket")
            
    # reset product form - might need to reload product here? TODO: check! or should we just redirect to the basket?
    product_form = ShopProductForm(product=product)
 
    return render(request, "shop/product_view.html", {'product_form':product_form, 'product':product, 'basket':basket})


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




    return render(request, "shop/basket.html", {'basket':basket})




########## DASHBOARD VIEWS #####################

#TODO: AUTH
def dashboard(request):
    return render(request, "dashboard/index.html", {})


## Product views
class ProductList(ListView):
    model = Product
    template_name="dashboard/product_list.html"

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
             if product_form.cleaned_data.get("create_items", False):
                 return redirect(reverse('dashboard:product-edit-items', args=[product.pk]))
             else:
                 # create a fake item underneath this product
                 item = ProductItem(product=product)
                 item.save()

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



def product_view(request, product_pk=None):
    product = get_object_or_404(Product, pk=product_pk)

    return render(request, "dashboard/product_view.html", {'product':product})


## Product Image views

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

    print(str(form))
    return render(request, 'dashboard/productpicture_form.html', {'form': form, 'product':product})




## Product Item Views

def product_edit_items(request, product_pk):			# edit/add items to an existing product
    product = get_object_or_404(Product, pk=product_pk)
    ItemFormset = inlineformset_factory(Product, ProductItem, fields=['extra_text', 'quantity_in_stock'], extra=5, can_delete=False)

    if request.method == 'POST':
        item_formset = ItemFormset(request.POST, instance=product)
        if item_formset.is_valid():
   	    # save all the items
            items = item_formset.save()
            messages.success(request, "Saved " + str(len(items)) + " items on " + str(product))

            return redirect(reverse('dashboard:product-view', args=[product.pk]))

    else:
        item_formset = ItemFormset(instance=product)

    return render(request, "dashboard/product_items_add.html", {'product':product, 'item_formset':item_formset})




## Product Category views
class CategoryList(ListView):
    model = ProductCategory
    template_name="dashboard/productcategory_list.html"

class CategoryCreate(SuccessMessageMixin, CreateView):
    model = ProductCategory
    template_name="dashboard/productcategory_form.html"
    fields = ['name', 'hidden']
    success_url = reverse_lazy('dashboard:categories')
    success_message = "%(name)s was created successfully"

class CategoryUpdate(SuccessMessageMixin, UpdateView):
    model = ProductCategory
    template_name="dashboard/productcategory_form.html"
    fields = ['name', 'hidden']
    success_url = reverse_lazy('dashboard:categories')
    success_message = "%(name)s was updated successfully"

class CategoryDelete(DeleteView):
    model = ProductCategory
    template_name="dashboard/productcategory_delete.html"
    success_url = reverse_lazy('dashboard:categories')



## Supplier views
class SupplierList(ListView):
    model = Supplier
    template_name="dashboard/supplier_list.html"

class SupplierCreate(SuccessMessageMixin, CreateView):
    model = Supplier
    template_name="dashboard/supplier_form.html"
    fields = ['name']
    success_url = reverse_lazy('dashboard:suppliers')
    success_message = "%(name)s was created successfully"

class SupplierUpdate(SuccessMessageMixin, UpdateView):
    model = Supplier
    template_name="dashboard/supplier_form.html"
    fields = ['name']
    success_url = reverse_lazy('dashboard:suppliers')
    success_message = "%(name)s was updated successfully"

class SupplierDelete(DeleteView):
    model = Supplier
    template_name="dashboard/supplier_delete.html"
    success_url = reverse_lazy('dashboard:suppliers')

class SupplierDetail(DetailView):
    model = Supplier
    template_name="dashboard/supplier_view.html"
    context_object_name = 'supplier'


# receive a delivery from this supplier & update the stock levels
def supplier_delivery(request, supplier_pk):
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
 
    items = ProductItem.objects.filter(product__supplier=supplier)

    if request.method == 'POST':
	# validate the delivery & update stock levels
	# TODO: more workflow here about allocation
        items_count = 0
        for key, value in request.POST.items():
            #print(str(key) + " - " + str(value))
            if key.startswith("product_qty_"):
                x = key[12:]
                y = int(x)
                #print(" product = " + str(y) + " qty = " + str(value))
                item = ProductItem.objects.get(pk=y)
                qty_arrived = int(value)

                to_allocate = min(qty_arrived, item.quantity_allocated_on_order) 	# how many do we have to allocate?
                spare = max(0, qty_arrived - to_allocate)				# what's left from the order after allocations?

                item.quantity_on_order = max(0, item.quantity_on_order - qty_arrived)	# can't go below zero on this
                item.quantity_allocated_on_order = item.quantity_allocated_on_order - to_allocate  # this can't be above the amount we are tracking
                item.quantity_allocated = item.quantity_allocated + to_allocate
                item.quantity_in_stock = item.quantity_in_stock + spare
                
                item.save()

                items_count = items_count + qty_arrived

        messages.success(request, 'Added %d items from delivery' % (items_count,))

        return redirect(reverse('dashboard:supplier-view', kwargs={'pk': supplier.pk}))

    return render(request, 'dashboard/supplier_delivery.html', {'supplier': supplier, 'items': items })


# create a new order for this supplier, and adjust stock levels accordingly
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
class OrderList(ListView):
    model = Order
    template_name="dashboard/order_list.html"
    context_object_name = 'orders'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context['order_status'] = "All"
        return context


class PaidOrderList(ListView):
    queryset = Order.objects.filter(status=Order.STATUS_PAID)
    template_name="dashboard/order_list.html"
    context_object_name = 'orders'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context['order_status'] = "Fully Paid"
        return context



class OrderDetail(DetailView):
    model = Order
    template_name="dashboard/order_view.html"
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super(OrderDetail, self).get_context_data(**kwargs)
        context['form'] = OrderHistoryItemForm()
        return context
