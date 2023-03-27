#!/usr/bin/env python3.9

import yaml
import traceback
from datetime import datetime, timezone
import snscrape.modules.twitter as sntwitter

def save_yaml(dictionary, filepath, write_mode):
    with open(filepath, write_mode) as f:
        yaml.dump(dictionary, f)


def load_yaml(filepath):
    # yaml_path = os.path.join(pwd, filepath)
    try:
        with open(filepath, "r") as stream:
            dictionary = yaml.safe_load(stream)
            return dictionary
    except:
        traceback.print_exc()
        return None
        
def sns_timestamp_to_utc_datetime(timestamp):
    return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=timezone.utc)
    
    
def id_from_screen_name(screen_name):
    """
    Gets the numerical user id given the user handle.
    """
    x = sntwitter.TwitterUserScraper(screen_name)
    userdata = x._get_entity()
    return int(userdata.id)

def numerical_id(user_id):
    try:
        int_user_id = int(user_id)
    except:
        int_user_id = id_from_screen_name(user_id)
        
    return int_user_id
    