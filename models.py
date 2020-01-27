from sqlalchemy import ForeignKey, Column, Integer, Text, DateTime, Enum, Boolean, Float, String
from sqlalchemy.orm import backref, validates, relationship
from sqlalchemy.ext.declarative import declarative_base
import enum
import datetime

Base = declarative_base()



class TourType(enum.Enum):
    Land = 1
    Water = 2
    Air = 3

class TransportType(enum.Enum):
    Drive = 1
    Hike = 2
    Bike = 3
    Climb = 4
    Ski = 5
    Snowboard = 6
    Skateboard = 7
    Rollerblade = 8
    OtherLand = 9
    Sail = 10
    Kayak = 11
    Raft = 12
    StandupPaddleBoard = 13
    OtherWater = 14
    Drone = 15
    HangGlide = 16
    Parachute = 17
    Windsuit = 18
    Plane = 19
    OtherAir = 20


class TourTransport(Base):
    __tablename__ = 'tour_description'
    transp_id = Column(Integer, primary_key=True)
    tour_type = Column(Enum(TourType))
    tour_transport = Column(Enum(TransportType))
    tours = relationship('Tour', backref='transport')

    def __repr__(self):
        return '{}-{}'.format(self.tour_type.name, self.tour_transport.name)

class TourBook(Base):
    __tablename__ = 'tourbook'
    tourbook_id = Column(Integer, primary_key=True)
    explorer_tourbook_id = Column(Integer, unique=True)
    tourbook_name = Column(String(255), nullable=False, unique=True)
    tourbook_description = Column(String(240), nullable=True)
    tours = relationship('Tour', backref='tourbook')
    
class Tour(Base):
    __tablename__ = 'tour'
    id = Column(Integer, primary_key=True)
    explorer_tour_id = Column(Integer, unique=True)
    created = Column(DateTime, default=datetime.datetime.now())
    updated = Column(DateTime)
    name = Column(String(70), nullable=True, unique=True)
    description = Column(String(140), nullable=True)
    tags = Column(String(240), nullable=True)
    photos = relationship('Photo', backref='tour')
    tour_id = Column(String(10), nullable=False, unique=True)
    transp_id = Column(Integer, ForeignKey('tour_description.transp_id'))
    tourbook_tour_id = Column(Integer, ForeignKey('tourbook.tourbook_id'))
    integrations = Column(String(100), nullable=True)
    
class Photo(Base):
    __tablename__ = 'photo'
    id = Column(Integer, primary_key=True)
    photo_id = Column(String(10), nullable=True, unique=True)
    explorer_photo_id = Column(Integer, unique=True)
    tour_id = Column(Integer, ForeignKey('tour.tour_id'))
    updated = Column(DateTime)
    created = Column(DateTime, default=datetime.datetime.now())
    taken = Column(DateTime)
    uploaded = Column(Boolean, default=False)
    viewpoint = Column(Boolean, default=False)
    filename = Column(String(50))
    filepath = Column(String(150))
    fullpath = Column(String(150))
    lon = Column(String(20))
    lat = Column(String(20))
    elevation = Column(Text())
    camera_make = Column(Text())
    camera_model = Column(Text())
    connections = Column(Text())
    locality = Column(Text())
    administrative_area_level_1 = Column(Text())
    administrative_area_level_2 = Column(Text())
    administrative_area_level_3 = Column(Text())
    postal_code = Column(String(250))
    city = Column(String(50))
    country = Column(String(50))
    country_code = Column(String(50))
    location_code = Column(String(20))
    place_id = Column(String(100))
    postal_code = Column(String(250))
    street_view_url = Column(Text())
    street_view_view_count = Column(Text())
    street_view_publish_status = Column(Text())
    street_view_photoid = Column(Text())
    street_view_capture_time = Column(Text())
    street_view_sharelink = Column(Text())
    street_view_download_url = Column(Text())
    street_view_thumbnail_url = Column(Text())
    street_view_lat = Column(String(30))
    street_view_lon = Column(String(30))
    street_view_altitude = Column(String(20))
    street_view_heading = Column(Text())
    street_view_pitch = Column(Text())
    street_view_roll = Column(Text())
    street_view_level = Column(Text())
    street_view_connections = Column(Text())
    otv_pano_id = Column(String(20))
    photo_heading = Column(Text())
