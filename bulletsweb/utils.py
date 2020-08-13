from django.conf import settings
from templated_email import send_templated_mail, InlineImage
from django.utils.encoding import iri_to_uri
from django.contrib.sites.models import Site
from urllib.parse import urljoin
from django.contrib.auth.models import User

# get list of people to email
def who_to_email():
    return User.objects.filter(groups__name='ShopTeam').values_list('email', flat=True)

# wrapper around the mail email function, primarily to give consistency on sender email address
def send_bullet_mail(template_name, recipient_list, context, extra_headers={}, from_email=None):
    if from_email == None:
        from_email = settings.DEFAULT_FROM_EMAIL

    with open('bullets.png', 'rb') as bulletpic:
        image = bulletpic.read()
    inline_image = InlineImage(filename="bullets.png", content=image)
    context['bullet_pic'] = inline_image

    return send_templated_mail(
         template_name=template_name,
         from_email=from_email,
         recipient_list=recipient_list,
         context=context,
         headers=extra_headers)


# A wrapper to send managers emails when required
def send_manager_email(template_name, context={}, extra_headers={}):
    return send_bullet_mail(template_name=template_name,
        recipient_list=who_to_email(),
        context=context,
        extra_headers=extra_headers)



def build_absolute_uri(location):
    # type: (str, bool, saleor.site.models.SiteSettings) -> str
    host = Site.objects.get_current().domain
    protocol = 'https' if settings.ENABLE_SSL else 'http'
    current_uri = '%s://%s' % (protocol, host)
    location = urljoin(current_uri, location)
    return iri_to_uri(location)	



# Decorator style for checking user is in the Core Team & can edit things on the site (News Items, etc)
def is_core_team(user):
    return user.groups.filter(name='CoreTeam').exists()

# Decorator style for checking user is in a view-only mode, and can see statistics etc.
def is_stats_team(user):
    return user.groups.filter(name='StatsTeam').exists()

# Decorator style for checking user is in the Shop Team, and can edit things in the shop
def is_shop_team(user):
    return user.groups.filter(name='ShopTeam').exists()

# Decorator style for checking user is in the Leaders Team, and can edit things in the Leaders app
def is_leaders_team(user):
    return user.groups.filter(name='LeadersTeam').exists()
