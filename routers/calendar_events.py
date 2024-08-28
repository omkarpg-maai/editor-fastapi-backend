from fastapi import APIRouter
from src.cron_scheduler.scheduler_service import SchedulerService

router = APIRouter()

# Create a global instance of SchedulerService
scheduler_service = SchedulerService()

@router.get("/cron/handle-calendar-events")
async def handle_calendar_events():
    # Directly call the async method
    await scheduler_service.handle_calendar_events_cron()
    return {"message": "Calendar events handled 2"}
