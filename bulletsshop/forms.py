from django import forms
from django.forms import ModelForm
from .models import Product, ProductItem 
from django_summernote.widgets import SummernoteWidget, SummernoteInplaceWidget
from captcha.fields import ReCaptchaField
import datetime




class ProductForm(ModelForm):
    available_from = forms.DateField(widget=forms.DateInput(format = '%d-%m-%Y', attrs={'class': 'datepicker'},), input_formats=('%d-%m-%Y',), initial=datetime.date.today)
    available_until = forms.DateField(widget=forms.DateInput(format = '%d-%m-%Y', attrs={'class': 'datepicker'},), input_formats=('%d-%m-%Y',), required=False )
 
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'hidden', 'available_from', 'available_until', 'category', 'supplier', 'allow_supplier_orders', 'postage_required', 'only_buy_one']

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
 

