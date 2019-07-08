#!/usr/bin/python
# -*- coding: utf-8 -*-

from sqlalchemy import ForeignKey, Column, Integer, Text, DateTime, Enum
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


class TourDescription(Base):
    __tablename__ = 'tour_description'
    descr_id = Column(Integer, primary_key=True)
    tour_type = Column(Enum(TourType))
    tour_transport = Column(Enum(TransportType))
    tours = relationship("Tour", backref="descr")

    def __repr__(self):
        return "{}-{}".format(self.tour_type.name, self.tour_transport.name)

        
class Tour(Base):
    __tablename__ = 'tour'
    tour_id = Column(Integer, primary_key=True)
    tour_created = Column(DateTime, default=datetime.datetime.now())
    tour_name = Column(Text(), nullable=True)
    tour_descr_id = Column(Integer, ForeignKey('tour_description.descr_id'))
    photos = relationship("Photo", backref="tour", cascade="all,delete")
    
    
class Photo(Base):
    __tablename__ = 'photo'
    photo_id = Column(Integer, primary_key=True)
    photo_tour_id = Column(Integer, ForeignKey('tour.tour_id'))
    photo_filename  = Column(Text())
    photo_google_id = Column(Text())

    
