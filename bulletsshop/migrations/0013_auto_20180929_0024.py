# Generated by Django 2.1.1 on 2018-09-28 23:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bulletsshop', '0012_auto_20180928_2314'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='address',
        ),
        migrations.RemoveField(
            model_name='order',
            name='name',
        ),
        migrations.RemoveField(
            model_name='order',
            name='postcode',
        ),
        migrations.AddField(
            model_name='order',
            name='billing_address',
            field=models.TextField(blank=True, verbose_name='Billing Address'),
        ),
        migrations.AddField(
            model_name='order',
            name='billing_name',
            field=models.CharField(default='', max_length=500, verbose_name='Billing Name'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='billing_postcode',
            field=models.CharField(default='', max_length=8, verbose_name='Billing Postcode'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_address',
            field=models.TextField(blank=True, verbose_name='Delivery Address'),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_name',
            field=models.CharField(default='', max_length=500, verbose_name='Delivery Name'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_postcode',
            field=models.CharField(default='', max_length=8, verbose_name='Delivery Postcode'),
            preserve_default=False,
        ),
    ]
