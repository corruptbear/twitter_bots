from datetime import datetime, timezone
from dateutil import tz
def ctime_to_unix_timestamp(ctime_str):
    return datetime.timestamp(datetime.strptime(ctime_str, '%a %b %d %H:%M:%S +0000 %Y').replace(tzinfo=timezone.utc).astimezone(tz.gettz()))

def ctime_to_localtime(ctime_str):
    local_time = datetime.strptime(ctime_str, '%a %b %d %H:%M:%S +0000 %Y').replace(tzinfo=timezone.utc).astimezone(tz.gettz()).strftime('%Y-%m-%d %H:%M:%S')
    return local_time

def unixtime_to_localtime(unixtime_str):
    local_time = datetime.utcfromtimestamp(int(unixtime_str)).replace(tzinfo=timezone.utc).astimezone(tz.gettz()).strftime('%Y-%m-%d %H:%M:%S')
    return local_time


def tweet_create_event_info(event):
    if 'in_reply_to_status_id' in event and event['in_reply_to_status_id'] is not None:
        return {'event_type':'reply','with_id':int(event['in_reply_to_user_id_str'])}

    if 'quoted_status' in event:
        return {'event_type':'quoted_retweet','with_id':int(event['quoted_status']['user']['id'])}

    if 'retweeted_status' in event:
        return {'event_type':'unquoted_retweet','with_id':int(event['retweeted_status']['user']['id'])}

    return {'event_type':'new_tweet'}
