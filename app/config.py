from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- POI suitability judge (local Ollama model) ----
    enable_llm: bool = True
    llm_model: str = "llama3.2"                  # any model you've `ollama pull`ed
    ollama_host: str = "http://localhost:11434"

    # ---- Coordinate validation bounds ----
    lat_min: float = -90.0
    lat_max: float = 90.0
    lon_min: float = -180.0
    lon_max: float = 180.0


settings = Settings()
