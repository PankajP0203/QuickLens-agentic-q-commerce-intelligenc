from __future__ import annotations

from urllib.parse import quote_plus

# Constraint: Indiranagar Bangalore pincode, used as URL param for Blinkit
DEFAULT_PINCODE = "560038"

SUPPORTED_PLATFORMS = ["blinkit", "zepto", "swiggy_instamart"]


def build_search_url(platform: str, query: str, pincode: str = DEFAULT_PINCODE) -> str:
    """Return the search URL for a given platform and query string."""
    platform = platform.lower().strip()
    dispatch = {
        "blinkit": _blinkit_url,
        "zepto": _zepto_url,
        "swiggy_instamart": _swiggy_instamart_url,
    }
    if platform not in dispatch:
        raise ValueError(f"Unknown platform '{platform}'. Supported: {SUPPORTED_PLATFORMS}")
    return dispatch[platform](query, pincode)


def _blinkit_url(query: str, pincode: str = DEFAULT_PINCODE) -> str:
    # Blinkit accepts pincode as a URL param; this also triggers the correct
    # location context in the scraping browser session.
    return f"https://blinkit.com/s/?q={quote_plus(query)}&pincode={pincode}"


def _zepto_url(query: str, pincode: str = DEFAULT_PINCODE) -> str:
    return f"https://www.zeptonow.com/search?query={quote_plus(query)}"


def _swiggy_instamart_url(query: str, pincode: str = DEFAULT_PINCODE) -> str:
    return f"https://www.swiggy.com/instamart/search?query={quote_plus(query)}"
