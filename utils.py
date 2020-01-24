import os
import sys
import json
import uuid
import math

from datetime import datetime
from math import radians, cos, sin, asin, sqrt

import click
import inquirer
import pycountry
import reverse_geocode

from PIL import Image, ExifTags
from GPSPhoto import gpsphoto
from geopy.geocoders import Nominatim

from constants import *
from models import Base, TourType, TransportType, Tour, Photo, TourTransport

import openlocationcode as olc


intg_modules = []
init = True

try:
    from modules.googlestreetview import GoogleStreetView
    gsv = GoogleStreetView(init)
    intg_modules.append((gsv.name, gsv.short_name))
except:
    pass

try:
    from modules.opentrailview import OpenTrailView
   
    otv = OpenTrailView(init)
    intg_modules.append((otv.name, otv.short_name))
except:
    pass

try:
    from modules.explorer import Explorer
    explorer = Explorer(init)
    intg_modules.append((explorer.name, explorer.short_name))
except:
    pass



def initdb():
    '''
    Initialize the database
    '''
    Base.metadata.create_all(engine, checkfirst=True)
    landtours = [ 
        TransportType.Drive,
        TransportType.Hike,
        TransportType.Bike,
        TransportType.Climb,
        TransportType.Ski,
        TransportType.Snowboard,
        TransportType.Skateboard,
        TransportType.Rollerblade,
        TransportType.OtherLand
    ]
    
    for l in landtours:
        landdescr = TourTransport(tour_type=TourType.Land, tour_transport=l)
        session.add(landdescr)
        session.commit()

    watertours = [ 
        TransportType.Sail,
        TransportType.Kayak,
        TransportType.Raft,
        TransportType.StandupPaddleBoard,
        TransportType.OtherWater
    ]

    for w in watertours:
        waterdescr = TourTransport(tour_type=TourType.Water, tour_transport=w)
        session.add(waterdescr)
        session.commit()
    
    airtours = [ 
        TransportType.Drone,
        TransportType.HangGlide,
        TransportType.Parachute,
        TransportType.Windsuit,
        TransportType.Plane,
        TransportType.OtherAir
    ]

    for a in airtours:
        airdescr = TourTransport(tour_type=TourType.Air, tour_transport=a)
        session.add(airdescr)
        session.commit()

    print('Database created')


def validate_string(what, value, maxlen):
    if len(value) <= maxlen:
        return value
    else:
        click.echo('{} too long, should be no more than {} characters'.format(what, maxlen))
        value = click.prompt('Please enter a new {}'.format(what.lower()), type=str, default=value)
        return validate_string(what, value, maxlen)


def calculate_initial_compass_bearing(pointA, pointB):
    if (type(pointA) != tuple) or (type(pointB) != tuple):
        raise TypeError('Only tuples are supported as arguments')

    lat1 = math.radians(pointA[0])
    lat2 = math.radians(pointB[0])

    diffLong = math.radians(pointB[1] - pointA[1])

    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1)
            * math.cos(lat2) * math.cos(diffLong))

    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing


def haversine(lon1, lat1, lon2, lat2):
    '''
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    '''
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371

    distance = (c * r) * 1000

    return distance


def find_connection(photo_1, photo_2):
    lat1 = float(photo_1.lat)
    lon1 = float(photo_1.lon)
    lat2 = float(photo_2.lat)
    lon2 = float(photo_2.lon)

    distance = haversine(lon1, lat1, lon2, lat2)
    elevation = float(photo_2.elevation) - float(photo_1.elevation)
    heading = calculate_initial_compass_bearing((lat1, lon1), (lat2, lon2))

    try:
        pitch = elevation / distance
    except ZeroDivisionError:
        pitch = 0

    if -5 <= elevation <= 5 and distance <= 10:
        connection = {
            'photo_id': photo_2.photo_id,
            'distance': distance,
            'elevation': elevation,
            'pitch': pitch,
            'heading': heading
        }
    else:
        connection = None

    return connection


def validate_file(path):
    is_file_valid = True
    errorcase = []
    _, fext = os.path.splitext(path)

    if fext.lower() not in SUPPORTED_FORMATS:
        is_file_valid = False
        errorcase.append('The photo are not a supported filetype')
    else:
        img = Image.open(path)
        exif_data = {
            ExifTags.TAGS[k]: v
            for k, v in img._getexif().items()
            if k in ExifTags.TAGS
        }

        imgwidth = exif_data.get('ImageWidth', 1)
        imgheight = exif_data.get('ImageLength', 1)
        gpsinfo = gpsphoto.getGPSData(path)
        
        if len(gpsinfo) > 0:
            time = gpsinfo.get('UTC-Time')
            date = gpsinfo.get('Date')
            dt = date + ' ' + time
            timestamp = datetime.strptime(dt, '%m/%d/%Y %H:%M:%S')
        else:
            timestamp = exif_data.get('DateTimeOriginal', None)

        fsize = os.stat(path)

        if len(gpsinfo) == 0:
            is_file_valid = False
            errorcase.append('The photo do not contain any GPS data')

        if not gpsinfo.get('Latitude'):
            is_file_valid = False
            errorcase.append('The photo has no latitude')
        
        if not gpsinfo.get('Longitude'):
            is_file_valid = False
            errorcase.append('The photo has no longitude')

        if not gpsinfo.get('Altitude'):
            is_file_valid = False
            errorcase.append('The photo has no altitude')

        if not timestamp:
            is_file_valid = False
            errorcase.append('The photo has no taken date')

        if fsize.st_size >= 75000000:
            is_file_valid = False
            errorcase.append('The photo file size too large')

        if all([imgwidth > 1, imgheight > 1]) and imgwidth / imgheight != 2:
            errorcase.append('Warning: The following photo do not meet the minimum Google Street View aspect ratio 2:1')
        
        if imgwidth * imgheight < 7500000:
            is_file_valid = False
            errorcase.append('The photo megapixels too small')

        if imgwidth * imgheight > 100000000:
            is_file_valid = False
            errorcase.append('The photo megapixels too large')
        
    if is_file_valid:
        return {'fname': path, 'meta': exif_data, 'timestamp': timestamp, 'gpsdata': gpsinfo}
    else:
        errorcase = '\n'.join(errorcase)
        click.confirm('{}. \n{} will be ignored. Do you want to continue?'.format(errorcase, path), abort=True)


def get_tour_transport():
    transports = session.query(TourTransport).all()
    transp_message = '\n'.join(['{}. {}-{}'.format(t.transp_id, t.tour_type.name, t.tour_transport.name) for t in transports])
    transp_message = 'Please select tour type: \n' + transp_message + '\n'
    tour_transp_id = click.prompt(transp_message, type=int)

    tourtransp = session.query(TourTransport).filter(TourTransport.transp_id == tour_transp_id).first()
    if not tourtransp:
        print('There is no such id, try again')
        return get_tour_transport()
    else:
        return tourtransp


def get_integrations():
    status = False
    i_modules = integrations_status(status) 
    integrations_select = [
        inquirer.Checkbox('integrations',
            message='Select the integrations you want to sync tour. To configure a new integration before uploading, please read the docs. (use spacebar)',
            choices=i_modules
        )
    ]

    integrations = inquirer.prompt(integrations_select)
    if integrations:
        intgr = integrations.get('integrations')
    else:
        sys.exit()

    return intgr


def get_available_integrations(tour, select=None):
    status = False
    available_integrations = integrations_status(status) 
    integrations_list = [] 

    if select == 'include':
        integrations_list = []
        if not tour.integrations:
            return None
    elif select == 'exclude':
        integrations_list += available_integrations

    if tour.integrations:
        intg = tour.integrations.split(',')
    else:
        intg = []

    for x in available_integrations:
        for i in intg:
            if select == 'include' and x[1] == i:
                integrations_list.append(x)
            elif select == 'exclude' and x[1] == i:
                integrations_list.remove(x)
            elif not select and x[1] == i:
                integrations_list.append(x[0])

    if select:
        if integrations_list:
            integration_select = [
                    inquirer.List('integration',
                        message='Select the integration on which you want to take action',
                        choices=integrations_list
                    )
            ]
            
            integration = inquirer.prompt(integration_select)
            if integration:
                intg = integration.get('integration')
                for x in known_modules:
                    if x[1] == intg:
                        integrations = x
            else:
                sys.exit()
        else:
            return None
    else:
        if integrations_list:
            integrations = ', '.join(integrations_list)
        else:
            integrations = 'No integrations'

    return integrations


def get_options():
    options_select = [
            inquirer.Checkbox('options',
                message='Choose what you want to do. (use spacebar)',
                choices=[
                    ('Edit tour fields', 'edit_tour'),
                    ('Add new photos', 'add_photos'),
                    ('Delete photo', 'delete_photo'),
                    ('Add new integration', 'add_integration'),
                    ('Remove integration', 'remove_integration'),
                    ('Delete entire tour', 'delete_tour')
                ]
            )
    ]
    
    options = inquirer.prompt(options_select)
    if options:
        opt = options.get('options')
    else:
        sys.exit()
    
    if not opt:
        print('Choose at least one option')
        return get_options()
    else:
        return opt


def get_tags():
    choices = [('Enter tags manually', 'manual')]

    with open('tag-library.json', 'r') as f:
        ch = json.load(f)

    for x in ch:
        descr = x[0].capitalize() + ' - ' + x[1]
        choices.append(tuple([descr, x[0]]))

    tags_select = [
            inquirer.Checkbox('tags',
                message='Select the tags you want to add. (use spacebar)',
                choices=choices
            )
    ]
    
    tags = inquirer.prompt(tags_select)
    if tags:
        tgs = tags.get('tags')
    else:
        sys.exit()

    if not tgs:
        print('Choose at least one tag')
        return get_tags()
    else:
        return tgs


def get_fields():
    fields_select = [
            inquirer.Checkbox('fields',
                message='Select the fields you want to edit tour. (use spacebar)',
                choices=[
                    ('Description', 'description'),
                    ('Tags', 'tags'),
                    ('Type', 'type')
                ]
            )
    ]
    
    fields = inquirer.prompt(fields_select)
    if fields:
        fld = fields.get('fields')
    else:
        sys.exit()

    if not fld:
        print('Choose at least one field')
        return get_fields()
    else:
        return fld


def integrations_status(status):
    av_modules = []
    for x in intg_modules:
        if x[1] == 'gsv':
            if auth_config[0]['client_id'] and auth_config[0]['client_secret']:
                if status:
                    print(x[0], 'Active')
                av_modules.append(x)
            else:
                if status:
                    print(x[0], 'Inactive')
        elif x[1] == 'otv':
            if auth_config[1]['client_id'] and auth_config[1]['client_secret']:
                if status:
                    print(x[0], 'Active')
                av_modules.append(x)
            else:
                if status:
                    print(x[0], 'Inactive')
        elif x[1] == 'explorer':
            if auth_config[2]['key']:
                if status:
                    print(x[0], 'Active')
                av_modules.append(x)
            else:
                if status:
                    print(x[0], 'Inactive')

    return av_modules
        

def edit_tour(tour):
    print('Select the fields to edit:')
    fields = get_fields()

    if 'description' in fields:
        print('Description: ' + tour.description)
        descr = validate_string('Tour description', click.prompt('Please enter new description', type=str), 200)
        tour.description = descr
    else:
        descr = tour.description

    if 'tags' in fields:
        print('Tags: ' +  tour.tags)
        tags = get_tags()
        if 'manual' in tags:
            tags = ','.join(tags[:-1])
            manual_tags = validate_string('Tour tags', click.prompt('Please enter new tags, comma-separated', type=str), 500)
            tags += ',' + manual_tags
        else:
            tags = ','.join(tags)

        tour.tags = tags
    else:
        tags = tour.tags

    if 'type' in fields:
        tour_type = tour.transport.tour_type.name
        transport_type = tour.transport.tour_transport.name
        print('Tour type: {}  Tour transport: {}'.format(tour_type, transport_type))
        transport = get_tour_transport()
        tour.transport = transport
    else:
        transport = tour.transport

    integrations = tour.integrations.split(',')

    if 'explorer' in integrations:
        explorer = Explorer()
        tour_type = transport.tour_type.name.lower()
        transport_type = transport.tour_transport.name.lower()
        tags = tour.tags.replace(',', ', ')
        explorer.update_tour(tour.explorer_tour_id, tour.tour_id, descr, tags, tour_type, transport_type, None)
        
    session.add(tour)
    session.commit()


def set_tour_connections(tour):
    sorted_photos = []

    previous_photo = None
    for x in tour.photos:
        connections = []
        next_photo = None
        
        for y in tour.photos:
            if x != y:
                if x.taken < y.taken and next_photo:
                    if y.taken < next_photo.taken:
                        next_photo = y

                elif x.taken < y.taken:
                    next_photo = y
                        
                connection = find_connection(x, y)
                if not connection:
                    continue
                else:
                    connections.append(connection)

        if next_photo:
            lat1 = float(x.lat)
            lon1 = float(x.lon)
            lat2 = float(next_photo.lat)
            lon2 = float(next_photo.lon)
            
            x.photo_heading = calculate_initial_compass_bearing((lat1, lon1), (lat2, lon2))
            for xc in connections:
                adjusted_heading_degrees = x.photo_heading - xc['heading']
                xc['adjusted_heading'] = adjusted_heading_degrees

        elif previous_photo:
            x.photo_heading = previous_photo.photo_heading
            for xc in connections:
                adjusted_heading_degrees = float(previous_photo.photo_heading) - xc['heading']
                xc['adjusted_heading'] = adjusted_heading_degrees

        previous_photo = x
        x.connections = json.dumps(connections)
        session.add(x)
        session.commit()


def update_connections(photos):
    for x in photos:
        photo_id = x['tourer[photo_id]']
        photo = session.query(Photo).filter(Photo.photo_id == photo_id).first()
        x['tourer[heading_degrees]'] = photo.photo_heading
        connections = json.loads(photo.connections)
        for i, y in enumerate(connections):
            con = {
                'tourer[connections][{}][photo_id]'.format(i): y['photo_id'],
                'tourer[connections][{}][distance_meters]'.format(i): y['distance'],
                'tourer[connections][{}][elevation_meters]'.format(i): y['elevation'],
                'tourer[connections][{}][pitch_degrees]'.format(i): y['pitch'],
                'tourer[connections][{}][heading_degrees]'.format(i): y['heading'],
                'tourer[connections][{}][adjusted_heading_degrees]'.format(i): y.get('adjusted_heading'),
            }
            x.update(con)


def upload_photos(tour, validated_files, integrations, mode='basic'):
    photos = []
    integrations_list = []

    if validated_files:
        file_count = len(validated_files)        
        for fl in validated_files:
            if mode == 'integration':
                photo = session.query(Photo).filter(Photo.photo_id == fl['photo_id']).first()
            else:
                capture_time = fl['timestamp']
                latitude = fl['gpsdata']['Latitude']
                longitude = fl['gpsdata']['Longitude']
                altitude = fl['gpsdata'].get('Altitude', None)
                camera_make = fl['meta'].get('Make', None)
                camera_model = fl['meta'].get('Model', None)
                crd = (latitude, longitude), (31.76, 35.21)
                geolocator = reverse_geocode.search(crd)[0]
                country = geolocator['country']
                country_code = geolocator['country_code']
                lc = olc.encode(latitude, longitude)
                path, filename = os.path.split(fl['fname'])
                photo_id = str(uuid.uuid4())[:8]

                photo = Photo(
                    tour=tour,
                    filename=filename,
                    filepath=path,
                    fullpath=fl['fname'],
                    country_code=country_code, 
                    country=country,
                    lat=latitude,
                    lon=longitude,
                    elevation=str(altitude),
                    location_code=lc,
                    camera_make=camera_make,
                    camera_model=camera_model,
                    photo_id=photo_id,
                    taken=capture_time,
                    uploaded=True
                )

                session.add(photo)
                session.commit()
    
                print('New photo created, photo ID: {}'.format(photo_id))

            if 'explorer' in integrations:
                photo_data = set_photo_data(photo)
                photos.append(photo_data)

    set_tour_connections(tour)

    if 'gsv' in integrations:
        terms = click.confirm('Google Street View: Do you agree to Google’s Terms of Service? https://policies.google.com/terms')
        if not terms:
            print('Google Street View: We can not upload files without your agreement')
            return None

        gsv = GoogleStreetView()
        integrations_list.append('gsv')
        if mode != 'integration':
            tour.integrations = ','.join(integrations_list)
            session.add(tour)
            session.commit()

        photos = []
        for photo in tour.photos:
            if mode == 'integration':
                old_photo = session.query(Photo).filter(Photo.photo_id == photo.photo_id).first()
                photo = old_photo

            fl = {
                'timestamp': photo.taken,
                'fname': photo.fullpath,
                'gpsdata': {
                    'Latitude': photo.lat,
                    'Longitude': photo.lon,
                    'Altitude': photo.elevation
                }
            }
            uploaded_photo = gsv.upload_photo(fl)
            photo.street_view_photoid = uploaded_photo.photo_id.id
            if photo.street_view_photoid:
                photo.street_view_download_url = uploaded_photo.download_url
                photo.street_view_sharelink = uploaded_photo.share_link
                photo.street_view_thumbnail_url = uploaded_photo.thumbnail_url
                photo.street_view_capture_time = str(fl['timestamp'])
                photo.street_view_lat = str(fl['gpsdata']['Latitude'])
                photo.street_view_lon = str(fl['gpsdata']['Longitude'])
                photo.street_view_altitude = str(fl['gpsdata']['Altitude'])
                session.add(photo)
                session.commit()

            if 'explorer' in integrations:
                photo_data = set_photo_data(photo)
                photos.append(photo_data)

        print('Google Street View: Your tour is now being uploaded to Google. It can take up to 72 hours for them to be published.')

    if 'otv' in integrations:
        otv = OpenTrailView()
        integrations_list.append('otv')
        if mode != 'integration':
            tour.integrations = ','.join(integrations_list)
            session.add(tour)
            session.commit()

        photos = []
        for photo in tour.photos:
            fl = {
                'timestamp': photo.taken,
                'fname': photo.fullpath,
                'gpsdata': {
                    'Latitude': photo.lat,
                    'Longitude': photo.lon,
                    'Altitude': photo.elevation
                }
            }
            photo.otv_pano_id = otv.upload_photo(fl, tour.tour_id)
            session.add(photo)
            session.commit()

            if 'explorer' in integrations:
                photo_data = set_photo_data(photo)
                photos.append(photo_data)
        
    if 'explorer' in integrations:
        explorer = Explorer()
        tour_type = tour.transport.tour_type.name.lower()
        transport_type = tour.transport.tour_transport.name.lower()
        tags = tour.tags.replace(',', ', ')
        update_connections(photos)

        if mode == 'update':
            explorer.update_tour(tour.explorer_tour_id, photos=photos)
            # update_photo_list = []
            # for p in tour.photos:
            #     photo_data = set_photo_data(p)
            #     update_photo_list.append(photo_data)

            # update_connections(update_photo_list)
            # for x in update_photo_list:
            #     explorer.update_photo(x, tour.explorer_tour_id, x['explorer_photo_id'])

        else:
            explorer_tour_id = explorer.create_tour(tour.name, tour.description, tags, tour_type,
                                                    transport_type, tour.tour_id)
            if explorer_tour_id:
                tour.explorer_tour_id = explorer_tour_id
                integrations_list.append('explorer')
                if mode != 'integration':
                    tour.integrations = ','.join(integrations_list)
                session.add(tour)
                session.commit()
                
                for photo in photos:
                    explorer_photo_id = explorer.add_photo(explorer_tour_id, photo)
                    photo_id = photo['tourer[photo_id]']
                    photo = session.query(Photo).filter(Photo.photo_id == photo_id).first()
                    photo.explorer_photo_id = explorer_photo_id
                    session.add(photo)
                    session.commit()

            else:
                if mode == 'integration':
                    print('Failed to add explorer integration')
                    sys.exit()

    if mode == 'integration':
        if tour.integrations:
            intg = tour.integrations.split(',') + integrations_list
            tour.integrations = ','.join(intg)
        else:
            tour.integrations = ','.join(integrations_list)
    else:
        tour.integrations = ','.join(integrations)

    return tour


def create_tour(validated_files, integrations, name, description, tags, transport):
    tour_id = str(uuid.uuid4())[:8]
    tour = Tour(
                name=name,
                description=description,
                tags=tags,
                transport=transport,
                tour_id=tour_id
            )

    tour_inst = upload_photos(tour, validated_files, integrations)
   
    session.add(tour_inst)
    session.commit()

    print('New tour created, tour ID: {}'.format(tour_id))


def update_tour(tour, validated_files):
    integrations = tour.integrations.split(',')
    tour_inst = upload_photos(tour, validated_files, integrations, 'update')

    print('Tour {} updated'.format(tour.name))
    

def delete_tour(tour, integration=None):
    delete = True
    
    if integration:
        integrations = integration
    else:
        confirm = click.prompt('Please type DELETE to delete tour', type=str)
        if not confirm == 'DELETE':
            print('Confirmation failed')
            return None
        integrations = tour.integrations.split(',')

    if 'gsv' in integrations:
        gsv = GoogleStreetView()
        for p in tour.photos:
            if hasattr(p, 'street_view_photoid'):
                gsv_photo_id = p.street_view_photoid
                success = gsv.delete_photo(gsv_photo_id)
                if not success:
                    confirm = click.confirm('This photo cannot be deleted this time. Do you still want to continue with delete? This will mean you cannot delete this photo later using tourer',
                                            abort=True)
                    if not confirm:
                        sys.exit()
            else:
                delete = False
                print('Google Street View is out of sync, run forcesync to sync, then run delete')
                break
   
    if 'otv' in integrations:
        otv = OpenTrailView()
        for p in tour.photos:
            if hasattr(p, 'otv_pano_id'):
                otv_pano_id = p.otv_pano_id
                success = otv.delete_photo(otv_pano_id)
                if not success:
                    delete = False
                    return None
            else:
                delete = False
                print('Open Trail View is out of sync, run forcesync to sync, then run delete')
                break

    if 'explorer' in integrations:
        explorer = Explorer()
        explorer_tour_id = tour.explorer_tour_id        
        success = explorer.delete_tour(explorer_tour_id)
        if not success:
            delete = False
            return None

    if not integration:
        if delete:
            for photo in tour.photos:
                session.delete(photo)
                session.commit()

            session.delete(tour)
            session.commit()
            print('Tour {} deleted'.format(tour.name))
        else:
            print('Tour {} cannot be deleted'.format(tour.name))


def delete_photo(tour):
    delete = True
    photo_id = click.prompt('Enter photo ID', type=str)
    photo = session.query(Photo).filter(Photo.photo_id == photo_id).first()
    if not photo:
        print('There is no photo with ID {}'.format(photo_id))
        return None
        
    integrations = tour.integrations.split(',')

    if 'gsv' in integrations:
        gsv = GoogleStreetView()
        success = gsv.delete_photo(photo.street_view_photoid)
        if not success:
            delete = False
            confirm = click.confirm('This photo cannot be deleted this time. Do you still want to continue with delete? This will mean you cannot delete this photo later using tourer', abort=True)
            if not confirm:
                sys.exit()
        
    if 'otv' in integrations:
        otv = OpenTrailView()
        success = otv.delete_photo(photo.otv_pano_id)
        if not success:
            delete = False

    if 'explorer' in integrations:
        explorer = Explorer()
        success = explorer.delete_photo(tour.explorer_tour_id, photo.explorer_photo_id)
        if not success:
            delete = False

    if delete:
        set_tour_connections(tour)

        # if 'explorer' in integrations:
        #     update_photo_list = []
        #     for p in tour.photos:
        #         photo_data = set_photo_data(p)
        #         update_photo_list.append(photo_data)

        #     update_connections(update_photo_list)
        #     for x in update_photo_list:
        #         explorer.update_photo(x, tour.explorer_tour_id, x['explorer_photo_id'])
                
        session.delete(photo)
        session.commit()
        print('Photo {} deleted'.format(photo.photo_id))
    else:
        print('Photo {} cannot be deleted'.format(photo.photo_id))


def list_tours(tours):
    if tours:
        for t in tours:
            integrations = get_available_integrations(t)
            print('ID: {}  Created: {}  Name: {}  Description: {}  Photos: {}  Integrations: {}'
                    .format(t.tour_id, t.created, t.name, t.description, len(t.photos), integrations))
    else:
        print('You have not created any tours yet')


def list_photos(tour_id):
    tour = session.query(Tour).filter(Tour.tour_id == tour_id).first()
    if tour:
        photos = tour.photos
        if photos:
            for p in photos:
                print('ID: {}  Created: {}  Filename: {}'.format(p.photo_id, p.created, p.filename))
        else:
            print('You have not uploaded any photos yet')
    else:
        print('There is no tour with ID {}'.format(tour_id))


def fetchgsv():
    gsv = GoogleStreetView()
    photos = session.query(Photo).all()
    gsv_photo_ids = []
    for photo in photos:
        if photo.street_view_photoid:
            gsv_photo_ids.append(photo.street_view_photoid)
    
    info_batch = gsv.get_photo_info(gsv_photo_ids)

    if info_batch:
        for info in info_batch:
            if not info.status:
                photo.street_view_sharelink = info.share_link
                photo.street_view_lat = info.pose.lat_lng_pair.latitude
                photo.street_view_lon = info.pose.lat_lng_pair.latitude
                photo.street_view_altitude = info.pose.altitude
                photo.street_view_heading = info.pose.heading
                photo.street_view_pitch = info.pose.pitch
                photo.street_view_roll = info.pose.roll
                photo.street_view_level = str(info.pose.level)
                
                session.add(photo)
                session.commit()
    else:
        print('Google Street View: Failed to get photo data')


def validate_files(path):
    is_valid_path = True
    single_file = False
    validated_files = []
    
    if os.path.isfile(path):
        single_file = True
        print('Single file: {}'.format(path))
    elif os.path.isdir(path):
        print('Directory: {}'.format(path))
    else:
        is_valid_path = False
        print('Invalid path {}'.format(path))
        return None

    if single_file:
        validated_files.append(validate_file(path))
    else:
        for f in os.listdir(path):
            if not f.startswith('.'):
                f = os.path.abspath(os.path.join(path,f))
                valid_file = validate_file(f)
                if valid_file:
                    validated_files.append(valid_file)
            
    return validated_files

def set_photo_data(photo):
    photo_data = {
        'explorer_photo_id': photo.explorer_photo_id,
        'fullpath': photo.fullpath,
        'filename': photo.filename,
        'taken_at': photo.taken,
        'latitude': str(photo.lat),
        'longitude': str(photo.lon),
        'elevation_meters': photo.elevation,
        'camera_make': photo.camera_make,
        'camera_model': photo.camera_model,
        'google[plus_code_global_code]': photo.location_code,
        'google[plus_code_compound_code]': None,
        'address[cafe]': None,
        'address[road]': None,
        'address[suburb]': None,
        'address[county]': None,
        'address[region]': None,
        'address[state]': None,
        'address[postcode]': None,
        'address[country]': photo.country,
        'address[country_code]': photo.country_code,
        'streetview[photo_id]': photo.street_view_photoid,
        'streetview[capture_time]': photo.street_view_capture_time,
        'streetview[share_link]': photo.street_view_sharelink,
        'streetview[download_url]': photo.street_view_download_url,
        'streetview[thumbnail_url]': photo.street_view_thumbnail_url,
        'streetview[lat]': photo.street_view_lat,
        'streetview[lon]': photo.street_view_lon,
        'streetview[altitude]': photo.street_view_altitude,
        'streetview[heading]': '0',
        'streetview[pitch]': '0',
        'streetview[roll]': '0',
        'streetview[level]': None,
        'streetview[connections]': None,
        'opentrailview[photo_id]': photo.otv_pano_id,
        'tourer[photo_id]': photo.photo_id,
    }

    return photo_data


def set_local_tour(local_tour, ed):
    tags = ','.join(ed['tags'])
    transport = session.query(TourTransport).filter(TourTransport.tour_type == ed['tour_type'].capitalize(),
                                            TourTransport.tour_transport == ed['transport_type'].capitalize()).first()
    local_tour.name = ed['name']
    local_tour.description = ed['description']
    local_tour.tags = tags
    local_tour.transport = transport

    session.add(local_tour)
    session.commit()

    
def set_local_photo(local_photo, ed):
    local_photo.filename = ed['filename']
    local_photo.taken = datetime.strptime(ed['taken_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
    local_photo.latitude = ed['latitude']
    local_photo.longitude = ed['longitude']
    local_photo.elevation = ed['elevation_meters']
    local_photo.location_code = ed['google']['plus_code_global_code']
    local_photo.country = ed['address']['country']
    local_photo.country_code = ed['address']['country_code']
    local_photo.street_view_photoid = ed['streetview']['photo_id']
    local_photo.street_view_capture_time = ed['streetview']['capture_time']
    local_photo.street_view_sharelink = ed['streetview']['share_link']
    local_photo.street_view_download_url = ed['streetview']['download_url']
    local_photo.street_view_thumbnail_url = ed['streetview']['thumbnail_url']
    local_photo.street_view_lat = ed['streetview']['lat']
    local_photo.street_view_lon = ed['streetview']['lon']
    local_photo.street_view_altitude = ed['streetview']['altitude']
    local_photo.street_view_heading = ed['streetview']['heading']                                  
    local_photo.street_view_pitch = ed['streetview']['pitch']                          
    local_photo.street_view_roll = ed['streetview']['roll']                               
    local_photo.street_view_level = ed['streetview']['level']                         
    local_photo.street_view_connections = ed['streetview']['connections']
    local_photo.connections = str(ed['tourer']['connections'])
                                                                   
    session.add(local_photo)
    session.commit()


def sync_pull():
    explorer = Explorer()
    user_id = explorer.get_user_id()
    if user_id:
        tours = explorer.list_tours(user_id)
        for tour in tours:
            explorer_tour_id = tour['id']
            local_tour = session.query(Tour).filter(Tour.explorer_tour_id == explorer_tour_id).first()
            if local_tour:
                set_local_tour(local_tour, tour)
                photos = explorer.list_photos(explorer_tour_id)
                for photo in photos:
                    explorer_photo_id = photo['id']
                    local_photo = session.query(Photo).filter(Photo.explorer_photo_id == explorer_photo_id).first()
                    if local_photo:
                        set_local_photo(local_photo, photo)
  

def sync_push(intg_status):
    tours = session.query(Tour).all()
    for tour in tours:
        if tour.integrations:
            tour_intg = tour.integrations.split(',')
        else:
            tour_intg = []
        
        if ('Google Street View', 'gsv') in intg_status and 'gsv' in tour_intg:
            gsv = GoogleStreetView()
            for photo in tour.photos:
                if not photo.street_view_photoid:
                    fl = {
                        'timestamp': photo.taken,
                        'fname': photo.fullpath,
                        'gpsdata': {
                            'Latitude': photo.lat,
                            'Longitude': photo.lon,
                            'Altitude': photo.elevation
                        }
                    }
                    uploaded_photo = gsv.upload_photo(fl)
                    photo.street_view_photoid = uploaded_photo.photo_id.id
                    if photo.street_view_photoid:
                        photo.street_view_download_url = uploaded_photo.download_url
                        photo.street_view_sharelink = uploaded_photo.share_link
                        photo.street_view_thumbnail_url = uploaded_photo.thumbnail_url
                        photo.street_view_capture_time = str(fl['timestamp'])
                        photo.street_view_lat = str(fl['gpsdata']['Latitude'])
                        photo.street_view_lon = str(fl['gpsdata']['Longitude'])
                        photo.street_view_altitude = str(fl['gpsdata']['Altitude'])
                        session.add(photo)
                        session.commit()

        if ('Open Trail View', 'otv') in intg_status and 'otv' in tour_intg:
            otv = OpenTrailView()
            for photo in tour.photos:
                if not photo.otv_pano_id:
                    fl = {
                        'timestamp': photo.taken,
                        'fname': photo.fullpath,
                        'gpsdata': {
                            'Latitude': photo.lat,
                            'Longitude': photo.lon,
                            'Altitude': photo.elevation
                        }
                    }
                
                    photo.otv_pano_id = otv.upload_photo(fl, tour.tour_id)
                    session.add(photo)
                    session.commit()

        photos = session.query(Photo).filter(Photo.tour_id == tour.tour_id)
        explorer_tour_id = tour.explorer_tour_id
        update_photo_list = []
        for photo in tour.photos:
            photo_data = set_photo_data(photo)
            update_photo_list.append(photo_data)
            
        if explorer_tour_id and ('Trek View Explorer', 'explorer') in intg_status:
            explorer = Explorer()
            name = tour.name
            description = tour.description
            tags = tour.tags.replace(',', ', ')
            tour_type = tour.transport.tour_type.name.lower()
            transport_type = tour.transport.tour_transport.name.lower()
               
            update_connections(update_photo_list)
            for photo_data in update_photo_list:
                explorer_photo_id = photo_data.get('explorer_photo_id')
                if explorer_photo_id:
                    explorer.update_photo(photo_data, explorer_tour_id, explorer_photo_id)
                else:
                    explorer_photo_id = explorer.add_photo(explorer_tour_id, photo_data)
                    if explorer_photo_id:
                        photo_id = photo_data['tourer[photo_id]']
                        photo = session.query(Photo).filter(Photo.photo_id == photo_id).first()
                        photo.explorer_photo_id = explorer_photo_id
                        session.add(photo)
                        session.commit()

            explorer.update_tour(explorer_tour_id, tour.tour_id, description, tags, tour_type, transport_type, None)
  

def add_integration(tour):
    intg = get_available_integrations(tour, 'exclude')
    if intg:
        validated_files = []
        for p in tour.photos:
            f = validate_file(p.fullpath)
            f['photo_id'] = p.photo_id
            validated_files.append(f)

        tour = upload_photos(tour, validated_files, [intg[1]], 'integration')
        intg_list = tour.integrations.split(',')

        if intg_list:
            session.add(tour)
            session.commit()
            print('Integration {} added'.format(intg[0]))
        else:
            print('Failed to add integration')

    else:
        print('You do not have integrations available')


def remove_integration(tour):
    intg = get_available_integrations(tour, 'include')
    if intg:
        delete_tour(tour, [intg[1]])
        intg_list = tour.integrations.split(',')
        intg_list.remove(intg[1])
        if intg_list:
            tour.integrations = ','.join(intg_list)            
        else:
            tour.integrations = ''

        session.add(tour)
        session.commit()
        print('Integration {} removed'.format(intg[0]))
    else:
        print('No integrations to remove')
