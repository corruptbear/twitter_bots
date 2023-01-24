#!/usr/bin/env python3
  
from flask import Flask, request, jsonify, render_template, send_from_directory
import time
import random
import json
import os
import hmac
import hashlib
import base64
from filelock import Timeout, FileLock
import yaml



app = Flask(__name__)

CONSUMER_SECRET = "pAQrz7DcuSwnq9Zv9kn5ocaDwYhuMWoryklfVkLlxNQze99sZ0"

# The GET method for webhook should be used for the CRC check
@app.route("/mywebhook", methods=["GET"])
def twitter_crc_validation():
    crc = request.args['crc_token']
    validation = hmac.new(
        key=bytes(CONSUMER_SECRET, 'utf-8'),
        msg=bytes(crc, 'utf-8'),
        digestmod = hashlib.sha256
    )
    digested = base64.b64encode(validation.digest())
    response = {
        'response_token': 'sha256=' + format(str(digested)[2:-1])
    }
    print('responding to CRC call')
    return json.dumps(response)


from utils import unixtime_to_localtime,  ctime_to_localtime, tweet_create_event_info
@app.route("/mywebhook", methods=["POST"])
# Event manager block
def event_manager():
    print(request.json)
    tweet_create_logs,follow_logs,favorite_logs = dict(),dict(),dict()
    tweet_create_users,follow_users,favorite_users = dict(),dict(),dict()
    if 'tweet_create_events' in request.json:
        tweet_create_events = request.json["tweet_create_events"]

        tweet_create_logs = { ctime_to_localtime(event['created_at']):{**{'id':event['user']['id'],'screen_name':event['user']['screen_name']},**tweet_create_event_info(event)} for event in tweet_create_events}

        #tweet_create_users = {event['user']['id']:{'screen_name':event['user']['screen_name'],'event_type':'tweet_create_event','created_at':event['created_at']} for event in tweet_create_events}

    if 'follow_events' in request.json:
        follow_events = request.json['follow_events']

        follow_logs = {unixtime_to_localtime(event['created_timestamp'][:10]):{'id':event['source']['id'], 'screen_name':event['source']['screen_name'],'event_type':'follow'} for event in follow_events}

        #follow_users = {event['source']['id']:{'screen_name':event['source']['screen_name'],'event_type':'follow_event','created_at':event['created_timestamp'][:10]} for event in follow_events}

    if 'favorite_events' in request.json:
        favorite_events = request.json['favorite_events']

        favorite_logs = { ctime_to_localtime(event['created_at']):{'id':event['user']['id'],'screen_name':event['user']['screen_name'],'event_type':'favorite'} for event in favorite_events}

        #favorite_users = {event['user']['id']:{'screen_name':event['user']['screen_name'],'event_type':'favorite_event','created_at':event['created_at']} for event in favorite_events}

    #users =  {**tweet_create_users, **follow_users, **favorite_users}

    event_logs = {**tweet_create_logs, **follow_logs, **favorite_logs}
    print(event_logs)
    if len(event_logs)>0:
        event_log_path = "/home/opc/twitter_bots/hook_events_ids.log"
        lock_path = event_log_path + ".lock"
        lock = FileLock(lock_path, timeout=5)
        with lock:
            with open(event_log_path,"a") as f:
                yaml.dump(event_logs, f)
    return "200"



#this is for printing data
@app.route("/",methods=['GET'])
def hello():
    html = "<p> hello world </p>"

    return html

if __name__ == "__main__":
    app.debug = True
    app.run(host = '0.0.0.0',ssl_context='adhoc')
    #app.run(host = '0.0.0.0')
