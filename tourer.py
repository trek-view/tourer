import os
import sys

import click

from models import Tour, Photo
from utils import (
                    sync_push,
                    sync_pull,
                    initdb,
                    integrations_status,
                    create_tour,
                    delete_tour,
                    update_tour,
                    edit_tour,
                    list_tours,
                    list_photos,
                    delete_photo,
                    validate_string,
                    validate_files,
                    get_tour_transport,
                    get_integrations,
                    get_options,
                    get_fields,
                    get_tags,
                    fetchgsv,
                    add_integration,
                    remove_integration
                )
from constants import db_file, session 



@click.group()
def cli():
    try:
        if not os.path.isfile(db_file):
            initdb()
    except:
        sys.exit()


@cli.command()
def listtours():
    '''
    List all saved tours
    '''
    tours = session.query(Tour).all()
    list_tours(tours)


@cli.command()
@click.argument('tour_id')
def listphotos(tour_id):
    '''
    List all saved photos of a given <tour_id>
    '''
    list_photos(tour_id)


@cli.command()
def status():
    '''
    Integrations status
    '''
    status = True
    integrations_status(status)


@cli.command()
@click.argument('tour_id')
def updatetour(tour_id):
    '''
    Edit name, description, tags and type or add/delete photos of a given <tour_id>
    '''
    tour = session.query(Tour).filter(Tour.tour_id == tour_id).first()
    if not tour:
        print('There is no tour with ID {}'.format(tour_id))
    else:
        options = get_options()

        if 'edit_tour' in options:
            list_tours([tour])
            edit_tour(tour)
        
        if 'add_photos' in options:
            list_photos(tour_id)
            path = click.prompt('Enter photos path')
            validated_files = validate_files(path)
            if validated_files:
                update_tour(tour, validated_files)

        if 'delete_photo' in options:
            list_photos(tour_id)
            delete_photo(tour)
        
        if 'add_integration' in options:
            add_integration(tour)

        if 'remove_integration' in options:
            remove_integration(tour)

        if 'delete_tour' in options:
            delete_tour(tour)


@cli.command()
@click.argument('path')
def createtour(path):
    '''
    Create new tour from photos located at <path>
    '''
    validated_files = validate_files(path)
    name = validate_string('Tour name', click.prompt('Please enter a new tour name', type=str), 300)
    tour = session.query(Tour).filter(Tour.name == name).first()
    if tour:
        print('Tour {} already exists'.format(name))
        return None

    description = validate_string('Tour description', click.prompt('Please enter tour description', type=str), 500)
    transport = get_tour_transport()
    tags = get_tags()

    if 'manual' in tags:
        tags = ','.join(tags[:-1])
        manual_tags = validate_string('Tour tags', click.prompt('Please enter tour tags, comma-separated', type=str), 500)
        tags += ',' + manual_tags
    else:
        tags = ','.join(tags)

    status = False
    intg_status = integrations_status(status)
    if intg_status:
        integrations = get_integrations()
    else:
        integrations = []

    create_tour(validated_files, integrations, name, description, tags, transport)              


@cli.command()
def forcesync():
    '''
    Pull data from modules that support pull (GET) actions
    and push data to modules that support push (PUT) actions.
    '''
    status = False
    intg_status = integrations_status(status)

    if ('Google Street View', 'gsv') in intg_status:
        print('Fetching Google Street View photo data')
        fetchgsv()

    if intg_status:
        print('Pushing data to integrations')
        sync_push(intg_status)
    else:
        print('No integrations configured')
    

if __name__ == '__main__':
    cli()
