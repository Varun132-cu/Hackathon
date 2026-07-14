"""Telephony adapters. Live calling is explicitly gated by application settings."""

from dataclasses import dataclass
import ssl

from requests.adapters import HTTPAdapter
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client
from twilio.request_validator import RequestValidator

from app.config import Settings


@dataclass
class ProviderCall:
    sid: str
    status: str


class TLS12Adapter(HTTPAdapter):
    """Compatibility adapter for networks that stall on Python's TLS 1.3 negotiation."""

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        pool_kwargs["ssl_context"] = context
        return super().init_poolmanager(connections, maxsize, block, **pool_kwargs)


class TwilioVoiceProvider:
    def __init__(self, settings: Settings):
        settings.validate_live_call_settings()
        self.settings = settings
        http_client = TwilioHttpClient(timeout=20)
        http_client.session.mount("https://", TLS12Adapter())
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token, http_client=http_client)

    def place_outbound_call(self, phone_number: str, call_id: int) -> ProviderCall:
        base_url = self.settings.public_base_url.rstrip("/")
        media_url = base_url.replace("https://", "wss://", 1) + "/api/telephony/twilio/media"
        # Inline TwiML avoids a second HTTP fetch before the Media Stream begins.
        # The call still uses the signed status callback for persisted provider progress.
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<Response><Connect><Stream url="{media_url}" '
            f'statusCallback="{base_url}/api/telephony/twilio/stream-status?call_id={call_id}" '
            'statusCallbackMethod="POST">'
            f'<Parameter name="call_id" value="{call_id}" />'
            '</Stream></Connect></Response>'
        )
        call = self.client.calls.create(
            to=phone_number,
            from_=self.settings.twilio_from_number,
            twiml=twiml,
            status_callback=f"{base_url}/api/telephony/twilio/status?call_id={call_id}",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            timeout=20,
            record=False,
        )
        return ProviderCall(sid=call.sid, status=call.status)


def get_voice_provider(settings: Settings) -> TwilioVoiceProvider:
    if settings.voice_provider == "twilio":
        return TwilioVoiceProvider(settings)
    raise ValueError(f"Unsupported live voice provider: {settings.voice_provider}")


def validate_twilio_webhook(settings: Settings, path_and_query: str, params: dict[str, str], signature: str | None) -> bool:
    """Validate Twilio's signed callbacks against the configured public HTTPS URL."""
    if not signature or not settings.twilio_auth_token or not settings.public_base_url:
        return False
    url = f"{settings.public_base_url.rstrip('/')}{path_and_query}"
    return RequestValidator(settings.twilio_auth_token).validate(url, params, signature)
