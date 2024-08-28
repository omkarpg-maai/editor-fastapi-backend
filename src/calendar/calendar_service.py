from typing import Dict, Any, Optional
from urllib.parse import urlparse, unquote
from fastapi import HTTPException
import httpx
import os

class CalendarService:
    
    def __init__(self, nylas_api_key: str, nylas_api_uri: str):
        self.nylas_api_key = nylas_api_key
        self.nylas_api_uri = nylas_api_uri

    async def connect_bot_to_event(self, event_url: str, event_start_time: str, bot_config: Dict[str, Any], transcription_options: Dict[str, Any]) -> Dict[str, Any]:
        api_url = f"{os.getenv('RECALL_API_BASE')}/v1/bot/"
        req_body = {
            "transcription_options": transcription_options,
            "chat": {
                "on_bot_join": {
                    "send_to": "everyone",
                    "message": "Hello! I am a Supaloops virtual assistant that will be taking notes during this call.",
                }
            },
            "automatic_leave": {
                "silence_detection": {
                    "timeout": 300,
                    "activate_after": 400,
                },
                "bot_detection": {
                    "using_participant_events": {
                        "timeout": 300,
                        "activate_after": 400,
                    }
                },
                "waiting_room_timeout": 530,
            },
            "meeting_url": event_url,
            "bot_name": bot_config.get("bot_name"),
            "join_at": event_start_time,
        }

        headers = {
            "Authorization": f"Token {os.getenv('RECALL_API_KEY')}",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(api_url, json=req_body, headers=headers)
                response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
                return {"data": response.json()}
            except httpx.HTTPStatusError as e:
                error_msg = e.response.json().get("detail", e.response.reason_phrase)
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get(0, {}).get("msg", "Unknown error")
                raise HTTPException(status_code=e.response.status_code, detail=error_msg)
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Request error: {e}")

    def get_meeting_unique_identifier_from_url(self, meeting_url: str, provider: str) -> Optional[str]:
        unique_id = None
        try:
            if provider == 'Microsoft Teams':
                # Handle Microsoft Teams URL parsing if needed
                pass
            else:
                # Parse URL to extract unique identifier
                parsed_url = urlparse(unquote(meeting_url))
                path_parts = parsed_url.path.strip('/').split('/')
                unique_id = path_parts[-1] if path_parts else None
                
        except Exception as e:
            # Handle any errors (optional: log the error)
            print(f"Error parsing meeting URL: {e}")
        
        return unique_id

    def get_meeting_transcript_options(self, provider: str) -> Dict[str, Any]:
        transcription_options = {'provider': 'meeting_captions'}
        
        if provider in ['Zoom Meeting', 'Slack']:
            transcription_options = {
                'provider': 'deepgram',
                'deepgram': {
                    'model': 'nova-2',
                    'smart_format': True,
                    'numerals': True
                }
            }
        
        return transcription_options
