import requests, os
from datetime import datetime
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.dateparse import parse_datetime
from django.core.cache import cache
from .models import Event, EventCategory


def fetch_events_from_api(city, latitude, longitude):
    cache_key = f"events_{city}"
    cached_events = cache.get(cache_key)

    if cached_events:
        print("Using cached events")
        return cached_events

    Event.objects.all().delete()

    url = 'https://app.ticketmaster.com/discovery/v2/events.json'
    api_key = os.getenv('TICKETMASTER_API_KEY')
    params = {
        'apikey': api_key,
        'latlong': f'{latitude},{longitude}',
        'radius': 50,
        'unit': 'miles',
        'sort': 'relevance,desc',
        'size': 100,
        'page': 0,
        'priceMax': 0  # Aim to fetch free events
    }

    events = []
    while True:
        response = requests.get(url, params=params)
        data = response.json()

        if '_embedded' not in data or 'events' not in data['_embedded']:
            print('No events found in the response.')
            break

        events.extend(data['_embedded']['events'])

        if 'page' in data:
            current_page = data['page']['number']
            print(f'Page: {current_page}')
            total_pages = data['page']['totalPages']
            if current_page >= total_pages - 1:
                break
            params['page'] += 1
        else:
            break

    for event_data in events:
        skip_event = False

        # Check explicitly for price ranges, which should indicate paid events
        if 'priceRanges' in event_data:
            for price_range in event_data['priceRanges']:
                min_price = price_range.get('min')
                if min_price is not None and min_price > 0:
                    print(f"Skipping paid event: {event_data['name']} with min price {min_price}")
                    skip_event = True
                    break

        # Use free-related keywords as another filter check
        free_keywords = ['free', 'no charge', 'complimentary']
        title_description = f"{event_data.get('name', '')} {event_data.get('description', '')}".lower()
        if not any(keyword in title_description for keyword in free_keywords):
            print(f"Skipping event without clear 'free' indication: {event_data['name']}")
            skip_event = True

        # Avoid false positives from unrelated 'free' mentions
        misleading_phrases = ['free parking', 'free with purchase', 'free entry with ticket']
        if any(phrase in title_description for phrase in misleading_phrases):
            print(f"Skipping event due to misleading 'free' context: {event_data['name']}")
            skip_event = True

        if skip_event:
            continue

        # Extract event details as usual and save to the database
        category_name = event_data['classifications'][0]['segment']['name'] if 'classifications' in event_data and event_data['classifications'] else 'Other'
        category, _ = EventCategory.objects.get_or_create(
            name=category_name,
            defaults={'category': category_name}
        )

        title = event_data['name']
        event_url = event_data['url'] if event_data.get('url') else ''
        description = event_data.get('description', '')
        cover_photo = event_data['images'][0]['url'] if event_data.get('images') else ''
        venue = event_data['_embedded']['venues'][0] if 'venues' in event_data['_embedded'] else {}
        location = venue.get('address', {}).get('line1', 'Unknown Location')
        city = venue.get('city', {}).get('name', '')
        state = venue.get('state', {}).get('stateCode', '')
        full_address = f"{location}, {city}, {state}"
        latitude = venue.get('location', {}).get('latitude', 0)
        longitude = venue.get('location', {}).get('longitude', 0)
        event_date_str = event_data['dates']['start'].get('dateTime', '')
        event_date = parse_datetime(event_date_str) if event_date_str else None
        if not event_date:
            print(f"Skipping event '{title}' due to missing or invalid date.")
            continue
        family_friendly = event_data['classifications'][0].get('family', False) if 'classifications' in event_data and event_data['classifications'] and 'family' in event_data['classifications'][0] else False

        event_defaults = {
            'description': description,
            'date': event_date,
            'location': full_address,
            'latitude': latitude,
            'longitude': longitude,
            'cover_photo': cover_photo,
            'category': category,
            'family_friendly': family_friendly
        }

        Event.objects.update_or_create(
            title=title,
            url=event_url,
            defaults=event_defaults
        )

    cache.set(cache_key, events, timeout=3600)

    return events

def get_user_location():
    try:
        response = requests.get('https://ipinfo.io')
        data = response.json()

        city = data.get('city', 'Seattle')
        loc = data.get('loc', '47.6062,-122.3321')
        latitude, longitude = map(float, loc.split(','))
        
        print(f'User City: {city}, Latitude: {latitude}, Longitude: {longitude}')
        return city, latitude, longitude

    except requests.RequestException as e:
        print(f"Error fetching location: {e}")
        return 'Seattle'

def home(request):
    city, latitude, longitude = get_user_location()
    fetch_events_from_api(city, latitude, longitude)

    events_tonight = Event.objects.filter(date__date = datetime.today())[:5]
    crowd_favorites = Event.objects.all()[:5]
    family_events = Event.objects.filter(family_friendly = True)[:5]

    context = {
        'events_tonight': events_tonight, 
        'crowd_favorites': crowd_favorites, 
        'family_events': family_events
        }
    
    return render(request, 'events/home.html', context)

def all_events(request):
    search_query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    page_number = request.GET.get('page', 1)

    all_events = Event.objects.all().order_by('date')

    if search_query:
        all_events = all_events.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))

    if category_filter:
        all_events = all_events.filter(Q(category__name__iexact=category_filter))

    paginator = Paginator(all_events, 20) 
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'category_filter': category_filter
    }

    return render(request, 'events/all_events.html', context)

def event_detail(request, event_id):
    event = get_object_or_404(Event, id = event_id)
    return render(request, 'events/event_view.html', {'event': event})

def map_view(request):
    city, latitude, longitude = get_user_location()

    all_events = Event.objects.all()

    events_data = list(all_events.values('id', 'title', 'date', 'location', 'latitude', 'longitude'))

    context = {
        'all_events': events_data,
        'latitude': latitude, 
        'longitude': longitude 
    }

    return render(request, 'events/map_view.html', context)