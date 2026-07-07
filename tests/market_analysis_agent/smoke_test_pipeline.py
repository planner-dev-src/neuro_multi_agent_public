from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from src.agents.market_analysis_agent.pipeline import run_market_analysis


def _project_root() -> Path:
    return Path.cwd()


def _reports_root() -> Path:
    return _project_root() / "data" / "reports" / "market_agent"


def _analysis_reports_root() -> Path:
    return _project_root() / "data" / "reports" / "market_analysis_agent"


def _latest_market_report_json(reports_root: Path) -> Path:
    if not reports_root.exists():
        raise FileNotFoundError(f"Market agent reports root does not exist: {reports_root}")

    files = [path for path in reports_root.glob("market_agent_*.json") if path.is_file()]
    if not files:
        raise FileNotFoundError(
            f"No market_agent_*.json files found in: {reports_root}"
        )

    return max(files, key=lambda p: p.stat().st_mtime)


def _to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    raise TypeError(f"Cannot convert object to dict: {type(obj)!r}")


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _len_of(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    return 0


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception:
        return default


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _print_json(title: str, payload: dict[str, Any]) -> None:
    if title:
        print(title)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _extract_bundle(result: Any) -> Any:
    if isinstance(result, dict):
        bundle = result.get("bundle")
        _assert(bundle is not None, "run_market_analysis result must contain 'bundle'")
        return bundle

    bundle = _get_attr(result, "bundle", None)
    _assert(bundle is not None, "run_market_analysis result must contain bundle attribute")
    return bundle


def _extract_summary(result: Any, bundle: Any) -> dict[str, Any]:
    result_summary = result.get("summary") if isinstance(result, dict) else _get_attr(result, "summary", None)
    bundle_summary = _get_attr(bundle, "summary", None)

    if isinstance(result_summary, dict) and result_summary:
        return result_summary
    if isinstance(bundle_summary, dict) and bundle_summary:
        return bundle_summary
    return {}


def _extract_counts(result: Any, bundle: Any) -> dict[str, Any]:
    summary = _extract_summary(result, bundle)

    offer_features = _get_attr(bundle, "offer_features", [])
    trend_signals = _get_attr(bundle, "trend_signals", [])
    competitive_gaps = _get_attr(bundle, "competitive_gaps", [])
    platform_aggregates = _get_attr(bundle, "platform_aggregates", [])
    platform_positioning = _get_attr(bundle, "platform_positioning", [])

    catalog_items_total_raw = summary.get(
        "catalog_items_total_raw",
        _get_attr(bundle, "catalog_items_total_raw", 0),
    )
    catalog_items_total_after_dedup = summary.get(
        "catalog_items_total_after_dedup",
        _get_attr(bundle, "catalog_items_total_after_dedup", 0),
    )
    catalog_items_total_deduped = summary.get(
        "catalog_items_total_deduped",
        _get_attr(bundle, "catalog_items_total_deduped", 0),
    )
    catalog_items_total_noise = summary.get(
        "catalog_items_total_noise",
        _get_attr(bundle, "catalog_items_total_noise", 0),
    )
    catalog_items_total_kept = summary.get(
        "catalog_items_total_kept",
        _get_attr(bundle, "catalog_items_total_kept", 0),
    )

    counts = {
        "platforms_total": summary.get("platforms_total", _get_attr(bundle, "platforms_total", 0)),
        "catalog_items_total_raw": catalog_items_total_raw,
        "catalog_items_total_after_dedup": catalog_items_total_after_dedup,
        "catalog_items_total_deduped": catalog_items_total_deduped,
        "catalog_items_total_noise": catalog_items_total_noise,
        "catalog_items_total_kept": catalog_items_total_kept,
        "raw_offer_features_total": summary.get("raw_offer_features_total", 0),
        "deduped_offer_features_total": summary.get("deduped_offer_features_total", 0),
        "filtered_offer_features_total": summary.get(
            "filtered_offer_features_total",
            _len_of(offer_features),
        ),
        "trend_signals_total": summary.get("trend_signals_total", _len_of(trend_signals)),
        "competitive_gaps_total": summary.get("competitive_gaps_total", _len_of(competitive_gaps)),
        "platform_aggregates_total": summary.get("platform_aggregates_total", _len_of(platform_aggregates)),
        "platform_positioning_total": summary.get("platform_positioning_total", _len_of(platform_positioning)),
        "min_quality_score": _safe_float(summary.get("min_quality_score", 0.0), 0.0),
    }

    return counts


def _validate_result_shape(result: Any, bundle: Any) -> dict[str, Any]:
    _assert(isinstance(result, dict), "run_market_analysis must return dict[str, Any]")
    _assert("bundle" in result, "run_market_analysis result must contain 'bundle'")
    _assert("summary" in result, "run_market_analysis result must contain 'summary'")
    _assert("files" in result, "run_market_analysis result must contain 'files'")

    files = result.get("files")
    summary = _extract_summary(result, bundle)

    _assert(_get_attr(bundle, "generated_at_utc", ""), "MarketAnalysisBundle.generated_at_utc must be non-empty")
    _assert(isinstance(summary, dict), "summary must be dict")
    _assert(isinstance(files, dict), "files must be dict")

    return {
        "result_has_bundle": 1,
        "result_has_summary": 1,
        "result_has_files": 1,
    }


def _validate_positioning(bundle: Any) -> dict[str, Any]:
    items = _get_attr(bundle, "platform_positioning", None) or []

    checked = 0
    with_core = 0
    with_statement = 0
    with_evidence = 0

    for item in items:
        checked += 1
        platform_name = _get_attr(item, "platform_name", "")
        core_signals = _get_attr(item, "core_signals", []) or []
        positioning_statement = _get_attr(item, "positioning_statement", "") or ""
        evidence_items = _get_attr(item, "evidence_items", []) or []

        _assert(bool(platform_name), "PlatformPositioning.platform_name must be non-empty")
        _assert(isinstance(core_signals, list), "PlatformPositioning.core_signals must be list")
        _assert(isinstance(evidence_items, list), "PlatformPositioning.evidence_items must be list")

        if core_signals:
            with_core += 1
            _assert(
                all(isinstance(x, str) and x.strip() for x in core_signals),
                f"PlatformPositioning.core_signals contains invalid values for {platform_name!r}",
            )

        if positioning_statement.strip():
            with_statement += 1

        if evidence_items:
            with_evidence += 1
            _assert(
                all(isinstance(x, str) and x.strip() for x in evidence_items),
                f"PlatformPositioning.evidence_items contains invalid values for {platform_name!r}",
            )

    _assert(checked > 0, "platform_positioning must not be empty")
    _assert(with_statement > 0, "At least one positioning_statement must be populated")

    return {
        "platform_positioning_checked": checked,
        "positioning_with_core_signals": with_core,
        "positioning_with_statement": with_statement,
        "positioning_with_evidence": with_evidence,
    }


def _validate_trend_signals(bundle: Any) -> dict[str, Any]:
    items = _get_attr(bundle, "trend_signals", None) or []
    checked = 0
    core_signal_trends = 0

    for item in items:
        checked += 1
        trend_type = _get_attr(item, "trend_type", "")
        topic = _get_attr(item, "topic", "")
        platforms_count = _get_attr(item, "platforms_count", 0)

        _assert(bool(topic), "TrendSignal.topic must be non-empty")
        _assert(int(platforms_count) >= 0, "TrendSignal.platforms_count must be >= 0")

        if trend_type == "core_signal":
            core_signal_trends += 1

    return {
        "trend_signals_checked": checked,
        "trend_signals_core_signal_type": core_signal_trends,
    }


def _validate_bundle_contract(bundle: Any) -> dict[str, Any]:
    metadata = _get_attr(bundle, "metadata", {}) or {}
    contract = metadata.get("contract", {}) if isinstance(metadata, dict) else {}

    contract_core_enabled = contract.get("offer_features_core_signals_enabled")
    trend_types = contract.get("trend_types", [])
    gap_types = contract.get("gap_types", [])

    _assert(isinstance(metadata, dict), "MarketAnalysisBundle.metadata must be dict")
    _assert(isinstance(contract, dict), "MarketAnalysisBundle.metadata.contract must be dict")

    if contract:
        _assert(
            contract_core_enabled is True,
            "metadata.contract.offer_features_core_signals_enabled must be True",
        )
        _assert(
            "core_signal" in trend_types,
            "metadata.contract.trend_types must include 'core_signal'",
        )
        _assert(
            "core_signal" in gap_types,
            "metadata.contract.gap_types must include 'core_signal'",
        )

    return {
        "bundle_contract_present": 1 if contract else 0,
        "bundle_contract_core_signals_enabled": 1 if contract_core_enabled is True else 0,
    }


def _validate_counts(counts: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    raw_total = int(counts["catalog_items_total_raw"])
    after_dedup = int(counts["catalog_items_total_after_dedup"])
    deduped = int(counts["catalog_items_total_deduped"])
    noise = int(counts["catalog_items_total_noise"])
    kept = int(counts["catalog_items_total_kept"])

    _assert(int(counts["platforms_total"]) > 0, "platforms_total must be > 0")
    _assert(raw_total > 0, "catalog_items_total_raw must be > 0")
    _assert(after_dedup >= 0, "catalog_items_total_after_dedup must be >= 0")
    _assert(after_dedup <= raw_total, "catalog_items_total_after_dedup must be <= raw_total")

    # Дедупликация могла сработать на уровне market_agent (normalizer.py) ДО
    # формирования MarketAnalysisBundle. В таком случае deduped == 0 на этом
    # этапе — норма, а не ошибка.
    if deduped > 0:
        _assert(deduped == raw_total - after_dedup, "catalog_items_total_deduped mismatch")

    _assert(noise >= 0, "catalog_items_total_noise must be >= 0")
    _assert(kept >= 0, "catalog_items_total_kept must be >= 0")
    _assert(noise + kept == after_dedup, "noise + kept must equal after_dedup")
    _assert(
        int(counts["platform_aggregates_total"]) == int(counts["platforms_total"]),
        "platform_aggregates_total must equal platforms_total",
    )
    _assert(
        int(counts["platform_positioning_total"]) == int(counts["platforms_total"]),
        "platform_positioning_total must equal platforms_total",
    )

    deduped_offer_features_total = int(counts["deduped_offer_features_total"])
    filtered_offer_features_total = int(counts["filtered_offer_features_total"])

    if deduped_offer_features_total > 0:
        _assert(
            filtered_offer_features_total <= deduped_offer_features_total,
            "filtered_offer_features_total must be <= deduped_offer_features_total",
        )

    if int(counts["trend_signals_total"]) == 0:
        warnings.append("No trend_signals produced.")

    if int(counts["competitive_gaps_total"]) == 0:
        warnings.append("No competitive_gaps produced.")

    if filtered_offer_features_total == 0:
        warnings.append("No filtered_offer_features produced.")

    return warnings


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _validate_output_files(result: Any, bundle: Any) -> dict[str, Any]:
    files = result.get("files") if isinstance(result, dict) else _get_attr(result, "files", None)
    _assert(isinstance(files, dict), "files must be dict")

    expected_keys = {
        "json_report",
        "offer_features_csv",
        "platform_positioning_csv",
        "trend_signals_csv",
        "competitive_gaps_csv",
        "markdown_report",
        "rag_chunks_json",
    }
    _assert(
        expected_keys.issubset(files.keys()),
        f"files must contain keys: {sorted(expected_keys)}",
    )

    resolved_paths: dict[str, Path] = {}
    for key in expected_keys:
        raw_path = files.get(key)
        _assert(isinstance(raw_path, str) and raw_path.strip(), f"files[{key!r}] must be non-empty path string")
        path = Path(raw_path).resolve()
        resolved_paths[key] = path
        _assert(path.exists(), f"Output file does not exist: {path}")
        _assert(path.is_file(), f"Output path must be a file: {path}")

    json_report_path = resolved_paths["json_report"]
    offer_features_csv_path = resolved_paths["offer_features_csv"]
    platform_positioning_csv_path = resolved_paths["platform_positioning_csv"]
    trend_signals_csv_path = resolved_paths["trend_signals_csv"]
    competitive_gaps_csv_path = resolved_paths["competitive_gaps_csv"]
    markdown_report_path = resolved_paths["markdown_report"]

    json_payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    _assert(isinstance(json_payload, dict), "json_report must contain top-level JSON object")

    markdown_text = markdown_report_path.read_text(encoding="utf-8")
    _assert(markdown_text.strip(), "markdown_report must not be empty")
    _assert("# Исполнительный обзор рынка" in markdown_text, "markdown_report missing title")
    _assert("## Обзор" in markdown_text, "markdown_report missing overview section")
    _assert(
        "## Canonical AI differentiation axes" in markdown_text,
        "markdown_report missing canonical core axes section",
    )
    _assert("## Покрытие направлений" in markdown_text, "markdown_report missing topic coverage section")
    _assert("## Позиционирование платформ" in markdown_text, "markdown_report missing platform positioning section")
    _assert("## Гипотезы по gap-направлениям" in markdown_text, "markdown_report missing gap hypotheses section")

    offer_rows = _read_csv_rows(offer_features_csv_path)
    positioning_rows = _read_csv_rows(platform_positioning_csv_path)
    trend_rows = _read_csv_rows(trend_signals_csv_path)
    gap_rows = _read_csv_rows(competitive_gaps_csv_path)

    _assert(
        len(offer_rows) == _len_of(_get_attr(bundle, "offer_features", [])),
        "offer_features_csv row count must equal bundle.offer_features size",
    )
    _assert(
        len(positioning_rows) == _len_of(_get_attr(bundle, "platform_positioning", [])),
        "platform_positioning_csv row count must equal bundle.platform_positioning size",
    )
    _assert(
        len(trend_rows) == _len_of(_get_attr(bundle, "trend_signals", [])),
        "trend_signals_csv row count must equal bundle.trend_signals size",
    )
    _assert(
        len(gap_rows) == _len_of(_get_attr(bundle, "competitive_gaps", [])),
        "competitive_gaps_csv row count must equal bundle.competitive_gaps size",
    )

    if offer_rows:
        first_offer = offer_rows[0]
        for required_col in [
            "platform_name",
            "item_id",
            "title",
            "canonical_url",
            "item_type",
            "topic_clusters",
            "competency_families",
            "audience_segments",
            "core_signals",
            "quality_score",
            "is_noise",
        ]:
            _assert(required_col in first_offer, f"offer_features_csv missing column: {required_col}")

    if positioning_rows:
        first_positioning = positioning_rows[0]
        for required_col in [
            "platform_name",
            "audience_focus",
            "value_props",
            "core_signals",
            "dominant_topics",
            "dominant_competency_families",
            "positioning_statement",
        ]:
            _assert(required_col in first_positioning, f"platform_positioning_csv missing column: {required_col}")

    if trend_rows:
        first_trend = trend_rows[0]
        for required_col in [
            "trend_id",
            "topic",
            "trend_type",
            "topic_label",
            "platforms_count",
            "items_count",
            "platform_share",
            "signal_strength",
            "interpretation",
        ]:
            _assert(required_col in first_trend, f"trend_signals_csv missing column: {required_col}")

    if gap_rows:
        first_gap = gap_rows[0]
        for required_col in [
            "topic",
            "gap_type",
            "topic_label",
            "platforms_count",
            "platform_share",
            "underrepresented_platforms",
            "opportunity_score",
            "interpretation",
        ]:
            _assert(required_col in first_gap, f"competitive_gaps_csv missing column: {required_col}")

    _assert(
        json_payload.get("generated_at_utc") == _get_attr(bundle, "generated_at_utc", None),
        "json_report generated_at_utc must match bundle.generated_at_utc",
    )

    return {
        "output_files_checked": len(expected_keys),
        "offer_features_csv_rows": len(offer_rows),
        "platform_positioning_csv_rows": len(positioning_rows),
        "trend_signals_csv_rows": len(trend_rows),
        "competitive_gaps_csv_rows": len(gap_rows),
        "markdown_report_non_empty": 1,
        "json_report_top_level_object": 1,
    }


def _validate_output_paths_location(result: Any) -> dict[str, Any]:
    files = result.get("files") if isinstance(result, dict) else _get_attr(result, "files", None)
    _assert(isinstance(files, dict), "files must be dict")

    analysis_root = _analysis_reports_root().resolve()

    checked = 0
    for key, raw_path in files.items():
        _assert(isinstance(raw_path, str) and raw_path.strip(), f"files[{key!r}] must be non-empty path string")
        path = Path(raw_path).resolve()
        try:
            path.relative_to(analysis_root)
        except ValueError as exc:
            raise AssertionError(
                f"Output file {key!r} must be located under {analysis_root}, got {path}"
            ) from exc
        checked += 1

    return {
        "output_paths_under_market_analysis_root": 1,
        "output_paths_checked": checked,
    }


def main() -> None:
    project_root = _project_root()
    reports_root = _reports_root()
    source_json_path = _latest_market_report_json(reports_root)

    print(f"[smoke] project_root: {project_root}")
    print(f"[smoke] reports_root: {reports_root}")
    print(f"[smoke] source_json_path: {source_json_path}")

    result = run_market_analysis(source_json_path=str(source_json_path))
    bundle = _extract_bundle(result)

    counts = _extract_counts(result, bundle)
    counts["source_json_path"] = str(source_json_path)

    shape_stats = _validate_result_shape(result, bundle)
    contract_stats = _validate_bundle_contract(bundle)
    positioning_stats = _validate_positioning(bundle)
    trend_stats = _validate_trend_signals(bundle)
    file_stats = _validate_output_files(result, bundle)
    output_path_stats = _validate_output_paths_location(result)
    warnings = _validate_counts(counts)

    print("[smoke] pipeline OK")
    _print_json(
        "",
        {
            **counts,
            **shape_stats,
            **contract_stats,
            **positioning_stats,
            **trend_stats,
            **file_stats,
            **output_path_stats,
            "warnings": warnings,
        },
    )

    print(
        "[smoke] key counts: "
        f"platforms={counts['platforms_total']}, "
        f"raw={counts['catalog_items_total_raw']}, "
        f"after_dedup={counts['catalog_items_total_after_dedup']}, "
        f"duplicates_removed={counts['catalog_items_total_deduped']}, "
        f"noise={counts['catalog_items_total_noise']}, "
        f"kept={counts['catalog_items_total_kept']}, "
        f"trends={counts['trend_signals_total']}, "
        f"gaps={counts['competitive_gaps_total']}, "
        f"positioning={counts['platform_positioning_total']}, "
        f"files_checked={file_stats['output_files_checked']}"
    )

    if warnings:
        print("[smoke] warnings:")
        for item in warnings:
            print(f"  - {item}")


if __name__ == "__main__":
    main()