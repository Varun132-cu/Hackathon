from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DebtAssist API"
    database_url: str = "sqlite:///./debtassist.db"
    allowed_origins: str = "http://localhost:5173"
    voice_provider: str = "mock"
    live_calls_enabled: bool = False
    public_base_url: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    organisation_name: str = "Your Organisation"
    live_ai_voice_enabled: bool = False
    openai_api_key: str = ""
    openai_realtime_model: str = "gpt-realtime"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    def validate_live_call_settings(self) -> None:
        if not self.live_calls_enabled:
            raise ValueError("Live calling is disabled. Set LIVE_CALLS_ENABLED=true only after compliance approval.")
        if self.voice_provider != "twilio":
            raise ValueError("The configured voice provider is not supported for live calls.")
        if not all([self.public_base_url, self.twilio_account_sid, self.twilio_auth_token, self.twilio_from_number]):
            raise ValueError("Twilio live calling needs PUBLIC_BASE_URL, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER.")
        if not self.public_base_url.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL must use HTTPS for provider webhooks.")

    def validate_live_ai_settings(self) -> None:
        self.validate_live_call_settings()
        if not self.live_ai_voice_enabled:
            raise ValueError("Live AI voice is disabled. Set LIVE_AI_VOICE_ENABLED=true for a controlled test.")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for the live AI voice bridge.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
