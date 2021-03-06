# Generated by Django 2.1.4 on 2019-01-13 17:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bulletsshop', '0020_producthistory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producthistory',
            name='event',
            field=models.CharField(choices=[('c', 'Created'), ('d', 'Dispatched to customer'), ('o', 'Ordered from supplier'), ('r', 'Received from supplier'), ('x', 'Refunded')], default='c', max_length=1, verbose_name='Event'),
        ),
    ]
