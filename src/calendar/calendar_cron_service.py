from typing import List
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from utils.redis.redis_utils import RedisManager
from src.calendar.calendar_service import CalendarService
from sqlalchemy import update
from db.models.models import User, UserMeetings
from nylas import Client
from src.slack_notifications.slack_notification_service import SlackNotificationService
import os

class CalendarCronService:
    def __init__(self, nylas_api_key: str, nylas_api_uri: str):
        self.logger = logging.getLogger("CalendarService")
        self.logger.setLevel(logging.DEBUG)  # Set log level to DEBUG
        handler = logging.StreamHandler()  # Use StreamHandler to log to console
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.nylas_api_key = nylas_api_key
        self.nylas_api_uri = nylas_api_uri
        self.slack_notification_service = SlackNotificationService()
        self.calendar_service = CalendarService(nylas_api_key, nylas_api_uri)
        self.cache_manager = RedisManager()
        try:
            self.nylas = Client(
            api_uri= os.getenv("NYLAS_API_URI"),
            api_key=os.getenv("NYLAS_API_KEY")
            )   
        except Exception as e:
            self.logger.error(f"Nylas Init failed: {e}")
            self.nylas = None  # Set to None if initialization fails

    async def get_all_users(self, session: AsyncSession) -> List[User]:
        self.logger.debug("Fetching all users from the database.")
        try:
            query = select(User)
            self.logger.debug("Executing query to fetch users.")
            result = await session.execute(query)
            users = result.scalars().all()
            self.logger.debug(f"Fetched {len(users)} users from the database.")
            return users
        except Exception as e:
            self.logger.error(f"Error fetching users from the database: {e}", exc_info=True)
            return []

    async def get_user_meetings(self, user_ids: List[int], start_time: datetime, end_time: datetime, session: AsyncSession) -> List[UserMeetings]:
        self.logger.debug("Fetching user meetings.")
        try:
            self.logger.debug(start_time)
            self.logger.debug(end_time)
            query = select(UserMeetings).filter(
                UserMeetings.userId.in_(user_ids),
                UserMeetings.start_time >= start_time,
                UserMeetings.end_time <= end_time,
            )
            result = await session.execute(query)
            user_meetings = result.scalars().all()
            self.logger.debug(f"Fetched {len(user_meetings)} user meetings.")
            return user_meetings
        except Exception as e:
            self.logger.error(f"Error fetching user meetings: {e}", exc_info=True)
            return []

    async def update_user_meeting(self, meeting_id: int, bot_id: str, session: AsyncSession) -> bool:
        self.logger.debug(f"Updating user meeting with ID {meeting_id}.")
        try:
            await session.execute(
                update(UserMeetings)
                .where(UserMeetings.id == meeting_id)
                .values(bot_id=bot_id)
            )
            await session.commit()
            self.logger.info(f"Successfully updated meeting ID {meeting_id} with bot ID {bot_id}.")
            return True
        except Exception as e:
            self.logger.error(f"Error updating user meeting: {e}")
            return False

    async def process_fetch_calendar_events(self, session: AsyncSession) -> bool:
        self.logger.debug("Processing fetch calendar events.")
        try:
            
            start_time = int((datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp())
            end_time = int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())

            users = await self.get_all_users(session)

           

            # Filter users with grants
            users_with_grants = list(filter(lambda user: user.grant_id, users))

            self.logger.debug("Users with grants: %d", len(users_with_grants))
            user_ids = list(map(lambda user: user.id, users_with_grants))
            self.logger.debug("Users ID with grants: %d", len(user_ids))

            user_meetings = await self.get_user_meetings(user_ids, start_time, end_time, session)
            print("get user_meetings",user_meetings )

           

            self.logger.debug(f"Processing events for {len(users_with_grants)} users.")
            for user in users_with_grants:
                try:
                    user_bot_config = user.bot_config or {}
                    fetch_start_time = start_time
                    fetch_end_time = end_time

                    is_bot_disabled = False
                    if user_bot_config.get('isDisabled', False):
                        if start_time > user_bot_config.get('startTime', 0) and end_time < user_bot_config.get('endTime', 0):
                            is_bot_disabled = True
                        else:
                            bot_disable_start_time = user_bot_config.get('startTime', 0)
                            bot_disable_end_time = user_bot_config.get('endTime', 0)

                            if start_time < bot_disable_start_time and end_time > bot_disable_start_time:
                                fetch_end_time = bot_disable_start_time

                            if start_time < bot_disable_end_time and end_time > bot_disable_end_time:
                                fetch_start_time = bot_disable_end_time

                    if not is_bot_disabled:
                        grant_id = user.grant_id
                        

                        self.logger.debug(grant_id)
                        
                        calendars = self.nylas.calendars.find(identifier=grant_id, calendar_id='primary')
                      
                        self.logger.debug("Line 128")
                        primary_calendar_id = calendars.data.id
                        print("primary calendar id" , primary_calendar_id)
                        calendar_events_list_response = self.nylas.events.list(
                        grant_id,
                        query_params={
                        "start": str(fetch_start_time),
                        "end": str(fetch_end_time),
                        "calendar_id": primary_calendar_id
                        }
                        )


                        #print(calendar_events_list_response.data , "calendar_events_list_response")
                        calendar_events_list = calendar_events_list_response.data

                        print(calendar_events_list,"calendar_events_list")

                        if calendar_events_list:
                            for calendar_meet in calendar_events_list:

                                print(calendar_meet,"calendar_meet")
                                try:
                                    event_url = calendar_meet.conferencing.details['url']
                                    print("event_url",event_url)
                                except KeyError:
                                        event_url = None
                                

                                if event_url:
                                   
                                    organizer = calendar_meet.organizer
                                    participants = calendar_meet.participants
                                    print(organizer,"organizer")
                                    print(participants,"participants")
                                    
                                   

                                    if not any(p.email.lower() == organizer['email'].lower() for p in participants):
                                        participants.append({
                                            'email': organizer['email'],
                                            'name': organizer['name'],
                                            'status': 'noreply',
                                            'comment': None,
                                            'phoneNumber': None
                                        })
                                        print("I m insode evemt URL")


                                    emails_arr = [p.email.lower() for p in participants]
                                   
                                    print(emails_arr," this is emails_arr")

                                    is_bot_disabled_for_current_meeting = False

                                    print(user.email, "user email")

                                    matching_meeting = next(
                                        (meeting for meeting in user_meetings if meeting.calendar_uid == calendar_meet.ical_uid and
                                         meeting.start_time == calendar_meet.when.start_time and
                                         user.email in emails_arr),
                                        None
                                    )
                                    print(matching_meeting,"matching_meeting")

                                    if matching_meeting and matching_meeting.disable_bot:
                                        is_bot_disabled_for_current_meeting = True
                                        print(is_bot_disabled_for_current_meeting,"is_bot_disabled_for_current_meeting")

                                    if not is_bot_disabled_for_current_meeting:
                                        meeting_unique_identifier = self.calendar_service.get_meeting_unique_identifier_from_url(event_url, calendar_meet.conferencing.provider)
                                        print(meeting_unique_identifier,"meeting_unique_identifier")
                                        if not meeting_unique_identifier:
                                            meeting_unique_identifier = calendar_meet.ical_uid
                                            print(meeting_unique_identifier,"meeting_unique_identifier")

                                        cal_cache_key = f'sl_cal_{meeting_unique_identifier}'
                                        print(cal_cache_key,"cal_cache_key")
                                        cache_obj = await self.cache_manager.get(cal_cache_key)
                                        print(cache_obj,"cache_obj")
                                        
                                        if not cache_obj:
                                            print("not cache obj",cache_obj)
                                            event_start_time = (datetime.fromtimestamp(calendar_meet.when.start_time, timezone.utc) - timedelta(seconds=30)).isoformat()
                                            print(event_start_time,"event_start_time")
                                            organizer_user = next((u for u in users_with_grants if u.email.lower() == organizer['email'].lower()), None)
                                            print(organizer_user,"organizer_user")
                                            bot_config = organizer_user.bot_config if organizer_user else user.bot_config
                                            print("🚀 ~ bot_config:", bot_config)

                                            transcription_options = self.calendar_service.get_meeting_transcript_options(calendar_meet.conferencing.provider)
                                            print("🚀 ~ transcription_options:", transcription_options)
                                            bot_data = await self.calendar_service.connect_bot_to_event(event_url, event_start_time, bot_config, transcription_options)
                                            print( "HEre I 'm bot_data",bot_data['data'])
                                            bot_data['data']['eventLastCheckedTime'] = datetime.utcnow().timestamp()
                                            print("bot data with time", bot_data['data'])

                                            await self.cache_manager.set(cal_cache_key, str(bot_data['data']), 7200)

                                            

                                            participant_user_ids = [u.id for u in users_with_grants if u.email.lower() in emails_arr]
                                            print(participant_user_ids,"participant_user_ids")
                                            bot_user_cache_key = f'sl_bot_metadata_{bot_data['data']["id"]}'
                                            print(bot_user_cache_key,"bot_user_cache_key")
                                            connected_user_meetings = []

                                            for meeting in user_meetings:

                                                is_matching_identifier = False
                                                print("my meeting" , meeting)
                                                print("data1",meeting.uniq_identifier , meeting_unique_identifier)

                                                if meeting.uniq_identifier:

                                                    is_matching_identifier = meeting.uniq_identifier == meeting_unique_identifier
                                                    print(is_matching_identifier,"is_matching_identifier")
                                                else:
                                                    is_matching_identifier = meeting.calendar_uid == calendar_meet.ical_uid
                                                    print(is_matching_identifier,"is_matching_identifier")
    
                                                is_matching_time = meeting.start_time == calendar_meet.when.start_time
                                                print(is_matching_time,"is_matching_time")

                                                if is_matching_identifier and is_matching_time:
                                                    connected_user_meetings.append(meeting)
                                            print(connected_user_meetings,"connected_user_meetings")
                                            meeting_ids = [meeting.id for meeting in connected_user_meetings]
                                            print("meeting_ids",meeting_ids)

                                            await self.cache_manager.set(
                                                bot_user_cache_key,
                                                str({
                                                    'user_id': organizer_user.id if organizer_user else user.id,
                                                    'ical_uid': calendar_meet.ical_uid,
                                                    'identifier': meeting_unique_identifier,
                                                    'title': calendar_meet.title,
                                                    'provider': calendar_meet.conferencing.provider,
                                                    'userIds': participant_user_ids,
                                                    'lastStartTime': calendar_meet.when.start_time,
                                                    'eventStartTime': event_start_time,
                                                    'userTimeZone': calendar_meet.when.start_timezone,
                                                    'participants': participants,
                                                    'organizer': calendar_meet.organizer,
                                                    'meetingIds': meeting_ids
                                                }),
                                                18000
                                            )

                                            if connected_user_meetings:
                                                
                                                print("Inside connected_user_meetings:", connected_user_meetings)
                                                for meeting_obj in connected_user_meetings:
                                                    print("Processing meeting_obj:", meeting_obj)
                                                    try:
                                                        print("Updating user meeting with ID:", meeting_obj.id)
                                                        await self.update_user_meeting(meeting_obj.id, bot_data['data']['id'],session)
                                                        meeting_reminder_cache_key = f'meeting_reminder:{meeting_obj.id}:{meeting_obj.userId}'
                                                        print("Generated meeting_reminder_cache_key:", meeting_reminder_cache_key)
                                                        user_meeting_reminder_cache = await self.cache_manager.get(meeting_reminder_cache_key)
                                                        print("Fetched user_meeting_reminder_cache:", user_meeting_reminder_cache)

                                                        if not user_meeting_reminder_cache:
                                                            print("No reminder cache found for meeting_obj.id:", meeting_obj.id)
                                                            user_obj = next((u for u in users_with_grants if u.id == meeting_obj.userId), None)
                                                            print("Fetched user_obj:", user_obj)
                                                            await self.slack_notification_service.send_meeting_reminder_to_user(meeting_obj, user_obj, participants, organizer)
                                                            print("Sent meeting reminder to user.")
                                                        else:
                                                            print(f"Reminder already sent for meeting {meeting_obj.id} to user {meeting_obj.userId}. Skipping...")
                                                    except Exception as error:
                                                        print(f"Failed to send reminder for meeting {meeting_obj.id} to user {meeting_obj.userId}. - error => ", error)
                                        else:
                                            print('Event already logged')
                except Exception as error:
                    print(f'Error processing events for {user.email} - Failed - => {error}')

            return True
        except Exception as e:
            self.logger.error(f"Error processing calendar events: {e}")
            return False
