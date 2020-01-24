import os
import sys
import json

import requests

from constants import auth_config, session
from models import Photo



class Explorer(object):
    def __init__(self, init=False):
        self.name = 'Trek View Explorer'
        self.short_name = 'explorer'
        self.api_url = 'https://staging.explorer.trekview.org/api/v1/'
        self.key_reason = None
        self.headers = None

        version_file = 'VERSION.txt'
        if os.path.exists(version_file):
            with open(version_file, 'r') as vfs:
                self.version = vfs.read()
        else:
            self.version = '0'
        
        if not init:
            ek = auth_config[2]['key']
            if ek:
                self.headers = {
                    'Content-Type': 'application/json',
                    'api-key': ek
                }
                user_id = self.get_user_id()
                if not user_id:
                    self.key_reason = 'with invalid'
                    print(self.name + ': Invalid API key')
            else:
                self.key_reason = 'without'
                print(self.name + ': API key not entered')

    def get_user_id(self):
        if self.key_reason:
            print(self.name + ': You can not get user id {} API key'.format(self.key_reason))
            return None

        user_info_url = self.api_url + 'users'

        r = requests.get(user_info_url, headers=self.headers)

        if r.status_code == 200 or r.status_code == 201:
            user_id = r.json()['user']['id']
            return user_id
        else:
            return None
    
    def add_photo(self, explorer_tour_id, photo):
        if self.key_reason:
            print(self.name + ': You can not add photos {} API key'.format(self.key_reason))
            return None
        
        photo['tourer[version]'] = self.version
        add_photo_url = self.api_url + 'tours/{}/photos'.format(explorer_tour_id)
        files = {'image': open(photo['fullpath'], 'rb')}
        headers = {
            'api-key': auth_config[2]['key']
        }
        r = requests.post(add_photo_url, data=photo, files=files, headers=headers)
        if r.status_code == 200 or r.status_code == 201:
            photo_id = r.json()['photo']['id']
            print(self.name + ': Photo uploaded, explorer photo ID ' + str(photo_id))
            return photo_id
        else:
            print(self.name + ': Failed to add photo')
            return None
    
    def update_photo(self, photo, explorer_tour_id, explorer_photo_id):
        if self.key_reason:
            print(self.name + ': You can not add photos {} API key'.format(self.key_reason))
            return None
            
        photo['tourer[version]'] = self.version
        update_photo_url = '{}tours/{}/photos/{}'.format(self.api_url, explorer_tour_id, explorer_photo_id)
        headers = {
            'api-key': auth_config[2]['key']
        }
        r = requests.put(update_photo_url, data=photo, headers=headers)
        if r.status_code == 200 or r.status_code == 201:
            print(self.name + ': Photo updated')
        else:
            print(self.name + ': Failed to update photo')

    def list_photos(self, explorer_tour_id):
        if self.key_reason:
            print(self.name + ': You can not list photos {} API key'.format(self.key_reason))
            return None

        list_url = self.api_url + 'tours/{}/photos'.format(explorer_tour_id)
        r = requests.get(list_url, headers=self.headers)
        if r.status_code == 200 or r.status_code == 201:
            photos = r.json()['photos']
            print(self.name + ': Photo list fetched')
            return photos
        else:
            return None

    def delete_photo(self, explorer_tour_id, explorer_photo_id):
        if self.key_reason:
            print(self.name + ': You can not delete photo {} API key'.format(self.key_reason))
            return None

        delete_photo_url = self.api_url + 'tours/{}/photos/{}'.format(
                                explorer_tour_id, explorer_photo_id)

        r = requests.delete(delete_photo_url, headers=self.headers)
        if r.status_code == 200 or r.status_code == 201:
            print(self.name + ': Photo deleted, explorer photo ID ' + str(explorer_photo_id))
            return True
        else:
            print(self.name + ': Failed to delete photo')
            return False
        
    def create_tour(self, name, description, tags, tour_type, transport_type, tour_id):
        if self.key_reason:
            print(self.name + ': You can not create photos {} API key'.format(self.key_reason))
            return None

        create_url = self.api_url + 'tours'    
        tour = {
                'name': name,
                'description': description, 
                'tags': tags,
                'tour_type': tour_type,
                'transport_type': transport_type,
                'tourer': {
                    'tour_id': tour_id,
                    'version': self.version
                }
            }

        data = json.dumps(tour)
        r = requests.post(create_url, data=data, headers=self.headers)
        if r.status_code == 200 or r.status_code == 201:
            explorer_tour_id = r.json()['tour']['id']
            print(self.name + ': Tour created, explorer tour ID ' + str(explorer_tour_id))
            return explorer_tour_id
        else:
            print(self.name + ': Tour creation failed')
            return None

    def delete_tour(self, explorer_tour_id):
        if self.key_reason:
            print(self.name + ': You can not delete tour {} API key'.format(self.key_reason))
            return None

        delete_url = '{}tours/{}'.format(self.api_url, explorer_tour_id)
        r = requests.delete(delete_url, headers=self.headers)

        if r.status_code == 200 or r.status_code == 201:
            print(self.name + ': Tour deleted, explorer tour ID ' + str(explorer_tour_id))
            return True
        else:
            print(self.name + ': Falied to delete tour')
            return False
    
    def update_tour(self, explorer_tour_id, tour_id=None, description=None, tags=None, tour_type=None, transport_type=None, photos=None):
        if self.key_reason:
            print('{}: You can not update tour {} API key'.format(self.name, self.key_reason))
            return None

        if photos:
            for photo in photos:
                explorer_photo_id = self.add_photo(explorer_tour_id, photo)
                photo_id = photo['tourer[photo_id]']
                photo = session.query(Photo).filter(Photo.photo_id == photo_id).first()
                photo.explorer_photo_id = explorer_photo_id
                session.add(photo)
                session.commit()
        else:
            update_url = '{}tours/{}'.format(self.api_url, explorer_tour_id)
            tour_fields = {
                'description': description, 
                'tags': tags,
                'tour_type': tour_type,
                'transport_type': transport_type,
                'tourer': {
                    'tour_id': tour_id,
                    'version': self.version
                }
            }
                
            data = json.dumps(tour_fields)
            r = requests.put(update_url, data=data, headers=self.headers)

        print(self.name + ': Tour updated')

    def list_tours(self, user_id):
        if self.key_reason:
            print(self.name + ': You can not list tours {} API key'.format(self.key_reason))
            return None

        list_url = self.api_url + 'tours?user_ids[]=' + str(user_id)

        r = requests.get(list_url, headers=self.headers)

        if r.status_code == 200 or r.status_code == 201:
            tours = r.json()['tours']
            print(self.name + ': Tour list fetched')
            return tours
        else:
            return None
