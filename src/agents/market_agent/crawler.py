from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests

from src.agents.market_agent.crawler_config import CrawlerConfig


@dataclass(slots=True)
class CrawlDocument:
    source_url: str
    final_url: str
    status_code: int | None
    html: str
    content_type: str
    encoding: str | None
    access_mode: str
    fetched_at_ts: float
    meta: dict = field(default_factory=dict)


class MarketCrawlerError(RuntimeError):
    pass


class SnapshotNotFoundError(MarketCrawlerError):
    pass


class MarketCrawler:
    def __init__(self, config: CrawlerConfig) -> None:
        self.config = config

    def fetch_many(self, urls: Iterable[str]) -> list[CrawlDocument]:
        return [self.fetch_one(url) for url in urls]

    def fetch_one(self, url: str) -> CrawlDocument:
        if self.config.is_offline():
            return self._fetch_from_snapshot(url)
        return self._fetch_live(url)

    def _fetch_live(self, url: str) -> CrawlDocument:
        self._validate_domain(url)
        session = self._build_session()

        last_error: Exception | None = None

        for attempt in range(1, self.config.max_retries + 2):
            try:
                response = session.get(
                    url,
                    timeout=self.config.timeout_seconds,
                    allow_redirects=self.config.follow_redirects,
                    verify=self.config.verify_ssl,
                )
                response.raise_for_status()

                html = response.text or ""
                content_type = response.headers.get("Content-Type", "text/html")

                return CrawlDocument(
                    source_url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    html=html,
                    content_type=content_type,
                    encoding=response.encoding,
                    access_mode=self.config.access_mode,
                    fetched_at_ts=time.time(),
                    meta={
                        "headers": dict(response.headers),
                        "attempt": attempt,
                        "used_proxy_mode": self.config.is_proxy_mode(),
                        "snapshot_path": None,
                    },
                )
            except Exception as exc:
                last_error = exc
                if attempt <= self.config.max_retries:
                    time.sleep(self.config.retry_backoff_seconds * attempt)
                else:
                    break

        raise MarketCrawlerError(
            f"Failed to fetch URL after retries: {url}. Last error: {last_error}"
        )

    def _fetch_from_snapshot(self, url: str) -> CrawlDocument:
        snapshot_path = self._resolve_snapshot_path(url)
        if not snapshot_path.exists():
            raise SnapshotNotFoundError(
                f"Snapshot not found for URL: {url}. Expected file: {snapshot_path}"
            )

        html = snapshot_path.read_text(encoding="utf-8")

        return CrawlDocument(
            source_url=url,
            final_url=url,
            status_code=200,
            html=html,
            content_type="text/html",
            encoding="utf-8",
            access_mode=self.config.access_mode,
            fetched_at_ts=time.time(),
            meta={
                "headers": {},
                "attempt": 1,
                "used_proxy_mode": False,
                "snapshot_path": str(snapshot_path),
            },
        )

    def _build_session(self) -> requests.Session:
        session = requests.Session()

        session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            }
        )

        if self.config.is_direct_mode():
            session.trust_env = self.config.use_system_env_by_default
            if not session.trust_env:
                session.proxies = {}
            return session

        if self.config.is_proxy_mode():
            session.trust_env = self.config.proxy_env_enabled
            if self.config.proxies:
                session.proxies.update(self.config.proxies)
                if not self.config.proxy_env_enabled:
                    session.trust_env = False
            return session

        session.trust_env = False
        session.proxies = {}
        return session

    def _resolve_snapshot_path(self, url: str) -> Path:
        if self.config.snapshot_index_file and self.config.snapshot_index_file.exists():
            mapping = json.loads(self.config.snapshot_index_file.read_text(encoding="utf-8"))
            mapped_path = mapping.get(url)
            if mapped_path:
                return Path(mapped_path)

        parsed = urlparse(url)
        domain = parsed.netloc.replace(":", "_")
        path = parsed.path.strip("/") or "index"
        path = path.replace("/", "__")
        filename = f"{domain}__{path}.html"

        return self.config.snapshot_root / filename

    def _validate_domain(self, url: str) -> None:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if self.config.allowed_domains:
            if not any(domain.endswith(allowed.lower()) for allowed in self.config.allowed_domains):
                raise MarketCrawlerError(f"Domain not allowed: {domain}")

        if self.config.denied_domains:
            if any(domain.endswith(denied.lower()) for denied in self.config.denied_domains):
                raise MarketCrawlerError(f"Domain denied: {domain}")