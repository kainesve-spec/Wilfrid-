"""Wilfrid — opérations desktop génériques (P2.4)."""

from __future__ import annotations

from platforms.desktop.browser import (
    _chrome_executable,
    _chrome_monitor_bounds,
    _chrome_monitor_pixel_size,
    _chrome_monitor_top_left,
    _chrome_new_window_wait_timeout_s,
    _chrome_site_user_data_dir,
    _chrome_window_size,
    _cursor_executable,
    _open_url_in_chrome,
    open_binance_btc_in_chrome,
    open_claude_in_chrome,
    open_cursor_window,
)

__all__ = [
    "_chrome_executable",
    "_chrome_monitor_top_left",
    "_chrome_monitor_bounds",
    "_chrome_monitor_pixel_size",
    "_chrome_window_size",
    "_chrome_site_user_data_dir",
    "_chrome_new_window_wait_timeout_s",
    "_open_url_in_chrome",
    "open_claude_in_chrome",
    "open_binance_btc_in_chrome",
    "_cursor_executable",
    "open_cursor_window",
]
