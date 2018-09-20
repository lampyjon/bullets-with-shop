#### OLD IWD stuff

# views.py

# View to handle IWD rider registrations
def iwd_register(request):
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        iwd_form = IWDForm(request.POST)
        	# check whether it's valid:
        if iwd_form.is_valid():
            iwd = iwd_form.save()
            
            unregister_evans_url = build_absolute_uri(reverse('iwd-unregister', args=['evans', iwd.email_check_ref]))
            unregister_ride_url = build_absolute_uri(reverse('iwd-unregister', args=['ride', iwd.email_check_ref]))
            ride_info_url = build_absolute_uri(reverse('ride-info'))

            context = {'iwd':iwd, 'unregister_evans_url':unregister_evans_url, 'unregister_ride_url':unregister_ride_url, 'ride_info_url':ride_info_url} 

            send_bullet_mail(
                template_name='bullets/iwd',
                recipient_list=[iwd.email],
                context=context)
			
            messages.success(request, "You have successfully registered - we will email you to confirm!");
			            
            return redirect(reverse('index'))

   	# if a GET (or any other method) we'll create a blank form
    else:
        iwd_form = IWDForm()
   
    return render(request, "bullets/iwd/register.html", {'form': iwd_form})

# someone no longer wants to do the IWD ride
def iwd_unregister(request, event_type, uuid):
    iwd = get_object_or_404(IWDRider, email_check_ref=uuid)
    if request.method == 'POST':
        if event_type == 'evans':
            iwd.evans = False
            messages.success(request, "Thank you for unregistering from the Evans Bike Maintenance event, " + str(iwd.name))
        elif event_type == 'ride':
            iwd.speed = IWDRider.NO
            messages.success(request, "Thank you for unregistering from the Womens Interclub Ride, " + str(iwd.name))
        elif event_type == 'both':
            iwd.evans = False
            iwd.speed = IWDRider.NO
            messages.success(request, "Thank you for unregistering from these events, " + str(iwd.name))

        iwd.save()

        if ((iwd.evans == False) and (iwd.doing_ride() == False)):
            iwd.delete()

        return redirect(reverse('index'))
    else:
        return render(request, "bullets/iwd/unregister.html", {'iwd':iwd})




# IWD view
class IWDList(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = IWDRider
    template_name = "bullets/iwd/iwd_list_admin.html"
    def test_func(self):
        return is_core_team(self.request.user)

class IWDUpdate(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = IWDRider
    form_class = IWDForm
    success_url = reverse_lazy('iwd-list-admin')
    def test_func(self):
        return is_core_team(self.request.user)

class IWDDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = IWDRider
    success_url = reverse_lazy('iwd-list-admin')  
    def test_func(self):
        return is_core_team(self.request.user)



### FORMS.py

class IWDForm(ModelForm):
    class Meta:
        model = IWDRider
        fields = ['name', 'email', 'club', 'evans', 'speed']


### URLS.py

    url(r'^events/Womens-Events/register$', views.iwd_register, name='iwd-register'),
    url(r'^events/Womens-Events/unregister/(?P<event_type>evans|ride|both)/(?P<uuid>[0-9a-z-]+)/$', views.iwd_unregister, name='iwd-unregister'),
    url(r'^events/Womens-Events/admin/list/$', views.IWDList.as_view(), name='iwd-list-admin'), 
    url(r'^events/Womens-Events/admin/update/(?P<pk>[0-9]+)/$', views.IWDUpdate.as_view(), name='iwd-update'),
    url(r'^events/Womens-Events/admin/delete/(?P<pk>[0-9]+)/$', views.IWDDelete.as_view(), name='iwd-delete'),
  





### Models.py

# For the Womens' Ride
class IWDRider(Person):
    club = models.CharField("Usual club", max_length=200, blank=True)

    NO = 'n'
    SLOWEST = 'a'
    SLOW = 'b'
    MEDIUM = 'c'
    FAST = 'd' 
    FASTEST = 'e'

    SPEED_CHOICES = (
        (NO, 'I do not wish to take part in the ride'),
	(SLOWEST, '10-11mph'),
	(SLOW, '12-13mph'),
        (MEDIUM, '14-15mph'),
        (FAST, '16-17mph'), 
        (FASTEST, '18+mph'),
    )
    
    evans = models.BooleanField("Evans Event?", help_text="Check this box if you'd like to take part in the bike maintenance event at Evans", default=True)
    speed = models.CharField("Women's Ride?", help_text="What speed would you like to do the ride at?", max_length=1, choices=SPEED_CHOICES, default=NO)

    def doing_ride(self):
        return (self.speed != self.NO)



