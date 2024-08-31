from django.db import models


class EventCategory(models.Model):
    name = models.CharField(max_length = 100)
    category = models.CharField(max_length = 50, unique = True, null = True)

    def __str__(self):
        return self.name
    
class Event(models.Model):
    title = models.CharField(max_length = 200)
    description = models.TextField()
    date = models.DateTimeField()
    location = models.CharField(max_length = 200)
    latitude = models.FloatField()
    longitude = models.FloatField()
    url = models.URLField(blank = True)
    cover_photo = models.URLField(blank = True)
    family_friendly = models.BooleanField(default = False)
    category = models.ForeignKey(EventCategory, null = True, on_delete = models.SET_NULL)

    def __str__(self):
        return self.title