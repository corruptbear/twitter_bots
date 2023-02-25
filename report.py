#!/usr/bin/env python3.9

import re
import json
import secrets

import snscrape.modules.twitter as sntwitter


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
    report_get_token_form = {
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

    single_choice_payload = {
        "subtask_inputs": [
            {
                "subtask_id": "single-selection",
                "choice_selection": {
                    "link": "next_link",
                    "selected_choices": [
                        "EveryoneOnTwitterOption"
                    ],  # TargetingMeOption, ZazuTargetingSomeoneElseOrGroupOption
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
            "choices": ["EveryoneOnTwitterOption", "SpammedOption", "UsingMultipleAccountsOption"],
            "context_text": "this account is part of a coordinated campaingn from chinese government",
        }
    }

    def __init__(self, headers, session):
        self._headers = headers
        self._session = session
        self._headers["Content-Type"] = "application/json"

    def get_flow_token(self, screen_name, user_id):
        form = ReportHandler.report_get_token_form

        # if user id is not provided
        if user_id == None:
            print("query to get user id...")
            x = sntwitter.TwitterUserScraper(screen_name)
            userdata = x._get_entity()
            user_id = userdata.id

        s = form["input_flow_data"]["requested_variant"]

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

        form["input_flow_data"]["requested_variant"] = s

        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json?flow_name=report-flow",
            headers=self._headers,
            data=json.dumps(form),
        )

        self.flow_token = r.json()["flow_token"]

    def handle_intro(self):
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

    def handle_single_choice(self, choice):
        # make choices
        single_choice_payload = ReportHandler.single_choice_payload

        print("choice:", choice)
        single_choice_payload["subtask_inputs"][0]["choice_selection"]["selected_choices"] = [choice]
        single_choice_payload["flow_token"] = self.flow_token
        r = self._session.post(
            "https://api.twitter.com/1.1/report/flow.json",
            headers=self._headers,
            data=json.dumps(single_choice_payload),
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

    def handle_diagnosis(self):
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

    def handle_review_and_submit(self, context_text):
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

    def handle_completion(self):
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

    def report_spam(self, screen_name, option_name, user_id=None):
        choices = ReportHandler.options[option_name]["choices"]
        # detail could be one of: ['SharingLinksOption', 'PostingSpamOption', 'LikeRetweetReplySpamOption', 'FakeEngagementOption', 'UsingMultipleAccountsOption', 'InflatingFollowshipOption', 'SomethingElseOption']
        target, how, detail = choices[0], choices[1], choices[2]

        # set the initial flow token
        self.get_flow_token(screen_name, user_id)

        self.handle_intro()

        self.handle_single_choice(target)
        self.handle_single_choice(how)
        self.handle_single_choice(detail)
        self.handle_diagnosis()

        context_text = ReportHandler.options[option_name]["context_text"]

        self.handle_review_and_submit(context_text)
        self.handle_completion()
