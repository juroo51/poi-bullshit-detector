from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Crowd Tester thresholds / profile
    crowd_p95_ms: float = 300.0
    crowd_error_rate: float = 0.01          # 1%
    crowd_concurrency: int = 50
    crowd_duration_s: float = 10.0
    crowd_request_timeout_s: float = 5.0

    # Bullshit Detector
    enable_llm_sanity: bool = True
    anthropic_api_key: str | None = None    # falls back to ANTHROPIC_API_KEY env

    # Sanity bounds for navigation payloads
    lat_min: float = -90.0
    lat_max: float = 90.0
    lon_min: float = -180.0
    lon_max: float = 180.0


settings = Settings()
