#!/usr/bin/env python3.9

import platform
from selenium import webdriver
from time import sleep
from datetime import datetime
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from webdriver_manager.firefox import GeckoDriverManager

import snscrape.modules.twitter as sntwitter

import os
import sys
import glob
import random
import pickle
import time
import traceback
import yaml

from datetime import datetime, timezone

def save_yaml(dictionary, filepath, write_mode):
    yaml_path = os.path.join(pwd, filepath)
    with open(yaml_path, write_mode) as f:
        yaml.dump(dictionary, f)


def load_yaml(filepath):
    yaml_path = os.path.join(pwd, filepath)
    try:
        with open(yaml_path, "r") as stream:
            dictionary = yaml.safe_load(stream)
            return dictionary
    except:
        traceback.print_exc()
        return None

pwd = os.path.dirname(os.path.realpath(__file__))


d = load_yaml("login.yaml")

email = d['email']
password = d['password']
screenname = d["screenname"]
phonenumber = d["phonenumber"]


class SeleniumTwitterBot:
    # login url
    url = "https://twitter.com/rats_in_maze"
    notification_url = "https://twitter.com/notifications"
    home_url = "https://twitter.com/home"

    cookie_path = "sl_cookies.pkl"

    # ------------------------ALL XPATHS--------------------------
    # login banner at the bottom of a page, if logged out
    # if screen is small, somehow the path is different!?
    enter_login_button_alt_xpath = (
        "//*[@id='layers']/div/div[1]/div/div/div/div/div/div/div/div[1]/a"
    )
    # on normal screen
    enter_login_button_xpath = (
        "//*[@id='layers']/div/div[1]/div/div/div/div[2]/div[2]/div/div/div[1]/a"
    )
    banner_xpath = "//*[@id='modal-header']/span"

    # email input and next button
    # user_name_input_xpath= "/html/body/div/div/div/div[1]/div/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div/div/div/div[5]/label/div/div[2]/div/input"
    email_input_xpath = "//*[@id='layers']/div/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div/div/div/div[5]/label/div/div[2]/div/input"
    next_button_xpath = "//*[@id='layers']/div/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div/div/div/div[6]/div"

    # password input and login button
    password_input_xpath = "//*[@id='layers']/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[1]/div/div/div[3]/div/label/div/div[2]/div[1]/input"
    login_button_xpath = "//*[@id='layers']/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[2]/div/div[1]/div/div/div"

    # possible warning title
    title_xpath = "//*[@id='modal-header']/span/span"
    warning_title = "Enter your phone number or username"
    warning_detail_xpath = "//*[@id='layers']/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[1]/div/div[1]/div/div/div/div/span/span"

    # unusual activity input and next button (leading to password screen)
    warning_input_xpath = "//*[@id='layers']/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[1]/div/div[2]/label/div/div[2]/div/input"
    warning_next_button_xpath = "//*[@id='layers']/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[2]/div/div/div/div/div"

    # handle phone check
    phone_input_xpath = "/html/body/div[1]/div/div/div[1]/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[1]/div/div[2]/label/div/div[2]/div/input"

    # notification tab
    notification_tab_xpath = (
        "//*[@id='react-root']/div/div/div[2]/header/div/div/div/div[1]/div[2]/nav/a[3]"
    )
    notification_indication_xpath = "//*[@id='react-root']/div/div/div[2]/header/div/div/div/div[1]/div[2]/nav/a[3]/div/div/div"

    cell_xpath = (
        lambda i: f"//*[@id='react-root']/div/div/div[2]/main/div/div/div/div/div/div[3]/section/div/div/div[{i}]"
    )
    # non_reply_item_xpath = lambda i: f"//*[@id='react-root']/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/section/div/div/div[{i}]/div/div/article"
    non_reply_item_xpath = (
        lambda i: f"/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/section/div/div/div[{i}]/div/div/article"
    )
    non_reply_id_xpath = (
        lambda i: f"/html/body/div[1]/div/div/div[2]/main/div/div/div/div/div/div[3]/section/div/div/div[{i}]/div/div/article/div[1]/div[2]/div[2]/div/a"
    )
    # reply_item_xpath = lambda i: f"//*[@id='react-root']/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/section/div/div/div[{i}]/div/div/div/article"
    reply_item_xpath = (
        lambda i: f"/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/section/div/div/div[{i}]/div/div/div/article"
    )
    reply_id_xpath = (
        lambda i: f"/html/body/div[1]/div/div/div[2]/main/div/div/div/div/div/div[3]/section/div/div/div[{i}]/div/div/div/article/div/div/div/div[2]/div[2]/div[1]/div/div/div[1]/div/div/div[1]/div/a"
    )
    reply_time_xpath = (
        lambda i: f"/html/body/div[1]/div/div/div[2]/main/div/div/div/div/div/div[3]/section/div/div/div[{i}]/div/div/div/article/div/div/div/div[2]/div[2]/div[1]/div/div/div[1]/div/div/div[2]/div/div[3]/a/time"
    )

    # sometimes you get a square page saying there is an error, refresh or logout?
    refresh_button_xpath = "//*[@id='layers']/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div/div[2]/div[2]/div[1]"

    # items to click for block via user page
    operation_menu_button_xpath = "//*[@id='react-root']/div/div/div[2]/main/div/div/div/div/div/div[3]/div/div/div/div/div[1]/div[2]/div[1]"
    block_button_xpath = (
        "//*[@id='layers']/div[2]/div/div/div/div[2]/div/div[3]/div/div/div/div[3]"
    )
    agree_block_button_xpath = (
        "//*[@id='layers']/div[2]/div/div/div/div/div/div[2]/div[2]/div[2]/div[1]"
    )

    # problem: the path is different depending on user profile
    following_count_xpath = "/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/div/div/div/div/div[5]/div[1]/a/span[1]/span"
    follower_count_xpath = "/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/div/div/div/div/div[5]/div[2]/a/span[1]/span"
    join_date_xpath = "/html/body/div[1]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/div/div/div/div/div[4]/div/span/span"

    def __init__(self):
        SeleniumTwitterBot.cookie_path = os.path.join(
            pwd, SeleniumTwitterBot.cookie_path
        )
        self.setup_driver()

    def setup_driver(self):
        current_platform = platform.system()
        print("current_platform:", current_platform)
        if current_platform == "Darwin":
            # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=chrome_options)
            driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()))
        if current_platform == "Linux":
            chrome_options.add_argument("--headless=new")
            driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()))
        # user agent
        # driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.5414.119 Safari/537.36'})
        print(driver.execute_script("return navigator.userAgent;"))

        self.driver = driver

    def check_element_exists(self, xpath):
        elements = self.driver.find_elements(By.XPATH, xpath)
        return len(elements) > 0

    def wait_for_element_xpath(self, xpath):
        wait = WebDriverWait(self.driver, 20)
        wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def wait_and_find_element_xpath(self, xpath):
        self.wait_for_element_xpath(xpath)
        return self.driver.find_element(By.XPATH, xpath)

    def click_button_xpath(self, xpath):
        button = self.wait_and_find_element_xpath(xpath)
        self.driver.execute_script("arguments[0].click();", button)

    def input_xpath(self, text, xpath):
        input_field = self.wait_and_find_element_xpath(xpath)
        input_field.send_keys(text)
        # enter return key
        input_field.send_keys(Keys.ENTER)

    def auto_block_user(self, user):
        target_url = "https://twitter.com/" + user
        self.driver.get(target_url)
        self.click_button_xpath(SeleniumTwitterBot.operation_menu_button_xpath)
        self.click_button_xpath(SeleniumTwitterBot.block_button_xpath)
        self.click_button_xpath(SeleniumTwitterBot.agree_block_button_xpath)

    def load_cookies(self, cookies_filepath):
        print("...loading cookies...")
        cookies = pickle.load(open(cookies_filepath, "rb"))
        print(cookies)
        for cookie in cookies:
            # if 'expiry' in cookie and cookie['expiry'] < time.time():
            #    cookie['expiry'] = int(time.time()) + 604800

            self.driver.add_cookie(cookie)
            print(cookie)

    def get_reply_user_url_finished(self, d):
        self._user_url = d.execute_script(
            "return arguments[0].getAttribute('href');", self._current_element
        )
        return self._user_url is not None

    def get_reply_user_datetime_finished(self, d):
        self._user_datetime = d.execute_script(
            "return arguments[0].getAttribute('datetime');", self._current_time_element
        )
        return self._user_datetime is not None

    def get_non_reply_user_url_finished(self, d):
        self._user_url = d.execute_script(
            "return arguments[0].getAttribute('href');", self._current_element
        )
        return self._user_url is not None

    def check_user(self, user_name):
        x = sntwitter.TwitterUserScraper(user_name)
        userdata = x._get_entity()
        tweet_count = userdata.statusesCount
        following_count = userdata.friendsCount
        followers_count = userdata.followersCount
        author_created = userdata.created
        current_time = datetime.now(timezone.utc)
        time_diff = current_time - author_created
        print(tweet_count, following_count, followers_count, time_diff.days)

    # manual login and set the page to the notification page
    def twitter_login_manual(self):
        print("...manual log in...")
        self.driver.get(SeleniumTwitterBot.url)
        # click login button from homepage
        try:
            self.click_button_xpath(SeleniumTwitterBot.enter_login_button_xpath)
        except:
            self.click_button_xpath(SeleniumTwitterBot.enter_login_button_alt_xpath)

        banner = self.wait_and_find_element_xpath(SeleniumTwitterBot.banner_xpath)
        print(banner.text)

        # fill in email
        self.input_xpath(email, SeleniumTwitterBot.email_input_xpath)

        # test if the system requires screenname
        title = self.wait_and_find_element_xpath(SeleniumTwitterBot.title_xpath).text
        print(title)
        if title == SeleniumTwitterBot.warning_title:
            print(
                self.driver.find_element(
                    By.XPATH, SeleniumTwitterBot.warning_detail_xpath
                ).text
            )

            # fill in screenname
            self.input_xpath(screenname, SeleniumTwitterBot.warning_input_xpath)

        # fill in password
        self.input_xpath(password, SeleniumTwitterBot.password_input_xpath)

    def twitter_login(self):
        # cookie refreshment? expiration? what will happen when one of the cookies expire?
        if os.path.exists(SeleniumTwitterBot.cookie_path):
            self.driver.get(SeleniumTwitterBot.home_url)

            try:
                self.load_cookies(SeleniumTwitterBot.cookie_path)

                sleep(1)
                l = self.driver.find_elements(
                    By.XPATH, SeleniumTwitterBot.refresh_button_xpath
                )
                if len(l) > 0:
                    print("NEED TO CLICK THE REFRESH BUTTON")
                    # after click the refresh button, the page will redirect to home page, not notification page
                    self.click_button_xpath(SeleniumTwitterBot.refresh_button_xpath)
                # after cookie is loading, there will be no autodirect, so you need to manually redirect if you want to go another page
                self.driver.get(SeleniumTwitterBot.home_url)

            except:
                traceback.print_exc()
                # if there is any error in cookie loading
                self.twitter_login_manual()
        else:
            self.twitter_login_manual()

        # ensure that we are on homepage
        # otherwise handle "enter phone number for safety"
        try:
            print("at the end of login:", self.driver.current_url)
            # without cookie, after login, it will auto-redirect to home
            WebDriverWait(self.driver, timeout=10).until(
                EC.url_to_be(SeleniumTwitterBot.home_url)
            )
            print("On homepage!", self.driver.current_url)
        except:
            self.input_xpath(phonenumber, SeleniumTwitterBot.phone_input_xpath)
            self.wait_and_find_element_xpath(
                SeleniumTwitterBot.phone_input_xpath
            ).send_keys(Keys.ENTER)

    def check_notifications(self):
        # the notification indication will only show after refreshing
        self.driver.refresh()

        print(
            "///////////////new notification?////////////////",
            self.check_element_exists(SeleniumTwitterBot.notification_indication_xpath),
        )
        self.driver.get(SeleniumTwitterBot.notification_url)
        print("notification page title:", self.driver.title)
        # to include more cells in one screen
        self.driver.execute_script("document.body.style.zoom='67%'")

        sleep(2)

        user_urls = set()
        self._user_url = None
        self._user_datetime = None
        self._current_element = None
        self._current_time_element = None

        # twitter's notification "articles"' seq number is dynamically renamed. if you scroll down a lot, the elements will start from 1 again
        for k in range(1):
            # records the xpath of last visited element
            last = -1
            for i in range(1, 100):
                l1 = self.driver.find_elements(
                    By.XPATH, SeleniumTwitterBot.non_reply_item_xpath(i)
                )
                l2 = self.driver.find_elements(
                    By.XPATH, SeleniumTwitterBot.reply_item_xpath(i)
                )

                # there are non-reply items
                if len(l1) > 0:
                    last = SeleniumTwitterBot.non_reply_item_xpath(i)
                    user_id = self.driver.find_elements(
                        By.XPATH, SeleniumTwitterBot.non_reply_id_xpath(i)
                    )

                    # not all non-reply items have user id (for example, login warning)
                    if len(user_id) > 0:
                        print("retrive---------non-reply-user------------", i, len(l1))

                        try:
                            self._current_element = user_id[0]
                            WebDriverWait(self.driver, 10).until(
                                self.get_non_reply_user_url_finished
                            )
                        except:
                            traceback.print_exc()

                        # user_url = driver.execute_script("return arguments[0].getAttribute('href');", user_id[0])
                        # WebDriverWait(driver, 10).until(lambda d: d.execute_script("return arguments[0].getAttribute('href');", user_id[0]) is not None)

                        print("ID url:", self._user_url)
                        user_urls.add(self._user_url)
                    # print(i,l1[0].text)

                # there are reply items
                if len(l2) > 0:
                    print("retrive---------reply-user------------", i, len(l2))

                    last = SeleniumTwitterBot.reply_item_xpath(i)

                    # user_url = driver.execute_script("return arguments[0].getAttribute('href');", driver.find_element(By.XPATH,reply_id_xpath(i)))
                    # WebDriverWait(driver, 10).until(lambda d: d.execute_script("return arguments[0].getAttribute('href');", wait_and_find_element_xpath(driver,reply_id_xpath(i))) is not None)
                    try:
                        self._current_element = self.wait_and_find_element_xpath(
                            SeleniumTwitterBot.reply_id_xpath(i)
                        )
                        WebDriverWait(self.driver, 10).until(
                            self.get_reply_user_url_finished
                        )

                        self._current_time_element = self.wait_and_find_element_xpath(
                            SeleniumTwitterBot.reply_time_xpath(i)
                        )
                        WebDriverWait(self.driver, 10).until(
                            self.get_reply_user_datetime_finished
                        )

                    except:
                        traceback.print_exc()

                    print("ID url:", self._user_url)
                    user_urls.add(self._user_url)
                    print("TIMESTAMP:", self._user_datetime)

                    # print(i,l2[0].text)

            print("last seen:", last)
            print("////////////////ONE ROLL END/////////////////")
            # actions = ActionChains(driver)
            # actions.move_to_element(driver.find_element(By.XPATH,last)).perform()
            self.driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")
            self.wait_for_element_xpath(SeleniumTwitterBot.cell_xpath(1))

        print("user_urls:", user_urls)
        user_names = [x[1:] for x in user_urls]

        for x in user_names:
            self.check_user(x)
            # test autoblock
            # auto_block_user(driver,x)

        pickle.dump(
            self.driver.get_cookies(), open(SeleniumTwitterBot.cookie_path, "wb")
        )


if __name__ == "__main__":
    b = SeleniumTwitterBot()
    b.twitter_login()
    b.check_notifications()
