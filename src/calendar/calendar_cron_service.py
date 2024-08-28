from typing import List
from datetime import datetime, timedelta, timezone
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models.user import User
from db.models.user_meetings import UserMeetings
from utils.redis.redis_utils import RedisManager
from src.calendar.calendar_service import CalendarService
from sqlalchemy import update
import aiohttp
import pytz


class CalendarCronService:
    def __init__(self, nylas_api_key: str, nylas_api_uri: str, session: AsyncSession):
        self.nylas_api_key = nylas_api_key
        self.nylas_api_uri = nylas_api_uri
        self.logger = logging.getLogger("CalendarService")
        self.calendar_service = CalendarService(nylas_api_key, nylas_api_uri)
        self.cache_manager = RedisManager()
        self.session = session

    async def get_all_users(self) -> List[User]:
        self.logger.debug("Fetching all users from the database.")
        try:
            query = select(User)
            result = await self.session.execute(query)
            users = result.scalars().all()
            self.logger.debug(f"Fetched {len(users)} users.")
            return users
        except Exception as e:
            self.logger.error(f"Error fetching users: {e}")
            return []

    async def get_user_meetings(self, user_ids: List[int], start_time: datetime, end_time: datetime) -> List[UserMeetings]:
        self.logger.debug("Fetching user meetings.")
        try:
            query = select(UserMeetings).filter(
                UserMeetings.user_id.in_(user_ids),
                UserMeetings.start_time >= start_time,
                UserMeetings.end_time <= end_time,
            )
            result = await self.session.execute(query)
            user_meetings = result.scalars().all()
            self.logger.debug(f"Fetched {len(user_meetings)} user meetings.")
            return user_meetings
        except Exception as e:
            self.logger.error(f"Error fetching user meetings: {e}")
            return []

    async def update_user_meeting(self, meeting_id: int, bot_id: str) -> bool:
        self.logger.debug(f"Updating user meeting with ID {meeting_id}.")
        try:
            await self.session.execute(
                update(UserMeetings)
                .where(UserMeetings.id == meeting_id)
                .values(bot_id=bot_id)
            )
            await self.session.commit()
            self.logger.info(f"Successfully updated meeting ID {meeting_id} with bot ID {bot_id}.")
            return True
        except Exception as e:
            self.logger.error(f"Error updating user meeting: {e}")
            return False

    async def process_fetch_calendar_events(self) -> bool:
        self.logger.debug("Processing fetch calendar events.")
        try:
            current_time = datetime.now(timezone.utc)
            start_time = current_time - timedelta(minutes=10)
            end_time = current_time + timedelta(minutes=30)

            users = await self.get_all_users()

            users_with_grants = [user for user in users if user.get("grant_id")]
            user_ids = [user["id"] for user in users_with_grants]
            user_meetings = await self.get_user_meetings(user_ids, start_time, end_time)

            self.logger.debug(f"Processing events for {len(users_with_grants)} users.")
            for user in users_with_grants:
                try:
                    user_bot_config = user.get("bot_config", {})
                    fetch_start_time = start_time
                    fetch_end_time = end_time

                    is_bot_disabled = False
                    if user_bot_config.get("isDisabled"):
                        if start_time > user_bot_config.get("startTime") and end_time < user_bot_config.get("endTime"):
                            is_bot_disabled = True
                        else:
                            bot_disable_start_time = user_bot_config.get("startTime")
                            bot_disable_end_time = user_bot_config.get("endTime")

                            if start_time < bot_disable_start_time and end_time > bot_disable_start_time:
                                fetch_end_time = bot_disable_start_time

                            if start_time < bot_disable_end_time and end_time > bot_disable_end_time:
                                fetch_start_time = bot_disable_end_time

                    if not is_bot_disabled:
                        grant_id = user["grant_id"]

                        async with aiohttp.ClientSession() as session:
                            self.logger.debug(f"Fetching calendars for user {user['email']}.")
                            calendars_response = await session.get(
                                f"{self.nylas_api_uri}/calendars",
                                headers={"Authorization": f"Bearer {self.nylas_api_key}"},
                            )
                            calendars = await calendars_response.json()
                            primary_calendar_id = calendars["data"][0]["id"]

                            self.logger.debug(f"Fetching events from calendar ID {primary_calendar_id}.")
                            events_response = await session.get(
                                f"{self.nylas_api_uri}/events",
                                headers={"Authorization": f"Bearer {self.nylas_api_key}"},
                                params={
                                    "calendarId": primary_calendar_id,
                                    "start": str(int(fetch_start_time.timestamp())),
                                    "end": str(int(fetch_end_time.timestamp())),
                                },
                            )
                            calendar_events_list = await events_response.json()

                        if calendar_events_list["data"]:
                            self.logger.debug(f"Found {len(calendar_events_list['data'])} calendar events.")
                            for calendar_meet in calendar_events_list["data"]:
                                event_url = (
                                    calendar_meet.get("conferencing", {})
                                    .get("details", {})
                                    .get("url")
                                )
                                if event_url:
                                    organizer = calendar_meet["organizer"]
                                    participants = calendar_meet["participants"]

                                    if not any(
                                        participant["email"].lower() == organizer["email"].lower()
                                        for participant in participants
                                    ):
                                        participants.append(
                                            {
                                                "email": organizer["email"],
                                                "name": organizer["name"],
                                                "status": "noreply",
                                                "comment": None,
                                                "phoneNumber": None,
                                            }
                                        )

                                    emails_arr = [participant["email"].lower() for participant in participants]

                                    is_bot_disabled_for_current_meeting = any(
                                        meeting["calendar_uid"] == calendar_meet["icalUid"]
                                        and meeting["start_time"] == calendar_meet["when"]["startTime"]
                                        and user["email"].lower() in emails_arr
                                        for meeting in user_meetings
                                        if meeting.get("disable_bot")
                                    )

                                    if not is_bot_disabled_for_current_meeting:
                                        meeting_unique_identifier = (
                                            self.calendar_service.get_meeting_unique_identifier_from_url(
                                                event_url,
                                                calendar_meet["conferencing"]["provider"],
                                            )
                                            or calendar_meet["icalUid"]
                                        )

                                        cal_cache_key = f"sl_cal_{meeting_unique_identifier}"
                                        cache_obj = await self.cache_manager.get(cal_cache_key)

                                        if not cache_obj:
                                            event_start_time = (
                                                datetime.fromtimestamp(
                                                    calendar_meet["when"]["startTime"],
                                                    tz=timezone.utc,
                                                ).astimezone(
                                                    pytz.timezone(
                                                        calendar_meet["when"]["startTimezone"]
                                                    )
                                                )
                                                - timedelta(seconds=30)
                                            ).isoformat()

                                            organizer_user = next(
                                                (
                                                    user_obj
                                                    for user_obj in users
                                                    if user_obj["email"].lower() == organizer["email"].lower()
                                                ),
                                                None,
                                            )

                                            bot_config = (
                                                organizer_user["bot_config"]
                                                if organizer_user
                                                else user["bot_config"]
                                            )

                                            transcription_options = self.calendar_service.get_meeting_transcript_options(
                                                calendar_meet["conferencing"]["provider"]
                                            )

                                            self.logger.debug(f"Connecting bot to event with URL {event_url}.")
                                            bot_data = await self.calendar_service.connect_bot_to_event(
                                                event_url,
                                                event_start_time,
                                                bot_config,
                                                transcription_options,
                                            )

                                            bot_data["data"]["eventLastCheckedTime"] = int(datetime.now().timestamp())

                                            await self.cache_manager.set(
                                                cal_cache_key,
                                                json.dumps(bot_data["data"]),
                                                7200000,
                                            )

                                            participant_user_ids = [
                                                userin_system["id"]
                                                for userin_system in users
                                                if userin_system["email"].lower()
                                                in (participant["email"].lower() for participant in participants)
                                            ]

                                            bot_user_cache_key = f"sl_bot_metadata_{bot_data['data']['id']}"

                                            connected_user_meetings = [
                                                meeting_obj
                                                for meeting_obj in user_meetings
                                                if (
                                                    meeting_obj.get("uniq_identifier")
                                                    == meeting_unique_identifier
                                                    if meeting_obj.get("uniq_identifier")
                                                    else meeting_obj["calendar_uid"]
                                                    == calendar_meet["icalUid"]
                                                )
                                                and meeting_obj["start_time"] == calendar_meet["when"]["startTime"]
                                            ]

                                            meeting_ids = [user_meet["id"] for user_meet in connected_user_meetings]

                                            await self.cache_manager.set(
                                                bot_user_cache_key,
                                                json.dumps(
                                                    {
                                                        "user_id": (
                                                            organizer_user["id"]
                                                            if organizer_user
                                                            else user["id"]
                                                        ),
                                                        "ical_uid": calendar_meet["icalUid"],
                                                        "identifier": meeting_unique_identifier,
                                                        "title": calendar_meet["title"],
                                                        "provider": calendar_meet["conferencing"]["provider"],
                                                        "userIds": participant_user_ids,
                                                        "lastStartTime": calendar_meet["when"]["startTime"],
                                                        "eventStartTime": event_start_time,
                                                        "botId": bot_data["data"]["botId"],
                                                        "botJoinUrl": bot_data["data"]["joinUrl"],
                                                    }
                                                ),
                                                7200000,
                                            )

                                            for meeting_id in meeting_ids:
                                                await self.update_user_meeting(meeting_id, bot_data["data"]["botId"])

                        else:
                            self.logger.debug(f"No calendar events found for user {user['email']}.")

                except Exception as e:
                    self.logger.error(f"Error processing events for user {user['email']}: {e}")

            return True
        except Exception as e:
            self.logger.error(f"Error processing calendar events: {e}")
            return False
