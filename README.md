# twitter_bots

current usage
- personal anti-harassment bot
- auto-block accounts interacting with me based on number of followers and registration time
- works with & without twitter webhook
- for webhook to work, you need to set it up and add event handler code to save the ids and screen_names of users interacting with you to `hook_events_ids.log` in this folder (which could be parsed as yaml)

## install

```bash
git clone https://github.com/wsluo/twitter_bots
cd twitter_bots
pip3 install -r requirements.txt
```

## config
put friends in `white_list.csv` with following header line
```csv
twitter_id,name
```

make `conf.yaml` in this directory, fill in the information from your bot app
```yaml
MY_ID: your_id_number
secrets:
  CLIENT_ID: your_actual_stuff_here
  CLIENT_SECRET: your_actual_stuff_here
  BEARER_TOKEN: your_actual_stuff_here
  ACCESS_TOKEN: your_actual_stuff_here
  ACCESS_SECRET: your_actual_stuff_here
  CONSUMER_KEY: your_actual_stuff_here
  CONSUMER_SECRET: your_actual_stuff_here
```

## Cron scheduling setup
you can schedule the bot to run periodically using job scheduler Cron. 

make necessary changes and copy the example schedule to the cron job folder
```bash
#copy the cron file to the cron folder
sudo cp anti_harassment /etc/cron.d/anti_harassment
#you can then modify schedule there
sudo vim /etc/cron.d/anti_harassment
```

## view files
```bash
#check the block list
cat block_list.yaml
#check the white list
cat white_list.csv
```

## webhook setup

make `hook_conf.yaml` in this directory
```yaml
MY_ID: your_id_number
env_name: your_env_name
web_app_url: your_hook_url
secrets:
  CLIENT_ID: your_actual_stuff_here
  CLIENT_SECRET: your_actual_stuff_here
  BEARER_TOKEN: your_actual_stuff_here
  ACCESS_TOKEN: your_actual_stuff_here
  ACCESS_SECRET: your_actual_stuff_here
  CONSUMER_KEY: your_actual_stuff_here
  CONSUMER_SECRET: your_actual_stuff_here
```

suppose you have already [setup your webhook to handle crc](https://dev.to/twitterdev/building-a-live-leaderboard-on-twitter-49g9#gs-registering),
then you can register your webhook and make yourself a subscriber

*Do not run this multiple times*
```bash
python3 register_webhook.py
python3 subscribe_owning_user.py
```

prepare the logs accessible for writing
```bash
touch hook_events_ids.log && chmod 777 hook_events_ids.log
touch hook_events_ids.log.lock && chmod 777 hook_events_ids.log.lock
```
