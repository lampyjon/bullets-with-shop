from django.core.management.base import BaseCommand, CommandError
from bulletsweb.models import Bullet
from django.conf import settings
import csv
import codecs
from django.utils import timezone

# Bullet
#    name = models.CharField("name", max_length=200)
#    email = models.EmailField('email address', max_length=200)
#    date_added = models.DateField("date created", auto_now_add=True)
#    email_checked = models.DateField("date email confirmed", blank=True, null=True)
#    email_check_ref = models.UUIDField("random uuid for email confirmation", default=uuid.uuid4, editable=False)
#    postcode = models.CharField('first part of postcode', max_length=5)	
#    contact_no = models.CharField('contact number', max_length=100)
#    over_18 = models.BooleanField('over 18', help_text='Please confirm that you are over 18?')
#    get_emails = models.BooleanField("happy to receive emails", help_text='Can we contact you regarding Collective events?')
#    voting_ref = models.UUIDField("random uuid for voting", default=uuid.uuid4, editable=False, blank=True, null=True)		# URL for charity of the year 2017



class Command(BaseCommand):
    help = 'Import the old user CSV file into our database'

    def add_arguments(self, parser):
        parser.add_argument('csvname', help="File to load")
        parser.add_argument(
            '--oldformat',
            action='store_true',
            help='Old format of CSV file'
        )
    def handle(self, *args, **options):
        csvname = options['csvname']
        self.stdout.write("Importing the old user file: " + str(csvname))

        row_count = 0
        added = 0
        skipped = 0



        with open(csvname, 'rt') as csvfile:
            self.stdout.write("opened file")
            reader = csv.DictReader(csvfile)
            self.stdout.write("created reader")
            for row in reader:
                if options["oldformat"]:
                    if row["email_checked"] == 'true':
                        ec = row["joined"]
                    else:
                        ec = None
                else:
                    if row["email_checked"] == "":
                        ec = None
                    else:
                        ec = row["email_checked"]

                obj, created = Bullet.objects.get_or_create(name=row["name"], email=row["email"], postcode=row["postcode"], over_18=row["over_18"]=='true', get_emails=row["get_emails"]=='true', contact_no=row["contact_no"], email_checked=ec)
                self.stdout.write("Created " + str(obj))

#	SELECT name, email, joined, email_checked, email_check_ref, postcode, contact_no, over_18, get_emails, voting_ref FROM bullets_oldbullet;
# 	SELECT name, email, date_added, email_checked, email_check_ref, postcode, contact_no, over_18, get_emails, voting_ref FROM bullets_bullet;

