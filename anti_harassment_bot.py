#!/usr/bin/env python3

import tweepy
import time
from os import path

from datetime import datetime, timezone
from dateutil import tz

import csv
import yaml


def get_id_by_username(username):
    response = client.get_user(username=username)
    user = response.data
    return user.id
    

def junk_id_oracle(author_id): 
    #query info about the author
    response = client.get_user(id=author_id)
    
    #get the account creation time
    author_created = response.data.created_at
    #get the user name
    author_name = response.data.username
    
    #get the followers
    response = client.get_users_followers(id=author_id)
    followers = response.data
    
    if followers == None:
        num_of_followers = 0
    else:
        num_of_followers = len(followers)
    #too few followers and not in whitelist
    if num_of_followers < 3:
        print(f"ORACLE TIME!: id {author_id} name {author_name} number_of_followers {num_of_followers} is bad")
        block_list[author_id] = author_name
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
    t = time.localtime()
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", t)
    print('TIME:',current_time)


    #generate paths for relavant files
    pwd = path.dirname(path.realpath(__file__))
    conf_path = path.join(pwd,'conf.yaml')
    white_list_path = path.join(pwd,'white_list.csv')
    block_list_path = path.join(pwd,'block_list.yaml')

    with open(conf_path, 'r') as stream:
        conf = yaml.safe_load(stream)
    #load secrets
    secrets = conf['secrets']
    #load my own id
    MY_ID = conf['MY_ID']

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
    users = {user.id:user.username for user in users}
    
    for tweet in tweets:
        #get the user id
        author_id = tweet.author_id
        # localize time zone
        local_time = tweet.created_at.replace(tzinfo=timezone.utc).astimezone(tz.gettz()).strftime('%Y-%m-%d %H:%M:%S')
        
        if author_id not in WHITE_LIST:
            if author_id in block_list:
                #no need to repeat blocking
                print(f"ABUSER FOUND: id {author_id} name {block_list[author_id]} who interacted with me at {local_time} has already been blocked!")
            else:
                #unknown new account, in neither whitelist nor blocklist
                is_bad = junk_id_oracle(int(author_id))
                if is_bad:
                    # block a user
                    result = client.block(target_user_id=author_id)
                    print(f"DOUBLE CHECK: id {author_id} name {users[author_id]} who interacted with me at {local_time} blocked? {result.data['blocking']}")
        else:
            #from friends
            print(f"FRIEND FOUND: id {author_id} name {WHITE_LIST[author_id]} who interacted with me at {local_time} is from the WHITE LIST")
            
        
    #save the updated block list
    with open(block_list_path,'w') as f:
        yaml.dump(block_list,f)