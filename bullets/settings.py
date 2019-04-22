import os
import ast
import os.path

import dj_database_url
import dj_email_url

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get('SECRET_KEY')

def get_list(text):
    return [item.strip() for item in text.split(',')]

def get_bool_from_env(name, default_value):
    if name in os.environ:
        value = os.environ[name]
        try:
            return ast.literal_eval(value)
        except ValueError as e:
            raise ValueError(
                '{} is an invalid value for {}'.format(value, name)) from e
    return default_value


DEBUG = get_bool_from_env('DEBUG', True)

ALLOWED_HOSTS = []

LOGOUT_REDIRECT_URL = "/"


# EMAIL
EMAIL_URL = os.environ.get('EMAIL_URL')
email_config = dj_email_url.parse(EMAIL_URL or 'console://')

EMAIL_FILE_PATH = email_config['EMAIL_FILE_PATH']
EMAIL_HOST_USER = email_config['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = email_config['EMAIL_HOST_PASSWORD']
EMAIL_HOST = email_config['EMAIL_HOST']
EMAIL_PORT = email_config['EMAIL_PORT']
EMAIL_BACKEND = email_config['EMAIL_BACKEND']
EMAIL_USE_TLS = email_config['EMAIL_USE_TLS']
EMAIL_USE_SSL = email_config['EMAIL_USE_SSL']

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')

AWS_SES_REGION_NAME = 'eu-west-1'   # TODO: make parameters
AWS_SES_REGION_ENDPOINT = 'email.eu-west-1.amazonaws.com'
EMAIL_BACKEND = 'django_ses.SESBackend'


# Application definition

INSTALLED_APPS = [
    'storages',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    'bootstrap4',
    'captcha',
    'django_summernote',
    'bulletsweb',
    'bulletsshop',
    'versatileimagefield',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bullets.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bullets.wsgi.application'


DATABASES = {
    'default': dj_database_url.config(
        default='postgres://user:password@localhost:5432/db',
        conn_max_age=600)}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

SITE_ID = 1

TIME_ZONE = 'Europe/London'
LANGUAGE_CODE = 'en'

USE_I18N = True
USE_L10N = True
USE_TZ = True



NOCAPTCHA = True

# Set Google's reCaptcha keys
RECAPTCHA_PUBLIC_KEY = os.environ.get('RECAPTCHA_PUBLIC_KEY')
RECAPTCHA_PRIVATE_KEY = os.environ.get('RECAPTCHA_PRIVATE_KEY')

ENABLE_SSL = get_bool_from_env('ENABLE_SSL', False)

SUMMERNOTE_THEME = 'bs4'


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = '/static/'

ALLOWED_HOSTS = get_list(
    os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1'))

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Amazon S3 configuration
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_LOCATION = os.environ.get('AWS_LOCATION', '')
AWS_MEDIA_BUCKET_NAME = os.environ.get('AWS_MEDIA_BUCKET_NAME')
AWS_MEDIA_CUSTOM_DOMAIN = os.environ.get('AWS_MEDIA_CUSTOM_DOMAIN')
AWS_QUERYSTRING_AUTH = get_bool_from_env('AWS_QUERYSTRING_AUTH', False)
AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_STATIC_CUSTOM_DOMAIN')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
AWS_DEFAULT_ACL = "public-read"

S3_URL = STATIC_URL 		# BULLETS: need this to make the various bits of AWS S3 code for custom storages work

if AWS_STORAGE_BUCKET_NAME:
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    S3_URL = 'https://%s.s3.amazonaws.com/assets/' % AWS_STORAGE_BUCKET_NAME   # BULLETS: added this

# TODO: fix this 
if AWS_MEDIA_BUCKET_NAME:
    DEFAULT_FILE_STORAGE = 'bullets.storage_backends.MediaStorage' 
#    THUMBNAIL_DEFAULT_STORAGE = DEFAULT_FILE_STORAGE

## STRAVA SETTINGS
STRAVA_ACCESS_TOKEN = os.environ.get('STRAVA_ACCESS_TOKEN', None)
STRAVA_CYCLING_CLUB = os.environ.get('STRAVA_CYCLING_CLUB', '0')
STRAVA_RUNNING_CLUB = os.environ.get('STRAVA_RUNNING_CLUB', '0')
STRAVA_CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID', '0')
STRAVA_CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET', None)

## FOR MAILCHIMP
MAILCHIMP_API_KEY = os.environ.get('MAILCHIMP_API_KEY')
MAILCHIMP_LISTID = os.environ.get('MAILCHIMP_LISTID')
MAILCHIMP_WEBHOOK_APIKEY = os.environ.get('MAILCHIMP_WEBHOOK_APIKEY')

#
# Payments
#
def get_host():
    from django.contrib.sites.models import Site
    return Site.objects.get_current().domain

PAYMENT_HOST = get_host
#
PAYMENT_MODEL = 'bulletsshop.Payment'
#
if DEBUG:
    PAYMENT_VARIANTS = {
        'default': ('payments.dummy.DummyProvider', {})
        }
else:
    PAYMENT_VARIANTS = {
        'paypal': ('payments.paypal.PaypalProvider', {
            'client_id': os.environ.get('PAYPAL_CLIENT_ID'),   
            'secret': os.environ.get('PAYPAL_SECRET'),
            'endpoint': 'https://api.paypal.com',
            'capture': True}),       
        }



LOGIN_REDIRECT_URL = 'core-team-admin'



