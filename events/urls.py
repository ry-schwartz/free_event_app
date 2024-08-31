from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name = 'home'),
    path('all_events/', views.all_events, name = 'all_events'),
    path('event/<int:event_id>', views.event_detail, name = 'event_detail'),
    path('map/', views.map_view, name = 'map_view'),
]