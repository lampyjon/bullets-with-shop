# Generated by Django 2.2 on 2019-11-03 20:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bulletsshop', '0026_auto_20190203_1642'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ['name']},
        ),
    ]