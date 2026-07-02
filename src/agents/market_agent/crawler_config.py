from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


AccessMode = Literal["live_direct", "live_proxy", "offline_snapshot"]


@dataclass(slots=True)
class CrawlerConfig:
    access_mode: AccessMode = "live_direct"

    timeout_seconds: float = 20.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.5

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    verify_ssl: bool = True
    follow_redirects: bool = True

    proxy_env_enabled: bool = False
    proxies: dict[str, str] = field(default_factory=dict)
    use_system_env_by_default: bool = False

    snapshot_root: Path = Path("data/market_snapshots")
    snapshot_index_file: Path | None = None

    allowed_domains: list[str] = field(default_factory=list)
    denied_domains: list[str] = field(default_factory=list)

    def is_offline(self) -> bool:
        return self.access_mode == "offline_snapshot"

    def is_proxy_mode(self) -> bool:
        return self.access_mode == "live_proxy"

    def is_direct_mode(self) -> bool:
        return self.access_mode == "live_direct"