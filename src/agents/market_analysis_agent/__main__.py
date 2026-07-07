from __future__ import annotations

import argparse
import json

from .agent import MarketAnalysisAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run market analysis agent")
    parser.add_argument(
        "--source-json",
        dest="source_json_path",
        default=None,
        help="Path to market_agent JSON report",
    )
    args = parser.parse_args()

    agent = MarketAnalysisAgent()
    result = agent.run(source_json_path=args.source_json_path)

    print(result.message)
    print(json.dumps(result.payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()