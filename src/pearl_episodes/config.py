from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from the environment and `.env`."""

    model_config = SettingsConfigDict(env_prefix="PEARL_", env_file=".env", extra="ignore")

    host: str = Field(description="Pearl device host or IP")
    username: str = "admin"
    password: str = ""
    api_prefix: str = "/api/v2.0"
    verify_tls: bool = False
    episodes_recordings_dir: Path = Path("./recordings")
    episodes_output_dir: Path = Path("./episodes")

    @property
    def base_url(self) -> str:
        return f"https://{self.host}{self.api_prefix}"
