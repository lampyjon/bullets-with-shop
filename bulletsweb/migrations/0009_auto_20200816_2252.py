# Generated by Django 3.1 on 2020-08-16 21:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bulletsweb', '0008_bulletevent_have_sent_initial_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='availability',
            name='leading',
            field=models.BooleanField(default=None, null=True),
        ),
    ]
