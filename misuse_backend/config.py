from pydantic_settings import BaseSettings, SettingsConfigDict
import logging


class Settings(BaseSettings):
    HOST: str = '0.0.0.0'
    PORT: int = 8080
    DEBUG: bool = True
    WORKERS: int = 1
    LOGGING_LEVEL: int = logging.INFO

    IPINFO_ACCESS_TOKEN: str = ''
    RETURN_TYPE: str = 'png'

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')



settings = Settings()
