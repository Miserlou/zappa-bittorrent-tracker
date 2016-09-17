#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

zappa-bittorrent-tracker

An experimental, completely server-less BitTorrent tracker powered by Zappa, Flask and (DynamoDB || S3).
@jarus' "flaker" was used as a reference to get this project started. https://github.com/jarus/flacker/

"""

import cgi
import decimal
import json
import os
import socket
import time
from binascii import b2a_hex
from datetime import datetime, timedelta
from struct import pack

import boto3
import botocore
from boto3.dynamodb.conditions import Key, Attr

from bencode import bencode
from flask import Flask, render_template, request, Response, make_response, redirect, abort

##
# Conf
##

ANNOUNCE_INTERVAL = 1800
DEBUG = True

AWS_REGION = "us-east-1"
DATASTORE = "S3" # Or "DynamoDB"
TABLE_NAME = "zabito" # Dynamo only
BUCKET_NAME = "lmbda" # S3 Only

##
# AWS
##

if DATASTORE == "DynamoDB":
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(TABLE_NAME)
elif DATASTORE == "S3":
    boto_session = boto3.Session()
    s3 = boto_session.resource('s3')
    s3_client = boto3.client('s3')

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

    all_items = get_all_items()
    items = []
    for item in all_items:
        items.append({
            'info_hash': item['info_hash'],
            'peers': len(item['peers']),
            'completed': item['completed']
        })

    return render_template('index.html', items=items)

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
        # DynamoDB results get mangled into an extra list, I don't know why.
        if DATASTORE == "DynamoDB":
            b_peers.append({
                'ip': str(peers[peer_id][0]['ip']),
                'port': int(peers[peer_id][0]['port']),
                'peer_id': str(peer_id)
            })
        else:
            b_peers.append({
                'ip': str(peers[peer_id]['ip']),
                'port': int(peers[peer_id]['port']),
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

def purge_expired_peers():
    """
    Removes peers who haven't announced in the last internval.

    Should be set as a recurring event source in your Zappa config.
    """

    if DATASTORE == "DynamoDB":
        # This is a costly operation, but I think it has to be done.
        # Optimizations (pagination? queries? batching?) welcomed.
        all_torrents = table.scan()
        for torrent in all_torrents['Items']:
            for peer_id in torrent['peers']:
                peer_last_announce = int(torrent['peers'][peer_id][0]['last_announce'])
                window = datetime.now() - timedelta(seconds=ANNOUNCE_INTERVAL)
                window_unix = int(time.mktime(window.timetuple()))

                if peer_last_announce < window_unix:
                    remove_peer_from_info_hash(torrent['info_hash'], peer_id)
    else:
        # There must be a better way to do this.
        # Also, it should probably be done as a recurring function and cache,
        # not dynamically every time.
        for key in s3_client.list_objects(Bucket=BUCKET_NAME)['Contents']:
            if 'peers.json' in key['Key']:
                remote_object = s3.Object(BUCKET_NAME, key['Key']).get()
                content = remote_object['Body'].read().decode('utf-8')
                torrent = json.loads(content)
                for peer_id in torrent['peers']:
                    peer_last_announce = int(torrent['peers'][peer_id]['last_announce'])
                    window = datetime.now() - timedelta(seconds=ANNOUNCE_INTERVAL)
                    window_unix = int(time.mktime(window.timetuple()))

                    if peer_last_announce < window_unix:
                        remove_peer_from_info_hash(torrent['info_hash'], peer_id)

    return

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
                left,
            ):
    
    if DATASTORE == "DynamoDB":
        return add_peer_to_info_hash_dynamo(
                                    info_hash, 
                                    peer_id, 
                                    ip,
                                    port, 
                                    uploaded, 
                                    downloaded, 
                                    left,
                                )
    else:
        return add_peer_to_info_hash_s3(
                                    info_hash, 
                                    peer_id, 
                                    ip,
                                    port, 
                                    uploaded, 
                                    downloaded, 
                                    left,
                                )

def add_peer_to_info_hash_dynamo(
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
        "port": port,
        "last_announce": int(time.time())
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

def add_peer_to_info_hash_s3(
                info_hash, 
                peer_id, 
                ip,
                port, 
                uploaded, 
                downloaded, 
                left
            ):
    """
    Update an info_hash with this peer, S3 bucket based.
    """

    ensure_torrent_exists(info_hash)

    # Prep the new info
    info_set = {
        "uploaded": uploaded,
        "downloaded": downloaded,
        "left": left,
        "ip": ip,
        "port": port,
        "last_announce": int(time.time())
    }
        
    remote_object = s3.Object(BUCKET_NAME, info_hash + '/peers.json').get()
    content = remote_object['Body'].read().decode('utf-8')
    torrent_info = json.loads(content)

    torrent_info['peers'][peer_id] = info_set
    torrent_info_s = json.dumps(torrent_info)
    result = s3.Object(BUCKET_NAME, info_hash + '/peers.json').put(
        Body=torrent_info_s,
        ContentEncoding='utf-8'
    )

    if result['ResponseMetadata']['HTTPStatusCode'] == 200 and 'Attributes' in result:
        return True
    return False

def add_peer_to_info_hash_dynamo(
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
        "port": port,
        "last_announce": int(time.time())
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

    if DATASTORE == "DynamoDB":
        return remove_peer_from_info_hash_dynamo(
                                        info_hash, 
                                        peer_id, 
                                    )
    else:
        return remove_peer_from_info_hash_s3(
                                        info_hash, 
                                        peer_id, 
                                    )

def remove_peer_from_info_hash_dynamo(
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

def remove_peer_from_info_hash_s3(
                            info_hash, 
                            peer_id, 
                        ):

    ensure_torrent_exists(info_hash)
    remote_object = s3.Object(BUCKET_NAME, info_hash + '/peers.json').get()
    content = remote_object['Body'].read().decode('utf-8')
    torrent_info = json.loads(content)

    del torrent_info['peers'][peer_id]

    torrent_info_s = json.dumps(torrent_info)
    result = s3.Object(BUCKET_NAME, info_hash + '/peers.json').put(
        Body=torrent_info_s,
        ContentEncoding='utf-8'
    )

    if result['ResponseMetadata']['HTTPStatusCode'] == 200 and 'Attributes' in result:
        return True
    return False

def increment_completed(info_hash):
    """
    Atomic increment completed for a torrent.
    """

    if DATASTORE == "DynamoDB":
        return increment_completed_dynamo(
                                        info_hash, 
                                    )
    else:
        return increment_completed_s3(
                                        info_hash, 
                                    )

def increment_completed_dynamo(info_hash):
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

def increment_completed_s3(info_hash):
    """
    Atomic increment completed for a torrent.
    """

    ensure_torrent_exists(info_hash)
    remote_object = s3.Object(BUCKET_NAME, info_hash + '/peers.json').get()
    content = remote_object['Body'].read().decode('utf-8')
    torrent_info = json.loads(content)

    torrent_info['completed'] = torrent_info['completed'] + 1
    torrent_info_s = json.dumps(torrent_info)
    result = s3.Object(BUCKET_NAME, info_hash + '/peers.json').put(
        Body=torrent_info_s,
        ContentEncoding='utf-8'
    )

    if result['ResponseMetadata']['HTTPStatusCode'] == 200 and 'Attributes' in result:
        return True
    return False    

def ensure_torrent_exists(info_hash):
    """
    Ensure a torrent exists before updating.
    """

    if DATASTORE == "DynamoDB":
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
    else:
        # S3
        try:
            remote_obj = s3.Object(BUCKET_NAME, info_hash + '/peers.json').get()
        except Exception as e:  # pragma: no cover
            # No item here, let's get it started.
            item = {
                    'info_hash': info_hash,
                    'peers': {},
                    'completed': 0
                }
            item_s = json.dumps(item)
            remote_obj = s3.Object(BUCKET_NAME, info_hash + '/peers.json').put(
                Body=item_s,
                ContentEncoding='utf-8'
            )

    return

def get_peers_for_info_hash(
                info_hash, 
                limit=50
            ):
    """
    Get current peers
    """

    if DATASTORE == "DynamoDB":
        return get_peers_for_info_hash_dynamodb(info_hash, limit)
    else:
        return get_peers_for_info_hash_s3(info_hash, limit)

def get_peers_for_info_hash_dynamodb(
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

def get_peers_for_info_hash_s3(
                info_hash, 
                limit=50
            ):
    """
    Get current peers, S3.
    """

    remote_object = s3.Object(BUCKET_NAME, info_hash + '/peers.json').get()
    content = remote_object['Body'].read().decode('utf-8')
    torrent_info = json.loads(content)
    return torrent_info['peers']

def get_all_items():
    """
    Get all items
    """

    if DATASTORE == "DynamoDB":
        response = table.scan()
        if response['Count'] == 0:
            return []
        else:
            return response['Items']
    else:

        # We want info_hash, peers, and completed.
        items = []
        
        # There must be a better way to do this.
        # Also, it should probably be done as a recurring function and cache,
        # not dynamically every time.
        for key in s3_client.list_objects(Bucket=BUCKET_NAME)['Contents']:
            if 'peers.json' in key['Key']:
                remote_object = s3.Object(BUCKET_NAME, key['Key']).get()
                content = remote_object['Body'].read().decode('utf-8')
                torrent_info = json.loads(content)
                item = {
                    'info_hash': torrent_info['info_hash'],
                    'peers': torrent_info['peers'],
                    'completed': torrent_info['completed']
                }
                items.append(item)

        return items

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
