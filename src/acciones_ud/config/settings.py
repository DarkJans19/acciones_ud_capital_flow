from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "Acciones UD API"
    app_env: str = "development"
    database_url: str | None = None
    migration_database_url: str | None = None
    database_connection: SecretStr | None = None
    client_id: SecretStr | None = None
    client_secret: SecretStr | None = None
    alpaca_base_url: str | None = None
    alpaca_auth_url: str | None = None

    alpaca_broker_api_key: SecretStr | None = None
    alpaca_broker_api_secret: SecretStr | None = None
    alpaca_broker_base_url: str | None = None
    alpaca_data_base_url: str | None = None
    alpaca_stream_base_url: str | None = None
    alpaca_data_feed: str | None = None
    price_staleness_threshold_seconds: str = "900"
    jwt_secret: SecretStr | None = None
    access_token_ttl_seconds: str | None = None
    refresh_token_ttl_seconds: str | None = None
    cors_allowed_origins: str | None = None
    totp_encryption_key: SecretStr | None = None
    price_streaming_enabled: str = "false"
    alert_engine_enabled: str = "true"
    alert_evaluation_interval_seconds: str = "60"
    market_clock_check_interval_seconds: str = "60"
    catalog_max_age_hours: str = "24"
    kyc_status_refresh_enabled: str = "false"
    kyc_status_refresh_interval_seconds: str = "900"
    kyc_status_cache_ttl_seconds: str = "60"
    dashboard_default_symbols: str = "AAPL,MSFT,AMZN,GOOGL,META,NVDA,TSLA,JPM,V,KO"
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None
    smtp_host: str | None = None
    smtp_port: str | None = None
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    telegram_bot_token: SecretStr | None = None
    log_level: str = "INFO"

    # Reads process environment first; falls back to a local .env for development.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    @model_validator(mode="after")
    def legacy_connection_names(self) -> "Settings":
        # Explicit compatibility with the existing environment; OAuth credentials are
        # never treated as legacy HTTP Basic keys.
        if self.database_url is None and self.database_connection:
            try:
                url = make_url(self.database_connection.get_secret_value())
                if url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
                    raise ValueError()
                query = dict(url.query)
                query.pop("sslmode", None)
                query["ssl"] = "require"
                self.database_url = url.set(
                    drivername="postgresql+asyncpg", query=query
                ).render_as_string(hide_password=False)
                if self.migration_database_url is None:
                    self.migration_database_url = self.database_url
            except Exception:
                raise ValueError("Invalid DATABASE_CONNECTION") from None
        if self.alpaca_broker_base_url is None and self.alpaca_base_url:
            self.alpaca_broker_base_url = self.alpaca_base_url
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [x.strip() for x in (self.cors_allowed_origins or "").split(",") if x.strip()]


class InitialAdminSettings(BaseSettings):
    email: str | None = None
    password_hash: SecretStr | None = None
    first_names: str | None = None
    last_names: str | None = None
    phone: str | None = None
    country: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="INITIAL_ADMIN_", extra="ignore", hide_input_in_errors=True
    )


REQUIRED = (
    "alpaca_broker_api_key",
    "alpaca_broker_api_secret",
    "alpaca_broker_base_url",
    "alpaca_data_base_url",
    "alpaca_stream_base_url",
    "alpaca_data_feed",
    "database_url",
    "migration_database_url",
    "jwt_secret",
    "access_token_ttl_seconds",
    "refresh_token_ttl_seconds",
    "cors_allowed_origins",
    "totp_encryption_key",
)


def require_api_settings(settings: Settings) -> None:
    """RF-02, RNF configuration: report variable names, never their values."""
    invalid: set[str] = set()
    for name in REQUIRED:
        if name in {"alpaca_broker_api_key", "alpaca_broker_api_secret"} and settings.client_id:
            continue
        value = getattr(settings, name)
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if value is None or not value.strip():
            invalid.add(name.upper())
    for name in ("database_url", "migration_database_url"):
        url = getattr(settings, name) or ""
        try:
            query = parse_qs(urlsplit(url).query)
        except ValueError:
            query = {}
        if (
            not url.startswith("postgresql+asyncpg://")
            or "sslmode" in query
            or (settings.app_env != "test" and query.get("ssl") != ["require"])
        ):
            invalid.add(name.upper())
    if "*" in (settings.cors_allowed_origins or ""):
        invalid.add("CORS_ALLOWED_ORIGINS")
    if settings.jwt_secret and len(settings.jwt_secret.get_secret_value().encode()) < 32:
        invalid.add("JWT_SECRET")
    if settings.cookie_samesite not in {"lax", "strict"}:
        invalid.add("COOKIE_SAMESITE")
    if settings.alpaca_data_feed not in {"iex", "sip", "delayed_sip"}:
        invalid.add("ALPACA_DATA_FEED")
    bounds = {
        "access_token_ttl_seconds": (1, 900),
        "refresh_token_ttl_seconds": (1, 604800),
        "price_staleness_threshold_seconds": (1, 86400),
        "alert_evaluation_interval_seconds": (10, 3600),
        "market_clock_check_interval_seconds": (1, 86400),
        "catalog_max_age_hours": (1, 8760),
        "kyc_status_refresh_interval_seconds": (60, 86400),
        "kyc_status_cache_ttl_seconds": (0, 3600),
        "smtp_port": (1, 65535),
    }
    for name, (low, high) in bounds.items():
        raw = getattr(settings, name)
        if name == "smtp_port" and not raw:
            continue
        try:
            if not low <= int(raw) <= high:
                invalid.add(name.upper())
        except (ValueError, TypeError):
            invalid.add(name.upper())
    for name in ("price_streaming_enabled", "alert_engine_enabled", "kyc_status_refresh_enabled"):
        if getattr(settings, name).lower() not in {"true", "false"}:
            invalid.add(name.upper())
    if settings.totp_encryption_key:
        try:
            Fernet(settings.totp_encryption_key.get_secret_value().encode())
        except (ValueError, TypeError):
            invalid.add("TOTP_ENCRYPTION_KEY")
    if settings.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        invalid.add("LOG_LEVEL")
    if settings.client_id:
        if not settings.client_id.get_secret_value().strip():
            invalid.add("CLIENT_ID")
        if not settings.client_secret or not settings.client_secret.get_secret_value().strip():
            invalid.add("CLIENT_SECRET")
        if not settings.alpaca_auth_url:
            invalid.add("ALPACA_AUTH_URL")
    if invalid:
        raise RuntimeError("Missing or invalid configuration: " + ", ".join(sorted(invalid)))


@dataclass(frozen=True)
class KycRefreshConfig:
    """Parsed KYC_STATUS_* settings; ``require_api_settings`` validated them at startup."""

    enabled: bool
    interval_seconds: int
    cache_ttl_seconds: int


def kyc_refresh_config(settings: Settings) -> KycRefreshConfig:
    return KycRefreshConfig(
        enabled=settings.kyc_status_refresh_enabled.lower() == "true",
        interval_seconds=int(settings.kyc_status_refresh_interval_seconds),
        cache_ttl_seconds=int(settings.kyc_status_cache_ttl_seconds),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
