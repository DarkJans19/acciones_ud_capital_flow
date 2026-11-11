from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictBool, StrictInt


class PreferenceIn(BaseModel):
    event_type: Literal[
        "market_open",
        "market_close",
        "proposals",
        "approval_requests",
        "price_changes",
        "execution_confirmations",
        "daily_summary",
    ]
    channel: Literal["in_app", "email", "sms", "telegram"]
    enabled: StrictBool


class PreferencesIn(BaseModel):
    preferences: list[PreferenceIn] = Field(min_length=1, max_length=28)


class PortfolioViewIn(BaseModel):
    view_type: Literal["table", "cards", "chart"]
    sort_by: Literal["symbol", "market_value", "gain_loss", "allocation"]
    sort_direction: Literal["asc", "desc"]
    hide_threshold: Decimal = Field(ge=0, le=Decimal("999999999.99"), decimal_places=2)


class OrderControlsIn(BaseModel):
    default_order_type: Literal["market", "limit", "stop", "stop_limit", "trailing_stop"]
    daily_order_limit: StrictInt = Field(ge=1, le=1000)
    high_order_threshold_usd: Decimal = Field(gt=0, le=Decimal("999999999.99"), decimal_places=2)
    extra_confirmation: StrictBool


class TelegramIn(BaseModel):
    chat_id: str | None = Field(max_length=100)


class InterestsIn(BaseModel):
    interests: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(
        min_length=1, max_length=20
    )
    level: Literal["beginner", "experienced"]
