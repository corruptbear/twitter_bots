# twitter_bots

install

```bash
git clone https://github.com/wsluo/twitter_bots
cd twitter_bots
pip3 install -r requirements.txt
```


cron scheduling setup
```bash
#copy the cron file to the cron folder
sudo cp anti_harassment /etc/cron.d/anti_harassment
#you can then modify schedule there
sudo vim /etc/cron.d/anti_harassment
```

```bash
#check the block list
cat block_list.yaml
```
