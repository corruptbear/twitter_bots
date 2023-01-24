#!/usr/bin/env python3

import tweepy
import time
from os import path

from datetime import datetime, timezone
from dateutil import tz

import csv
import yaml

from filelock import FileLock, Timeout
from rule_parser import rule_eval

def get_id_by_username(username):
    response = client.get_user(username=username)
    user = response.data
    return user.id
    
def save_block_list():
    with open(block_list_path,'w') as f:
        yaml.dump(block_list,f)


def junk_id_oracle(author_id): 
    #query info about the author
    response = client.get_user(id=author_id, user_fields=['created_at','public_metrics'])
    
    #get the account creation time, which is timezone aware (utc)
    author_created = response.data.created_at
    followers_count = response.data.public_metrics['followers_count']
    following_count = response.data.public_metrics['following_count']
    tweet_count = response.data.public_metrics['tweet_count']
    #print(author_created.replace(tzinfo=timezone.utc).astimezone(tz.gettz()).strftime('%Y-%m-%d %H:%M:%S'))
    #calculate the timedelta
    time_diff = current_time - author_created

    #get the user name
    author_name = response.data.username
    
    """
    #get the followers using the followers list API
    response = client.get_users_followers(id=author_id)
    followers = response.data
    
    if followers == None:
        followers_count = 0
    else:
        followers_count = len(followers)
    """

    default_fule = "(followers_count < 5) or (days < 180)"

    rule_eval_vars =  {'followers_count':followers_count, 'following_count':following_count, 'tweet_count':tweet_count,'days':time_diff.days}

    try:
        r = rule_eval(filtering_rule, rule_eval_vars)
    except Exception as e:
        print(e)
        r = rule_eval(default_rule, rule_eval_vars)

    #too few followers or too new
    if r:
        print(f"ORACLE TIME!: id {author_id} name {author_name} followers_count {followers_count} is bad")
        return True
    else:
        print(f"ORACLE TIME!: id {author_id} name {author_name} is good")
        return False

#find id by username
#test_id = get_id_by_username("rats_in_maze")
#print(type(test_id), test_id) #the type is int
    
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description = "parser for twitter bot",formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    #both short and long; the default dest in this case is args.max_results
    parser.add_argument("-m", "--max_results",help = "the maximum number of examined mentions", type = int, required = False, default = 15) 
    args = parser.parse_args()
    
    #print a separator line
    print('-'*10)

    #print out current time
    current_time = datetime.now(timezone.utc)
    current_time_str = current_time.astimezone(tz.gettz()).strftime("%Y-%m-%d %H:%M:%S")
    print('TIME:',current_time_str)


    #generate paths for relavant files
    pwd = path.dirname(path.realpath(__file__))
    conf_path = path.join(pwd,'conf.yaml')
    white_list_path = path.join(pwd,'white_list.csv')
    block_list_path = path.join(pwd,'block_list.yaml')
    hook_log_path = path.join(pwd,'hook_events_ids.log')
    hook_log_backup_path = path.join(pwd,"backup_hook_events_id.log")

    with open(conf_path, 'r') as stream:
        conf = yaml.safe_load(stream)
    #load secrets
    secrets = conf['secrets']
    #load my own id
    MY_ID = conf['MY_ID']
    #load filtering rule
    filtering_rule = conf['filtering_rule']

    #load the ids of recently blocked accounts
    block_list = dict()
    if path.exists(block_list_path):  
        with open(block_list_path,'r') as stream:
            block_list = yaml.safe_load(stream)

    #load the whitelist which contains friendly ids    
    WHITE_LIST = dict()
    if path.exists(white_list_path):
        with open(white_list_path, "r") as f:
            reader = csv.DictReader(f)
            WHITE_LIST = {int(row['twitter_id']):row['name'] for row in reader}


    # Twitter API V2
    client = tweepy.Client(
        bearer_token=secrets['BEARER_TOKEN'],
        consumer_key=secrets['CONSUMER_KEY'], consumer_secret=secrets['CONSUMER_SECRET'],
        access_token=secrets['ACCESS_TOKEN'], access_token_secret=secrets['ACCESS_SECRET'],
        wait_on_rate_limit=True
    )
       
    #get latest mentions
    response = client.get_users_mentions(id=MY_ID, max_results=args.max_results, tweet_fields=['created_at'], expansions='author_id')
    tweets = response.data
    users = response.includes["users"]
    users = {int(user.id):user.username for user in users}
    
    for tweet in tweets:
        #get the user id
        author_id = tweet.author_id
        # localize time zone
        local_time = tweet.created_at.replace(tzinfo=timezone.utc).astimezone(tz.gettz()).strftime('%Y-%m-%d %H:%M:%S')
        
        if author_id not in WHITE_LIST:
            if author_id in block_list:
                #no need to repeat blocking
                print(f"ABUSER FOUND: interaction at {local_time} id {author_id} name {block_list[author_id]} has already been blocked!")
            else:
                #unknown new account, in neither whitelist nor blocklist
                is_bad = junk_id_oracle(int(author_id))
                if is_bad:
                    # block a user
                    result = client.block(target_user_id=author_id)
                    print(f"DOUBLE CHECK: interaction at {local_time} id {author_id} name {users[author_id]} blocked? {result.data['blocking']}")
                    
                    if result.data['blocking']:
                        #update the block list
                        block_list[author_id] = users[author_id]       
                        #save the updated block list immediately
                        save_block_list() 
        else:
            #from friends
            print(f"FRIEND FOUND: interaction at {local_time} id {author_id} name {WHITE_LIST[author_id]} is from the WHITE LIST")
   
   #if webhook is enabled
    if path.exists(hook_log_path):
        print("~~~WEBHOOK~~~")
        #get the lock
        lock_path = hook_log_path + ".lock"
        lock = FileLock(lock_path, timeout=2)
        with lock:
            with open(hook_log_path,'r') as stream:
                hook_log = yaml.safe_load(stream)
                #if the file is not empty
                if hook_log is not None:
                    for timestamp in hook_log:
                        #for some reason, not all are int, so need to convert
                        user_id = int(hook_log[timestamp]['id'])  
                        screen_name = str(hook_log[timestamp]['screen_name'])
                        #if the user recorded in the hook log is not already examined in the mentions
                        if user_id not in users:
                            if user_id not in WHITE_LIST:
                                if user_id in block_list:
                                    print(f"ABUSER FOUND: id {user_id} name {screen_name} has alerady been blocked!")
                                else:
                                    is_bad = junk_id_oracle(int(user_id))
                                    if is_bad:
                                        result = client.block(target_user_id=user_id)
                                        print(f"MISSED FISH!: id {user_id} name {screen_name} blocked? {result.data['blocking']}")
                                        if result.data['blocking']:
                                            block_list[user_id] = screen_name
                                            save_block_list()
                            else:
                                print(f"FRIEND FOUND: id {user_id} name {screen_name} is from the WHITE LIST")
                    #backup the processed hook users            
                    with open(hook_log_backup_path,"a") as f:
                        yaml.dump(hook_log,f)

            #reset the hook log to blank file
            with open(hook_log_path,'w') as blank_file:
                pass
