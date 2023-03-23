#!/usr/bin/env python3.9

import yaml
import traceback
from datetime import datetime, timezone

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