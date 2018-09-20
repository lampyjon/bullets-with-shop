from django.core.management.base import BaseCommand, CommandError
from bulletsweb.models import ActivityCache

from stravalib.client import Client
from stravalib import unithelper
from django.conf import settings

from datetime import timedelta, datetime
from django.utils import timezone
import dateutil.parser

from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Update the Strava Cache'


    def insert_into_db(self, activities, activity_type):
        added = 0
        skipped = 0
        for activity in activities:
            obj, created = ActivityCache.objects.get_or_create(activity_type=activity_type, distance = unithelper.miles(activity.distance).num, name=activity.name, athlete=activity.athlete)		
            if created:
                added = added + 1	
            else:
                skipped = skipped + 1
			
        self.stdout.write("Added " + str(added) + " activities, and skipped " + str(skipped))

	
 		

    def handle(self, *args, **options):
        settings_obj = Site.objects.get_current().settings

        self.stdout.write("Updating the Strava cache...")
        if settings.STRAVA_ACCESS_TOKEN == None:
            self.stdout.write("You must set STRAVA_ACCESS_TOKEN")
            return

        client = Client()
        client.access_token = settings.STRAVA_ACCESS_TOKEN

        if settings.STRAVA_CYCLING_CLUB != 0:
            cycling_club = client.get_club(settings.STRAVA_CYCLING_CLUB)
            self.stdout.write("Got this many cyclists = " + str(cycling_club.member_count))
            settings_obj.cyclists = cycling_club.member_count
            
            self.stdout.write("Getting cycling activities")
            cycling_activities = client.get_club_activities(settings.STRAVA_CYCLING_CLUB)	# Just get all of them, database can dedupe
            self.insert_into_db(cycling_activities, ActivityCache.RIDE)

        if settings.STRAVA_RUNNING_CLUB != 0:
            running_club = client.get_club(settings.STRAVA_RUNNING_CLUB)
            self.stdout.write("Got this many runners = " + str(running_club.member_count))
            settings_obj.runners = running_club.member_count

            self.stdout.write("Getting running activities")
            running_activities = client.get_club_activities(settings.STRAVA_RUNNING_CLUB)
            self.insert_into_db(running_activities, ActivityCache.RUN)

        settings_obj.save()


