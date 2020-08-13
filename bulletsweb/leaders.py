# View Functions for the Leaders application

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django import forms
from django.core.exceptions import ObjectDoesNotExist

from django.contrib.auth.decorators import login_required, user_passes_test

from .models import Leader, BulletEvent, Availability, DefaultSpeedGroup, EventSpeed, Bullet
from .utils import is_leaders_team, send_bullet_mail

from django.contrib import messages
from django.utils import timezone

import datetime

from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView

from django.contrib.messages.views import SuccessMessageMixin

from django.db.models import Count
from django.core import mail
from django.utils.html import strip_tags
from django.template.loader import render_to_string

from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin

# Decorator functions

# check if this person is a legitimate leader. 
def leader_required(function=None):
    def _dec(view_func):
        def _view(request, *args, **kwargs):
            leader = request.session.get("leader", None)
            
            if leader == None:
                messages.error(request, "You need to be logged in to access this page!")
                request.session["next"] = request.get_full_path()
                return redirect('leaders:start')
            else:    # they've logged in ok, let them through
                l = Leader.objects.get(pk=leader)
                l.last_login = timezone.now()		# update the 'login' time
                l.save()
                return view_func(request, *args, **kwargs)

        _view.__name__ = view_func.__name__
        _view.__dict__ = view_func.__dict__
        _view.__doc__ = view_func.__doc__

        return _view

    if function is None:
        return _dec
    else:
        return _dec(function)






# Views

# initial login page			# TODO: add recatchpa 
def leaders_start(request):
    form = LeaderForm(request.POST)
    request.session.set_expiry(0)		# 'logout' after browser close

    if "leader" in request.session:		# they are already logged in
        return redirect('leaders:view')
            
    if form.is_valid():
        try:
            l = Leader.objects.get(bullet__email__iexact=form.cleaned_data['email'])
            request.session["leader"] = l.pk			# stash their ID in the session

            redirect_url = request.session.get('next')        # do we need to redirect them somewhere?
            if redirect_url is not None:
                del request.session["next"]
                return redirect(redirect_url)
            else:
                return redirect('leaders:view')			# if no redirect, go to the generic view

        except ObjectDoesNotExist:
            form.add_error(None, 'Could not find your email address in the system')
    else:
        form = LeaderForm()

    return render(request, 'leaders/leader.html', {'form': form})


# log out and clear session variables
def logout(request):
    if "next" in request.session:
        del request.session["next"]
    if "leader" in request.session:
        del request.session["leader"]

    messages.info(request, "You have been logged out")
    
    return redirect('index')
    


@leader_required
def leaders_view(request):        # this is the main page leaders see - the next 10 events, and ability to say they're leading them
    l = get_object_or_404(Leader, pk=request.session.get('leader'))

    next_ten_events = l.get_next_events()[:10]

    avail = []
    for x in next_ten_events:
        a, created = Availability.objects.get_or_create(leader_id=l.pk, event_id=x.pk)
        avail.append((x, a))     

    return render(request, 'leaders/leader-detail.html', {'avail':avail, 'leader':l,})


@leader_required
def view_single_event(request, event_id):    # used to view one event - cut down view. Used in emails.    
    l = get_object_or_404(Leader,  pk=request.session.get('leader'))
    e = get_object_or_404(BulletEvent, pk=event_id)
    a, created = Availability.objects.get_or_create(leader_id=l.pk, event_id=e.pk)

    avail = [(e, a)]
    
    return render(request, 'leaders/leader-detail.html', {'avail':avail, 'leader':l, 'single_event':e})



@leader_required
def preferences(request):    # rendering a leader's preferences is fairly simple!
    l = get_object_or_404(Leader,  pk=request.session.get('leader'))
    return render(request, 'leaders/preferences.html', {'leader':l, })
    

@leader_required
def preferences_save(request):        # used to save changes to preferences
    leader = get_object_or_404(Leader, pk=request.session.get('leader'))

    leader.email_preference = False
    emailPref= request.POST.get('emailPref','off')
    if emailPref == 'on':
        leader.email_preference = True
    

    if leader.rider:    
        show_sat = request.POST.get('showSat', "off")
        leader.show_sat_rides = (show_sat == "on")

        show_sun = request.POST.get('showSun', "off")
        leader.show_sun_rides = (show_sun == "on")


    leader.save()

    messages.success(request, "Saved changes!")    
    
    return  redirect('leaders:view')



# DOESN'T NEED DECORATOR - used in email links
def set_email_preference_off(request, pk):
    l = get_object_or_404(Leader, pk=pk)
    l.email_preference = False
    l.save()

    messages.success(request, "You will not get any more emails from this site!")    
    
    return go_to_leader(request, pk)
    


# DOESN'T NEED DECORATOR - used in email links
def leader_event_view_set(request, leader_id, event_id, speed_id=None):
    avail, created = Availability.objects.get_or_create(leader_id=leader_id, event_id=event_id)

    avail.speed_options.clear()     # clear out previous submissions
    if (speed_id != None):
        avail.leading = True    # They've said they'll come

        speed = get_object_or_404(EventSpeed, pk=speed_id)
        avail.speed_options.add(speed)    # add the speed they said to the set
    else:
        avail.leading = False

    avail.save()

    messages.success(request, "Your availability choice was saved!")
    # stick the leader ID into the cookie
                        
    return go_to_leader(request, leader_id)


# DOESN'T NEED DECORATOR - used in email links
def leader_event_view_no(request, leader_id, event_id):    # set to 'not leading'
    return leader_event_view_set(request, leader_id, event_id, None)


# no decorator required - this redirects us to the main leader page if we know the leader_id
def go_to_leader(request, leader_id):
    request.session["leader"] = leader_id
    
    l = Leader.objects.get(pk=leader_id)
    l.last_login = datetime.datetime.now()
    l.save()

    return redirect(reverse('leaders:view'))




@leader_required
def leaders_save(request):        # this is where we go when the leader clicks 'save' on their main page
    leader = get_object_or_404(Leader, pk=request.session.get('leader'))        

    results = []
    rides = {}

    x = request.POST.getlist("events", [])

    for event in x:
        key = "es-" + event
        speeds = request.POST.getlist(key, [])

        t = int(key[3:])        
 
        avail = get_object_or_404(Availability, pk=t)
        avail.speed_options.clear()    # Clear out old speed settings
                
        if speeds == []:
            # indecisive
            avail.leading = None    

        elif "no" in speeds:
            # they're not coming - set to False
            avail.leading = False
        else:
            # set some speeds
            avail.leading = True
            # add all the speeds in the speeds[] to avail many-to-many link with speed groups
            for s in speeds:
                avail.speed_options.add(s)            

        avail.save()

    # leader.save()

    messages.success(request, "Saved changes!")    
    
    return redirect('leaders:view')



######################################################
###           Leader Admin views                  ####
######################################################



def boss_to_leader(request):				# TODO: check that email address matches + reject otherwise?
    try:
        l = Leader.objects.get(bullet__email__iexact=request.user.email)   # Leader who the admin auth thinks we are                 
        request.session["leader"] = l.pk
        return l
    except ObjectDoesNotExist:
         return None


@leader_required
@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group?    
def boss_view(request):
    leader = boss_to_leader(request)
    if leader == None:
        messages.warning(request, "You are not a Bullets Leader Admininstrator")
        return redirect(reverse('core-team-admin'))


    if (leader.rider and leader.runner):
        # get both lists
        events = BulletEvent.objects.order_by("date").filter(date__gte=datetime.datetime.now())
        leaders = Leader.objects.order_by("bullet").all()
    elif (leader.rider):
        events = BulletEvent.objects.order_by("date").filter(date__gte=datetime.datetime.now()).filter(cycling_event=True)
        leaders = Leader.objects.order_by("bullet").filter(rider=True)
    else:
        events = BulletEvent.objects.order_by("date").filter(date__gte=datetime.datetime.now()).filter(running_event=True)
        leaders = Leader.objects.order_by("bullet").filter(runner=True)

    return render(request, 'leaders/boss_mode.html', {'events':events, 'leaders':leaders})




@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group?   
def CreateEvent(request, event_id=None):
    leader = boss_to_leader(request)
    if leader == None:
        messages.warning(request, "You are not a Bullets Leader Admininstrator")
        return redirect(reverse('core-team-admin'))

    if request.method == 'POST':
        # create the event
        
        event_type = request.POST.get("event_type", "run")
        event_date = datetime.datetime.strptime(request.POST.get("event_date", "01-01-2016"), '%d-%m-%y')

        speedOpt = request.POST.get("speedOpt")
        runSpeeds = request.POST.getlist("runSpeed")
        rideSpeeds = request.POST.getlist("rideSpeed")
        customSpeeds = request.POST.getlist("customSpeed")
            

        if event_type == "run":
            running_event = True
            cycling_event = False
        else:
            running_event = False
            cycling_event = True


        event_id = request.POST.get("event_id", None)
        e, created = BulletEvent.objects.update_or_create(pk=event_id, running_event=running_event, cycling_event=cycling_event, date=event_date)	        
        if (speedOpt == 'runDefault'):
            speeds = DefaultSpeedGroup.objects.filter(group_type=DefaultSpeedGroup.RUN).values_list("name", "display_order")
        elif (speedOpt == 'rideDefault'):
            speeds = DefaultSpeedGroup.objects.filter(group_type=DefaultSpeedGroup.RIDE).values_list("name", "display_order")
        elif (speedOpt == 'runCustom'):
            speeds = [(y, x) for x, y in enumerate(runSpeeds)]
        elif (speedOpt == 'rideCustom'):
            speeds = [(y, x) for x, y in enumerate(rideSpeeds)]

        else:
            speeds = [(y, x) for x, y in enumerate(customSpeeds)]


        keep_set = []
        for (s,o) in speeds:
            if ((s != "") and (s != None)):        # squash blanks
                es, created_two = EventSpeed.objects.get_or_create(name=s, display_order=o, event=e)
                
                keep_set.append(es)

        for es in EventSpeed.objects.filter(event=e):    # delete all event speeds we didn't get sent
            if es not in keep_set:
                es.delete()

        if created:
            messages.success(request, "Event was created!")
            return redirect(reverse('leaders:send-message-new-event', args=[e.id]))
        else:
            messages.success(request, "Event was updated!")
            return redirect(reverse('leaders:event', args=[e.id]))
        
    else:
        if (event_id != None):
            event = get_object_or_404(BulletEvent, pk=event_id)
        else:
            event = None

        run_speeds = DefaultSpeedGroup.objects.filter(group_type=DefaultSpeedGroup.RUN)
        ride_speeds = DefaultSpeedGroup.objects.filter(group_type=DefaultSpeedGroup.RIDE)

        return render(request, 'leaders/event_create.html', {'leader': leader, 'event':event, 'run_speeds': run_speeds, 'ride_speeds':ride_speeds})



@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group?   
def EventDetail(request, pk):
    leader = boss_to_leader(request)
    if leader == None:
        messages.warning(request, "You are not a Bullets Leader Admininstrator")
        return redirect(reverse('core-team-admin'))
   
    event = get_object_or_404(BulletEvent, pk=pk)

    avails = event.said_yes()
    maybe = event.said_maybe_or_nothing()
    nos = event.said_no()

    # Work out whether they've lead in the last four weeks
    
    avail = []
    t = event.date
    lastevents = BulletEvent.objects.filter(date__lt=t).order_by("date").filter(running_event=event.running_event).filter(cycling_event=event.cycling_event)[:4]
    
    for a in avails:
        l = a.leader
        c = 0
        for e in lastevents:  
            d = Availability.objects.filter(leader__pk=l.pk).filter(event_id=e.id).filter(leading=True).count()    
            c = c + d
        avail.append((a, c))

    unknown_avail = event.get_not_leading()
    speeds = event.speeds.all()

    # recommended allocations
         # for i = 1 to len(speeds)
    #   find people who can only lead (i) speed(s) groups
    #       allocate them to the slowest speed they've said they can do
    unallocated = avails.all()    
    allocation = {}
    speed_count = {}

    for i in speeds:
        speed_count[i] = 0

    for i in range(len(speeds)):
        j = i + 1
        a = unallocated.annotate(num_speeds=Count('speed_options')).filter(num_speeds=j)

        for l in a:    # for each availability... (i.e. each person who can lead at <i> speeds....
            unallocated = unallocated.exclude(pk=l.id)    # remove this one from the unallocated set

            # work out which of their speeds to set them too

            # for each speed they've said they can lead at, see how many leaders we've got allocated to that speed already
            # find the minimum number of leaders-per-speed, and allocate them to that
            min_seen = None
            min_seen_count = 100000    # hopefully we never have more than 100000 leaders

            for leaderspeed in l.speed_options.all():
                if speed_count[leaderspeed] < min_seen_count:
                    min_seen_count = speed_count[leaderspeed]        # this is the lowest one we've seen
                    min_seen = leaderspeed
            # assign them to min_seen, increment the number of leaders for it

            allocation[l.id] = min_seen
            speed_count[min_seen] = speed_count[min_seen] + 1

        #    messages.success(request, "Suggesting " + str(l.leader) + " for speed group " + str(min_seen))    
            

    return render(request, 'leaders/event_detail.html', {'leader':leader, 'event':event, 'avail':avail, 'maybe':maybe, 'unknown_avail':unknown_avail, 'speeds':speeds, 'nos':nos, 'allocation': allocation})





@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group?   
def EventSavePlan(request):
    event = get_object_or_404(BulletEvent, pk=request.POST.get("event"))

    # for each availability object associated with this event, see if there's a value been sent for a speed to lead at

    for avail in event.availability_set.all():
        t = "avail-" + str(avail.id)
        sg_p = request.POST.get(t, None)
        if sg_p != None:
            sg = get_object_or_404(EventSpeed, pk=sg_p)
        else:    
            sg = None

        avail.plan = sg

        avail.save()

    messages.success(request, "Saved availability plan")    
    return  redirect(reverse('leaders:event', args=[event.pk]))



@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group?  
def EventGroupDetail(request, pk):        	  # Show what allocations we have made to this particular event
    event = get_object_or_404(BulletEvent, pk=pk)
    leader = boss_to_leader(request)
    if leader == None:
        messages.warning(request, "You are not a Bullets Leader Admininstrator")
        return redirect(reverse('core-team-admin'))

    avails = event.said_yes().order_by('plan')
    maybe = event.said_maybe_or_nothing()
    nos = event.get_speedgroups_no_leaders()

    return render(request, 'leaders/event_group_detail.html', {'leader':leader, 'event':event, 'avail':avails, 'maybe':maybe, 'no_leaders':nos})




class EventUpdate(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = BulletEvent
    fields = ['date', 'cycling_event', 'running_event']
    success_message = "Changes to event were saved"
    def test_func(self):
        return is_leaders_team(self.request.user)


class EventDelete(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, DeleteView):
    model = BulletEvent
    template_name = "leaders/event_confirm_delete.html"
    success_url = reverse_lazy('leaders:events-next')
    success_message = "Event was deleted"    
    def test_func(self):
        return is_leaders_team(self.request.user)


class EventViewAll(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "leaders/event_list.html"
    def get_queryset(self):
        return BulletEvent.objects.order_by("date")
    def test_func(self):
        return is_leaders_team(self.request.user)


class EventViewNext(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "leaders/event_list.html"
    def get_queryset(self):
        """Return the next ten events"""
        return BulletEvent.objects.order_by("date").filter(date__gte=datetime.datetime.now())[:10]
    def test_func(self):
        return is_leaders_team(self.request.user)


class EventViewNextRuns(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "leaders/event_list.html"
    def get_queryset(self):
        """Return the next ten events"""
        return BulletEvent.objects.order_by("date").filter(date__gte=datetime.datetime.now()).filter(running_event=True)[:10]
    def test_func(self):
        return is_leaders_team(self.request.user)


class EventViewNextRides(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "leaders/event_list.html"
    def get_queryset(self):
        """Return the next ten events"""
        return BulletEvent.objects.order_by("date").filter(date__gte=datetime.datetime.now()).filter(cycling_event=True)[:10]
    def test_func(self):
        return is_leaders_team(self.request.user)



class LeaderForm(forms.Form):			# Used in entry page
    email = forms.EmailField(label="Your email", required=True)


class LeaderUpdateForm(forms.ModelForm):
    class Meta:
        model = Leader
        fields = ['bullet', 'rider', 'runner']
    def __init__(self, *args, employee_pk=None, **kwargs):
       super().__init__(*args, **kwargs)
       self.fields['bullet'].queryset = Bullet.objects.exclude(leader__isnull=False)



class LeaderCreate(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = Leader
    form_class = LeaderUpdateForm
    template_name = "leaders/leader_form.html"
    success_message = "Leader successfully added"
    success_url = reverse_lazy('leaders:boss-mode')
    def test_func(self):
        return is_leaders_team(self.request.user)


class LeaderDelete(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, DeleteView):
    model = Leader
    template_name = "leaders/leader_confirm_delete.html"
    success_url = reverse_lazy('leaders:boss-mode')
    success_message = "Leader was deleted"    
    def test_func(self):
        return is_leaders_team(self.request.user)


class LeaderEdit(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = Leader
    fields = ['rider', 'runner', 'email_preference']
    template_name = "leaders/leader_form.html"
    success_url = reverse_lazy('leaders:boss-mode')
    success_message = "Changes to leader were saved"
    def test_func(self):
        return is_leaders_team(self.request.user)


class LeaderList(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "leaders/leader_list.html"
    model = Leader
    def test_func(self):
        return is_leaders_team(self.request.user)



#### Email functions #####

@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group?  
def send_message_update_event(request, pk):
    event = get_object_or_404(BulletEvent, pk=pk)
    leader = boss_to_leader(request)
    if leader == None:
        messages.warning(request, "You are not a Bullets Leader Admininstrator")
        return redirect(reverse('core-team-admin'))
    
    l = Availability.objects.filter(event_id=event.pk).exclude(leading=None).values('leader')

    if (event.running_event):
        maybe = Leader.objects.exclude(pk__in=l).filter(rider=True)
    else:
        maybe = Leader.objects.exclude(pk__in=l).filter(runner=True)

    who_to_send_to = maybe.filter(email_preference=True)

    if request.method == 'POST':
        # actually take action!
        event.have_sent_email = True
        event.save()
        
        message = request.POST.get("custom_message", "")
        if message == "":
            message = " "

        x = send_leaders_an_email_about_event(leader.bullet, who_to_send_to, "emails/leaders-hurry-up", [event], message)

        messages.success(request, "Have sent a suitably encouraging email to " + str(x) + " leaders!")
    
        return redirect(reverse('leaders:event', args=[pk]))

    else:
        return render(request, 'leaders/who_to_email.html', {'event':event, 'emails':who_to_send_to})
    

    
@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group?  
def iceman(request, pk):
    event = get_object_or_404(BulletEvent, pk=pk)
    leader = boss_to_leader(request)
    if leader == None:
        messages.warning(request, "You are not a Bullets Leader Admininstrator")
        return redirect(reverse('core-team-admin'))


    leaders_to_contact = Leader.objects.filter(availability__event_id=event.id, availability__leading=True).filter(email_preference=True)

    if request.method == 'POST':
        # actually take action!
        event.have_sent_email = True
        event.save()
       
        message = request.POST.get("custom_message", "")
        if message == "":
            message = " "

        x = send_leaders_an_email_about_event(leader.bullet, leaders_to_contact, "emails/leaders-iceman", [event], message)

        messages.success(request, "Have sent a suitably icy email to " + str(x) + " leaders!")
    
        return redirect(reverse('leaders:event', args=[pk]))

    else:
        return render(request, 'leaders/who_to_email_iceman.html', {'event': event, 'emails':leaders_to_contact, 'leader':leader})
    



# we come here after creating a new event to see if the boss would like to email everyone about it (and any other new events)
@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group?  
def send_message_new_event_partA(request, pk):        
    event = get_object_or_404(BulletEvent, pk=pk)
    leader = boss_to_leader(request)
    if leader == None:
        messages.warning(request, "You are not a Bullets Leader Admininstrator")
        return redirect(reverse('core-team-admin'))

    if (leader.rider_and_runner() == True):
        all_new_events = BulletEvent.objects.filter(have_sent_initial_email=False)
    elif (leader.rider == True):
        all_new_events = BulletEvent.objects.filter(have_sent_initial_email=False).filter(cycing_event = True, running_event=False)
    else:
        all_new_events = BulletEvent.objects.filter(have_sent_initial_email=False).filter(cycling_event = False, running_event = True)

    events = all_new_events.filter(date__gte=datetime.datetime.now())

    return render(request, 'leaders/who_to_email_new_events.html', {'new_event':event, 'events':events})



@login_required
@user_passes_test(is_leaders_team, login_url="/") # are they in the leaders admin group? 
def send_message_new_event_partB(request):
    leader = boss_to_leader(request)
    if leader == None:
        messages.warning(request, "You are not a Bullets Leader Admininstrator")
        return redirect(reverse('core-team-admin'))

    # iterate over all the events we have in the set that the boss said 'yes' to sending and produce an email for everyone
    
    event_list = []
    for e_id in request.POST.getlist("event"):
        event = get_object_or_404(BulletEvent, pk=e_id)
        event.have_sent_initial_email = True
        event.save()

        event_list.append(event)

    who_to_send_to = Leader.objects.filter(email_preference=True)        

    x = send_leaders_an_email_about_event(leader.bullet, who_to_send_to, "emails/leaders-new-event", event_list)

    messages.success(request, "Have sent an email about the event to " + str(x) + " leaders!")    
    
    return redirect(reverse('leaders:boss-mode'))





# This function does the hard work of emailing
def send_leaders_an_email_about_event(boss, leaders, template, events, custom_message=""):
    base_url = "https://www.boldmerebullets.com"    # TODO: could this be a setting?

    i = 0

    for leader in leaders:
        if leader.email_preference:  # DOUBLE CHECK! :)
            event_details = []
            for event in events:    
                speed_urls = []
            
                for speed in event.get_speedgroups():
                    speed_url = base_url + reverse('leaders:eventYes', kwargs={'leader_id':leader.pk, 'event_id':event.id, 'speed_id':speed.id})
                    speed_urls.append((speed, speed_url))

                no_url = base_url + reverse('leaders:eventNo', kwargs={'leader_id':leader.pk, 'event_id':event.id})
            
                if leader.show_ride_on_day(event): # work out whether this event is of interest to this leader...
                    if (((event.is_ride()) and (leader.rider)) or ((event.is_run()) and (leader.runner))):
                        event_details.append((event, speed_urls, no_url))

            if len(event_details) > 0:     # anything worth sending?
                stop_url = base_url + reverse('leaders:email-off', kwargs={'pk':leader.pk})
                       
                from_address = boss.name + " <leaders@boldmerebullets.com>"
                ctx = {'stop_url':stop_url, 'send_to':leader, 'sent_from':boss, 'events':event_details, 'custom_message':custom_message, }

                send_bullet_mail(template_name=template, recipient_list=[leader.bullet.email], context=ctx, from_email=from_address)

                i = i + 1
    return i




