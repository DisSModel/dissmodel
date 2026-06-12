# dissmodel/executor/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Global platform settings.

    Pydantic reads values automatically from the .env file or from
    system environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore variables in .env that are not defined in this class
        extra="ignore",
    )

    # Default value when nothing is configured
    default_output_base: str = "./outputs"

    # Future settings can go here, e.g.:
    # redis_url: str = "redis://localhost:6379/0"
    # minio_endpoint: str = "localhost:9000"


settings = Settings()