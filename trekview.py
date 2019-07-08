#!/usr/bin/env python
# -*- coding: utf-8 -*-

import configparser
from google.streetview.publish_v1.proto import resources_pb2
from google.streetview.publish_v1 import street_view_publish_service_client as client
from google.streetview.publish_v1 import enums
from google.api_core.gapic_v1.method import DEFAULT as retrymethod
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from oauth2client import tools
import google.oauth2.credentials
import requests
import time
import datetime
import os
import json
from PIL import Image, ExifTags
from tqdm import tqdm
import googleapiclient.discovery
import click
import pprint
from GPSPhoto import gpsphoto

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from models import Base, TourType, TransportType, Tour, Photo, TourDescription

pp = pprint.PrettyPrinter(indent=4)

config = configparser.ConfigParser()
config.read('config.ini')
client_id = config['googleauth']['client_id']
client_secret = config['googleauth']['client_secret']
credentials_file = config['googleauth']['credentials_file']
db_file = config['other']['database_file']

engine = create_engine(f'sqlite:///{db_file}')
Session = sessionmaker(bind=engine)
session = Session()

successful_upload_message = "Your tour is now being uploaded to Google. It can take up to 72 hours for them to be published on Google Street View"

@click.group()
def cli():
    pass

def validate_file(fpath):
    is_file_valid = True
    errorcase = []
    img = Image.open('MULTISHOT_1782_000016.jpg')
    exif_data = {
        ExifTags.TAGS[k]: v
        for k, v in img._getexif().items()
        if k in ExifTags.TAGS
    }
    imgwidth = exif_data.get('ImageWidth', 1)
    imgheight = exif_data.get('ImageLength', 1)
    timestamp = exif_data.get('DateTimeOriginal', None)
    fsize = os.stat(fpath)
    gpsinfo = gpsphoto.getGPSData(fpath)
    # has timestamp
    if not timestamp:
        is_file_valid = False
        errorcase.append("no timestamp")
    if  3000000 >= fsize.st_size or fsize.st_size >= 75000000:
        is_file_valid = False
        errorcase.append("insuffisent filesize")
    # validate ratio: must be 2:1 w:h
    if all([imgwidth > 1, imgheight > 1]):
        if imgwidth/imgheight != 2:
            is_file_valid = False
            errorcase.append("insuffisent width:height ratio")
    else:
        is_file_valid = False
    # validate resolution: must be at least 7.5MP (4K)
    if imgwidth * imgheight < 7500000:
        is_file_valid = False
        errorcase.append("resolution too small ")

    # validate coordinates
    if len(gpsinfo) == 0:
        is_file_valid = False

    if is_file_valid:
        return {"fname": fpath, "meta": exif_data}
    else:
        errorcase = ", ".join(errorcase)
        click.confirm(f"File {fpath} is invalid, the case is {errorcase}. This file wouldn't be published. Do you want to continue?", abort=True)
        
def get_access_token():
    flow = OAuth2WebServerFlow(client_id=client_id,
                               client_secret=client_secret,
                               scope=['https://www.googleapis.com/auth/streetviewpublish',
                                      'https://www.googleapis.com/auth/userinfo.email',
                                      'https://www.googleapis.com/auth/userinfo.profile'
                               ],
    )
    storage = Storage(credentials_file)
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        # don't open browser, show the auth link in terminal
        credentials = tools.run_flow(flow, storage, tools.argparser.parse_args(args=['--noauth_local_webserver']))
    # check token 
    tokeninfo = get_token_info(credentials.access_token)
    if tokeninfo == -1:
        #credentials = tools.run_flow(flow, storage, tools.argparser.parse_args(args=['--noauth_local_webserver']))
        credentials = refresh_token(credentials, storage)
    exp = credentials.token_expiry
    # print(exp)
    assert credentials.access_token is not None
    return credentials, storage

def get_token_info(token):
    tokeninfo = json.loads(requests.get(f"https://www.googleapis.com/oauth2/v1/tokeninfo?alt=json&access_token={token}").text)
    seconds_to_expire = int(tokeninfo.get('expires_in', 0))
    if seconds_to_expire == 0:
        return -1
    else:
        expires = datetime.datetime.now() + datetime.timedelta(seconds=seconds_to_expire)
        return expires.strftime("%H:%M:%S %d/%m/%Y")

def refresh_token(credentials, storage):
    token = credentials.access_token
    refresh = credentials.refresh_token
    refresh_credentials = google.oauth2.credentials.Credentials(
      token,
      refresh_token=refresh,
      client_id=client_id,
      client_secret=client_secret,
      token_uri="https://www.googleapis.com/oauth2/v4/token"
    )
    
    refresh_credentials.refresh(google.auth.transport.requests.Request())
    token = refresh_credentials.token
    credentials.access_token = token
    storage.put(credentials)
    return credentials
    
def authenticate_user():
    credentials, storage = get_access_token()
    token = credentials.access_token
    return credentials, token

def get_tour_descr():
    descriptions = session.query(TourDescription).all()
    descr_message = "\n".join(["{}. {}-{}".format(d.descr_id, d.tour_type.name, d.tour_transport.name) for d in descriptions])
    descr_message = "Please select tour type: \n" + descr_message + "\n"
    tour_descr_id =  click.prompt(descr_message, type=int)
    # save new tour
    tourdescr = session.query(TourDescription).filter(TourDescription.descr_id == tour_descr_id).first()
    if not tourdescr:
        print("There's no such id, try again")
        get_tour_descr()
    else:
        return tourdescr

def upload_files(path, tour=None):
    creds, token = authenticate_user()
    credentials = google.oauth2.credentials.Credentials(token) 
    is_valid_path = True
    single_file = False
    validated_files = []
    
    if os.path.isfile(path):
        single_file = True
        print(f"Single file: {path}")
    elif os.path.isdir(path):
        print(f'Directory: {path}')
    else:
        is_valid_path = False
        print(f"There's no such path {path}")

    if is_valid_path:
        if not click.confirm("Do you agree to Google’s Terms of Service? https://policies.google.com/terms"):
            print("We can't upload files without your agreement")
        else:
            print("Validating files before upload")
            if single_file:
                validated_files.append(validate_file(path))
            else:
                for f in os.listdir(path):
                    f = os.path.abspath(os.path.join(path,f))
                    valid_file = validate_file(f)
                    if valid_file:
                        validated_files.append(valid_file)
            if not tour:
                tourname = click.prompt('Please enter a new tour name', type=str)
                tourdescr = get_tour_descr()
                tour = Tour(tour_name=tourname, descr=tourdescr)
                session.add(tour)
                session.commit()
                print("New tour saved, tour ID: {}".format(tour.tour_id))

            print("Ready to upload {} file(s) for tour {}, ID {}".format(len(validated_files), tour.tour_name, tour.tour_id))

            print("Starting upload")
            # Publish validated files
            # return
            for fl in tqdm(validated_files):
                stclient = client.StreetViewPublishServiceClient(credentials=credentials)
                # TODO: check stclient status
                upload_ref = stclient.start_upload(retry=retrymethod)
                with open(fl['fname'], "rb") as pict:
                    raw_data = pict.read()
                    headers = {
                        "Authorization": "Bearer " + token,
                        "Content-Type": "image/jpeg",
                        "X-Goog-Upload-Protocol": "raw",
                        "X-Goog-Upload-Content-Length": str(len(raw_data)),
                    }
                    # TODO resumable upload
                    r = requests.post(upload_ref.upload_url, data=raw_data, headers=headers)
                    if r.status_code == 200:
                        photo = resources_pb2.Photo()
                        photo.upload_reference.upload_url = upload_ref.upload_url
                        create_photo_response = stclient.create_photo(photo, retry=retrymethod)
                        # TODO check create response
                        photo_id = create_photo_response.photo_id.id
                        print(create_photo_response)
                        newphoto = Photo(tour=tour, photo_filename=fl['fname'], photo_google_id=create_photo_response.photo_id.id)
                        session.add(newphoto)
                        session.commit()
                    
            print(successful_upload_message)

    
@cli.command()
def initdb():
    # create schemas
    Base.metadata.create_all(engine, checkfirst=True)
    # fill tours description table
    # Land tours
    landtours = [ TransportType.Drive,
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
        landdescr = TourDescription(tour_type=TourType.Land, tour_transport=l)
        session.add(landdescr)
        session.commit()
    watertours = [ TransportType.Sail,
                   TransportType.Kayak,
                   TransportType.Raft,
                   TransportType.StandupPaddleBoard,
                   TransportType.OtherWater
    ]
    for w in watertours:
        waterdescr = TourDescription(tour_type=TourType.Water, tour_transport=w)
        session.add(waterdescr)
        session.commit()
        
    
    airtours = [ TransportType.Drone,
                 TransportType.HangGlide,
                 TransportType.Parachute,
                 TransportType.Windsuit,
                 TransportType.Plane,
                 TransportType.OtherAir
    ]
    for a in airtours:
        airdescr = TourDescription(tour_type=TourType.Air, tour_transport=a)
        session.add(airdescr)
        session.commit()
    print("Database created")

    
@cli.command()
def status():
    creds, token = authenticate_user()
    oauth2_client = googleapiclient.discovery.build(
      'oauth2', 'v2',
      credentials=creds)
    clientinfo = oauth2_client.userinfo().v2().me().get().execute()
    print("Your Google account email is {}".format(clientinfo['email']))
    tokeninfo = get_token_info(token)
    if tokeninfo == -1:
        print("Your token has expired")
    else:
        print(f"Your token expires {tokeninfo}")

@cli.command()
def listtours():
    tours = session.query(Tour).all()
    for t in tours:
        descr = t.descr
        print("ID: {} Created: {}  Name: {}, Descr: {} Photos: {}".format(t.tour_id, t.tour_created, t.tour_name, t.descr, len(t.photos)))
        
@cli.command()
@click.argument('tourid')
def listphotos(tourid):
    print("Note: Recently created photos that are still being indexed are not returned in the StreetView response.")
    tour = session.query(Tour).filter(Tour.tour_id == tourid).first()
    if not tour:
        print(f"There's no tour with ID {tourid}")
    else:
        creds, token = authenticate_user()
        credentials = google.oauth2.credentials.Credentials(token) 
        stclient = client.StreetViewPublishServiceClient(credentials=credentials)
        view = enums.PhotoView.BASIC
        photosinfo = stclient.batch_get_photos([p.photo_google_id for p in tour.photos], view, retry=retrymethod)
        localphotos = {p.photo_google_id: {'fname': p.photo_filename, 'id': p.photo_id} for p in tour.photos}
        
        for r in photosinfo.results:
            publishstatus = r.photo.MapsPublishStatus.Name(r.photo.maps_publish_status)
            lat = r.photo.pose.lat_lng_pair.latitude
            lon = r.photo.pose.lat_lng_pair.longitude
            viewcount = r.photo.view_count
            link = r.photo.share_link
            google_id = r.photo.photo_id.id
            localphotos[google_id]['lat'] = lat
            localphotos[google_id]['lon'] = lon
            localphotos[google_id]['viewcount'] = viewcount
            localphotos[google_id]['link'] = link
            localphotos[google_id]['status'] = publishstatus
        for p in localphotos:
            print("ID: {}, Filename: {}, Lat: {} Lon: {}\n Link: {} Viewcount: {} Status: {}".format(
                localphotos[p]['id'],
                localphotos[p]['fname'],
                localphotos[p]['lat'],
                localphotos[p]['lon'],
                localphotos[p]['link'],
                localphotos[p]['viewcount'],
                localphotos[p]['status']
            )
            )
        
@cli.command()
@click.argument('objid')
def delete(objid):
    photo = session.query(Photo).filter(Photo.photo_google_id == objid).first()
    tour = session.query(Tour).filter(Tour.tour_id == objid).first()
    if not tour and not photo:
        print(f"There's no photo or tour with ID {objid}")
    else:
        confirm =  click.prompt("Please type DELETE to delete photo/tour", type=str)
        if confirm == "DELETE":
            creds, token = authenticate_user()
            credentials = google.oauth2.credentials.Credentials(token) 
            stclient = client.StreetViewPublishServiceClient(credentials=credentials)

            if photo:
                delete_response = stclient.delete_photo(objid, retry=retrymethod)
                session.delete(photo)
                session.commit()
                print(f"Photo {photoid} deleted")
            elif tour:
                delete_response = stclient.batch_delete_photos([p.photo_google_id for p in tour.photos], retry=retrymethod)
                # TODO check delete response
                numphotos = len(tour.photos)
                session.delete(tour)
                session.commit()
                print(f"Tour {objid} and {numphotos} related photos deleted")

@cli.command()
@click.argument('tourid')
@click.argument('path')
def updatetour(tourid, path):
    tour = session.query(Tour).filter(Tour.tour_id == tourid).first()
    if not tour:
        print(f"There's no tour with ID {tourid}")
    else:
        upload_files(path, tour)
        
@cli.command()
@click.argument('path')
def createtour(path):
    upload_files(path)
    
if __name__ == '__main__':
    cli()


# Trekview Functions:
# + status - return user's email & token expiry date
# + create_tour [path to file] (local & net)
# + update_tour [tour_id, path_to_file] (local & net)
# + list_tours [tour_id] (local + net)
# + delete_tour [tour_id] (local & net)
# + delete_photo [photo_id] (local & net)
# + Google Auth functions
# + Validate photo
