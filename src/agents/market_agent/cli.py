from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.agents.market_agent.crawler_config import CrawlerConfig
from src.agents.market_agent.pipeline import MarketAgent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run-market-agent",
        description="Run market_agent for a list of platforms from a JSON file.",
    )
    parser.add_argument(
        "input_json",
        help="Path to input JSON file with platforms payload.",
    )
    parser.add_argument(
        "--access-mode",
        default="live_direct",
        choices=["live_direct", "live_proxy", "offline_snapshot"],
        help="Crawler access mode.",
    )
    parser.add_argument(
        "--snapshot-root",
        default="data/market_snapshots",
        help="Snapshot directory for offline_snapshot mode.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum retry attempts per request.",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=1.5,
        help="Retry backoff in seconds.",
    )
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        help="HTTP User-Agent header.",
    )
    parser.add_argument(
        "--verify-ssl",
        dest="verify_ssl",
        action="store_true",
        default=True,
        help="Enable SSL certificate verification.",
    )
    parser.add_argument(
        "--no-verify-ssl",
        dest="verify_ssl",
        action="store_false",
        help="Disable SSL certificate verification.",
    )
    parser.add_argument(
        "--follow-redirects",
        dest="follow_redirects",
        action="store_true",
        default=True,
        help="Follow HTTP redirects.",
    )
    parser.add_argument(
        "--no-follow-redirects",
        dest="follow_redirects",
        action="store_false",
        help="Disable HTTP redirects.",
    )
    parser.add_argument(
        "--proxy-env-enabled",
        action="store_true",
        default=False,
        help="Enable proxy environment usage in crawler logic.",
    )
    parser.add_argument(
        "--use-system-env-by-default",
        action="store_true",
        default=False,
        help="Allow requests/session trust_env behavior where supported by crawler.",
    )
    parser.add_argument(
        "--allowed-domain",
        action="append",
        default=[],
        help="Allowed domain filter. Repeat flag to pass multiple values.",
    )
    parser.add_argument(
        "--denied-domain",
        action="append",
        default=[],
        help="Denied domain filter. Repeat flag to pass multiple values.",
    )
    return parser


def _load_input_payload(path: Path) -> dict | list:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_platforms(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        platforms = payload
    elif isinstance(payload, dict):
        if "platforms" in payload:
            platforms = payload["platforms"]
        else:
            raise ValueError("Input payload must contain a 'platforms' list.")
    else:
        raise ValueError("Input JSON must contain a top-level object or list.")

    if not isinstance(platforms, list):
        raise ValueError("Input payload must contain a 'platforms' list.")

    normalized: list[dict] = []
    for index, item in enumerate(platforms):
        if not isinstance(item, dict):
            raise ValueError(f"Platform entry at index {index} must be an object.")
        normalized.append(item)

    return normalized


def _build_crawler_config(args: argparse.Namespace) -> CrawlerConfig:
    return CrawlerConfig(
        access_mode=args.access_mode,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        user_agent=args.user_agent,
        verify_ssl=args.verify_ssl,
        follow_redirects=args.follow_redirects,
        proxy_env_enabled=args.proxy_env_enabled,
        use_system_env_by_default=args.use_system_env_by_default,
        snapshot_root=Path(args.snapshot_root),
        allowed_domains=list(args.allowed_domain),
        denied_domains=list(args.denied_domain),
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input_json).expanduser().resolve()
    if not input_path.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"Input file not found: {str(input_path)}",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    try:
        payload = _load_input_payload(input_path)
        platforms = _resolve_platforms(payload)
        crawler_config = _build_crawler_config(args)

        agent = MarketAgent()
        result = agent.run(
            platforms=platforms,
            crawler_config=crawler_config,
        )

        print(
            json.dumps(
                {
                    "status": result.status,
                    "agent_name": result.agent_name,
                    "payload": result.payload,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0 if result.status == "success" else 2

    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())