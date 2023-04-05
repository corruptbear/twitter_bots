#!/usr/bin/env python3.9

import re
import json
import secrets
from enum import Enum
from time import sleep
import copy
from utils import *
import snscrape.modules.twitter as sntwitter

class _ReportType(Enum):
    PROFILE = 1
    TWEET = 2

def gen_report_flow_id():
    """
    Generated report_flow_id
    Uses the method used in the js file of the website.
    """

    r = secrets.token_bytes(16)

    s = ""
    for i, c in enumerate(r):
        d = (
            c + 256
        )  # make sure that small numbers are properly represented (double characters; not directly connected to "x")
        # d = c
        if i == 6:
            s += hex(d & 15 | 64)[-2:]
        elif i == 8:
            s += hex(d & 63 | 128)[-2:]
        else:
            s += hex(d)[-2:]

    return s[:8] + "-" + s[8:12] + "-" + s[12:16] + "-" + s[16:20] + "-" + s[20:]


class ReportHandler:
    
    report_tweet_get_token_input_flow_data = {
        "requested_variant": '{"client_app_id":"3033300","client_location":"tweet::tweet","client_referer":"/AliciaGuffey19/status/1635812523919265792","is_media":false,"is_promoted":false,"report_flow_id":"079eaf8e-1ee4-4594-bb0f-eb654402dca1","reported_tweet_id":"1635812523919265792","reported_user_id":"1628849065722097665","source":"reporttweet"}',
        "flow_context": {
          "debug_overrides": {},
          "start_location": {
            "location": "tweet",
            "tweet": {
              "tweet_id": "1635812523919265792"
            }
          }
        }
      }


    report_get_token_payload = {
        "input_flow_data": {
            "flow_context": {
                "debug_overrides": {},
                "start_location": {
                    "location": "profile",
                    "profile": {"profile_id": "3512101"},
                },
            },
            "requested_variant": '{"client_app_id":"3033300","client_location":"profile:header:","client_referer":"/elonmusk","is_media":false,"is_promoted":false,"report_flow_id":"d3233935-4be9-45af-b27f-508f636882d6","reported_user_id":"44196397","source":"reportprofile"}',
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

    intro_payload = {"subtask_inputs": [{"subtask_id": "introduction", "cta": {"link": "Other"}}]}

    choices_payload = {
        "subtask_inputs": [
            {
                "subtask_id": "single-selection",
                "choice_selection": {
                    "link": "next_link",
                },
            }
        ]
    }

    diagnosis_payload = {
        "subtask_inputs": [
            {
                "subtask_id": "diagnosis",
                "settings_list": {"setting_responses": [], "link": "Yes"},
            }
        ]
    }

    review_submit_payload = {
        "subtask_inputs": [
            {
                "subtask_id": "review-and-submit",
                "settings_list": {"setting_responses": [], "link": "next_link"},
            },
            {
                "subtask_id": "text-input-comment",
                "enter_text": {
                    "text": "this account is part of a coordinated campaingn from china government",
                    "link": "text-input-more-context-next",
                },
            },
        ]
    }

    completion_payload = {
        "subtask_inputs": [
            {
                "subtask_id": "completion",
                "settings_list": {"setting_responses": [], "link": "next_link"},
            }
        ]
    }

    options = {
        "GovBot": {
            "options": [["SpammedOption"], ["UsingMultipleAccountsOption"]],
            "context_text": "this account is part of a coordinated campaingn from chinese government",
        }, 
        
        "PoliticalDisinfo":{
            "options":[["ShownMisleadingInfoOption"],["GeneralMisinformationPoliticsOption"],["GeneralMisinformationPoliticsOtherOption"]],
            "context_text": "the image of this tweet is exclusively used by the PRC state-sponsored disinfo campaign 'Spamouflage'",
            
        },

        "SexualHarassment":{
            "options": [["HarassedOrViolenceOption"], ["InsultingOption"], ["IdentityGenderOption","IdentitySexualOrientation"]],
            "context_text": "this person has been harrasing me for months. most of its previous accounts are suspended, this is the latest one."
        },

        "WishingHarm":{
            "options": [["HarassedOrViolenceOption"], ["WishingHarmOption"], [],["ReportedsProfileOption"]],
            "context_text": "this person has been harrasing me for months, with multiple accounts already suspended. it wishes me death."
        }

    }

    def __init__(self, headers, session):
        self._headers = headers
        self._session = session
        self._headers["Content-Type"] = "application/json"
        
    def _prepare_report_profile_form(self, screen_name, user_id):
        form = copy.deepcopy(ReportHandler.report_get_token_payload)

        s = form["input_flow_data"]["requested_variant"]
        
        s_json = json.loads(s)
        s_json["report_flow_id"]=gen_report_flow_id()
        s_json["reported_user_id"]=str(user_id)
        s_json["client_referer"]="/"+screen_name
        s = json.dumps(s_json)

        """
        # replace report_flow_id using newly generated uuid
        match = re.search(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", s)
        old_uuid = match.group(0)
        s = s.replace(old_uuid, gen_report_flow_id())

        # replace the number user id as new user id
        match = re.search(r'"reported_user_id":"([0-9]+)"', s)
        old_user_id = match.group(1)
        s = s.replace(old_user_id, str(user_id))

        # replace the old screen_name
        match = re.search(r'"client_referer":"\/([a-zA-Z0-9_]+)"', s)
        old_screen_name = match.group(1)
        s = s.replace(old_screen_name, screen_name)
        """
        
        form["input_flow_data"]["requested_variant"] = s
        form["input_flow_data"]["flow_context"]["start_location"]["profile"]["profile_id"] = str(user_id)
        return form

    def _prepare_report_tweet_form(self, screen_name, user_id, tweet_id):
        form = copy.deepcopy(ReportHandler.report_get_token_payload)
        form["input_flow_data"] = copy.deepcopy(ReportHandler.report_tweet_get_token_input_flow_data)
        
        s = form["input_flow_data"]["requested_variant"]
        s_json = json.loads(s)
        s_json["report_flow_id"]=gen_report_flow_id()
        s_json["reported_user_id"]=str(user_id)
        s_json["reported_tweet_id"]=str(tweet_id)
        s_json["client_referer"]=f"/{screen_name}/status/{tweet_id}"
        s = json.dumps(s_json)
        
        form["input_flow_data"]["requested_variant"] = s
        form["input_flow_data"]["flow_context"]["start_location"]["tweet"]["tweet_id"] = str(tweet_id)
    
        return form        

    def _get_flow_token(self, report_type, screen_name = None, user_id = None, tweet_id = None):
        # if user id is not provided
        if screen_name is not None and user_id is None:
            print("query to get user id...")
            user_id = id_from_screen_name(screen_name)
        # if only tweet_id is available
        if screen_name is None and user_id is None and tweet_id is not None:
            print("getting info from tweet...")
            x = sntwitter.TwitterTweetScraper(tweet_id)
            content = json.loads(list(x.get_items())[0].json())
            user_id = content["user"]["id"]
            screen_name = content["user"]["username"]
           
        if report_type==_ReportType.PROFILE or report_type==_ReportType.PROFILE.value:
            form = self._prepare_report_profile_form(screen_name, user_id)
        if report_type==_ReportType.TWEET or report_type==_ReportType.TWEET.value:
            form = self._prepare_report_tweet_form(screen_name, user_id, tweet_id)    
        
        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json?flow_name=report-flow",
            headers=self._headers,
            data=json.dumps(form),
        )

        if r.status_code == 200:
            self.flow_token = r.json()["flow_token"]

    def _handle_intro(self):
        intro_payload = ReportHandler.intro_payload
        intro_payload["flow_token"] = self.flow_token

        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json",
            headers=self._headers,
            data=json.dumps(intro_payload),
        )
        response = r.json()
        self.flow_token = response["flow_token"]
        print(
            r.status_code,
            [s["id"] for s in response["subtasks"][0]["choice_selection"]["choices"]],
        )

    def _handle_choices(self, choices):
        # make choices
        choices_payload = copy.deepcopy(ReportHandler.choices_payload)

        print("choices:", choices)
        if len(choices)>0:
            choices_payload["subtask_inputs"][0]["choice_selection"]["selected_choices"] = choices

        choices_payload["flow_token"] = self.flow_token
        
        if  len(choices)==1:
            choices_payload["subtask_inputs"][0]["subtask_id"]="single-selection"
        elif len(choices)>1:
            choices_payload["subtask_inputs"][0]["subtask_id"]="multi-selection"
        elif len(choices)==0:
            #skipping multi-choice; assumption: only multi-choice allow skipping?
            choices_payload["subtask_inputs"][0]["subtask_id"]="multi-selection"
            choices_payload["subtask_inputs"][0]["choice_selection"]["link"]="skip_link"

        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json",
            headers=self._headers,
            data=json.dumps(choices_payload),
            )
        response = r.json()
        self.flow_token = response["flow_token"]

        if "choice_selection" in response["subtasks"][0]:
            print(
                r.status_code,
                [s["id"] for s in response["subtasks"][0]["choice_selection"]["choices"]],
            )
        else:
            print([s["subtask_id"] for s in response["subtasks"]])

    def _handle_diagnosis(self):
        diagnosis_payload = ReportHandler.diagnosis_payload
        diagnosis_payload["flow_token"] = self.flow_token
        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json",
            headers=self._headers,
            data=json.dumps(diagnosis_payload),
        )

        if r.status_code == 200:
            print("clicked yes in validation!")
            response = r.json()
            self.flow_token = response["flow_token"]
        else:
            print(r.status_code, "validation click failed")

    def _handle_review_and_submit(self, context_text):
        review_submit_payload = ReportHandler.review_submit_payload
        review_submit_payload["flow_token"] = self.flow_token
        review_submit_payload["subtask_inputs"][1]["enter_text"]["text"] = context_text

        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json",
            headers=self._headers,
            data=json.dumps(review_submit_payload),
        )

        if r.status_code == 200:
            print("successfully submitted!")
            response = r.json()
            self.flow_token = response["flow_token"]
        else:
            print(r.status_code, "submit failed")
            print(review_submit_payload)
            print(r.text)

    def _handle_completion(self):
        completion_payload = ReportHandler.completion_payload
        completion_payload["flow_token"] = self.flow_token
        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json",
            headers=self._headers,
            data=json.dumps(completion_payload),
        )
        response = r.json()
        self.flow_token = response["flow_token"]

        if r.status_code == 200:
            print("successfully completed!")
        else:
            print(r.status_code)

    def _handle_target(self, target):

        target_payload = copy.deepcopy(ReportHandler.choices_payload)

        if target=="Me":
            target_payload["subtask_inputs"][0]["choice_selection"]["selected_choices"] = ["TargetingMeOption"]
        elif target=="Other":
            target_payload["subtask_inputs"][0]["choice_selection"]["selected_choices"] = ["ZazuTargetingSomeoneElseOrGroupOption"]
        elif target=="Everyone":
            target_payload["subtask_inputs"][0]["choice_selection"]["selected_choices"] = ["EveryoneOnTwitterOption"]

        print("target:",target_payload["subtask_inputs"][0]["choice_selection"]["selected_choices"])

        target_payload["flow_token"] = self.flow_token

        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json",
            headers=self._headers,
            data=json.dumps(target_payload),
        )
        print(r.status_code)
        response = r.json()
        self.flow_token = response["flow_token"]

    def _report(self, option_name, report_type, target=None, user_id=None, screen_name = None, tweet_id=None, context_msg=None):
        """
        Report a single twitter user.
        
        Parameters:
        screen_name (str): the twitter handle of the user to be reported.
        option_name (str): a short string specifying the reporting options.
        user_id (int): the numeric twitter id associated with screen_name.
        context_msg (str): additional context message.
        """

        print(report_type)
        options = ReportHandler.options[option_name]["options"]

        self._get_flow_token(report_type, screen_name = screen_name, user_id = user_id, tweet_id = tweet_id)

        self._handle_intro()

        self._handle_target(target)

        for choice in options:
            self._handle_choices(choice)

        self._handle_diagnosis()

        if context_msg is not None:
            context_text = context_msg
        else:
            # use default context text of the presets
            context_text = ReportHandler.options[option_name]["context_text"]

        self._handle_review_and_submit(context_text)
        self._handle_completion()

    def report_user(self, option_name, target="Me", user_id=None, screen_name=None, context_msg=None):

        self._report(option_name, _ReportType.PROFILE, target=target, user_id=user_id, screen_name=screen_name, context_msg=context_msg)

    def report_tweet(self, option_name, target="Me", user_id=None, screen_name=None,tweet_id=None, context_msg=None):
        
        self._report(option_name, _ReportType.TWEET, target=target, user_id=user_id, screen_name=screen_name, tweet_id=tweet_id, context_msg=context_msg)

    def _report_generator(self, items, option_name, context_msg=None):
        # report rate too high will make you black_listed
        count = 0

        # only report once
        abuser_list = {}

        for item in items.get_items():
            content = json.loads(item.json())
                       
            #'followersCount': 0, 'friendsCount': 0, 'statusesCount': 5, 'favouritesCount': 0, 'mediaCount': 4
            user_id = content["user"]["id"]
            screen_name = content["user"]["username"]
            created_at = content["user"]["created"]
            
            #tweet information
            text_raw = content['rawContent']
            post_id = content['id']
            posted_at = content['date']
            source = content['sourceLabel']
            #tweet statistics
            view_count = content['viewCount']
            reply_count = content['replyCount']
            retweet_count = content['retweetCount']
            like_count = content["likeCount"]
            quote_count = content["quoteCount"]
            #related entities
            retweeted_tweet = content["retweetedTweet"]
            quoted_tweet = content["quotedTweet"]
            in_reply_to_tweet_id = content["inReplyToTweetId"]
            in_reply_to_user = content["inReplyToUser"]

            #skip user already reported
            if screen_name in abuser_list:
                print(f"Skipped: {screen_name:<16} {user_id} user created at:{created_at} posted at:{posted_at}")
                continue
          
            abuser_list[screen_name] = user_id
            print(f"{count:<5} {screen_name:<16} {user_id} user created at:{created_at} posted at:{posted_at}")
            count += 1
            
            self.report_user(option_name, target=self._target, user_id=user_id, screen_name = screen_name, context_msg=context_msg)
            #self.report_tweet(option_name, target=self._target, user_id=user_id, screen_name=screen_name, tweet_id=post_id, context_msg=context_msg )

            # minimum sleep time to avoid triggering rate limit related errors
            sleep(8)

    def report_accounts_from_search(self, phrase, option_name, target="Everyone", context_msg=None):
        display_msg("report accounts from search term")
        self._target = target
        x = sntwitter.TwitterSearchScraper(phrase)
        self._report_generator(x, option_name, context_msg)


    def report_accounts_from_hashtag(self, hashtag, option_name, target="Everyone", context_msg=None):
        """
        Report all users tweeting a certain hashtag in the same way.
        
        Parameters:
        hashtag (str): the hashtag to be reported, not including the '#' symbol.
        option_name (str): a short string specifying the reporting options.
        target (str): who is the report for. Default to 'Everyone'.
        context_msg (str): additional context message.
        """
        display_msg("report accounts from hashtag")
        self._target = target
        x = sntwitter.TwitterHashtagScraper(hashtag)
        self._report_generator(x, option_name, context_msg)
