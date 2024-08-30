from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
import os
from datetime import datetime
from src.calendar.calendar_cron_service import CalendarCronService
from dotenv import load_dotenv

from db.sessions import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

# Load environment variables from .env file
load_dotenv()


class SchedulerService:
    def __init__(self):
        self.logger = logging.getLogger("SchedulerService")
        self.logger.setLevel(logging.DEBUG)  # Set log level to DEBUG
        handler = logging.StreamHandler()  # Use StreamHandler to log to console
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self.logger.debug("Initializing SchedulerService")

        self.scheduler = BackgroundScheduler()
        self.logger.debug("BackgroundScheduler created")

        self.calendar_service = CalendarCronService(
            nylas_api_key=os.getenv("NYLAS_API_KEY"),
            nylas_api_uri=os.getenv("NYLAS_API_URI"),
        )

        self.logger.debug("CalendarCronService initialized")

        # Schedule the cron job
        self.logger.debug("Scheduling cron job")
        self.scheduler.add_job(
            self.handle_calendar_events_cron,
            trigger=IntervalTrigger(minutes=60),
            id="calendarEvents",
            name="Calendar Events Cron Job",
            replace_existing=True,
        )
        self.logger.debug("Cron job scheduled")

        self.scheduler.start()
        self.logger.debug("Scheduler started")

    async def handle_calendar_events_cron(self):
        self.logger.debug("Handling calendar events cron job")

        if os.getenv("RUN_CALENDAR_CRON") == "true":
            self.logger.debug(f"Calendar Event cron job ran at => {datetime.now()}")

        # Use async for to iterate over the async generator
        async for session in get_async_session():
            try:
                # Pass the session to process_fetch_calendar_events
                await self.calendar_service.process_fetch_calendar_events(session)
                self.logger.debug("process_fetch_calendar_events method completed")
                return True
            except Exception as e:
                self.logger.error(f"Calendar Event cron job failed - error => {e}")
                return False
        else:
            self.logger.debug(
                "RUN_CALENDAR_CRON environment variable is not set to 'true'"
            )
        return False
