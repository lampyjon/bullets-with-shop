


#### Squares

from bullets.models import SquareRider, SquareRide
def squares_start(request):
    client = Client()
    url = build_absolute_uri(reverse('squares-map')) 
    strava_url = client.authorization_url(client_id=settings.STRAVA_CLIENT_ID, redirect_uri=url) 
      
    return render(request, "bullets/squares/start.html", {'strava_url':strava_url})


def squares_map(request):
    code = request.GET.get("code", None)

    if code != None:
        client = Client()
        access_token = client.exchange_code_for_token(client_id=settings.STRAVA_CLIENT_ID, client_secret=settings.STRAVA_CLIENT_SECRET, code=code)
        client.access_token = access_token
        athlete = client.get_athlete()

        rider, created = SquareRider.objects.update_or_create(rider_id=athlete.id, defaults={'access_token':access_token})
        #created = True # TODO remove for cache
        ctx = {}
        result = squares_background_rides.delay(rider_id=rider.id)
        ctx['token'] = True
        ctx['url'] = reverse('squares-rides-task', args=[result.task_id])
      #  ctx['rides_url'] = reverse('squares-rides-ride', args=[rider.id])
        ctx['rides'] = SquareRide.objects.filter(rider=rider)
  
        return render(request, "bullets/squares/map.html", ctx)

    return redirect(reverse('squares_start'))



# update the leaderboard for this rider - go and get their most recent activities
@task(bind=True)
def squares_background_rides(self, rider_id):
    rider = get_object_or_404(SquareRider, pk=rider_id)

    client = Client()
    client.access_token = rider.access_token  
    rides = client.get_activities()

    for ride in rides:
        if SquareRide.objects.filter(rider=rider, strava_id=ride.id).exists() != True:   # Save hitting Strava for every ride every time
            if ride.map.summary_polyline:
                detail_ride = client.get_activity(ride.id)
                if detail_ride.map.polyline:
                # print(str(detail_ride.name) + " - " + str(detail_ride.map) + " - " + str(detail_ride.map.polyline))
                    r, created = SquareRide.objects.update_or_create(rider=rider, strava_id=detail_ride.id, defaults={'name':detail_ride.name, 'polyline':detail_ride.map.polyline})
                #print("Background got " + str(detail_ride.name))
                    self.update_state(state='PROGRESS', meta={'ride': r.name, 'polyline':r.polyline, 'id':r.id})
    return 



from math import radians, floor
def get_squares_for_line(polyline):
    points = decode_polyline(polyline)
    ldae = 69.172
    squares = []
    # print(str(points))
    for (lat,lng) in points:
        miles_north = lat * ldae
        miles_west = radians(lat) * ldae * lng

        square_s = int(miles_north * 2) / 2
        square_e = int(miles_west * 2) / 2
        
        squares.append((square_s, square_e))

   #     print("Lat / Lng = " + str(lat) + ", " + str(lng) + " = " + str(square_north) + " north and " + str(square_west) + " west")
        
    squares = list(set(squares))

    results = []
    for (s, e) in squares:
        n = make_bigger(s)
        w = make_bigger(e)
        nw = miles_to_latlng(n, w)
        se = miles_to_latlng(s, e)
        results.append((nw, se))

   # print(str(results))
    return results


def miles_to_latlng(north, west):
    ldae = 69.172
    lat = north / ldae
    lng = west / (ldae * radians(lat))
     
    return (lat, lng)


def make_bigger(x):
    if x > 0:
       x = x + 0.5
    elif x < 0:
       x = x - 0.5
    return x

def squares_rides_task(request, task_id):
    job = AsyncResult(task_id)
    results = {'state': str(job.state)}
    if job.state == "PROGRESS":
        results['id'] = job.result['id']
        results['ride'] = job.result['ride']
        results['polyline'] = job.result['polyline'] 
    return JsonResponse(results)


def squares_rides_ride(request, ride_id):
    ride = get_object_or_404(SquareRide, pk=ride_id)
    squares = get_squares_for_line(ride.polyline)
    results = {'id':ride.id, 'ride':ride.name, 'polyline':ride.polyline, 'squares':squares}
    return JsonResponse(results)


def decode_polyline(polyline_str):
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    # Coordinates have variable length when encoded, so just keep
    # track of whether we've hit the end of the string. In each
    # while loop iteration, a single coordinate is decoded.
    while index < len(polyline_str):
        # Gather lat/lon changes, store them in a dictionary to apply them later
        for unit in ['latitude', 'longitude']: 
            shift, result = 0, 0

            while True:
                byte = ord(polyline_str[index]) - 63
                index+=1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break

            if (result & 1):
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = (result >> 1)

        lat += changes['latitude']
        lng += changes['longitude']

        coordinates.append((lat / 100000.0, lng / 100000.0))

    return coordinates


