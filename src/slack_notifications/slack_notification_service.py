import os

print("imported moment")
from fastapi import HTTPException

print("imported HTTPException from fastapi")
from slack_sdk import WebClient

print("imported WebClient from slack_sdk")
from slack_sdk.errors import SlackApiError

print("imported SlackApiError from slack_sdk.errors")
from typing import Dict

print("imported Dict from typing")
from db.models.models import User, UserMeetings

print("imported User and UserMeetings from db.models.models")
from typing import List

print("imported List from typing")
from datetime import datetime
import pytz


class SlackNotificationService:
    def __init__(self):
        print("Initializing SlackNotificationService")
        self.client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
        print("Initialized WebClient")
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        print("Set slack_bot_token")
        self.slack_app_token = os.getenv("SLACK_APP_TOKEN")
        print("Set slack_app_token")
        self.slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        print("Set slack_signing_secret")

    async def fetch_slack_user_id_by_email(self, email: str):
        print(f"Fetching Slack user ID by email: {email}")

        try:
            response = self.client.users_lookupByEmail(email=email)
            print(f"Received response: {response}")
            return response["user"]["id"]
        except SlackApiError as e:
            print(f"SlackApiError: {e.response['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching Slack user by email: {e.response['error']}",
            )

    async def fetch_slack_participant_info(self, email: str):
        print(f"Fetching Slack participant info by email: {email}")
        try:

            response = self.client.users_lookupByEmail(email=email)
            print(f"Received response: {response}")
            user = response["user"]
            print(f"Fetched user: {user}")
            return user["profile"]["first_name"]
        except SlackApiError as e:
            print(f"SlackApiError: {e.response['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching user info for {email}: {e.response['error']}",
            )

    async def send_slack_reminder(
        self, slack_user_id: str, meeting_details: Dict[str, str], intro_line: str
    ):
        print(f"Sending Slack reminder to user ID: {slack_user_id}")
        blocks = [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔔 Upcoming Meeting 🔔*\n\n{intro_line}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{meeting_details['event_url']}|{meeting_details['title']}>*\n{meeting_details['start_time']} — {meeting_details['end_time']}  |  {meeting_details['provider']}",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Join Video Call",
                            "emoji": True,
                        },
                        "style": "primary",
                        "url": meeting_details["event_url"],
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Do not record",
                            "emoji": True,
                        },
                        "style": "danger",
                        "value": "disable_bot",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"This call happens on {meeting_details['provider']}. You will have meeting preparation available. Click on the meeting name for an early preview.",
                    },
                ],
            },
        ]
        print(f"Constructed blocks: {blocks}")

        try:
            response = self.client.chat_postMessage(
                channel=slack_user_id,
                blocks=blocks,
                text="You have an upcoming meeting.",
            )
            print(f"Received response from chat_postMessage: {response}")
            return response.get("ok", False)
        except SlackApiError as e:
            print(f"SlackApiError: {e.response['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Error sending meeting reminder: {e.response['error']}",
            )

    async def send_meeting_reminder_to_user(
        self,
        meeting_obj: UserMeetings,
        user_obj: User,
        participants: List[User],
        organizer: User,
    ):
        print(
            f"Sending meeting reminder to user: {user_obj.email} for meeting: {meeting_obj.title}"
        )
        try:

            domains = {}
            print("Initialized domains dictionary")
            first_name = None
            print("Initialized first_name to None")

            if organizer["email"] != user_obj.email:
                print(
                    f"Organizer email {organizer['email']} is different from user email {user_obj.email}"
                )
                first_name = organizer.name or await self.fetch_slack_participant_info(
                    organizer["email"]
                )
                print(f"Fetched first_name: {first_name}")

            participant_first_names = []
            print("Initialized participant_first_names list")
            for participant_obj in participants:
                print(f"Processing participant: {participant_obj.email}")
                if participant_obj.email != user_obj.email:
                    print(
                        f"Participant email {participant_obj.email} is different from user email {user_obj.email}"
                    )
                    name = (
                        participant_obj.name
                        or await self.fetch_slack_participant_info(
                            participant_obj.email
                        )
                    )
                    print(f"Fetched name: {name}")
                    domain = participant_obj.email.split("@")[1]
                    print(f"Extracted domain: {domain}")
                    if domain not in domains:
                        domains[domain] = []
                        print(f"Added new domain to domains: {domain}")
                    domains[domain].append(name)
                    print(f"Appended name to domain in domains: {domains[domain]}")
                    participant_first_names.append(name)
                    print(
                        f"Appended name to participant_first_names: {participant_first_names}"
                    )

            if not first_name:
                first_name = (
                    participant_first_names[0] if participant_first_names else "Someone"
                )
                print(f"Set first_name to: {first_name}")

            external_domains = [
                domain for domain in domains if len(domains[domain]) == 1
            ]
            print(f"Filtered external_domains: {external_domains}")
            external_users = [domains[domain][0] for domain in external_domains]
            print(f"Extracted external_users: {external_users}")
            external_info = (
                f", including {len(external_users)} external users from {external_domains[0]}"
                if external_domains
                else ""
            )
            print(f"Constructed external_info: {external_info}")

            others_count = len(participant_first_names) - 1
            print(f"Calculated others_count: {others_count}")
            intro_line = f"You have a meeting with {first_name}{external_info}."
            print(f"Constructed intro_line: {intro_line}")
            if others_count > 0:
                intro_line = f"You have a meeting with {first_name} and {others_count} others{external_info}."
                print(f"Updated intro_line: {intro_line}")

            user_timezone = pytz.timezone(user_obj.timezone)
            start_time = (
                datetime.fromtimestamp(meeting_obj.start_time, pytz.utc)
                .astimezone(user_timezone)
                .strftime("%I:%M %p")
            )
            end_time = (
                datetime.fromtimestamp(meeting_obj.end_time, pytz.utc)
                .astimezone(user_timezone)
                .strftime("%I:%M %p")
            )

            meeting_details = {
                "title": meeting_obj.title,
                "event_url": meeting_obj.event_url,
                "start_time": start_time,
                "end_time": end_time,
                "provider": meeting_obj.provider,
            }
            print(f"Constructed meeting_details: {meeting_details}")

            slack_user_id = await self.fetch_slack_user_id_by_email(user_obj.email)
            print(f"Fetched slack_user_id: {slack_user_id}")
            success = await self.send_slack_reminder(
                slack_user_id, meeting_details, intro_line
            )
            print(f"Sent Slack reminder, success: {success}")

            if not success:
                print(f"Failed to send Slack reminder to user {user_obj.id}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error while sending meeting reminder to user {user_obj.id}",
                )

            print(
                f"Successfully sent meeting reminder to user {user_obj.id} for meeting {meeting_obj.id}"
            )
            return {
                "message": f"Successfully sent meeting reminder to user {user_obj.id} for meeting {meeting_obj.id}"
            }

        except Exception as e:
            print(f"Exception occurred: {e}")
            raise HTTPException(status_code=500, detail=str(e))
