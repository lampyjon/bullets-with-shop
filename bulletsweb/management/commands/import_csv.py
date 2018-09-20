from django.core.management.base import BaseCommand, CommandError
from bullets.models import ActivityCache
from django.conf import settings
import csv
from storages.backends.s3boto import S3BotoStorage
import codecs


class CSVStorage(S3BotoStorage):
    bucket_name = settings.CSVFILE_BUCKET_NAME
    location = settings.CSVFILE_LOCATION
    default_acl = 'private'


class Command(BaseCommand):
    help = 'Import the old CSV file into our database'

    def handle(self, *args, **options):
        self.stdout.write("Importing the old Strava cache...")

        x = CSVStorage()
        row_count = 0
        added = 0
        skipped = 0

        with x.open("activities.csv", 'rt') as csvfile:
            self.stdout.write("opened file")
            reader = csv.DictReader(codecs.iterdecode(csvfile, 'utf-8'))
            self.stdout.write("created reader")
            for row in reader:
       #             self.stdout.write("processing %s - %s - %s - %s" % (row['activity_id'],row['activity_type'], row['distance'],row['start_date']))
                    obj, created = ActivityCache.objects.get_or_create(
                                activity_id=row['activity_id'], 
                                activity_type=row['activity_type'], 
                                defaults={
                                        'distance': int(row['distance']),
                                        'start_date': row['start_date'],
                                        })

                    if created:
                        added = added + 1	
                    else:
                        skipped = skipped + 1
                    row_count = row_count + 1

        self.stdout.write("Read in " + str(row_count) + " rows from S3 CSV")
        self.stdout.write("Added " + str(added) + " activities, and skipped " + str(skipped))

