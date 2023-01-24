#!/usr/bin/env python3
  
import json
import os
import sys

import requests
from requests_oauthlib import OAuth1
import yaml

#the credentials are saved in hook_conf.yaml in the folder where the script is invoked
with open("hook_conf.yaml", 'r') as stream:
    conf = yaml.safe_load(stream)
    #load secrets
    secrets = conf['secrets']
    env_name = conf['env_name']
    #web_app_url = conf['web_app_url']

# Generate user context auth (OAuth1)
user_context_auth = OAuth1(secrets["CONSUMER_KEY"], secrets["CONSUMER_SECRET"], secrets["ACCESS_TOKEN"], secrets["ACCESS_SECRET"])

# Assign the resource url
hook_id = "1610046714823741440"

resource_url = f"https://api.twitter.com/1.1/account_activity/all/{env_name}/webhooks/{hook_id}.json"



response = requests.delete(resource_url, auth=user_context_auth)
print(response.status_code, response.text)
