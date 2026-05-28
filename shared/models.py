from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Platform = Literal["blinkit", "zepto", "swiggy_instamart"]
AlertType = Literal["OOS", "PRICE_DROP", "PRICE_RISE", "BACK_IN_STOCK", "NEW_LISTING"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WatchlistItem(BaseModel):
    sku_name: str
    platforms: list[Platform]
    pincodes: list[str]
    price_drop_threshold_pct: float = 5.0
    alert_on_oos: bool = True


class PriceSnapshot(BaseModel):
    sku: str
    platform: str
    pincode: str
    price: Optional[float] = None
    available: bool = True
    delivery_min: Optional[int] = None
    scraped_at: str = Field(default_factory=_now_iso)


class AlertEntry(BaseModel):
    timestamp: str = Field(default_factory=_now_iso)
    sku: str
    platform: str
    pincode: str
    alert_type: AlertType
    alert_text: str
    recommendation: str


class RankedResult(BaseModel):
    platform: str
    price: Optional[float] = None
    delivery_min: Optional[int] = None
    available: bool = True
    savings_vs_max: Optional[float] = None  # rupees saved vs most expensive option
    reasoning_note: str = ""


class ScrapeResult(BaseModel):
    url: str
    platform: str
    raw_markdown: str = ""
    success: bool
    error_msg: Optional[str] = None
    cached: bool = False
