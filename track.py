#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

zappa-bittorrent-tracker

An experimental, completely server-less BitTorrent tracker powered by Zappa, Flask and S3.
Or, maybe DynamoDB: https://github.com/jlafon/PynamoDB
@jarus' "flaker" was used as a reference to get this project started. https://github.com/jarus/flacker/

"""

import cgi
import decimal
import json
import os
import socket
from binascii import b2a_hex
from struct import pack

import boto3
import botocore
from boto3.dynamodb.conditions import Key, Attr

from bencode import bencode
from flask import Flask, render_template, request, Response, make_response, redirect, abort

##
# Conf
##

ANNOUNCE_INTERVAL = 300
DEBUG = True
TABLE_NAME = "zabito"
AWS_REGION = "us-east-1"

##
# AWS
##

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)

##
# App
##

app = Flask(__name__)
if DEBUG:
    app.debug = True
    app.config['DEBUG'] = True

##
# Main
##

@app.route('/')
def home():
    """
    Homepage. Nothing here yet.
    Could do some stats if we wanted.
    """

    return render_template('index.html')

@app.route('/announce', methods=['GET'])
def announce():
    """
    Main announce call.
    """

    # Ensure the request is all there
    need_args = (
            'info_hash', 
            'peer_id', 
            'port', 
            'uploaded', 
            'downloaded', 
            'left')
    for arg in need_args:
        if arg not in request.args:
            return fail('Missing Argument (%s)' % arg)
    
    # Get the request information
    peer_id = request.args['peer_id']
    info_hash = get_info_hash(request)
    uploaded = int(request.args['uploaded'])
    downloaded = int(request.args['downloaded'])
    left = int(request.args['left'])
    if 'ip' not in request.args:
        ip = request.args.get('ip', request.remote_addr)
        # TODO: Validate
    else:
        ip = request.args['ip']
        # TODO: Validate
    port = int(request.args['port'])

    if request.args.get('event') == 'stopped':
        remove_peer_from_info_hash(
                            info_hash, 
                            peer_id, 
                        )
        return bencode({})
    elif request.args.get('event') == 'completed': 
        increment_completed(info_hash)

    user_info = add_peer_to_info_hash(
                    info_hash, 
                    peer_id, 
                    ip,
                    port, 
                    uploaded, 
                    downloaded, 
                    left
                )

    peers = get_peers_for_info_hash(info_hash)

    b_peers = []
    for peer_id in peers:
        b_peers.append({
            'ip': str(peers[peer_id][0]['ip']),
            'port': int(peers[peer_id][0]['port']),
            'peer_id': str(peer_id)
        })

    response = bencode({
        'interval': ANNOUNCE_INTERVAL,
        'complete': 0,
        'incomplete': 0,
        'peers': b_peers
    })
    return Response(response, mimetype='text/plain')

@app.route('/scrape', methods=['GET'])
def scrape():
    """
    Scrape call.

    Ex: http://example.com/scrape.php?info_hash=aaaaaaaaaaaaaaaaaaaa&info_hash=bbbbbbbbbbbbbbbbbbbb&info_hash=cccccccccccccccccccc
    https://wiki.theory.org/BitTorrentSpecification#Tracker_.27scrape.27_Convention
    """

    files = {}
     # files: a dictionary containing one key/value pair for each torrent for which there are stats. If info_hash was supplied and was valid, this dictionary will contain a single key/value. Each key consists of a 20-byte binary info_hash. The value of each entry is another dictionary containing the following:
     #    complete: number of peers with the entire file, i.e. seeders (integer)
     #    downloaded: total number of times the tracker has registered a completion ("event=complete", i.e. a client finished downloading the torrent)
     #    incomplete: number of non-seeder peers, aka "leechers" (integer)
     #    name: (optional) the torrent's internal name, as specified by the "name" file in the info section of the .torrent file

    response = bencode({
        'files': files,
    })
    return Response(response, mimetype='text/plain')


def get_info_hash(request, multiple=False):
    """
    Get infohashes from a QS.
    """
    if not multiple:
        return b2a_hex(cgi.parse_qs(request.query_string)['info_hash'][0])
    else:
        hashes = set()
        for hash in cgi.parse_qs(request.query_string)['info_hash']:
            hashes.add(b2a_hex(hash))
    return hashes

def fail(message=""):
    """
    Failure.
    """
    return bencode({
        'interval': ANNOUNCE_INTERVAL,
        'failure reason': message,
    })

##
# Database
##

def add_peer_to_info_hash(
                info_hash, 
                peer_id, 
                ip,
                port, 
                uploaded, 
                downloaded, 
                left
            ):
    """
    Update an info_hash with this peer.
    """

    ensure_torrent_exists(info_hash)

    # Prep the new info
    info_set = {
        "uploaded": uploaded,
        "downloaded": downloaded,
        "left": left,
        "ip": ip,
        "port": port
    }

    # Update the torrents list with the new information
    result = table.update_item(
        Key={
            'info_hash': info_hash,
        },
        UpdateExpression="SET peers.#s = :i",
        ExpressionAttributeNames={
            '#s': peer_id,
        },
        ExpressionAttributeValues={
            ':i': [info_set],
        },
        ReturnValues="UPDATED_NEW"
    )

    if result['ResponseMetadata']['HTTPStatusCode'] == 200 and 'Attributes' in result:
        return True
    return False

def remove_peer_from_info_hash(
                            info_hash, 
                            peer_id, 
                        ):

    ensure_torrent_exists(info_hash)

    # Update the torrents list with the new information
    result = table.update_item(
        Key={
            'info_hash': info_hash,
        },
        UpdateExpression="REMOVE peers.#s",
        ExpressionAttributeNames={
            '#s': peer_id,
        },
        ReturnValues="UPDATED_NEW"
    )

    if result['ResponseMetadata']['HTTPStatusCode'] == 200 and 'Attributes' in result:
        return True
    return False

def increment_completed(info_hash):
    """
    Atomic increment completed for a torrent.
    """

    ensure_torrent_exists(info_hash)

    # Update the torrents list with the new information
    result = table.update_item(
        Key={
            'info_hash': info_hash,
        },
        UpdateExpression="SET completed = completed + :incr",
        ExpressionAttributeValues={
            ':incr': 1,
        },
        ReturnValues="UPDATED_NEW"
    )

    if result['ResponseMetadata']['HTTPStatusCode'] == 200 and 'Attributes' in result:
        return True
    return False

def ensure_torrent_exists(info_hash):
    """
    Ensure a torrent exists before updating.
    """

    # See if we have this peer yet
    response = table.query(
        KeyConditionExpression=Key('info_hash').eq(info_hash)
    )
    if response['Count'] == 0:
        # We don't, so make an empty torrent
        try:
            response = table.put_item(
               Item={
                    'info_hash': info_hash,
                    'peers': {},
                    'completed': 0
                }
            )
        except botocore.exceptions.ClientError as e:
            print(e)

    return

def get_peers_for_info_hash(
                info_hash, 
                limit=50
            ):
    """
    Get current peers
    """

    response = table.query(
        KeyConditionExpression=Key('info_hash').eq(info_hash)
    )
    if response['Count'] == 0:
        return []
    else:
        return response['Items'][0]['peers']

###
# Utility
###

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    """
    From http://docs.aws.amazon.com/amazondynamodb/latest/gettingstartedguide/GettingStarted.Python.03.html
    """
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)
