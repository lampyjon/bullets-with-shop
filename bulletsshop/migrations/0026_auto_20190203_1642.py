# Generated by Django 2.1.5 on 2019-02-03 16:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bulletsshop', '0025_auto_20190203_1620'),
    ]

    operations = [
        migrations.AddField(
            model_name='basket',
            name='voucher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='bulletsshop.Voucher'),
        ),
        migrations.AddField(
            model_name='order',
            name='voucher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='bulletsshop.Voucher'),
        ),
    ]
