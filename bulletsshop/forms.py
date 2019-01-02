from django import forms
from django.forms import ModelForm
from .models import Product, ProductItem, ProductPicture, Order
from django_summernote.widgets import SummernoteWidget, SummernoteInplaceWidget
from captcha.fields import ReCaptchaField
import datetime




class ProductForm(ModelForm):
    available_from = forms.DateField(widget=forms.DateInput(format = '%d-%m-%Y', attrs={'class': 'datepicker'},), input_formats=('%d-%m-%Y',), initial=datetime.date.today)
    available_until = forms.DateField(widget=forms.DateInput(format = '%d-%m-%Y', attrs={'class': 'datepicker'},), input_formats=('%d-%m-%Y',), required=False )
 
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'hidden', 'available_from', 'available_until', 'category', 'supplier', 'allow_supplier_orders', 'postage_option', 'postage_amount', 'only_buy_one']

        widgets = {
      #      'available_from': forms.DateInput(attrs={'class': 'datepicker'}, input_formats=('%d/%m/%Y',)),
      #      'available_until': forms.DateInput(attrs={'class': 'datepicker'},input_formats=('%d/%m/%Y',)),
            'description': SummernoteInplaceWidget(),
        }

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        p = ('%d-%m-%Y','%Y-%m-%d')
        self.fields['available_from'].input_formats=(p)
        self.fields['available_until'].input_formats=(p)

        if kwargs["instance"] == None:		# Add an extra button if this is not a form bound to an existing object 
            self.fields.update({
                'create_items': forms.BooleanField(label="Create sizes/colours/etc. for this product?", initial=True, required=False),
                 })
 

class ItemForm(ModelForm):
    class Meta:
        model = ProductItem
        fields = ['extra_text', 'quantity_in_stock']
 

class ProductPictureForm(ModelForm):
    class Meta:
        model = ProductPicture
        fields = ['image']


class OrderHistoryItemForm(forms.Form):
    comment = forms.CharField(required=False)




# Customer facing forms

class ShopProductForm(forms.Form):
   quantity = forms.IntegerField(min_value=0, max_value=50, initial=1)
   item = forms.ModelChoiceField(queryset=None, empty_label=None)
   
   def __init__(self, *args, **kwargs):
       product = kwargs.pop("product")
       super(ShopProductForm, self).__init__(*args, **kwargs)

       if (product.no_options):
		# add a hidden field with the only item's ID in it?
           self.fields['item'].queryset = product.items
           self.fields['item'].initial = product.items.first()
           self.fields['item'].widget = forms.HiddenInput()

       else:
		# multiple items to display
           self.fields['item'].queryset = product.items
      

class OrderFormPostage(forms.Form):
    def __init__(self, *args, **kwargs):
        basket = kwargs.pop("basket", None)

        super(OrderFormPostage, self).__init__(*args, **kwargs)

        if basket:
            postage = basket.max_postage()
            postage_required = basket.must_post
        
            if postage:  # add a field to show the postage amount
                postages = [(postage.price, '£' + str(postage.price) + " - " + str(postage.name))]
                if postage_required != True:
                    postages.append((0, '£0.00 - collect for free'))

                self.fields.update({
                    'postage_amount': forms.ChoiceField(label="Postage", choices=postages),
                     })



class OrderFormBillingAddress(forms.Form):
    email = forms.EmailField(label="Email")
    billing_name = forms.CharField(label="Your name", max_length=500)
    billing_address= forms.CharField(label="Address", widget=forms.Textarea(attrs={'rows':4}))
    billing_postcode = forms.CharField(label="Postcode", max_length=8)

    def __init__(self, *args, **kwargs):
        basket = kwargs.pop("basket", None)

        super(OrderFormBillingAddress, self).__init__(*args, **kwargs)

        if basket:
            self.fields["billing_name"].initial = basket.billing_name
            self.fields["billing_address"].initial = basket.billing_address
            self.fields["billing_postcode"].initial = basket.billing_postcode
            self.fields["email"].initial = basket.email
           
            if basket.postage_amount > 0:
                self.fields.update({
                    'same_delivery_address': forms.BooleanField(label="Same delivery and billing address?", initial=True, required=False),
                     })



class OrderFormDeliveryAddress(forms.Form):
    delivery_name = forms.CharField(label="Name", max_length=500)
    delivery_address= forms.CharField(label="Address", widget=forms.Textarea(attrs={'rows':4}))
    delivery_postcode = forms.CharField(label="Postcode", max_length=8)

# TODO set initial based on basket contents

