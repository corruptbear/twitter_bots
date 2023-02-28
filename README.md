# twitter_bots

current usage
- personal anti-harassment bot
- auto-block accounts interacting with me based on account information
- works with & without twitter webhook
- the webhook flask code is included. you need to have elevated twitter API access, register your webhook with `https` url and set it up with your apache server. 

## install

```bash
git clone https://github.com/wsluo/twitter_bots
cd twitter_bots

#create empty configuration files
touch white_list.yaml && touch conf.yaml && touch hook_conf.yaml

#create virtual env
python3 -m venv venv
#activate virtual env
. venv/bin/activate

pip3 install --upgrade pip
pip3 install -r requirements.txt
```

## API-free bot config
you need to configure `apifree.yaml` before running `python3.9 free_bot.py`
```yaml
latest_cursor:
login:
  email: your_actual_stuff_here
  password: your_actual_stuff_here
  phonenumber: your_actual_stuff_here
  screenname: your_actual_stuff_here
```

## API bot config config
put known friends in `white_list.yaml` line by line
```yaml
id1_of_your_friend: name1_of_your_friend
id2_of_your_friend: name2_of_your_friend
```

the content of `conf.yaml` should look like this. `filtering_rule` is explained later.
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
filtering_rule: your_filtering_rule_in_double_quotes
```

the content of `hook_conf.yaml` should look like this.
note that the url for you webhook needs to be `https`, `http` will not work. Self-signed SSL certificates will also not work here.
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

## filtering rule
logic expression describing bad accounts

- logic operators:  `not` `and` `or`  
- comparison operators:  `>` `<` `>=` `<=` `==` `!=`
- keywords: `followers_count ` `following_count`  `tweet_count` `days`  

Example
```
"(followers_count <= 5 and following_count <= 5) or (days <= 180)"
```

## Cron scheduling setup
you can schedule the bot to run periodically using job scheduler Cron. 
make necessary changes and copy the example schedule to the cron job folder

inside the cron file, make sure that you are invoking `venv/bin/python3`
```bash
#copy the cron file to the cron folder
sudo cp bot_schedule /etc/cron.d/bot_schedule
#you can then modify schedule there
sudo vim /etc/cron.d/bot_schedule
```

## view files
```bash
#check the block list, which will be auto-updated with auto-blocks
cat block_list.yaml
#check the white list
cat white_list.yaml
#check the full history of hook events
backup_hook_events_ids.log
```

## webhook setup

setup the mod_wsgi httpd configuration
```bash
cd venv/bin
#paste the result to the beginning of the main httpd.conf! 
#the version of mod_wsgi needs to match the python version, otherwise it's bug prone
mod_wsgi-express module-config
```

make the logs accessible for writing, then register the webhook (*Do not run this multiple times*)
```bash
#assuming you are now in the main folder
touch hook_events_ids.log && chmod 777 hook_events_ids.log
touch hook_events_ids.log.lock && chmod 777 hook_events_ids.log.lock

cd webhook
touch debug.log && chmod 776 debug.log

#register the webhook
cd .. && . venv/bin/activate

#if you need to revoke old webhook, change the hook id and run
#python3 revoke_webhook.py

python3 register_webhook.py
python3 subscribe_owning_user.py

#do not forget to save your webhook id
```


## SELinux setup
it's necessary for SELinux users.
suppose you are in the `twitter_bots` 's parent directory.
```bash
chcon -R --type=httpd_sys_content_t twitter_bots

cd twitter_bots
chcon -t httpd_sys_rw_content_t hook_events_ids.log
chcon -t httpd_sys_rw_content_t hook_events_ids.log.lock
#if you are using SELinux (change the path if you are using other versions)
chcon -t httpd_sys_script_exec_t  venv/lib64/python3.6/site-packages/mod_wsgi/server/mod_wsgi-py36.cpython-36m-aarch64-linux-gnu.so

cd webhook
chcon -t httpd_sys_script_exec_t hook.wsgi
chcon -t httpd_sys_script_exec_t hook_site.py
chcon -t httpd_sys_script_exec_t utils.py
chcon -t httpd_sys_script_exec_t __init__.py
chcon -t httpd_sys_rw_content_t debug.log
````