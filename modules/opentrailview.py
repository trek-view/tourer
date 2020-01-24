import os
import json
import click

import requests

from constants import auth_config



class OpenTrailView(object):
    def __init__(self, init=False):
        self.name = 'Open Trail View'
        self.short_name = 'otv'
        self.headers = None
        if not init:
            self.token = self.get_access_token()
            self.headers = {
                'Authorization': 'Bearer ' + self.token
            }
                
    def get_access_token(self):
        token = None

        credentials_file = auth_config[1]['credentials_file']
        if os.path.exists(credentials_file):
            with open(credentials_file, 'r') as cf:
                credentials = json.load(cf)
        else:
            credentials = None

        if credentials:
            token = credentials['access_token'] 
        else:
            client_id = auth_config[1]['client_id']
            client_secret = auth_config[1]['client_secret']
            
            url = 'https://opentrailview.org/oauth/auth/authorize?response_type=code&client_id={}&redirect_uri={}&directReturn=1'.format(
                    client_id, 'https://opentrailview.org/')
            print(self.name + ': ' + 'Use this link to get the code: ' + url)
            code = click.prompt('Enter URL code')

            data = {     
                'grant_type': 'authorization_code',
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
            }

            at_url = 'https://opentrailview.org/oauth/auth/access_token?redirect_uri=https://opentrailview.org'
            r = requests.post(at_url, data=data)

            if r.status_code == 200:
                token_data = r.json()
        
                with open(credentials_file, 'w') as cf:
                    json.dump(token_data, cf)
                
                token = token_data['access_token']

            elif r.status_code == 400:
                print(self.name + ': ' + 'Failed to recieve access token. Malformed auth code or wrong credentials.')
                token = ''
        
        return token
    
    def upload_photo(self, fl, tour_id):
        if not self.token:
            print(self.name + ': ' + 'Falied to upload photo, auth error')
            return None

        upload_url = 'https://opentrailview.org/oauth/api/panorama/upload'

        files = {
            'file': open(fl['fname'], 'rb'),
        }
        r = requests.post(upload_url, headers=self.headers, files=files)
        if r.status_code == 200:
            pano_id = r.json().get('id')
            print(self.name + ': ' + 'Photo uploaded, pano ID ' + str(pano_id))
            self.move_photo(pano_id, fl['gpsdata']['Latitude'], fl['gpsdata']['Longitude'])
            return pano_id
        else:
            print(self.name + ': ' + 'Falied to upload photo')
            return None

    def move_photo(self, pano_id, lat, lon):
        if not self.token:
            print(self.name + ': ' + 'Falied to move photo, auth error')
            return None

        data = {     
                'lat': lat,
                'lon': lon
            }
        move_url = 'https://opentrailview.org/oauth/api/panorama/' + str(pano_id) + '/move'
        r = requests.post(move_url, data=data, headers=self.headers)
        if r.status_code == 200:
            return True
        else:
            print(self.name + ': ' + 'Falied to move photo')
            return False

    def delete_photo(self, pano_id):
        if not self.token:
            print(self.name + ': ' + 'Falied to delete photo, auth error')
            return None
        
        delete_url = 'https://opentrailview.org/oauth/api/panorama/' + str(pano_id)

        r = requests.delete(delete_url, headers=self.headers)
        if r.status_code == 200:
            print(self.name + ': ' + 'Photo deleted, pano ID ' + str(pano_id))
            return True
        else:
            print(self.name + ': ' + 'Falied to delete photo')
            return False
