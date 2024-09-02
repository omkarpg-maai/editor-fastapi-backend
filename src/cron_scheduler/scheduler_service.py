import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
import os
from datetime import datetime
from src.calendar.calendar_cron_service import CalendarCronService
from dotenv import load_dotenv
from db.sessions import get_async_session

# Load environment variables from .env file
load_dotenv()


class SchedulerService:
    def __init__(self):
        self.logger = logging.getLogger("SchedulerService")
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
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

        self.loop = asyncio.get_event_loop()
        self.logger.debug("Asyncio event loop retrieved")

        # Schedule the cron job
        self.logger.debug("Scheduling cron job")
        self.scheduler.add_job(
            self.run_async_task,
            trigger=IntervalTrigger(seconds=10),
            id="calendarEvents",
            name="Calendar Events Cron Job",
            replace_existing=True,
        )
        self.logger.debug("Cron job scheduled")

        self.scheduler.start()
        self.logger.debug("Scheduler started")

    def run_async_task(self):
        self.logger.debug("Running async task")
        asyncio.run_coroutine_threadsafe(self.handle_calendar_events_cron(), self.loop)

    async def handle_calendar_events_cron(self):
        self.logger.debug("Handling calendar events cron job")

        if os.getenv("RUN_CALENDAR_CRON") == "true":
            self.logger.debug(f"Calendar Event cron job ran at => {datetime.now()}")

        async for session in get_async_session():
            try:
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

    def start(self):
        self.scheduler.start()
        self.logger.debug("Scheduler started")

    def shutdown(self):
        self.scheduler.shutdown()
        self.logger.debug("Scheduler stopped")
