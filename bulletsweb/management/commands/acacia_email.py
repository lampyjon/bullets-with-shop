from django.core.management.base import BaseCommand, CommandError
from bullets.models import BigBulletRider
from django.conf import settings
from templated_email import send_templated_mail, InlineImage, get_templated_mail

class Command(BaseCommand):
    help = 'Send the Acacia 10-10 email'

    def handle(self, *args, **options):
        self.stdout.write("Preparing the email...")

        riders = BigBulletRider.objects.all()


    #    with open('1010-sponsorship.pdf', 'rb') as sponspdf:
    #        pdf = sponspdf.read()
    #        inline_pdf = InlineImage(filename="1010-sponsorship.pdf", content=pdf)
          
        for rider in riders:
            self.stdout.write("Emailing " + str(rider.email))
            make_email(context={'rider':rider}, recipient=rider.email)



def make_email(context, recipient):
    from_email = settings.DEFAULT_FROM_EMAIL

    with open('bullets.png', 'rb') as bulletpic:
        image = bulletpic.read()
    inline_image = InlineImage(filename="bullets.png", content=image)
    context['bullet_pic'] = inline_image

 #   with open('acacia.png', 'rb') as acaciapic:
 #       image = acaciapic.read()
 #   inline_image_a = InlineImage(filename="acacia.png", content=image)
 #   context['extra_pic'] = inline_image_a

    mail = get_templated_mail(
         template_name="source/bullets/acacia-charity",
         from_email=from_email,
         to=[recipient],
         context=context)

    mail.attach_file('1010-sponsorship.pdf')

    mail.send()	# ???
