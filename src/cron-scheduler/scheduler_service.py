from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
import os
from datetime import datetime
from calendar.calendar_cron_service import CalendarCronService


class SchedulerService:
    def __init__(self):
        self.logger = logging.getLogger("SchedulerService")
        self.scheduler = BackgroundScheduler()
        self.calendar_service = CalendarCronService()

        # Schedule the cron job
        self.scheduler.add_job(
            self.handle_calendar_events_cron,
            trigger=IntervalTrigger(minutes=5),
            id='calendarEvents',
            name='Calendar Events Cron Job',
            replace_existing=True
        )

        self.scheduler.start()

    def handle_calendar_events_cron(self):
        if os.getenv('RUN_CALENDAR_CRON') == 'true':
            self.logger.debug(f"Calendar Event cron job ran at => {datetime.now()}")

            try:
                # Call the calendar service method
                self.calendar_service.process_fetch_calendar_events()
            except Exception as e:
                self.logger.error(f'Calendar Event cron job failed - error => {e}')
