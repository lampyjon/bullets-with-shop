# Generated by Django 2.1.1 on 2018-09-29 11:03

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bulletsshop', '0013_auto_20180929_0024'),
    ]

    operations = [
        migrations.AddField(
            model_name='basket',
            name='billing_address',
            field=models.TextField(blank=True, verbose_name='Billing Address'),
        ),
        migrations.AddField(
            model_name='basket',
            name='billing_name',
            field=models.CharField(blank=True, max_length=500, verbose_name='Billing Name'),
        ),
        migrations.AddField(
            model_name='basket',
            name='billing_postcode',
            field=models.CharField(blank=True, max_length=8, verbose_name='Billing Postcode'),
        ),
        migrations.AddField(
            model_name='basket',
            name='delivery_address',
            field=models.TextField(blank=True, verbose_name='Delivery Address'),
        ),
        migrations.AddField(
            model_name='basket',
            name='delivery_name',
            field=models.CharField(blank=True, max_length=500, verbose_name='Delivery Name'),
        ),
        migrations.AddField(
            model_name='basket',
            name='delivery_postcode',
            field=models.CharField(blank=True, max_length=8, verbose_name='Delivery Postcode'),
        ),
        migrations.AddField(
            model_name='basket',
            name='email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Email'),
        ),
        migrations.AddField(
            model_name='basket',
            name='postage_amount',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5, verbose_name='Postage'),
        ),
    ]