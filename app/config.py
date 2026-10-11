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
    admin_telegram_usernames: str = Field(
        default="",
        validation_alias=AliasChoices("ADMIN_TELEGRAM_USERNAMES", "ADMIN_USERNAMES"),
    )
    admin_bootstrap_points: int = Field(
        default=0,
        validation_alias=AliasChoices("ADMIN_BOOTSTRAP_POINTS",),
    )
    admin_password: str = "change_me"
    secret_key: str = "dev-secret-change-me"
    host: str = "0.0.0.0"
    port: int = Field(default=8765, validation_alias=AliasChoices("PORT", "port"))
    database_url: str = "sqlite:///./data/bot.db"
    enable_web_admin: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_WEB_ADMIN", "WEB_ADMIN_ENABLED"),
    )
    public_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "PUBLIC_URL",
            "RENDER_EXTERNAL_URL",
            "WEBHOOK_BASE_URL",
        ),
    )
    webhook_path: str = Field(default="/telegram/webhook")
    webhook_secret: str = Field(default="", validation_alias=AliasChoices("WEBHOOK_SECRET",))
    github_backup_token: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_BACKUP_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"),
    )
    github_repo: str = Field(
        default="diaa20040-dotcom/account-transfer-bot",
        validation_alias=AliasChoices("GITHUB_REPO", "GITHUB_REPOSITORY"),
    )
    github_backup_branch: str = Field(
        default="main",
        validation_alias=AliasChoices("GITHUB_BACKUP_BRANCH",),
    )

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
