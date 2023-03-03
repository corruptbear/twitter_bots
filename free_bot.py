#!/usr/bin/env python3.9
import os
import sys
import traceback

import requests
from urllib.parse import urlencode, quote

import dataclasses

from datetime import datetime, timezone
from dateutil import tz

import yaml
import json

import pickle
import random
import re
import secrets
import copy

from selenium_bot import SeleniumTwitterBot, save_yaml, load_yaml
from rule_parser import rule_eval
from report import ReportHandler

import snscrape.modules.twitter as sntwitter
from revChatGPT.V1 import Chatbot

from collections import abc
import keyword

class TwitterJSON:
    def __new__(cls, arg): 
        if isinstance(arg, abc.Mapping):
            return super().__new__(cls) 
        elif isinstance(arg, abc.MutableSequence):
            return [cls(item) for item in arg]
        else:
            return arg

    def __init__(self, mapping):
        self.__data = {}
        for key, value in mapping.items():
            if keyword.iskeyword(key):
                key += '_'
            self.__data[key] = value

    def __getattr__(self, name):
        try:
            #convert the mangled __typename back to original value
            if '__typename' in name:
                name = '__typename'
            return getattr(self.__data, name)
        except AttributeError:
            if name in self.__data:
                return TwitterJSON(self.__data[name])
            return None
            
    #still supports subscription, just in case        
    def __getitem__(self, name):
        return self.__getattr__(name)

    def __dir__(self):
        return self.__data.keys()
           
    def __repr__(self):
        return str(self.__data)
        
    def __len__(self):
        return len(self.__data)
        
    def __contains__(self,key):
        """
        called when `in` operation is used.
        """
        return key in self.__data
        
    def __iter__(self):
        return (key for key in self.__data)
              
    def values(self):
        return (TwitterJSON(x) for x in self.__data.values())
        

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
    print(f"\n{msg:.>50}")


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


def oracle(user, filtering_rule):
    default_rule = "(followers_count < 5) or (days < 180)"
    rule_eval_vars = {
        "followers_count": user.followers_count,
        "following_count": user.following_count,
        "tweet_count": user.tweet_count,
        "days": user.days_since_registration,
    }

    try:
        result = rule_eval(filtering_rule, rule_eval_vars)
    except Exception as e:
        print(e)
        result = rule_eval(default_rule, rule_eval_vars)

    return result


@dataclasses.dataclass
class TwitterUserProfile:
    user_id: int
    screen_name: str
    created_at: str = dataclasses.field(default=None)
    following_count: int = dataclasses.field(default=None)
    followers_count: int = dataclasses.field(default=None)
    tweet_count: int = dataclasses.field(default=None)
    media_count: int = dataclasses.field(default=None)
    favourites_count: int = dataclasses.field(default=None)
    days_since_registration: int = dataclasses.field(init=False, default=None)
    name: str = dataclasses.field(default=None, metadata={"keyword_only": True})

    def __post_init__(self):
        if self.created_at is not None:
            current_time = datetime.now(timezone.utc)
            created_time = datetime.strptime(self.created_at, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc).astimezone(tz.gettz())
            time_diff = current_time - created_time
            self.days_since_registration = time_diff.days


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

    def __init__(self, cookie_path=None, config_dict=None):
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

        self._cookie_path = cookie_path
        self._config_dict = config_dict
        self.load_config()

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

    def load_config(self):
        EMAIL = self._config_dict["login"]["email"]
        PASSWORD = self._config_dict["login"]["password"]
        SCREENNAME = self._config_dict["login"]["screenname"]
        PHONENUMBER = self._config_dict["login"]["phonenumber"]

        self.enter_email_payload = {
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

        self.enter_alternative_id_payload = {
            "flow_token": "g;167669570499095475:-1676695708216:wfmlDaSgvN5ydOS4EI5oJvr6:7",
            "subtask_inputs": [
                {
                    "subtask_id": "LoginEnterAlternateIdentifierSubtask",
                    "enter_text": {"text": SCREENNAME, "link": "next_link"},
                }
            ],
        }

        self.enter_password_payload = {
            "flow_token": "g;167658632144249788:-1676586337028:ZJlPGfGY6fmt0YNIvwX5MhR5:8",
            "subtask_inputs": [
                {
                    "subtask_id": "LoginEnterPassword",
                    "enter_password": {"password": PASSWORD, "link": "next_link"},
                }
            ],
        }

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

        pickle.dump(full_cookie, open(self._cookie_path, "wb"))
        display_msg("cookies from requests saved")

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
            self.enter_email_payload["flow_token"] = self.login_flow_token

            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(self.enter_email_payload),
            )

        # enter alternative identifier
        if task == 7:
            display_msg("enter alternative identifier")
            self.enter_alternative_id_payload["flow_token"] = self.login_flow_token
            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(self.enter_alternative_id_payload),
            )

        # enter password
        if task == 8:
            display_msg("enter password")
            self.enter_password_payload["flow_token"] = self.login_flow_token
            r = self._session.post(
                "https://api.twitter.com/1.1/onboarding/task.json",
                headers=self._headers,
                data=json.dumps(self.enter_password_payload),
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

        try:
            # the gt value is not directly visible in the returned cookies; it's hidden in the returned html file's script
            match = re.search(
                r'document\.cookie = decodeURIComponent\("gt=(\d+); Max-Age=10800; Domain=\.twitter\.com; Path=/; Secure"\);',
                r.text,
            )
            self._session.cookies.set("gt", match.group(1))
            self._headers["x-guest-token"] = str(self._session.cookies.get("gt"))

        except:
            display_msg("cannot find guest token from the webpage")
            r = self._session.post("https://api.twitter.com/1.1/guest/activate.json", data=b"", headers=self._headers)
            if r.status_code == 200:
                self._headers["x-guest-token"] = r.json()["guest_token"]
                display_msg("got guest token from the endpoint")

        # the ct0 value is just a random 32-character string generated from random bytes at client side
        self._session.cookies.set("ct0", genct0())

        # set the headers accordingly
        self._headers["x-csrf-token"] = self._session.cookies.get("ct0")

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
        "retweeters_url": "https://twitter.com/i/api/graphql/ViKvXirbgcKs6SfF5wZ30A/Retweeters",
        "followers_url": "https://twitter.com/i/api/graphql/utPIvA97eaEvxfra_PQz_A/Followers",
        "following_url": "https://twitter.com/i/api/graphql/AmvGuDw_fxEbJtEXie4OkA/Following",
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
        "cursor": "DAABDAABCgABAAAAABZfed0IAAIAAAABCAADYinMQAgABFMKJicACwACAAAAC0FZWlhveW1SNnNFCAADjyMIvwAA",
        "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,birdwatchPivot,enrichments,superFollowMetadata,unmentionInfo,editControl,collab_control,vibe",
    }

    following_followers_form = {
        "variables": {
            "userId": None,
            "count": 100,
            "includePromotedContent": False,
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
            "longform_notetweets_richtext_consumption_enabled": False,
            "responsive_web_enhance_cards_enabled": False,
        },
    }

    def __init__(self, cookie_path=None, config_path=None, white_list_path=None, block_list_path=None, filtering_rule=None):
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:110.0) Gecko/20100101 Firefox/110.0",
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

        self._cookie_path = cookie_path
        self._config_path = config_path
        self._config_dict = load_yaml(config_path)

        self._block_list_path = block_list_path
        if block_list_path:
            self._block_list = load_yaml(self._block_list_path)
        else:
            self._block_list = []

        self._white_list_path = white_list_path
        if white_list_path:
            self._white_list = load_yaml(self._white_list_path)
        else:
            self._white_list = []

        self._filtering_rule = filtering_rule

        try:
            self._load_cookies()
        except:
            # if the cookie does not exist
            traceback.print_exc()
            self.refresh_cookies()

        # display_session_cookies(self._session)

        # when disabled, will use the default cursor
        self.load_cursor()

        self.reporter = ReportHandler(self._headers, self._session)

    def _set_selenium_cookies(self, cookies):
        display_msg("setting cookies from selenium")
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

    def _load_cookies(self):
        display_msg("loading cookies")
        cookies = pickle.load(open(self._cookie_path, "rb"))
        self._set_selenium_cookies(cookies)

    def refresh_cookies(self):
        """
        Try to get the cookies through requests only TwitterLoginBot first.
        If it does not work, use SeleniumTwitterBot to get the cookies
        """
        try:
            display_msg("trying using requests to get cookies")
            b = TwitterLoginBot(cookie_path=self._cookie_path, config_dict=self._config_dict)
            self._load_cookies()
        except:
            display_msg("trying using selenium to get cookies")
            b = SeleniumTwitterBot()
            # new cookie will be saved from selenium
            b.twitter_login()
            b.save_cookies()

            self._set_selenium_cookies(b.driver.get_cookies())

    def get_badge_count(self):
        display_msg("get badge count")

        # display_session_cookies(self._session)
        badge_count_url = TwitterBot.urls["badge_count_url"]
        badge_form = TwitterBot.badge_form
        r = self._session.get(badge_count_url, headers=self._headers, params=badge_form)
        print(r.status_code, r.json())

    def update_local_cursor(self, val):
        TwitterBot.notification_all_form["cursor"] = val
        self._config_dict["latest_cursor"] = val

        save_yaml(self._config_dict, self._config_path, "w")

    def load_cursor(self):
        if len(self._config_dict["latest_cursor"]) > 0:
            TwitterBot.notification_all_form["cursor"] = self._config_dict["latest_cursor"]
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

    def handle_users(self, users):
        """
        Examine users coming from the notifications one by one.
        Block bad users. Update the local block list.
        """

        # ignore user already in block_list or white_list
        sorted_users = {user_id: users[user_id] for user_id in users if (user_id not in self._block_list) and (user_id not in self._white_list)}

        for user_id in sorted_users:
            user = sorted_users[user_id]

            is_bad = oracle(user, self._filtering_rule)

            conclusion_str = "bad" if is_bad else "good"

            if is_bad:
                self.block_user(user_id)

                self._block_list[user.user_id] = user.screen_name
                save_yaml(self._block_list, self._block_list_path, "w")

            print(f"ORACLE TIME!: id {user.user_id:<25} name {user.screen_name:<20} followers_count {user.followers_count:<10} is {conclusion_str}")

    def get_notifications(self):
        """
        Gets the recent notifications from the API.

        Whenever there is new notification, or you perform operations like block/unblock, mute/unmute, you will get new stuff here.

        Updates latest_cursor using the top cursor fetched. After the update, if no new thing happens, then you will not get anything here.

        """
        url = TwitterBot.urls["notification_all_url"]
        notification_all_form = TwitterBot.notification_all_form
        r = self._session.get(url, headers=self._headers, params=notification_all_form)

        display_msg("notifications/all.json")
        print(f"status_code: {r.status_code}, length: {r.headers['content-length']}")

        result = r.json()
        result = TwitterJSON(result)

        print("result keys:", result.keys())

        convo = set()
        tweets, notifications = [], []

        print("globalObjects keys:", result.globalObjects.keys(), "\n")

        logged_users = {}

        if result.globalObjects.users:
            users = result.globalObjects.users   
            #annoying: cannot use variable in dot attribute getter      
            for user in users.values():
                p = TwitterUserProfile(
                    user.id,
                    user.screen_name,
                    created_at = user.created_at,
                    following_count = user.friends_count,
                    followers_count = user.followers_count,
                    tweet_count = user.statuses_count,
                    media_count = user.media_count,
                    favourites_count = user.favourites_count,
                    name=user.name,
                )
                print(dataclasses.asdict(p))
                logged_users[p.user_id] = p
                
                #logged_users[user.id] = user #need to modify oracle

        display_msg("globalObjects['tweets]")
        id_indexed_tweets = {}
        # all related tweets (being liked; being replied to; being quoted; other people's interaction with me)
        if result.globalObjects.tweets:
            tweets = result.globalObjects.tweets
            for tweet in tweets.values():
                id_indexed_tweets[int(tweet.id)] = tweet
                print("convo id:", tweet.conversation_id)
                convo.add(tweet.conversation_id)
                print(tweet.user_id, tweet.created_at, tweet.full_text)

        interacting_users = {}

        display_msg("globalObjects['notifications']")
        if result.globalObjects.notifications:
            notifications = result.globalObjects.notifications
            for notification in notifications.values():
                #print(notification.message.text)
                for e in notification.message.entities:
                    entry_user_id = int(e.ref.user.id)
                    # add the users appearing in notifications (do not include replies)
                    interacting_users[entry_user_id] = logged_users[entry_user_id]

        display_msg("timeline")
        print("TIMELINE ID", result.timeline.id)
        instructions = result.timeline.instructions  # instructions is a list

        # print all keys
        print("instruction keys:", [x.keys() for x in instructions])

        # get entries
        for x in instructions:
            if x.addEntries:
                entries = x.addEntries.entries  # intries is a list

        # get cursor entries
        cursor_entries = [x for x in entries if x.content.operation]
        # entries that are not cursors
        non_cursor_entries = [x for x in entries if not x.content.operation]

        # includes like, retweet, other misc
        non_cursor_notification_entries = [x for x in non_cursor_entries if x.content.item.content.notification]
        # includes reply, quoted retweet
        non_cursor_tweet_entries = [x for x in non_cursor_entries if x.content.item.content.tweet]

        display_msg("timeline: non_cursor_notification")
        # users_liked_your_tweet/user_liked_multiple_tweets/user_liked_tweets_about_you/generic_login_notification/users_retweeted_your_tweet
        for x in non_cursor_notification_entries:
            print(x.sortIndex, x.content.item.clientEventInfo.element)

        display_msg("timeline: non_cursor_tweets")
        # user_replied_to_your_tweet/user_quoted_your_tweet
        for x in non_cursor_tweet_entries:
            print(x.sortIndex, x.content.item.clientEventInfo.element)
            entry_user_id = id_indexed_tweets[int(x.content.item.content.tweet.id)].user_id
            # add the users replying to me
            interacting_users[entry_user_id] = logged_users[entry_user_id]

        display_msg("check users interacting with me")
        self.handle_users(interacting_users)

        print("\ntweets VS non_cursor_entries", len(tweets), len(non_cursor_entries))
        print(
            "notifications VS non_cursor_notification",
            len(notifications),
            len(non_cursor_notification_entries),
        )
        print("number of convos", len(convo))

        display_msg("cursors")
        for x in cursor_entries:
            cursor = x.content.operation.cursor
            print(x.sortIndex, cursor)
            if cursor.cursorType == "Top":
                self.latest_sortindex = x.sortIndex

                self.update_local_cursor(cursor.value)
                #self.update_remote_latest_cursor()  # will cause the badge to disappear
                    
    def _cursor_from_entries(self,entries):
        for e in entries[-2:]:
            content = e.content
            if content.entryType == "TimelineTimelineCursor":
                if content.cursorType == "Bottom":
                    return content.value
                    
    def _users_from_entries(self, entries):
        for e in entries:
            content = e.content
            if content.entryType == "TimelineTimelineItem":
                r=content.itemContent.user_results.result
      
                if content.itemContent.user_results.result._TwitterBot__typename == "User":
                    
                    user = content.itemContent.user_results.result.legacy

                    p = TwitterUserProfile(
                        int(e.entryId.split("-")[1]),
                        user.screen_name,
                        created_at = user.created_at,
                        following_count = user.friends_count,
                        followers_count = user.followers_count,
                        tweet_count = user.statuses_count,
                        media_count = user.media_count,
                        favourites_count = user.favourites_count,
                        name=user.name,
                    )

                    yield p

                else:
                    # otherwise the typename is UserUnavailable
                    print("cannot get user data", e.entryId)
        

    def _json_headers(self):
        headers = copy.deepcopy(self._headers)
        headers["Content-Type"] = "application/json"
        headers["Host"] = "twitter.com"

        return headers

    def _navigate_graphql_entries(self, url, headers, form):
        while True:
            encoded_params = urlencode({k: json.dumps(form[k], separators=(",", ":")) for k in form})
            r = self._session.get(url, headers=headers, params=encoded_params)

            response = r.json()
            response = TwitterJSON(response)
            
            data = response.data
            
            if  data.retweeters_timeline:
                instructions = data.retweeters_timeline.timeline.instructions
            else:
                instructions = data.user.result.timeline.timeline.instructions         
            
            entries = [x for x in instructions if x.type == "TimelineAddEntries"][0].entries
            
            if len(entries)<=2:
                break
                
            yield entries
            
            bottom_cursor = self._d_cursor_from_entries(entries)
            form["variables"]["cursor"] = bottom_cursor

    def id_from_screen_name(self, screen_name):
        x = sntwitter.TwitterUserScraper(screen_name)
        userdata = x._get_entity()
        return userdata.id

    def get_following(self, user_id):
        """
        Gets the list of following.
        Returns a list of TwitterUserProfile.
        """
        try:
            int(user_id)
        except:
            user_id = self.id_from_screen_name(user_id)

        display_msg("get following")

        headers = self._json_headers()

        url = TwitterBot.urls["following_url"]

        form = copy.deepcopy(TwitterBot.following_followers_form)

        # set userID in form
        form["variables"]["userId"] = str(user_id)

        for entries in self._navigate_graphql_entries(url, headers, form):
            yield from self._users_from_entries(entries)

    def get_followers(self, user_id):
        """
        Gets the list of followers.
        Returns a list of TwitterUserProfile.
        """
        try:
            int(user_id)
        except:
            user_id = self.id_from_screen_name(user_id)

        display_msg("get followers")

        headers = self._json_headers()

        url = TwitterBot.urls["followers_url"]

        form = copy.deepcopy(TwitterBot.following_followers_form)

        # set userID in form
        form["variables"]["userId"] = str(user_id)

        for entries in self._navigate_graphql_entries(url, headers, form):
            yield from self._users_from_entries(entries)

    def get_retweeters(self, tweet_url):
        """
        Gets the list of visible (not locked) retweeters.
        Returns a list of TwitterUserProfile.
        """
        # needs to have the br decoding library installed for requests to handle br compressed results

        display_msg("get retweeters")

        headers = self._json_headers()

        url = TwitterBot.urls["retweeters_url"]

        form = copy.deepcopy(TwitterBot.following_followers_form)
        del form["variables"]["userId"]
        # del form["features"]["longform_notetweets_richtext_consumption_enabled"]

        # set tweetId in form
        form["variables"]["tweetId"] = tweet_url.split("/")[-1]

        for entries in self._navigate_graphql_entries(url, headers, form):
            yield from self._users_from_entries(entries)


if __name__ == "__main__":
    pwd = os.path.dirname(os.path.realpath(__file__))

    COOKIE_PATH = os.path.join(pwd, "sl_cookies.pkl")
    CONFIG_PATH = os.path.join(pwd, "apifree.yaml")

    WHITE_LIST_PATH = os.path.join(pwd, "white_list.yaml")
    BLOCK_LIST_PATH = os.path.join(pwd, "block_list.yaml")
    API_CONF_PATH = os.path.join(pwd, "conf.yaml")

    filtering_rule = load_yaml(API_CONF_PATH)["filtering_rule"]

    bot = TwitterBot(
        cookie_path=COOKIE_PATH,
        config_path=CONFIG_PATH,
        white_list_path=WHITE_LIST_PATH,
        block_list_path=BLOCK_LIST_PATH,
        filtering_rule=filtering_rule,
    )

    bot.update_local_cursor("DAABDAABCgABAAAAABZfed0IAAIAAAABCAADYinMQAgABFgwhLgACwACAAAAC0FZWlliaFJQdHpNCAADjyMIvwAA")
    try:
        # use a small query to test the validity of cookies
        bot.get_badge_count()
    except:
        bot.refresh_cookies()

    bot.get_notifications()

    count = 0
    # bot.get_retweeters("https://twitter.com/Anaimiya/status/1628281803407790080")
    # bot.get_followers(44196397)
    for x in bot.get_followers(44196397):
        count += 1
        # if count % 100 == 0:
        #    print(count)
        # match = re.search(r"[a-zA-Z]{6,8}[0-9]{8}", x.screen_name)
        if "us" in x.name or True:
            print(
                f"{x.screen_name:<16} following: {x.following_count:>9} follower: {x.followers_count:>9} media: {x.media_count:>8} tweet_per_day: {x.tweet_count / (x.days_since_registration + 0.05):>8.4f}"
            )

        if count == 10:
            break

    x = sntwitter.TwitterUserScraper("rapist86009197")
    count = 0
    for item in x.get_items():
        count+=1
        content = json.loads(item.json())
        print(chatgpt_moderation(content['rawContent']))
    print(count)
    #bot.reporter.report_user("KarenLoomis17", "GovBot", user_id = 1605874400816816128)
    #bot.reporter.report_user("rapist86009197","SexualHarassment", user_id = 1631332912120438796,  context_msg = "this person has been harrasing me for months. most of its previous accounts are suspended, this is the latest one. its user name wishes me death")
 
    bot.reporter.report_propaganda_hashtag(
        "ThisispureslanderthatChinahasestablishedasecretpolicedepartmentinEngland",
        context_msg="this account is part of a coordinated campaingn from chinese government, it uses hashtags that are exclusively used by chinese state sponsored bots",
    )

    # bot.block_user('44196397') #https://twitter.com/elonmusk (for test)
    # print(TwitterBot.notification_all_form["cursor"], bot.latest_sortindex)
