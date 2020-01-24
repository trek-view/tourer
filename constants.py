import sys
import configparser

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine



config = configparser.ConfigParser()
config.read('config.ini')


auth_config = []

try:
    gc = config['googleauth']
    auth_config.append({
        'name': 'google',
        'auth_uri': 'https://opentrailview.org/oauth2/v4/authorize',
        'client_id': gc['client_id'],
        'client_secret': gc['client_secret'],
        'credentials_file': gc['credentials_file'],
        'scope': ''   
    })
except:
    auth_config.append({
        'name': 'google',
        'auth_uri': 'https://opentrailview.org/oauth2/v4/authorize',
        'client_id': '',
        'client_secret': '',
        'credentials_file': '',
        'scope': ''   
    })

try:
    oc = config['otvauth']
    auth_config.append({   
        'name': 'otv',
        'auth_uri': 'https://opentrailview.org/oauth/auth/authorize',
        'client_id': oc['client_id'],
        'client_secret': oc['client_secret'],
        'credentials_file': oc['credentials_file'],
        'scope': ''
    })
except:
    auth_config.append({   
        'name': 'otv',
        'auth_uri': 'https://opentrailview.org/oauth/auth/authorize',
        'client_id': '',
        'client_secret': '',
        'credentials_file': '',
        'scope': ''
    })

try:
    ec = config['explorer']
    auth_config.append({   
        'name': 'explorer',
        'key': ec['explorer_key']
    })
except:
    auth_config.append({   
        'name': 'explorer',
        'key': ''
    })

try:
    db_file = config['other']['database_file']
except:
    print('No DB file config')
    sys.exit()
    

engine = create_engine('sqlite:///{}'.format(db_file))
Session = sessionmaker(bind=engine)
session = Session()

SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.tiff']

known_modules = [('Google Street View', 'gsv'),
                    ('Open Trail View', 'otv'),
                    ('Trek View Explorer', 'explorer')]
