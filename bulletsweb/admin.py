from django.contrib import admin
from .models import Bullet, Leader, ActivityCache, News, RunningEvent, BulletEvent, SiteSettings, Availability, EventSpeed, DefaultSpeedGroup
from django_summernote.admin import SummernoteModelAdmin


admin.site.register(SiteSettings)
admin.site.register(ActivityCache)
#admin.site.register(OldBullet)
admin.site.register(Bullet)
admin.site.register(Leader)
admin.site.register(RunningEvent)
admin.site.register(BulletEvent)
admin.site.register(DefaultSpeedGroup)
admin.site.register(EventSpeed)
admin.site.register(Availability)
#admin.site.register(BigBulletRider)

class NewsAdmin(SummernoteModelAdmin):
	pass

admin.site.register(News, NewsAdmin)

