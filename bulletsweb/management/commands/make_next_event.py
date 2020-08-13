from django.core.management.base import BaseCommand, CommandError

from bulletsweb.models import Leader, BulletEvent, Availability, EventSpeed, DefaultSpeedGroup
from bulletsweb.leaders import send_leaders_an_email_about_event

import datetime

class Boss(object):
	name = ""
	email = ""

class Command(BaseCommand):
    help = 'Creates the next event for the Boldmere Bullets'

    def add_arguments(self, parser):
        parser.add_argument('event-type', choices=['run', 'ride', 'both'], help="which type of event to create")
        parser.add_argument('--email', dest='email', default=False, help="send email to leaders about this event", action="store_true")
        parser.add_argument('--delete', dest='delete', help="delete events of this type older than this many days", type=int)



    def make_event(self, event_type, email):
        self.stdout.write(self.style.SUCCESS('Creating a new ' + event_type))
	
        boss = Boss()

        if (event_type == 'run'):
            speeds = DefaultSpeedGroup.objects.filter(group_type=DefaultSpeedGroup.RUN)	
            day_count = 6	# Sunday = 5
            boss.name = "Jonny"
            boss.email = "jonny@boldmerebullets.com"
            running_event = True
            cycling_event = False
        else:
            speeds = DefaultSpeedGroup.objects.filter(group_type=DefaultSpeedGroup.RIDE)
            day_count = 5	# Saturday = 5
            boss.name = "Jon"
            boss.email = "jon@boldmerebullets.com"
            running_event = False
            cycling_event = True

        t = datetime.date.today()
        days_ahead = (7 * 5)
        m = datetime.timedelta(((day_count - t.weekday()) % 7) + days_ahead)	

        event_date = t + m 

        e, created = BulletEvent.objects.get_or_create(date=event_date, running_event=running_event, cycling_event=cycling_event)

        if created:
            e.have_sent_initial_email = True
            e.save()
	
            for s in speeds:
                if ((s.name != "") and (s.name != None)):		# squash blanks
                    es, created_two = EventSpeed.objects.get_or_create(name=s.name, display_order=s.display_order, event=e)
				
            if email:   
                self.stdout.write(self.style.SUCCESS('Sending emails!'))

                who_to_send_to = Leader.objects.filter(email_preference=True)		
                event_list = [e]

                x = send_leaders_an_email_about_event(boss, who_to_send_to, "emails/leaders-new-event", event_list)

                self.stdout.write(self.style.SUCCESS('Sent ' + str(x) + " emails"))

            self.stdout.write(self.style.SUCCESS('Created event with ID = ' + str(e.id)))
        else:
            self.stdout.write(self.style.WARNING('Event already exists on that day and time'))



    def handle(self, *args, **options):
        event_type = options['event-type']
        email = options['email']
        delete_events = options['delete']
   
        cycling_event = False
        running_event = False	

        if (event_type == 'both'):
            self.make_event('run', email)
            self.make_event('ride', email)
            cycling_event = True
            running_event = True
        else:
            self.make_event(event_type, email)
            if event_type == "run": 
                running_event = True
            else:
                cycling_event = True


        if delete_events:
            t = datetime.date.today()
            d = datetime.timedelta(days=delete_events)
            search_before = t + d	
            events = BulletEvent.objects.filter(date__lt=search_before, cycling_event=cycling_event, running_event=running_event)
            self.stdout.write(self.style.SUCCESS("Deleting " + str(events.count()) + " " + event_type + " events dated before " + str(search_before)))
            events.delete()

