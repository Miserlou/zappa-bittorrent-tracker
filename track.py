#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

zappa-bittorrent-tracker

An experimental, completely server-less BitTorrent tracker powered by Zappa, Flask and S3.
@jarus' "flaker" was used as a reference to get this project started. https://github.com/jarus/flacker/

"""

import os
import cgi
import socket
from binascii import b2a_hex
from struct import pack

from bencode import bencode
from flask import Flask, render_template, request, make_response, redirect, abort

##
# Conf
##

ANNOUNCE_INTERVAL = 300
DEBUG = True

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
    
    peer_id = request.args['peer_id']
    info_hash = get_info_hash(request)

    if request.args.get('event') == 'stopped':
        # redis.srem(seed_set_key, peer_id)
        # redis.srem(leech_set_key, peer_id)
        # redis.delete(peer_key)
        return bencode({})
    elif request.args.get('event') == 'completed':
        # redis.hincrby(torrent_key, 'downloaded', 1)
        pass
    if 'ip' not in request.args:
        ip = request.args.get('ip', request.remote_addr)
        # TODO: Validate
    else:
        ip = request.args['ip']
        # TODO: Validate

    # redis.hset(peer_key, 'ip', ip)
    # redis.hset(peer_key, 'port', request.args.get('port', int))
    # redis.hset(peer_key, 'uploaded', request.args['uploaded'])
    # redis.hset(peer_key, 'downloaded', request.args['downloaded'])
    # redis.hset(peer_key, 'left', request.args['left'])
    # redis.expire(peer_key, announce_interval() + 60)

    # if request.args.get('left', 1, int) == 0 \
    # or request.args.get('event') == 'completed':
    #     redis.sadd(seed_set_key, peer_id)
    #     redis.srem(leech_set_key, peer_id)
    # else:
    #     redis.sadd(leech_set_key, peer_id)
    #     redis.srem(seed_set_key, peer_id)

    # peer_count = 0
    # if request.args.get('compact', False, bool):
    #     peers = ""
    # else:
    #     peers = []
    # for peer_id in redis.sunion(seed_set_key, leech_set_key):
    #     peer_key = 'peer:%s' % peer_id
    #     ip, port, left = redis.hmget(peer_key, 'ip', 'port', 'left')
    #     if (ip and port) is None:
    #         redis.srem(seed_set_key, peer_id)
    #         redis.srem(leech_set_key, peer_id)
    #         continue
    #     elif peer_count >= request.args.get('numwant', 50, int):
    #         continue
    #     elif int(left) == 0 and request.args.get('left', 1, int) == 0:
    #         continue

    #     peer_count += 1
    #     if request.args.get('compact', False, bool):
    #         try:
    #             ip = socket.inet_pton(socket.AF_INET, ip)
    #         except socket.error:
    #             continue
    #         port = pack(">H", int(port))
    #         peers += (ip + port)

    ip = "127.0.0.1"
    port = 1234
    peer_id = "abcdef"

    peers = []
    peer = {'ip': ip, 'port': int(port)}
    if 'no_peer_id' not in request.args:
        peer['peer_id'] = peer_id
    peers.append(peer)

    return bencode({
        'interval': ANNOUNCE_INTERVAL,
        'complete': 0,
        'incomplete': 0,
        'peers': peers
})

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
