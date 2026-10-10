from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    bot_username: str = ""
    admin_telegram_ids: str = Field(
        default="",
        validation_alias=AliasChoices("ADMIN_TELEGRAM_IDS", "ADMIN_IDS"),
    )
    admin_telegram_usernames: str = ""
    admin_password: str = "change_me"
    secret_key: str = "dev-secret-change-me"
    host: str = "0.0.0.0"
    port: int = Field(default=8765, validation_alias=AliasChoices("PORT", "port"))
    database_url: str = "sqlite:///./data/bot.db"

    @property
    def admin_ids(self) -> list[int]:
        if not self.admin_telegram_ids.strip():
            return []
        return [int(x.strip()) for x in self.admin_telegram_ids.split(",") if x.strip()]

    @property
    def admin_usernames(self) -> list[str]:
        if not self.admin_telegram_usernames.strip():
            return []
        return [
            x.strip().lstrip("@")
            for x in self.admin_telegram_usernames.split(",")
            if x.strip()
        ]


settings = Settings()
