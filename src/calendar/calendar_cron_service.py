from typing import List
from datetime import datetime, timedelta, timezone
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import User, UserMeeting
from utils.redis.redis_utils import RedisManager
from calendar.calendar_service import CalendarService
from sqlalchemy import update
import aiohttp



class CalendarCronService:
    def __init__(self, nylas_api_key: str, nylas_api_uri: str, session: AsyncSession):
        self.nylas_api_key = nylas_api_key
        self.nylas_api_uri = nylas_api_uri
        self.logger = logging.getLogger("CalendarService")
        self.calendar_service = CalendarService(nylas_api_key, nylas_api_uri)
        self.cache_manager = RedisManager()
        self.session = session

    async def get_all_users(self) -> List[User]:
        try:
            query = select(User)
            result = await self.session.execute(query)
            users = result.scalars().all()
            return users
        except Exception as e:
            self.logger.error(f"Error fetching users: {e}")
            return []

    async def get_user_meetings(
        self, user_ids: List[int], start_time: datetime, end_time: datetime
    ) -> List[UserMeeting]:
        try:
            # Query to fetch user meetings for specified user IDs and within the time range
            query = select(UserMeeting).filter(
                UserMeeting.user_id.in_(user_ids),
                UserMeeting.start_time >= start_time,
                UserMeeting.end_time <= end_time,
            )
            result = await self.session.execute(query)
            user_meetings = result.scalars().all()
            return user_meetings
        except Exception as e:
            self.logger.error(f"Error fetching user meetings: {e}")
            return []

    async def update_user_meeting(self, meeting_id: int, bot_id: str) -> bool:
        try:
            # Perform the update operation
            await self.session.execute(
                update(UserMeeting)
                .where(UserMeeting.id == meeting_id)
                .values(bot_id=bot_id)
            )
            # Commit the transaction
            await self.session.commit()
            return True
        except Exception as e:
            # Log the error
            self.logger.error(f"Error updating user meeting: {e}")
            return False

    async def process_fetch_calendar_events(self) -> bool:
        try:
            current_time = datetime.now(timezone.utc)
            start_time = current_time - timedelta(minutes=10)
            end_time = current_time + timedelta(minutes=30)

            # Fetch all users using SQLAlchemy
            users = await self.get_all_users()

            users_with_grants = [user for user in users if user.get("grant_id")]

            user_ids = [user["id"] for user in users_with_grants]
            user_meetings = await self.get_user_meetings(user_ids, start_time, end_time)

            for user in users_with_grants:
                try:
                    user_bot_config = user.get("bot_config", {})
                    fetch_start_time = start_time
                    fetch_end_time = end_time

                    is_bot_disabled = False
                    if user_bot_config.get("isDisabled"):
                        if start_time > user_bot_config.get(
                            "startTime"
                        ) and end_time < user_bot_config.get("endTime"):
                            is_bot_disabled = True
                        else:
                            bot_disable_start_time = user_bot_config.get("startTime")
                            bot_disable_end_time = user_bot_config.get("endTime")

                            if (
                                start_time < bot_disable_start_time
                                and end_time > bot_disable_start_time
                            ):
                                fetch_end_time = bot_disable_start_time

                            if (
                                start_time < bot_disable_end_time
                                and end_time > bot_disable_end_time
                            ):
                                fetch_start_time = bot_disable_end_time

                    if not is_bot_disabled:
                        grant_id = user["grant_id"]

                        async with aiohttp.ClientSession() as session:
                            calendars_response = await session.get(
                                f"{self.nylas_api_uri}/calendars",
                                headers={
                                    "Authorization": f"Bearer {self.nylas_api_key}"
                                },
                            )
                            calendars = await calendars_response.json()
                            primary_calendar_id = calendars["data"][0]["id"]

                            events_response = await session.get(
                                f"{self.nylas_api_uri}/events",
                                headers={
                                    "Authorization": f"Bearer {self.nylas_api_key}"
                                },
                                params={
                                    "calendarId": primary_calendar_id,
                                    "start": str(int(fetch_start_time.timestamp())),
                                    "end": str(int(fetch_end_time.timestamp())),
                                },
                            )
                            calendar_events_list = await events_response.json()

                        if calendar_events_list["data"]:
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
                                        participant["email"].lower()
                                        == organizer["email"].lower()
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

                                    emails_arr = [
                                        participant["email"].lower()
                                        for participant in participants
                                    ]

                                    is_bot_disabled_for_current_meeting = any(
                                        meeting["calendar_uid"]
                                        == calendar_meet["icalUid"]
                                        and meeting["start_time"]
                                        == calendar_meet["when"]["startTime"]
                                        and user["email"].lower() in emails_arr
                                        for meeting in user_meetings
                                        if meeting.get("disable_bot")
                                    )

                                    if not is_bot_disabled_for_current_meeting:
                                        meeting_unique_identifier = (
                                            self.calendar_service.get_meeting_unique_identifier_from_url(
                                                event_url,
                                                calendar_meet["conferencing"][
                                                    "provider"
                                                ],
                                            )
                                            or calendar_meet["icalUid"]
                                        )

                                        cal_cache_key = (
                                            f"sl_cal_{meeting_unique_identifier}"
                                        )
                                        cache_obj = await self.cache_manager.get(
                                            cal_cache_key
                                        )

                                        if not cache_obj:
                                            event_start_time = (
                                                datetime.fromtimestamp(
                                                    calendar_meet["when"]["startTime"],
                                                    tz=timezone.utc,
                                                ).astimezone(
                                                    pytz.timezone(
                                                        calendar_meet["when"][
                                                            "startTimezone"
                                                        ]
                                                    )
                                                )
                                                - timedelta(seconds=30)
                                            ).isoformat()

                                            organizer_user = next(
                                                (
                                                    user_obj
                                                    for user_obj in users
                                                    if user_obj["email"].lower()
                                                    == organizer["email"].lower()
                                                ),
                                                None,
                                            )

                                            bot_config = (
                                                organizer_user["bot_config"]
                                                if organizer_user
                                                else user["bot_config"]
                                            )

                                            transcription_options = self.calendar_service.get_meeting_transcript_options(
                                                calendar_meet["conferencing"][
                                                    "provider"
                                                ]
                                            )

                                            bot_data = await self.calendar_service.connect_bot_to_event(
                                                event_url,
                                                event_start_time,
                                                bot_config,
                                                transcription_options,
                                            )

                                            bot_data["data"]["eventLastCheckedTime"] = (
                                                int(datetime.now().timestamp())
                                            )

                                            await self.cache_manager.set(
                                                cal_cache_key,
                                                json.dumps(bot_data["data"]),
                                                7200000,
                                            )

                                            participant_user_ids = [
                                                userin_system["id"]
                                                for userin_system in users
                                                if userin_system["email"].lower()
                                                in (
                                                    participant["email"].lower()
                                                    for participant in participants
                                                )
                                            ]

                                            bot_user_cache_key = f"sl_bot_metadata_{bot_data['data']['id']}"

                                            connected_user_meetings = [
                                                meeting_obj
                                                for meeting_obj in user_meetings
                                                if (
                                                    meeting_obj.get("uniq_identifier")
                                                    == meeting_unique_identifier
                                                    if meeting_obj.get(
                                                        "uniq_identifier"
                                                    )
                                                    else meeting_obj["calendar_uid"]
                                                    == calendar_meet["icalUid"]
                                                )
                                                and meeting_obj["start_time"]
                                                == calendar_meet["when"]["startTime"]
                                            ]

                                            meeting_ids = [
                                                user_meet["id"]
                                                for user_meet in connected_user_meetings
                                            ]

                                            await self.cache_manager.set(
                                                bot_user_cache_key,
                                                json.dumps(
                                                    {
                                                        "user_id": (
                                                            organizer_user["id"]
                                                            if organizer_user
                                                            else user["id"]
                                                        ),
                                                        "ical_uid": calendar_meet[
                                                            "icalUid"
                                                        ],
                                                        "identifier": meeting_unique_identifier,
                                                        "title": calendar_meet["title"],
                                                        "provider": calendar_meet[
                                                            "conferencing"
                                                        ]["provider"],
                                                        "userIds": participant_user_ids,
                                                        "lastStartTime": calendar_meet[
                                                            "when"
                                                        ]["startTime"],
                                                        "eventStartTime": event_start_time,
                                                        "userTimeZone": calendar_meet[
                                                            "when"
                                                        ]["startTimezone"],
                                                        "participants": participants,
                                                        "organizer": calendar_meet[
                                                            "organizer"
                                                        ],
                                                        "meetingIds": meeting_ids,
                                                    }
                                                ),
                                                18000000,
                                            )

                                            if connected_user_meetings:
                                                for (
                                                    meeting_obj
                                                ) in connected_user_meetings:
                                                    try:
                                                        # need to fix this and create Generic for get and update .
                                                        await self.update_user_meeting(
                                                            meeting_id=meeting_obj.meeting_id,
                                                            bot_id=bot_data.get(
                                                                "data"
                                                            ).get("id"),
                                                        )

                                                        meeting_reminder_cache_key = f"meeting_reminder:{meeting_obj['id']}:{meeting_obj['userId']}"
                                                        user_meeting_reminder_cache = await self.cache_manager.get(
                                                            meeting_reminder_cache_key
                                                        )

                                                        if (
                                                            not user_meeting_reminder_cache
                                                        ):
                                                            user_obj = next(
                                                                (
                                                                    u
                                                                    for u in users
                                                                    if meeting_obj[
                                                                        "userId"
                                                                    ]
                                                                    == u["id"]
                                                                ),
                                                                None,
                                                            )
                                                            # have to work on slack_notification_service
                                                            await slack_notification_service.send_meeting_reminder_to_user(
                                                                meeting_obj,
                                                                user_obj,
                                                                participants,
                                                                organizer,
                                                            )
                                                        else:
                                                            logging.info(
                                                                f"Reminder already sent for meeting {meeting_obj['id']} to user {meeting_obj['userId']}. Skipping..."
                                                            )
                                                    except Exception as error:
                                                        logging.error(
                                                            f"Failed to send reminder for meeting {meeting_obj['id']} to user {meeting_obj['userId']}. - error => {error}"
                                                        )

                                        else:
                                            logging.info("Event already logged")

                except Exception as e:
                    print(f"Error processing events for {user['email']}: {str(e)}")

            return True
        except Exception as e:
            self.logger.error(f"Process Failed - error => {e}")
            return False

        try:
            with SessionLocal() as session:
                meetings = (
                    session.query(UserMeeting)
                    .filter(
                        UserMeeting.userId.in_(user_ids),
                        UserMeeting.start_time >= int(start_time.timestamp()),
                        UserMeeting.end_time <= int(end_time.timestamp()),
                    )
                    .all()
                )
                return [
                    {
                        "id": meeting.id,
                        "userId": meeting.userId,
                        "documentId": meeting.documentId,
                        "calendar_uid": meeting.calendar_uid,
                        "master_cal_uid": meeting.master_cal_uid,
                        "event_url": meeting.event_url,
                        "title": meeting.title,
                        "participants": meeting.participants,
                        "organizer": meeting.organizer,
                        "start_time": meeting.start_time,
                        "timezone": meeting.timezone,
                        "provider": meeting.provider,
                        "disable_bot": meeting.disable_bot,
                        "type": meeting.type,
                        "createdAt": meeting.createdAt,
                        "updatedAt": meeting.updatedAt,
                        "start_date": meeting.start_date,
                        "end_time": meeting.end_time,
                        "uniq_identifier": meeting.uniq_identifier,
                        "Agenda": meeting.Agenda,
                        "bot_id": meeting.bot_id,
                        "rough_notes": meeting.rough_notes,
                        "bot_status": meeting.bot_status,
                    }
                    for meeting in meetings
                ]
        except Exception as e:
            self.logger.error(f"Failed to fetch user meetings - error => {e}")
            return []
