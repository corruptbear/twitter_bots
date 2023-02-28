#!/usr/bin/env python3.9

import requests
import pickle
import sys
from time import sleep
from urllib.parse import urlencode, quote
import brotli
import dataclasses
from datetime import datetime, timezone
from dateutil import tz

import traceback
import os
import yaml

import json
import random
import re
import secrets
import copy

from selenium_bot import SeleniumTwitterBot, save_yaml, load_yaml
from rule_parser import rule_eval
from report import ReportHandler

MAX_MSG_LEN = 50

pwd = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(pwd, "apifree.yaml")
COOKIE_PATH = os.path.join(pwd, "sl_cookies.pkl")
WHITE_LIST_PATH = os.path.join(pwd, "white_list.yaml")
BLOCK_LIST_PATH = os.path.join(pwd, "block_list.yaml")
API_CONF_PATH = os.path.join(pwd, "conf.yaml")

config_dict = load_yaml(CONFIG_PATH)
block_list = load_yaml(BLOCK_LIST_PATH)
white_list = load_yaml(WHITE_LIST_PATH)
filtering_rule = load_yaml(API_CONF_PATH)["filtering_rule"]

EMAIL = config_dict["login"]["email"]
PASSWORD = config_dict["login"]["password"]
SCREENNAME = config_dict["login"]["screenname"]
PHONENUMBER = config_dict["login"]["phonenumber"]

from revChatGPT.V1 import Chatbot


def chatgpt_moderation(sentence):
    # https://chat.openai.com/api/auth/session
    chatbot = Chatbot(
        config={
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik1UaEVOVUpHTkVNMVFURTRNMEZCTWpkQ05UZzVNRFUxUlRVd1FVSkRNRU13UmtGRVFrRXpSZyJ9.eyJodHRwczovL2FwaS5vcGVuYWkuY29tL3Byb2ZpbGUiOnsiZW1haWwiOiJ3YXdueDcxNkBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiZ2VvaXBfY291bnRyeSI6IlVTIn0sImh0dHBzOi8vYXBpLm9wZW5haS5jb20vYXV0aCI6eyJ1c2VyX2lkIjoidXNlci00VU9DZGFhSGR3N2pob3p3Y3Z5c2VlT3EifSwiaXNzIjoiaHR0cHM6Ly9hdXRoMC5vcGVuYWkuY29tLyIsInN1YiI6Imdvb2dsZS1vYXV0aDJ8MTA0MTIzMjI3OTA5NjQ3MzI3NzUxIiwiYXVkIjpbImh0dHBzOi8vYXBpLm9wZW5haS5jb20vdjEiLCJodHRwczovL29wZW5haS5vcGVuYWkuYXV0aDBhcHAuY29tL3VzZXJpbmZvIl0sImlhdCI6MTY3NzQ3MzAyMywiZXhwIjoxNjc4NjgyNjIzLCJhenAiOiJUZEpJY2JlMTZXb1RIdE45NW55eXdoNUU0eU9vNkl0RyIsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwgbW9kZWwucmVhZCBtb2RlbC5yZXF1ZXN0IG9yZ2FuaXphdGlvbi5yZWFkIG9mZmxpbmVfYWNjZXNzIn0.InfRXdyfRubck8YSm6X7RXAelafEvDn_b7Oj442MmsWH-yVgQpUxQJnoB6wVgM2YUi6P5Cf7zo4I7ppnVss-IRobWNv7T3Jle5Ds7O9twCxg7GKy_OAnJTTeu0LGIEUNNESfmwHuDb5hm0MkcwpVphHifmaOYqaeLCdvzoFQ7-JUQQr3dqX2W1zMwv4yC0T4GP5o0Wko5Sn7c23r4KgviY4jYGQhxM8OZTjNIJfQMCg-iyI_1BE9b6zMat5UD-zYxg5JydWRm85_h9qDkKp_qhpFMuxc12JzXiHNtDTsnsVu8j-gpzSjJfSkTu24a6bC8GdUwzZplI6ZCUsW5R2FnA"
        }
    )

    prompt = f"is the chinese sentence '{sentence}' unfriendly, hostile, disrespectul, aggressive, misogynistic, harrassment (sexual or non-sexual), vulgar, insulting, or abusive？ assuming the recipient of this sentence has done nothing wrong. please answer the question using a single letter, if the answer is yes, use Y; if the answer if no, use N; do not add period"
    response = ""

    for data in chatbot.ask(prompt):
        response = data["message"]

    if response[0] == "Y":
        return True
    else:
        return False


def display_msg(msg):
    width = len(msg)
    print("")
    print("." * (MAX_MSG_LEN - width) + msg)


def display_session_cookies(s):
    display_msg("print cookies")
    for x in s.cookies:
        print(x)


def genct0():
    """
    Generated the ct0 cookie value.
    Uses the method used in the js file of the website.
    """

    random_value = secrets.token_bytes(32)

    s = ""
    for c in random_value:
        s += hex(c)[-1]

    return s


def oracle(user):
    default_rule = "(followers_count < 5) or (days < 180)"
    rule_eval_vars = {
        "followers_count": user.followers_count,
        "following_count": user.following_count,
        "tweet_count": user.tweet_count,
        "days": user.days,
    }

    try:
        result = rule_eval(filtering_rule, rule_eval_vars)
    except Exception as e:
        print(e)
        result = rule_eval(default_rule, rule_eval_vars)

    if result:
        print(f"ORACLE TIME!: id {user.user_id} name {user.screen_name} followers_count {user.followers_count} is bad")
        return True
    else:
        print(f"ORACLE TIME!: id {user.user_id} name {user.screen_name} is good")
        return False


@dataclasses.dataclass
class TwitterUserProfile:
    user_id: int
    screen_name: str
    created_at: str = dataclasses.field(default=None)
    following_count: int = dataclasses.field(default=None)
    followers_count: int = dataclasses.field(default=None)
    tweet_count: int = dataclasses.field(default=None)
    days: int = dataclasses.field(init=False, default=None)
    name: str = dataclasses.field(default="", metadata={"keyword_only": True})

    def __post_init__(self):
        if self.created_at is not None:
            current_time = datetime.now(timezone.utc)
            created_time = datetime.strptime(self.created_at, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc).astimezone(tz.gettz())
            time_diff = current_time - created_time
            self.days = time_diff.days


class TwitterLoginBot:
    get_token_payload = {
        "input_flow_data": {
            "flow_context": {
                "debug_overrides": {},
                "start_location": {"location": "manual_link"},
            }
        },
        "subtask_versions": {
            "action_list": 2,
            "alert_dialog": 1,
            "app_download_cta": 1,
            "check_logged_in_account": 1,
            "choice_selection": 3,
            "contacts_live_sync_permission_prompt": 0,
            "cta": 7,
            "email_verification": 2,
            "end_flow": 1,
            "enter_date": 1,
            "enter_email": 2,
            "enter_password": 5,
            "enter_phone": 2,
            "enter_recaptcha": 1,
            "enter_text": 5,
            "enter_username": 2,
            "generic_urt": 3,
            "in_app_notification": 1,
            "interest_picker": 3,
            "js_instrumentation": 1,
            "menu_dialog": 1,
            "notifications_permission_prompt": 2,
            "open_account": 2,
            "open_home_timeline": 1,
            "open_link": 1,
            "phone_verification": 4,
            "privacy_options": 1,
            "security_key": 3,
            "select_avatar": 4,
            "select_banner": 2,
            "settings_list": 7,
            "show_code": 1,
            "sign_up": 2,
            "sign_up_review": 4,
            "tweet_selection_urt": 1,
            "update_users": 1,
            "upload_media": 1,
            "user_recommendations_list": 4,
            "user_recommendations_urt": 1,
            "wait_spinner": 3,
            "web_modal": 1,
        },
    }

    get_sso_payload = {
        "flow_token": "g;167658632144249788:-1676586337028:ZJlPGfGY6fmt0YNIvwX5MhR5:0",
        "subtask_inputs": [
            {
                "subtask_id": "LoginJsInstrumentationSubtask",
                "js_instrumentation": {
                    "response": '{"rf":{"ae0c387278259a55d975ad389656c366bb247af661b87720a61ef1f00415a074":-1,"a08bdec063bd39221c4a9ed88833e66ed219aa1b1ffffbb689c7e878b77ed9c5":170,"a406e976cde22b2559c171f75fdb53d08cdec1b36eca8a157a8f8d535e5c4cfa":-12,"ec40d46fc7ad9581fc9c23c52181d7a1bb69fa94278a883ed01a381b4a0fe4d7":224},"s":"1pN0NCz6xs95SmhDHPdYrjG_zpdLJkzjMO8oTRG2VzM6oiyEuGIZFpGKUDLlNdVqJwMOIqLTOvnRQI860XuhPuft1-jMyHl_2rJGwyXKl2gcIP9lulFs39K9uRdaVfZK6UDmC_fWtbqJpiUt5DapQNK0T6wwq0PIAZG28cXYTveoiBZBJz3e3_fzUJYbSuYWZviw9W_M_AE3PAtFvF2294NwFENJ6n3DkNi-yaBVYq9nOeTieVGSiw_TdxnDGmd76yimmLpfD1yJFVDA1Z2WRy0ytCCzWjWck0MJuq1cBc1JpV9Jhjk_sPqqlKQiiG2pdbR5NP4fSN-AIa1luCSywwAAAYZcVUO7"}',
                    "link": "next_link",
                },
            }
        ],
    }

    enter_email_payload = {
        "flow_token": "g;167658632144249788:-1676586337028:ZJlPGfGY6fmt0YNIvwX5MhR5:1",
        "subtask_inputs": [
            {
                "subtask_id": "LoginEnterUserIdentifierSSO",
                "settings_list": {
                    "setting_responses": [
                        {
                            "key": "user_identifier",
                            "response_data": {"text_data": {"result": EMAIL}},
                        }
                    ],
                    "link": "next_link",
                },
            }
        ],
    }

    enter_alternative_id_payload = {
        "flow_token": "g;167669570499095475:-1676695708216:wfmlDaSgvN5ydOS4EI5oJvr6:7",
        "subtask_inputs": [
            {
                "subtask_id": "LoginEnterAlternateIdentifierSubtask",
                "enter_text": {"text": SCREENNAME, "link": "next_link"},
            }
        ],
    }

    enter_password_payload = {
        "flow_token": "g;167658632144249788:-1676586337028:ZJlPGfGY6fmt0YNIvwX5MhR5:8",
        "subtask_inputs": [
            {
                "subtask_id": "LoginEnterPassword",
                "enter_password": {"password": PASSWORD, "link": "next_link"},
            }
        ],
    }

    account_duplication_check_payload = {
        "flow_token": "g;167658632144249788:-1676586337028:ZJlPGfGY6fmt0YNIvwX5MhR5:11",
        "subtask_inputs": [
            {
                "subtask_id": "AccountDuplicationCheck",
                "check_logged_in_account": {"link": "AccountDuplicationCheck_false"},
            }
        ],
    }

    get_full_ct0_payload = {
        "flow_token": "g;167658632144249788:-1676586337028:ZJlPGfGY6fmt0YNIvwX5MhR5:17",
        "subtask_inputs": [],
    }

    # may be useful in the future if the mapping if subject to change
    tasks = {
        0: "LoginJsInstrumentationSubtask",
        1: "LoginEnterUserIdentifierSSO",
        7: "LoginEnterAlternateIdentifierSubtask",
        8: "LoginEnterPassword",
        11: "AccountDuplicationCheck",
        17: "LoginSuccessSubtask",
    }

    def __init__(self):
        self._headers = {
            "Host": "api.twitter.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:109.0) Gecko/20100101 Firefox/109.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://twitter.com/",
            # "x-twitter-polling": "true",
            # "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": "en",
            "x-twitter-active-user": "yes",
            "Origin": "https://twitter.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "Connection": "keep-alive",
            "TE": "trailers",
        }

        self._session = requests.Session()

        # get the flow_token
        self.get_login_flow_token()

        while int(self.login_flow_token.split(":")[-1]) != 17:
            self.do_task()

        # one more time to get longer ct0
        display_msg("update to full ct0")
        self.do_task()

        # save the cookies for reuse
        self.save_cookies()

        print("")

        """    
        display_msg("test login status")
        url = TwitterBot.urls["block_url"]
        block_form = {"user_id": str(44196397)}
        r = self._session.post("https://api.twitter.com/1.1/blocks/create.json", headers=self._headers, params=block_form)
        if r.status_code == 200:
            print("successfully sent block post!")
        display_msg("block")
        print(r.status_code, r.text)
        """

    def customize_headers(self, case):
        if case == "get_js":
            self._headers["Sec-Fetch-Mode"] = "no-cors"
            self._headers["Sec-Fetch-Dest"] = "script"
            self._headers["Referer"] = "https://twitter.com/i/flow/login"
            self._headers["Host"] = "twitter.com"
            del self._headers["Origin"]

        if case == "get_sso":
            self._headers["Sec-Fetch-Mode"] = "cors"
            self._headers["Sec-Fetch-Dest"] = "empty"
            self._headers["Referer"] = "https://twitter.com/"
            self._headers["Host"] = "api.twitter.com"
            self._headers["Origin"] = "https://twitter.com"
            self._headers["Content-Type"] = "application/json"

    def save_cookies(self):
        # convert the cookiejar object to a dictionary; among duplicated entries, only the latest entry is kept
        cookie_dict = requests.utils.dict_from_cookiejar(self._session.cookies)
        # convert the dictionary back to a cookiejar object
        unique_cookiejar = requests.utils.cookiejar_from_dict(cookie_dict)

        self._session.cookies = unique_cookiejar

        # make it compatible with selenium cookie
        full_cookie = [
            {
                "name": x.name,
                "value": x.value,
                "secure": x.secure,
                "domain": ".twitter.com",
                "path": x.path,
            }
            for x in self._session.cookies
        ]

        pickle.dump(full_cookie, open(COOKIE_PATH, "wb"))

    def prepare_next_login_task(self, r):
        print(r.status_code)
        j = r.json()
        self.login_flow_token = j["flow_token"]
        subtasks = j["subtasks"]

        print("flow_token:", self.login_flow_token)

        for s in subtasks:
            print(s["subtask_id"])

    def do_task(self):
        task = int(self.login_flow_token.split(":")[-1])

        # establish session and prepare for enter email
        if task == 0:
            self.customize_headers("get_js")
            r = self._session.get("https://twitter.com/i/js_inst?c_name=ui_metrics", headers=self._headers)

            # should have _twitter_sess cookie now
            # display_session_cookies(self._session)

            display_msg("ui_metrics.txt")

            match = re.search(r"{'rf':{'.+};};", r.text)
            m = match.group(0)

            matches = re.finditer(r":([a-f0-9]{64})", m)
            for match in matches:
                found_string = match.group(1)
                new_string = ":" + str(int(random.uniform(-50, 200)))
                m = m.replace(":" + found_string, new_string)

            # get rid of ending ;};
            m = m[:-3]
            double_quoted_m = m.replace("'", '"')
            TwitterLoginBot.get_sso_payload["subtask_inputs"][0]["js_instrumentation"]["response"] = double_quoted_m

            self.customize_headers("get_sso")
            TwitterLoginBot.get_sso_payload["flow_token"] = self.login_flow_token

            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(TwitterLoginBot.get_sso_payload),
            )

        # enter email
        if task == 1:
            display_msg("enter email")
            TwitterLoginBot.enter_email_payload["flow_token"] = self.login_flow_token

            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(TwitterLoginBot.enter_email_payload),
            )

        # enter alternative identifier
        if task == 7:
            display_msg("enter alternative identifier")
            TwitterLoginBot.enter_alternative_id_payload["flow_token"] = self.login_flow_token
            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(TwitterLoginBot.enter_alternative_id_payload),
            )

        # enter password
        if task == 8:
            display_msg("enter password")
            TwitterLoginBot.enter_password_payload["flow_token"] = self.login_flow_token
            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(TwitterLoginBot.enter_password_payload),
            )

        # duplication check
        if task == 11:
            display_msg("account duplication check")
            TwitterLoginBot.account_duplication_check_payload["flow_token"] = self.login_flow_token
            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(TwitterLoginBot.account_duplication_check_payload),
            )

        if task == 17:
            TwitterLoginBot.get_full_ct0_payload["flow_token"] = self.login_flow_token
            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(TwitterLoginBot.get_full_ct0_payload),
            )

        self.prepare_next_login_task(r)

    def get_login_flow_token(self):
        r = self._session.get("https://twitter.com/i/flow/login")

        # the gt value is not directly visible in the returned cookies; it's hidden in the returned html file's script
        match = re.search(
            r'document\.cookie = decodeURIComponent\("gt=(\d+); Max-Age=10800; Domain=\.twitter\.com; Path=/; Secure"\);',
            r.text,
        )
        self._session.cookies.set("gt", match.group(1))

        # the ct0 value is just a random 32-character string generated from random bytes at client side
        self._session.cookies.set("ct0", genct0())

        # set the headers accordingly
        self._headers["x-csrf-token"] = self._session.cookies.get("ct0")
        self._headers["x-guest-token"] = str(self._session.cookies.get("gt"))

        # display_session_cookies(self._session)

        r = self._session.post(
            "https://api.twitter.com/1.1/onboarding/task.json?flow_name=login",
            headers=self._headers,
            params=TwitterLoginBot.get_token_payload,
        )

        self.prepare_next_login_task(r)

        # att is set by the response cookie


class TwitterBot:
    urls = {
        "badge_count_url": "https://api.twitter.com/2/badge_count/badge_count.json",
        "notification_all_url": "https://api.twitter.com/2/notifications/all.json",
        "jot_url": "https://api.twitter.com/1.1/jot/client_event.json",
        "last_seen_cursor_url": "https://api.twitter.com/2/notifications/all/last_seen_cursor.json",
        "block_url": "https://api.twitter.com/1.1/blocks/create.json",
        "unblock_url": "https://api.twitter.com/1.1/blocks/destroy.json",
        # https://api.twitter.com/graphql/ViKvXirbgcKs6SfF5wZ30A/ would not work at all
        "retweeters_url": "https://twitter.com/i/api/graphql/ViKvXirbgcKs6SfF5wZ30A/Retweeters",
    }

    jot_form_success = {
        "keepalive": "false",
        "category": "perftown",
        "log": '[{"description":"rweb:urt:notifications:fetch_Top:success","product":"rweb","duration_ms":73},{"description":"rweb:urt:notifications:fetch_Top:format:success","product":"rweb","duration_ms":74}]',
    }

    badge_form = {"supports_ntab_urt": "1"}

    notification_all_form = {
        "include_profile_interstitial_type": "1",
        "include_blocking": "1",
        "include_blocked_by": "1",
        "include_followed_by": "1",
        "include_want_retweets": "1",
        "include_mute_edge": "1",
        "include_can_dm": "1",
        "include_can_media_tag": "1",
        "include_ext_has_nft_avatar": "1",
        "include_ext_is_blue_verified": "1",
        "include_ext_verified_type": "1",
        "skip_status": "1",
        "cards_platform": "Web-12",
        "include_cards": "1",
        "include_ext_alt_text": "true",
        "include_ext_limited_action_results": "false",
        "include_quote_count": "true",
        "include_reply_count": "1",
        "tweet_mode": "extended",
        "include_ext_collab_control": "true",
        "include_ext_views": "true",
        "include_entities": "true",
        "include_user_entities": "true",
        "include_ext_media_color": "true",
        "include_ext_media_availability": "true",
        "include_ext_sensitive_media_warning": "true",
        "include_ext_trusted_friends_metadata": "true",
        "send_error_codes": "true",
        "simple_quoted_tweet": "true",
        "count": "40",
        # timelineid:    AAAAABZfed0AAAABYinMQFMKJic AAAAABZfed0AAAABYinMQFgwhLg
        "cursor": "DAABDAABCgABAAAAABZfed0IAAIAAAABCAADYinMQAgABFMKJicACwACAAAAC0FZWlhveW1SNnNFCAADjyMIvwAA",
        "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,birdwatchPivot,enrichments,superFollowMetadata,unmentionInfo,editControl,collab_control,vibe",
    }

    def __init__(self):
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:109.0) Gecko/20100101 Firefox/109.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Host": "api.twitter.com",
            "Referer": "https://twitter.com/",
            "x-twitter-polling": "true",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": "en",
            "x-twitter-active-user": "yes",
            "x-csrf-token": "1fda97d345e0c46c2eb430eee5d916b3a4cb129ae6bb97f54a8bc279bff5b33b26a11ce36075550e911797aae312bb47365aa41ed205717c262310bcfd94746bca374a1c7f45ed0a214a389478d9590b",
            "Origin": "https://twitter.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "Connection": "keep-alive",
            "TE": "trailers",
        }

        self._session = requests.Session()

        try:
            self.load_cookies()
        except:
            # if the cookie does not exist
            traceback.print_exc()
            self.refresh_cookies()

        # display_session_cookies(self._session)

        # when disabled, will use the default cursor
        self.load_cursor()

        self.reporter = ReportHandler(self._headers, self._session)

    def set_selenium_cookies(self, cookies):
        for x in cookies:
            print(x)
            otherinfo = dict()
            if "secure" in x:
                otherinfo = {
                    "secure": x["secure"],
                    "domain": x["domain"],
                    "path": x["path"],
                }

            if "expiry" in x:
                otherinfo["expires"] = x["expiry"]
            self._session.cookies.set(x["name"], x["value"], **otherinfo)
        # make the header token consistent with the cookies
        self._headers["x-csrf-token"] = self._session.cookies.get("ct0")

    def load_cookies(self):
        cookies = pickle.load(open(COOKIE_PATH, "rb"))
        self.set_selenium_cookies(cookies)

    def refresh_cookies(self):
        try:
            b = TwitterLoginBot()
            self.load_cookies()
        except:
            b = SeleniumTwitterBot()
            # new cookie will be saved from selenium
            b.twitter_login_manual()

            self.set_selenium_cookies(b.driver.get_cookies())

    def get_badge_count(self):
        display_msg("get badge count")

        # display_session_cookies(self._session)
        badge_count_url = TwitterBot.urls["badge_count_url"]
        badge_form = TwitterBot.badge_form
        r = self._session.get(badge_count_url, headers=self._headers, params=badge_form)
        print(r.status_code, r.json())

    def update_local_cursor(self, val):
        TwitterBot.notification_all_form["cursor"] = val
        config_dict["latest_cursor"] = val

        save_yaml(config_dict, CONFIG_PATH, "w")

    def load_cursor(self):
        if len(config_dict["latest_cursor"]) > 0:
            TwitterBot.notification_all_form["cursor"] = config_dict["latest_cursor"]
        print("after loading cursor:", TwitterBot.notification_all_form["cursor"])

    def update_remote_cursor(self, val):
        url = TwitterBot.urls["last_seen_cursor_url"]
        cursor_form = {"cursor": val}
        r = self._session.post(url, headers=self._headers, params=cursor_form)
        print(r.status_code, r.text)

    def update_remote_latest_cursor(self):
        """
        Updates the top cursor value in the API, using self.latest_cursor.

        This function does not take any arguments and does not return a value.

        The badge will disappear after you refresh in a non-notification page
        """

        self.update_remote_cursor(TwitterBot.notification_all_form["cursor"])

    def block_user(self, user_id):
        url = TwitterBot.urls["block_url"]
        block_form = {"user_id": str(user_id)}
        r = self._session.post(url, headers=self._headers, params=block_form)
        if r.status_code == 200:
            print("successfully sent block post!")
        display_msg("block")
        print(r.status_code, r.text)

    def unblock_user(self, user_id):
        url = TwitterBot.urls["unblock_url"]
        unblock_form = {"user_id": str(user_id)}
        r = self._session.post(url, headers=self._headers, params=unblock_form)
        if r.status_code == 200:
            print("successfully sent unblock post!")
        display_msg("unblock")
        print(r.status_code, r.text)

    def report_profile(self, screen_name, option_name, user_id=None, context_msg=None):
        if option_name == "GovBot":
            # for reporting propaganda bots
            self.reporter.report_spam(screen_name, option_name, user_id=user_id, context_msg=context_msg)

    def report_propaganda_hashtag(self, hashtag, context_msg=None):
        import snscrape.modules.twitter as sntwitter

        x = sntwitter.TwitterHashtagScraper(hashtag)

        # report rate too high will make you black_listed
        count = 0

        # only report once
        abuser_list = {}

        for item in x.get_items():
            content = json.loads(item.json())
            screen_name = content["user"]["username"]

            if screen_name in abuser_list:
                continue

            user_id = content["user"]["id"]
            abuser_list[screen_name] = user_id
            print(count, screen_name, user_id)
            bot.report_profile(screen_name, "GovBot", user_id=user_id, context_msg=context_msg)

            count += 1

            # minimum sleep time to avoid triggering rate limit related errors
            sleep(8)

    def handle_users(self, users):
        """
        Examine users coming from the notifications one by one.
        Block bad users. Update the local block list.
        """

        # ignore user already in block_list or white_list
        sorted_users = {user_id: users[user_id] for user_id in users if (user_id not in block_list) and (user_id not in white_list)}

        for user_id in sorted_users:
            user = sorted_users[user_id]

            is_bad = oracle(user)

            if is_bad:
                # TODO: actually block the bad user

                block_list[user.user_id] = user.screen_name
                save_yaml(block_list, BLOCK_LIST_PATH, "w")

    def get_notifications(self):
        """
        Gets the new notifications from the API.

        Whenever there is new notification, or you perform operations like block/unblock, mute/unmute, you will get new stuff here.

        Updates latest_cursor using the top cursor fetched. After the update, if no new thing happens, then you will not get anything here.

        """
        url = TwitterBot.urls["notification_all_url"]
        notification_all_form = TwitterBot.notification_all_form
        r = self._session.get(url, headers=self._headers, params=notification_all_form)

        display_msg("notifications/all.json")
        print(r.status_code, r.headers["content-length"])

        result = r.json()

        display_msg("notifications/all.json")
        print("result keys:", result.keys())

        convo = set()
        tweets, notifications = [], []

        print("globalObjects keys:", result["globalObjects"].keys())

        logged_users = {}

        if "users" in result["globalObjects"]:
            users = result["globalObjects"]["users"]
            for x in users:
                user = users[x]
                p = TwitterUserProfile(
                    user["id"],
                    user["screen_name"],
                    user["created_at"],
                    user["friends_count"],
                    user["followers_count"],
                    user["statuses_count"],
                )
                print(dataclasses.asdict(p))
                logged_users[p.user_id] = p

        display_msg("globalObjects['tweets]")
        id_indexed_tweets = {}
        # all related tweets (being liked; being replied to; being quoted; other people's interaction with me)
        if "tweets" in result["globalObjects"]:
            tweets = result["globalObjects"]["tweets"]
            for x in tweets:
                tweet = tweets[x]
                id_indexed_tweets[int(tweet["id"])] = tweet
                print("convo id:", tweet["conversation_id"])
                convo.add(tweet["conversation_id"])
                print(tweet["user_id"], tweet["created_at"], tweet["full_text"])

        interacting_users = {}

        display_msg("globalObjects['notifications']")
        if "notifications" in result["globalObjects"]:
            notifications = result["globalObjects"]["notifications"]
            for x in notifications:
                notification = notifications[x]
                # print(x, notification["message"]["text"])

                for e in notification["message"]["entities"]:
                    entry_user_id = int(e["ref"]["user"]["id"])
                    # add the users appearing in notifications (do not include replies)
                    interacting_users[entry_user_id] = logged_users[entry_user_id]

        display_msg("timeline")
        print("TIMELINE ID", result["timeline"]["id"])
        instructions = result["timeline"]["instructions"]  # instructions is a list

        # print all keys
        print("instruction keys:", [x.keys() for x in instructions])

        # get entries
        for x in instructions:
            if "addEntries" in x:
                entries = x["addEntries"]["entries"]  # intries is a list

        # get cursor entries
        cursor_entries = [x for x in entries if "operation" in x["content"]]

        # entries that are not cursors
        non_cursor_entries = [x for x in entries if "operation" not in x["content"]]

        # includes like, retweet
        non_cursor_notification_entries = [x for x in non_cursor_entries if "notification" in x["content"]["item"]["content"]]
        # includes reply
        non_cursor_tweet_entries = [x for x in non_cursor_entries if "tweet" in x["content"]["item"]["content"]]

        display_msg("non_cursor_notification")
        # users_liked_your_tweet/user_liked_multiple_tweets/user_liked_tweets_about_you/generic_login_notification/users_retweeted_your_tweet
        for x in non_cursor_notification_entries:
            print(x["sortIndex"], x["content"]["item"]["clientEventInfo"]["element"])

        display_msg("non_cursor_tweets")
        # user_replied_to_your_tweet/user_quoted_your_tweet
        for x in non_cursor_tweet_entries:
            print(x["sortIndex"], x["content"]["item"]["clientEventInfo"]["element"])
            entry_user_id = id_indexed_tweets[int(x["content"]["item"]["content"]["tweet"]["id"])]["user_id"]
            # add the users replying to me
            interacting_users[entry_user_id] = logged_users[entry_user_id]

        display_msg("check users interacting with me")
        self.handle_users(interacting_users)

        print("")
        print("tweets VS non_cursor_entries", len(tweets), len(non_cursor_entries))
        print(
            "notifications VS non_cursor_notification",
            len(notifications),
            len(non_cursor_notification_entries),
        )
        print("number of convos", len(convo))

        display_msg("cursors")
        for x in cursor_entries:
            cursor = x["content"]["operation"]["cursor"]
            print(x["sortIndex"], cursor)
            if cursor["cursorType"] == "Top":
                self.latest_sortindex = x["sortIndex"]

                self.update_local_cursor(cursor["value"])
                # self.update_remote_latest_cursor()  # will cause the badge to disappear

    def get_retweeters(self, tweet_url):
        """
        Gets the list of visible (not locked) retweeters.
        Returns a list of TwitterUserProfile.
        """
        # needs to have the br decoding library installed for requests to handle br compressed results

        display_msg("get retweeters")

        headers = copy.deepcopy(self._headers)

        headers["Content-Type"] = "application/json"
        headers["Host"] = "twitter.com"

        url = TwitterBot.urls["retweeters_url"]

        form = {
            "variables": {
                "tweetId": 0,
                "count": 80,
                "includePromotedContent": True,
                "withSuperFollowsUserFields": True,
                "withDownvotePerspective": False,
                "withReactionsMetadata": False,
                "withReactionsPerspective": False,
                "withSuperFollowsTweetFields": True,
            },
            "features": {
                "responsive_web_twitter_blue_verified_badge_is_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": False,
                "verified_phone_label_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "tweetypie_unmention_optimization_enabled": True,
                "vibe_api_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "tweet_awards_web_tipping_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": False,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
                "interactive_text_enabled": True,
                "responsive_web_text_conversations_enabled": False,
                "responsive_web_enhance_cards_enabled": False,
            },
        }

        # set tweetId in form
        form["variables"]["tweetId"] = tweet_url.split("/")[-1]

        def get_cursor_and_users(response):
            entries = response["data"]["retweeters_timeline"]["timeline"]["instructions"][0]["entries"]
            users, bottom_cursor = [], ""

            for e in entries:
                if e["content"]["entryType"] == "TimelineTimelineItem":
                    if e["content"]["itemContent"]["user_results"]["result"]["__typename"] == "User":
                        user = e["content"]["itemContent"]["user_results"]["result"]["legacy"]

                        p = TwitterUserProfile(
                            int(e["entryId"].split("-")[1]),
                            user["screen_name"],
                            user["created_at"],
                            user["friends_count"],
                            user["followers_count"],
                            user["statuses_count"],
                            name=user["name"],
                        )
                        users.append(p)

                    else:
                        # otherwise the typename is UserUnavailable
                        print("cannot get user data", e["entryId"], e["content"]["itemContent"]["user_results"]["result"])

                if e["content"]["entryType"] == "TimelineTimelineCursor":
                    if e["content"]["cursorType"] == "Bottom":
                        bottom_cursor = e["content"]["value"]
            return users, bottom_cursor

        users_collection = []

        while True:
            encoded_params = urlencode({k: json.dumps(form[k], separators=(",", ":")) for k in form})
            r = self._session.get(url, headers=headers, params=encoded_params)
            response = r.json()

            users, bottom_cursor = get_cursor_and_users(response)
            form["variables"]["cursor"] = bottom_cursor
            users_collection = users_collection + users
            print(len(users_collection), bottom_cursor)

            # loop until no new data could be obtained
            if len(users) == 0:
                break

        return users_collection


if __name__ == "__main__":
    bot = TwitterBot()
    # bot.refresh_cookies()
    # bot.update_local_cursor("DAABDAABCgABAAAAABZfed0IAAIAAAABCAADYinMQAgABFgwhLgACwACAAAAC0FZWlliaFJQdHpNCAADjyMIvwAA")
    try:
        # use a small query to test the validity of cookies
        bot.get_badge_count()
    except:
        bot.refresh_cookies()

    bot.get_notifications()

    for x in bot.get_retweeters("https://twitter.com/SpokespersonCHN/status/1630193968993681410"):
        match = re.search(r"[a-zA-Z]{6,8}[0-9]{8}", x.screen_name)

        if match:
            print(x.screen_name, x.name, x.tweet_count / x.days)

    # bot.report_profile("KarenLoomis17", "GovBot", user_id = 1605874400816816128)

    """
    bot.report_propaganda_hashtag(
        "媒体污蔑中国在英设有秘密警察局",
        context_msg="this account is part of a coordinated campaingn from chinese government, it uses hashtags that are exclusively used by chinese state sponsored bots",
    )
    """

    print(chatgpt_moderation("女的生来就是做家务的"))

    # bot.block_user('44196397') #https://twitter.com/elonmusk (for test)
    # print(TwitterBot.notification_all_form["cursor"], bot.latest_sortindex)
