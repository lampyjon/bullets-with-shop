from django import forms
from django.forms import ModelForm
from .models import Bullet, News, RunningEvent, BulletEvent 
from django_summernote.widgets import SummernoteWidget, SummernoteInplaceWidget
from captcha.fields import ReCaptchaField

class RegisterForm(ModelForm):
	over_18 = forms.BooleanField(label='Please confirm you are over 18?')

	class Meta:
		model = Bullet
		fields = ['name', 'postcode', 'email', 'contact_no', 'get_emails']
	
	def save(self, commit=True):
        # do something with self.cleaned_data['temp_id']
		m = super(RegisterForm, self).save(commit=False)
		m.over_18 = True
		if commit:
			m.save()
		return m


class UnRegisterForm(forms.Form):
    name = forms.CharField(label='Name', max_length=100)
    email = forms.EmailField(label='Email address', max_length=200)


class ContactForm(forms.Form):
    name = forms.CharField(label="Your name", max_length=100)
    email = forms.EmailField(label='Your email', max_length=200)
    comment = forms.CharField(widget=forms.Textarea)
    captcha = ReCaptchaField(label="")


class RunningEventForm(ModelForm):
	class Meta:
		model = RunningEvent
		fields = ['date', 'session_type', 'session_details', 'meeting_point']
		widgets = {
			'date': forms.TextInput(attrs={'class': 'datepicker'}),
		}

	def __init__(self, *args, **kwargs):
		super(RunningEventForm, self).__init__(*args, **kwargs)
		p = ('%d-%m-%Y','%Y-%m-%d')
		self.fields['date'].input_formats=(p)


class NewsForm(ModelForm):
    class Meta:
        model = News
        fields = ['title', 'extra_title', 'redirect_to', 'story', 'display_after', 'display_until', 'front_page']

        widgets = {
            'display_after': forms.TextInput(attrs={'class': 'datepicker'}),
            'display_until': forms.TextInput(attrs={'class': 'datepicker'}),
            'story': SummernoteInplaceWidget(),
        }

    def __init__(self, *args, **kwargs):
        super(NewsForm, self).__init__(*args, **kwargs)
        p = ('%d-%m-%Y','%Y-%m-%d')
        self.fields['display_after'].input_formats=(p)
        self.fields['display_until'].input_formats=(p)


class BulletEventForm(ModelForm):
	class Meta:
		model = BulletEvent
		fields = ['date', 'name', 'link', 'running_event', 'cycling_event', 'social_event']
		widgets = {
			'date': forms.TextInput(attrs={'class': 'datepicker'}),
		}

	def __init__(self, *args, **kwargs):
		super(BulletEventForm, self).__init__(*args, **kwargs)
		p = ('%d-%m-%Y','%Y-%m-%d')
		self.fields['date'].input_formats=(p)





class CTSTime(forms.Form):
    STOPS = ( 
        ("CP1", "CP 1 (23 miles)"),
        ("CP2", "CP 2 (32 miles)"),
        ("SS1", "Stop 1 (42 miles)"),
        ("SS2", "Stop 2 (71 miles)"),
        ("CP3", "CP 3 (81 miles)"),
        ("SS3", "Stop 3 (100 miles)"),
        ("CP4", "CP 4 (115 miles)"),
        ("SS4", "Stop 4 (136 miles)"),
        ("CP5", "CP 5 (150 miles)"),
        ("SS5", "Stop 5 (166 miles)"),
        ("SS6", "Stop 6 (186 miles)"),
        ("DDD", "Do by distance"),
    )

    stop = forms.ChoiceField(label="Stop", choices=STOPS)
    distance = forms.IntegerField(label="Distance (miles)", required=False)
    time_left = forms.TimeField(label="Time riders left")





#class BigBulletRiderForm(ModelForm):
#    class Meta:
#        model = BigBulletRider
#        fields = ['name', 'email', 'distance']
#
#
#class BulletsRunnerForm(ModelForm):
#	class Meta:
#		model = BulletsRunner
#		fields = ['name', 'address', 'email', 'gender', 'contact_no', 'emergency_contact_no', 'age', 'club', 'race']
#
#
#class InterclubForm(ModelForm):
#	class Meta:
#		model = InterclubRider
#		fields = ['name', 'email', 'club', 'ice', 'speed']
#	
#
#
#class VeloFeedbackForm(ModelForm):
#	class Meta:
#		model = VeloFeedback
#		fields = ['name', 'email', 'volunteer_type', 'question_one', 'question_two', 'support_again', 'volunteer_again', 'question_three', 'question_four']
#
#
#
#class BulletsRunFeedbackForm(ModelForm):
#	class Meta:
#		model = BulletsRunFeedback
#		fields = ['name', 'email', 'question_one', 'question_two', 'run_again', 'question_three']
#
#
#
#
#class VeloForm(forms.Form):
#	RIDER = "r"
#	NON_RIDER = "n"
#	VOLUNTEER_TYPE_CHOICES = (
#		(RIDER, "rider"),
#		(NON_RIDER, "non-rider")
#	)
#	email = forms.EmailField(label='Email address', max_length=200)	
#
#	volunteer_type = forms.ChoiceField(choices=VOLUNTEER_TYPE_CHOICES)
#
#SIZE_XS = 'xs'
#SIZE_S = 's'
#SIZE_M = 'm'
#SIZE_L = 'l'
#SIZE_XL = 'xl'
#SIZE_XXL = 'xxl'
#SIZE_XXXL = 'xxxl'
#
#KIT_SIZE_CHOICES = (
#	(SIZE_XS, 'X Small'),
#	(SIZE_S, 'Small'),
#	(SIZE_M, 'Medium'),
#	(SIZE_L, 'Large'),
#	(SIZE_XL, 'X Large'),
#	(SIZE_XXL, 'XX Large'),
#	(SIZE_XXXL, 'XXX Large')
#)
#	
#MALE = 'm'
#FEMALE = 'f'
#KIT_SEX_CHOICES = (
#	(MALE, 'male-fit'),
#	(FEMALE, 'female-fit')
#)
#
#
#
#class VeloRiderForm(forms.Form):
#	address = forms.CharField(label="Your address", widget=forms.Textarea)
#
#	entered_velo = forms.BooleanField(label="Have you entered the Velo?", required=False)
#	average_speed = forms.CharField(label='Average Speed (mph)', max_length=10, help_text="What speed do you think you would average on a 100 mile ride?")
#	kit_sex = forms.ChoiceField(label='Kit type?', choices=KIT_SEX_CHOICES, help_text="Please indicate whether you require men's or women's-fit kit") 
#
#	jersey_size = forms.ChoiceField(label='Jersey size', choices=KIT_SIZE_CHOICES, help_text="Please see the <a href='https://www.primaleurope.com/pages/fit-guide' target='_blank'>Fit Guide</a> for more information on sizes")
#	short_size =  forms.ChoiceField(label='Bib short size', choices=KIT_SIZE_CHOICES, help_text="Please see the <a href='https://www.primaleurope.com/pages/fit-guide' target='_blank'>Fit Guide</a> for more information on sizes")
#
#
#class VeloRunnerForm(forms.Form):
#	name = forms.CharField(label="Your name") 
#	address = forms.CharField(label="Your address", widget=forms.Textarea)
#	contact_no = forms.CharField(label="Contact number")
#	tshirt_size = forms.ChoiceField(label="T-shirt size", choices=KIT_SIZE_CHOICES)
#	drive_van = forms.BooleanField(label="Are you willing to drive a van?", required=False)
#	drive_bus = forms.BooleanField(label="Are you willing to drive a minibus?", required=False, help_text="Please note: By saying you are able to drive a minibus, you are also confirming that you have a Category D1 driving licence, which means you can drive a minibus with up to 16 passenger seats without needing an additional driving test.")
#
#
#
#
#
#class tdbForm(forms.Form):
#	strava_id = forms.IntegerField(label="Athlete ID")
#
#
