from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Portal de Catastro Municipal"
    operativo_database_url: str
    municipal_database_url: str
    idec_erp_database_url: str | None = None
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8
    cors_origins: str = (
        "https://avaluos.am2ps.com.bo,http://avaluos.am2ps.com.bo,"
        "https://bkavaluos.am2ps.com.bo,http://bkavaluos.am2ps.com.bo,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
