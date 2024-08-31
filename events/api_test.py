import requests

url = 'https://app.ticketmaster.com/discovery/v2/events.json'
api_key = 'ry4YoK5jAApLFDyfiyG8azTVwanwSoVA'
params = {
    'apikey': api_key,
    'city': 'Seattle',
    'sort': 'relevance,desc',
    'size': 200,  
    'page': 0     
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
    if 'priceRanges' in event_data:
            price_ranges = event_data['priceRanges']
            min_price = min(price_range['min'] for price_range in price_ranges)
            if min_price > 0:
                print(f"Skipping paid event: {event_data['name']} with min price {min_price}")
                continue
            else: 
                 print(f"New Event: {event_data['name']} - {event_data['classifications'][0]['segment']['name']}")
