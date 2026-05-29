from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://sewastaff:sewastaff123@sewastaff-postgres:5432/sewastaff"
    REDIS_URL: str = "redis://sewastaff-redis:6379/0"
    WAHA_BASE_URL: str = "http://app-waha-1:3000"
    WAHA_API_KEY: str = ""
    WAHA_SESSION_IDS: str = "default"
    OPENROUTER_API_KEY: str = ""
    ADMIN_SECRET_KEY: str = "sewastaff-admin-2026"

    @property
    def session_ids_list(self) -> list[str]:
        return [s.strip() for s in self.WAHA_SESSION_IDS.split(",") if s.strip()]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
