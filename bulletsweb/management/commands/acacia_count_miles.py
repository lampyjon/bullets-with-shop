from django.core.management.base import BaseCommand, CommandError
from bullets.models import BigBulletRider, BigBulletRide

from stravalib.client import Client
from stravalib import unithelper
from django.conf import settings

from datetime import timedelta, datetime
from django.utils import timezone
import dateutil.parser

from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Update how many miles ridden and run for Acacia' 		

    def handle(self, *args, **options):
        self.stdout.write("Updating the Acacia event miles")
       
        client = Client()
        rides_after = datetime(2018, 9, 1)
        rides_before = datetime(2018, 9, 3)

        participants = BigBulletRider.objects.exclude(access_token__isnull=True)
        for particpant in participants:
            self.stdout.write("Looking up activities for " + str(particpant.name))

            client.access_token = particpant.access_token
            activities = client.get_activities(before=rides_before, after=rides_after)

            for activity in activities:
                km = unithelper.kilometers(activity.distance).num
                self.stdout.write("Got activity " + str(activity.id) + " distance = " + str(km) + " = " + str(activity))
                ride, created = BigBulletRide.objects.get_or_create(activity_id = activity.id, bullet = particpant, distance = km, start_date = activity.start_date)
                self.stdout.write("Created = " + str(created))


