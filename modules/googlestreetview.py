import os
import sys
import json
import time
import click
import datetime

import requests
import google.oauth2.credentials
import googleapiclient.discovery

from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.field_mask_pb2 import FieldMask
from google.streetview.publish_v1.proto import resources_pb2
from google.streetview.publish_v1 import street_view_publish_service_client as client, enums

from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from oauth2client import tools

from constants import auth_config



class GoogleStreetView(object):
    def __init__(self, init=False):
        self.name = 'Google Street View'
        self.short_name = 'gsv'
        
        if not init:
            self.token = self.get_access_token()
            credentials = google.oauth2.credentials.Credentials(self.token) 
            self.stclient = client.StreetViewPublishServiceClient(credentials=credentials)

    def upload_photo(self, fl):
        distance = None
        heading = None
        countries = []

        upload_ref = self.stclient.start_upload()

        filesize = os.stat(fl['fname']).st_size
        _, ftype = os.path.splitext(fl['fname'])
        ftype = ftype.lstrip('.')

        if 'jpg' in ftype.lower():
            ftype = 'jpeg'
        
        headers = {
            'Authorization': 'Bearer ' + self.token,
            'Content-Length': '0',
            'X-Goog-Upload-Protocol': 'resumable',
            'X-Goog-Upload-Header-Content-Length': str(filesize),
            'X-Goog-Upload-Header-Content-Type': 'image/{}'.format(ftype),
            'X-Goog-Upload-Command': 'start'
        }

        resumableUrl = requests.post(upload_ref.upload_url, headers=headers).headers['X-Goog-Upload-URL']

        chunk_size = 3 * 1024 * 1024
        f = open(fl['fname'], 'rb')
        num_of_chunks = int(filesize / chunk_size)

        for i in range(num_of_chunks):
            cnt = 0
            offset = chunk_size * i
            headers = {
                'Authorization': 'Bearer ' + self.token,
                'Content-Length': str(chunk_size),
                'X-Goog-Upload-Command': 'upload',
                'X-Goog-Upload-Offset': str(offset)
            }

            f.seek(offset)
            data = f.read(chunk_size)
            part_uploaded = False

            while not part_uploaded:
                try:
                    response = requests.post(resumableUrl, data=data, headers=headers)
                    part_uploaded = True
                except requests.exceptions.ConnectionError as e:
                    print('Network error, waiting for {} seconds before next attempt'.format(2 ** cnt))
                    time.sleep(2 ** cnt)
                    cnt += 1

        last_chunk = filesize % chunk_size
        offset = chunk_size * num_of_chunks
        headers = {
            'Authorization': 'Bearer ' + self.token,
            'Content-Length': str(last_chunk),
            'X-Goog-Upload-Command': 'upload, finalize',
            'X-Goog-Upload-Offset': str(offset)
        }

        f.seek(offset)
        data = f.read(last_chunk)
        last_part_uploaded = False
        last_cnt = 0

        while not last_part_uploaded:
            try:
                response = requests.post(resumableUrl, data=data, headers=headers)
                last_part_uploaded = True
            except requests.exceptions.ConnectionError as e:
                print('Network error, waiting for {} seconds before next attempt'.format(2 ** cnt))
                time.sleep(2 ** last_cnt)
                last_cnt += 1
            
        if last_part_uploaded:
            seconds = int((fl['timestamp'] - datetime.datetime.utcfromtimestamp(0)).total_seconds())
            timestamp = Timestamp(seconds=seconds)
            if fl['place_id']:
                place = resources_pb2.Place(place_id=fl['place_id'])
                photo = resources_pb2.Photo(capture_time=timestamp, places=[place])
            else:
                photo = resources_pb2.Photo(capture_time=timestamp)
            
            photo.upload_reference.upload_url = upload_ref.upload_url
            uploaded_photo = self.stclient.create_photo(photo)

            print('Google Street View: Photo uploaded, ID ' + uploaded_photo.photo_id.id)

            return uploaded_photo
            
    def delete_photo(self, gsv_photo_id):
        delete_response = None
        try:
            delete_response = self.stclient.delete_photo(gsv_photo_id)
        except:
            print('Google Street View: Photo not found')
            
        return delete_response

    def get_photo_info(self, gsv_photo_ids):
        view = enums.PhotoView.BASIC
        info = None
        try:
            info = self.stclient.batch_get_photos(gsv_photo_ids, view).results
        except:
            print('Google Street View: Photo not found')

        return info

    def get_access_token(self):
        client_id = auth_config[0]['client_id']
        client_secret = auth_config[0]['client_secret']
        if client_id != '' and client_secret != '':
            flow = OAuth2WebServerFlow(
                client_id=client_id,
                client_secret=client_secret,
                scope=['https://www.googleapis.com/auth/streetviewpublish',
                        'https://www.googleapis.com/auth/userinfo.email',
                        'https://www.googleapis.com/auth/userinfo.profile'
                        ],
            )
            path = 'creds/gsv_creds.data'
            
            if not os.path.isfile(path):
                open(path, 'tw', encoding='utf-8').close()

            storage = Storage(path) 
            credentials = storage.get()

            if credentials is None or credentials.invalid:
                credentials = tools.run_flow(flow, storage, tools.argparser.parse_args(args=['--noauth_local_webserver']))

            credentials = self.refresh_token(credentials, storage)
            
            tokeninfo = self.get_token_info(credentials.access_token)
            if tokeninfo == -2:
                print('Network unavailable')
                return None, None
            
            if tokeninfo == -1:
                credentials = self.refresh_token(credentials, storage)

            exp = credentials.token_expiry
            assert credentials.access_token is not None

            return credentials.access_token
        else:
            print('Google Street View: Credentials not entered')
            sys.exit()

    def get_token_info(self, token):
        url = 'https://www.googleapis.com/oauth2/v1/tokeninfo?alt=json&access_token={}'.format(token)
        cnt = 0

        while True:
            try:
                res = requests.get(url)
                tokeninfo = json.loads(res.text)
                seconds_to_expire = int(tokeninfo.get('expires_in', 0))
        
                if seconds_to_expire <= 0:
                    return -1
                else:
                    expires = datetime.datetime.now() + datetime.timedelta(seconds=seconds_to_expire)
                    return expires.strftime('%H:%M:%S %d/%m/%Y')

            except requests.exceptions.ConnectionError as e:
                print('Network error, waiting for {} seconds before next attempt'.format(2 ** cnt))
                time.sleep(2 ** cnt)
                cnt += 1

    def refresh_token(self, credentials, storage):
        token = credentials.access_token
        refresh = credentials.refresh_token
        refresh_credentials = google.oauth2.credentials.Credentials(
            token,
            refresh_token=refresh,
            client_id=auth_config[0]['client_id'],
            client_secret=auth_config[0]['client_secret'],
            token_uri='https://www.googleapis.com/oauth2/v4/token'
        )

        refresh_credentials.refresh(google.auth.transport.requests.Request())
        token = refresh_credentials.token
        credentials.access_token = token
        storage.put(credentials)
        
        return credentials

