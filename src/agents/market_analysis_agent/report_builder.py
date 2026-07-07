from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .taxonomy import (
    COMPETENCY_FAMILY_LABELS,
    CORE_SIGNAL_LABELS,
    TOPIC_KEYS,
    TOPIC_LABELS,
)
from .types import MarketAnalysisBundle


_DEFAULT_OUTPUT_DIR = Path("data/reports/market_analysis_agent")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_output_dir(path: Path | None = None) -> Path:
    if path is None:
        path = _DEFAULT_OUTPUT_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if x is not None and str(x).strip()]
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    return []


def _join_list(value: Any) -> str:
    return " | ".join(_as_str_list(value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _fmt_float(value: Any, digits: int = 3) -> str:
    return f"{_safe_float(value):.{digits}f}"


def _to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_serializable(asdict(value))
    if isinstance(value, dict):
        return {k: _to_serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_serializable(v) for v in value]
    if hasattr(value, "__dict__") and not isinstance(value, (str, int, float, bool, type(None))):
        result: dict[str, Any] = {}
        for k, v in value.__dict__.items():
            result[k] = _to_serializable(v)
        return result
    return value


def _bundle_to_dict(bundle: MarketAnalysisBundle) -> dict[str, Any]:
    if hasattr(bundle, "model_dump"):
        result = bundle.model_dump()
        return _to_serializable(result)
    if is_dataclass(bundle):
        result = asdict(bundle)
        return _to_serializable(result)
    if hasattr(bundle, "dict"):
        result = bundle.dict()
        return _to_serializable(result)
    return _to_serializable(bundle)


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _canonical_core_signal_order() -> list[str]:
    return list(CORE_SIGNAL_LABELS.keys())


def _trend_topic_key(item: Any) -> str:
    topic = getattr(item, "topic", "")

    if topic is None:
        return ""

    if isinstance(topic, str):
        return topic

    if hasattr(topic, "key"):
        key = getattr(topic, "key")
        if isinstance(key, str) and key:
            return key

    if hasattr(topic, "value"):
        value = getattr(topic, "value")
        if isinstance(value, str) and value:
            return value

    if hasattr(topic, "topic_key"):
        topic_key = getattr(topic, "topic_key")
        if isinstance(topic_key, str) and topic_key:
            return topic_key

    if hasattr(topic, "name"):
        name = getattr(topic, "name")
        if isinstance(name, str) and name:
            return name

    return str(topic)


def _gap_topic_key(item: Any) -> str:
    topic = getattr(item, "topic", "")
    if topic is None:
        return ""
    if isinstance(topic, str):
        return topic
    return _trend_topic_key(item)


def _display_label(topic: str, kind: str) -> str:
    if kind == "competency_family":
        return COMPETENCY_FAMILY_LABELS.get(topic, topic)
    if kind == "core_signal":
        return CORE_SIGNAL_LABELS.get(topic, topic)
    return TOPIC_LABELS.get(topic, topic)


def _topic_gap_map(bundle: MarketAnalysisBundle) -> dict[str, Any]:
    return {
        _gap_topic_key(item): item
        for item in bundle.competitive_gaps
        if getattr(item, "gap_type", "") == "topic_cluster"
    }


def _topic_trend_map(bundle: MarketAnalysisBundle) -> dict[str, Any]:
    return {
        _trend_topic_key(item): item
        for item in bundle.trend_signals
        if getattr(item, "trend_type", "") == "topic_cluster"
    }


def _core_trend_map(bundle: MarketAnalysisBundle) -> dict[str, Any]:
    return {
        _trend_topic_key(item): item
        for item in bundle.trend_signals
        if getattr(item, "trend_type", "") == "core_signal"
    }


def _top_dense_topics(bundle: MarketAnalysisBundle) -> list[str]:
    dense = [
        _display_label(_gap_topic_key(item), getattr(item, "gap_type", ""))
        for item in bundle.competitive_gaps
        if getattr(item, "gap_type", "") == "topic_cluster"
        and _safe_float(getattr(item, "platform_share", 0.0)) >= 0.8
    ]
    return dense[:8]


def _top_whitespace_topics(bundle: MarketAnalysisBundle) -> list[str]:
    whitespace = [
        _display_label(_gap_topic_key(item), getattr(item, "gap_type", ""))
        for item in bundle.competitive_gaps
        if getattr(item, "gap_type", "") == "topic_cluster"
        and _safe_float(getattr(item, "opportunity_score", 0.0)) >= 0.5
    ]
    return whitespace[:8]


def _translate_audience_label(value: str) -> str:
    mapping = {
        "beginners": "начинающие",
        "career_switchers": "смена профессии",
        "junior_specialists": "junior-специалисты",
        "working_professionals": "работающие специалисты",
        "senior_experts": "senior-эксперты",
        "managers_leads": "руководители и лиды",
        "students": "студенты",
        "corporate_teams": "корпоративные команды",
        "experienced_engineers": "опытные инженеры",
        "corporate_clients": "корпоративные клиенты",
        "managers_and_execs": "руководители и executives",
    }
    return mapping.get(value, value)


def _core_signal_prevalence(bundle: MarketAnalysisBundle) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for item in bundle.offer_features:
        counter.update(_as_str_list(getattr(item, "core_signals", [])))

    return [(key, counter.get(key, 0)) for key in _canonical_core_signal_order()]


def _core_axes_markdown() -> list[str]:
    lines = [
        "## Canonical AI differentiation axes",
        "",
        "Следующие сигналы используются как фиксированный первичный каркас сравнения компании с внешними платформами и полностью синхронизированы с canonical vocabulary из taxonomy.py.",
        "",
    ]

    for key in _canonical_core_signal_order():
        lines.append(f"- `{key}` — {CORE_SIGNAL_LABELS.get(key, key)}.")

    lines.extend(
        [
            "",
            "Все остальные характеристики следует интерпретировать как дополнительные сигналы, а не как основной baseline сравнения.",
            "",
        ]
    )
    return lines


def _build_rag_chunks(bundle: MarketAnalysisBundle) -> list[dict[str, Any]]:
    """Генерирует чанки для RAG-индексации из результатов анализа."""
    chunks: list[dict[str, Any]] = []
    generated_at = getattr(bundle, "generated_at_utc", "")

    # 1. Обзорный чанк
    chunks.append(
        {
            "chunk_id": "executive_summary",
            "source": "market_analysis_agent",
            "section": "overview",
            "title": "Обзор рынка",
            "text": (
                f"Проанализировано платформ: {getattr(bundle, 'platforms_total', 0)}. "
                f"Исходных курсов: {getattr(bundle, 'catalog_items_total_raw', 0)}. "
                f"После дедупликации: {getattr(bundle, 'catalog_items_total_after_dedup', 0)}. "
                f"Отфильтровано шума: {getattr(bundle, 'catalog_items_total_noise', 0)}. "
                f"Оставлено в аналитике: {getattr(bundle, 'catalog_items_total_kept', 0)}."
            ),
            "metadata": {
                "generated_at_utc": generated_at,
                "platforms_total": getattr(bundle, "platforms_total", 0),
            },
        }
    )

    # 2. Чанки по ключевым сигналам
    dense = _top_dense_topics(bundle)
    whitespace = _top_whitespace_topics(bundle)
    top_trends = [
        _display_label(_trend_topic_key(item), getattr(item, "trend_type", ""))
        for item in bundle.trend_signals
        if getattr(item, "items_count", 0) > 0
    ][:8]

    chunks.append(
        {
            "chunk_id": "key_signals",
            "source": "market_analysis_agent",
            "section": "key_signals",
            "title": "Ключевые исполнительные сигналы",
            "text": (
                f"Основные направления рынка: {', '.join(top_trends) or 'н/д'}. "
                f"Перегруженные направления: {', '.join(dense) or 'н/д'}. "
                f"Потенциальные направления — белые пятна: {', '.join(whitespace) or 'н/д'}."
            ),
            "metadata": {
                "generated_at_utc": generated_at,
                "top_trends": top_trends,
                "dense_topics": dense,
                "whitespace_topics": whitespace,
            },
        }
    )

    # 3. Чанки по каждому направлению
    gap_map = _topic_gap_map(bundle)
    trend_map = _topic_trend_map(bundle)

    for topic in TOPIC_KEYS:
        trend = trend_map.get(topic)
        gap = gap_map.get(topic)

        platforms = getattr(trend, "platforms_count", 0) if trend else 0
        items = getattr(trend, "items_count", 0) if trend else 0
        signal = _safe_float(getattr(trend, "signal_strength", 0.0) if trend else 0.0)
        share = _safe_float(getattr(gap, "platform_share", 0.0) if gap else 0.0)
        opportunity = _safe_float(getattr(gap, "opportunity_score", 0.0) if gap else 0.0)
        interpretation = getattr(trend, "interpretation", "") if trend else ""

        chunks.append(
            {
                "chunk_id": f"topic_coverage::{topic}",
                "source": "market_analysis_agent",
                "section": "topic_coverage",
                "title": TOPIC_LABELS.get(topic, topic),
                "text": (
                    f"Направление «{TOPIC_LABELS.get(topic, topic)}»: "
                    f"охвачено {platforms} платформами, {items} курсов, "
                    f"сила сигнала {_fmt_float(signal)}, "
                    f"доля платформ {_fmt_float(share)}, "
                    f"потенциал gap {_fmt_float(opportunity)}. "
                    f"{interpretation}"
                ).strip(),
                "metadata": {
                    "generated_at_utc": generated_at,
                    "topic_key": topic,
                    "topic_label": TOPIC_LABELS.get(topic, topic),
                    "platforms_count": platforms,
                    "items_count": items,
                    "signal_strength": signal,
                    "platform_share": share,
                    "opportunity_score": opportunity,
                },
            }
        )

    # 4. Чанки по позиционированию платформ
    for position in bundle.platform_positioning:
        platform_name = getattr(position, "platform_name", "")
        statement = getattr(position, "positioning_statement", "")
        audiences = [
            _translate_audience_label(x)
            for x in _as_str_list(getattr(position, "audience_focus", []))
        ]
        topics = [
            TOPIC_LABELS.get(x, x)
            for x in _as_str_list(getattr(position, "dominant_topics", []))
        ]
        competencies = [
            COMPETENCY_FAMILY_LABELS.get(x, x)
            for x in _as_str_list(getattr(position, "dominant_competency_families", []))
        ]
        signals = [
            CORE_SIGNAL_LABELS.get(x, x)
            for x in _as_str_list(getattr(position, "core_signals", []))
        ]

        chunks.append(
            {
                "chunk_id": f"platform_positioning::{platform_name}",
                "source": "market_analysis_agent",
                "section": "platform_positioning",
                "title": f"Позиционирование: {platform_name}",
                "text": (
                    f"Платформа «{platform_name}»: {statement}. "
                    f"Аудитории: {', '.join(audiences) if audiences else 'н/д'}. "
                    f"Ключевые темы: {', '.join(topics) if topics else 'н/д'}. "
                    f"Компетенции: {', '.join(competencies) if competencies else 'н/д'}. "
                    f"Сигналы дифференциации: {', '.join(signals) if signals else 'н/д'}."
                ),
                "metadata": {
                    "generated_at_utc": generated_at,
                    "platform_name": platform_name,
                    "positioning_statement": statement,
                    "audience_focus": audiences,
                    "dominant_topics": topics,
                    "dominant_competency_families": competencies,
                    "core_signals": signals,
                },
            }
        )

    # 5. Чанки по gap-гипотезам
    for item in bundle.competitive_gaps:
        topic_key = _gap_topic_key(item)
        chunks.append(
            {
                "chunk_id": f"competitive_gap::{topic_key}",
                "source": "market_analysis_agent",
                "section": "competitive_gaps",
                "title": f"Gap-гипотеза: {TOPIC_LABELS.get(topic_key, topic_key)}",
                "text": (
                    f"Направление «{TOPIC_LABELS.get(topic_key, topic_key)}»: "
                    f"доля платформ {_fmt_float(getattr(item, 'platform_share', 0.0))}, "
                    f"потенциал gap {_fmt_float(getattr(item, 'opportunity_score', 0.0))}. "
                    f"Недопредставленные платформы: "
                    f"{', '.join(_as_str_list(getattr(item, 'underrepresented_platforms', []))[:6]) or 'н/д'}. "
                    f"{getattr(item, 'interpretation', '')}"
                ).strip(),
                "metadata": {
                    "generated_at_utc": generated_at,
                    "topic_key": topic_key,
                    "topic_label": TOPIC_LABELS.get(topic_key, topic_key),
                    "platform_share": _safe_float(getattr(item, "platform_share", 0.0)),
                    "opportunity_score": _safe_float(getattr(item, "opportunity_score", 0.0)),
                    "underrepresented_platforms": _as_str_list(
                        getattr(item, "underrepresented_platforms", [])
                    ),
                },
            }
        )

    # 6. Чанки по трендам
    for item in bundle.trend_signals:
        trend_id = getattr(item, "trend_id", "")
        topic_key = _trend_topic_key(item)
        trend_type = getattr(item, "trend_type", "")
        chunks.append(
            {
                "chunk_id": f"trend_signal::{trend_id}",
                "source": "market_analysis_agent",
                "section": "trend_signals",
                "title": f"Тренд: {_display_label(topic_key, trend_type)}",
                "text": (
                    f"Тренд «{_display_label(topic_key, trend_type)}» "
                    f"(тип: {trend_type}): "
                    f"охвачено {getattr(item, 'platforms_count', 0)} платформ, "
                    f"{getattr(item, 'items_count', 0)} курсов, "
                    f"доля платформ {_fmt_float(getattr(item, 'platform_share', 0.0))}, "
                    f"сила сигнала {_fmt_float(getattr(item, 'signal_strength', 0.0))}. "
                    f"Представляющие платформы: "
                    f"{', '.join(_as_str_list(getattr(item, 'representative_platforms', []))[:6]) or 'н/д'}. "
                    f"{getattr(item, 'interpretation', '')}"
                ).strip(),
                "metadata": {
                    "generated_at_utc": generated_at,
                    "trend_id": trend_id,
                    "topic_key": topic_key,
                    "topic_label": _display_label(topic_key, trend_type),
                    "trend_type": trend_type,
                    "platforms_count": getattr(item, "platforms_count", 0),
                    "items_count": getattr(item, "items_count", 0),
                    "platform_share": _safe_float(getattr(item, "platform_share", 0.0)),
                    "signal_strength": _safe_float(getattr(item, "signal_strength", 0.0)),
                },
            }
        )

    return chunks


def _build_markdown(bundle: MarketAnalysisBundle) -> str:
    gap_map = _topic_gap_map(bundle)
    trend_map = _topic_trend_map(bundle)
    core_trend_map = _core_trend_map(bundle)

    lines: list[str] = []
    lines.append("# Исполнительный обзор рынка")
    lines.append("")
    lines.append("## Обзор")
    lines.append("")
    lines.append(f"- Время генерации (UTC): {getattr(bundle, 'generated_at_utc', '')}")
    lines.append(f"- Проанализированных платформ: {getattr(bundle, 'platforms_total', 0)}")
    lines.append(f"- Исходных курсов в каталоге: {getattr(bundle, 'catalog_items_total_raw', 0)}")
    lines.append(f"- Исключено при дедупликации: {getattr(bundle, 'catalog_items_total_deduped', 0)}")
    lines.append(f"- Отфильтровано как шум: {getattr(bundle, 'catalog_items_total_noise', 0)}")
    lines.append(f"- Курсов, оставшихся в аналитике: {getattr(bundle, 'catalog_items_total_kept', 0)}")
    lines.append("")

    lines.extend(_core_axes_markdown())

    lines.append("## Ключевые исполнительные сигналы")
    lines.append("")
    dense_topics = _top_dense_topics(bundle)
    whitespace_topics = _top_whitespace_topics(bundle)
    top_trends = [
        _display_label(_trend_topic_key(item), getattr(item, "trend_type", ""))
        for item in bundle.trend_signals
        if getattr(item, "items_count", 0) > 0
    ][:8]

    lines.append(f"- Основные направления рынка: {', '.join(top_trends) or 'н/д'}")
    lines.append(f"- Перегруженные направления: {', '.join(dense_topics) or 'н/д'}")
    lines.append(f"- Потенциальные направления-белые пятна: {', '.join(whitespace_topics) or 'н/д'}")
    lines.append("")

    core_prevalence = _core_signal_prevalence(bundle)
    if any(count > 0 for _, count in core_prevalence):
        lines.append("## Покрытие canonical AI differentiation axes")
        lines.append("")
        lines.append("| Ось дифференциации | Key | Количество курсов | Тренд-сигнал | Платформы |")
        lines.append("|---|---|---:|---:|---:|")
        for key, count in core_prevalence:
            trend = core_trend_map.get(key)
            lines.append(
                f"| {CORE_SIGNAL_LABELS.get(key, key)} | "
                f"`{key}` | "
                f"{count} | "
                f"{_fmt_float(getattr(trend, 'signal_strength', 0.0))} | "
                f"{getattr(trend, 'platforms_count', 0)} |"
            )
        lines.append("")

    lines.append("## Покрытие направлений")
    lines.append("")
    lines.append("| Направление | Платформы | Курсы | Сила сигнала | Доля платформ | Потенциал gap |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for topic in TOPIC_KEYS:
        trend = trend_map.get(topic)
        gap = gap_map.get(topic)
        lines.append(
            f"| {TOPIC_LABELS.get(topic, topic)} | "
            f"{getattr(trend, 'platforms_count', 0) if trend else 0} | "
            f"{getattr(trend, 'items_count', 0) if trend else 0} | "
            f"{_fmt_float(getattr(trend, 'signal_strength', 0.0) if trend else 0.0)} | "
            f"{_fmt_float(getattr(gap, 'platform_share', 0.0) if gap else 0.0)} | "
            f"{_fmt_float(getattr(gap, 'opportunity_score', 0.0) if gap else 0.0)} |"
        )
    lines.append("")

    competency_trends = [x for x in bundle.trend_signals if getattr(x, "trend_type", "") == "competency_family"]
    if competency_trends:
        lines.append("## Сигналы по семействам компетенций")
        lines.append("")
        lines.append("| Семейство компетенций | Платформы | Курсы | Сила сигнала | Интерпретация |")
        lines.append("|---|---:|---:|---:|---|")
        for item in competency_trends:
            topic_key = _trend_topic_key(item)
            lines.append(
                f"| {COMPETENCY_FAMILY_LABELS.get(topic_key, topic_key)} | "
                f"{getattr(item, 'platforms_count', 0)} | "
                f"{getattr(item, 'items_count', 0)} | "
                f"{_fmt_float(getattr(item, 'signal_strength', 0.0))} | "
                f"{getattr(item, 'interpretation', '')} |"
            )
        lines.append("")

    lines.append("## Интерпретация трендов")
    lines.append("")
    lines.append("| Направление | Интерпретация | Представляющие платформы |")
    lines.append("|---|---|---|")
    for topic in TOPIC_KEYS:
        trend = trend_map.get(topic)
        if not trend:
            continue
        lines.append(
            f"| {TOPIC_LABELS.get(topic, topic)} | "
            f"{getattr(trend, 'interpretation', '')} | "
            f"{', '.join(_as_str_list(getattr(trend, 'representative_platforms', []))[:6]) or 'н/д'} |"
        )
    lines.append("")

    lines.append("## Позиционирование платформ")
    lines.append("")
    lines.append("| Платформа | Темы | Компетенции | Ключевые сигналы | Аудитории | Позиционирование |")
    lines.append("|---|---|---|---|---|---|")
    for position in bundle.platform_positioning:
        lines.append(
            f"| {getattr(position, 'platform_name', '')} | "
            f"{', '.join(TOPIC_LABELS.get(x, x) for x in _as_str_list(getattr(position, 'dominant_topics', []))[:4]) or 'н/д'} | "
            f"{', '.join(COMPETENCY_FAMILY_LABELS.get(x, x) for x in _as_str_list(getattr(position, 'dominant_competency_families', []))[:4]) or 'н/д'} | "
            f"{', '.join(CORE_SIGNAL_LABELS.get(x, x) for x in _as_str_list(getattr(position, 'core_signals', []))[:4]) or 'н/д'} | "
            f"{', '.join(_translate_audience_label(x) for x in _as_str_list(getattr(position, 'audience_focus', []))[:3]) or 'н/д'} | "
            f"{getattr(position, 'positioning_statement', '')} |"
        )
    lines.append("")

    lines.append("## Гипотезы по gap-направлениям")
    lines.append("")
    lines.append("| Направление | Доля платформ | Потенциал gap | Недопредставленные платформы | Интерпретация |")
    lines.append("|---|---:|---:|---|---|")
    for item in bundle.competitive_gaps:
        if getattr(item, "gap_type", "") != "topic_cluster":
            continue
        topic_key = _gap_topic_key(item)
        lines.append(
            f"| {TOPIC_LABELS.get(topic_key, topic_key)} | "
            f"{_fmt_float(getattr(item, 'platform_share', 0.0))} | "
            f"{_fmt_float(getattr(item, 'opportunity_score', 0.0))} | "
            f"{', '.join(_as_str_list(getattr(item, 'underrepresented_platforms', []))[:6]) or 'н/д'} | "
            f"{getattr(item, 'interpretation', '')} |"
        )
    lines.append("")

    lines.append("## Входные данные для планирования")
    lines.append("")
    lines.append("- Использовать перегруженные направления как индикатор давления на паритет и высокой насыщенности конкурентами.")
    lines.append("- Использовать направления-белые пятна как гипотезы для расширения портфеля только после проверки относительно внутренних возможностей и спроса.")
    lines.append("- Сопоставлять внешнюю плотность направлений с базой знаний компании, текущей экспертизой команды, delivery-возможностями и коммерческой моделью.")
    lines.append("- Оценивать конкурентов сначала по каноническим AI-осям дифференциации, и только затем по вторичным или добавочным признакам.")
    lines.append("- Разделять провайдеров с академической глубиной и провайдеров, которые делают акцент на job outcome, production readiness, enterprise project practice и AI-native support layers.")
    lines.append("")

    return "\n".join(lines)


def build_market_analysis_report_bundle(bundle: MarketAnalysisBundle) -> dict[str, str]:
    output_dir = _ensure_output_dir()
    ts = _timestamp()

    json_path = output_dir / f"market_analysis_{ts}.json"
    offers_csv_path = output_dir / f"market_offer_features_{ts}.csv"
    positioning_csv_path = output_dir / f"platform_positioning_{ts}.csv"
    trends_csv_path = output_dir / f"trend_signals_{ts}.csv"
    gaps_csv_path = output_dir / f"competitive_gaps_{ts}.csv"
    markdown_path = output_dir / f"market_analysis_{ts}.md"
    rag_chunks_path = output_dir / f"market_analysis_rag_chunks_{ts}.json"

    _write_json(json_path, _bundle_to_dict(bundle))

    offer_rows = [
        {
            "platform_name": getattr(item, "platform_name", ""),
            "item_id": getattr(item, "item_id", ""),
            "title": getattr(item, "title", "") or getattr(item, "item_title", ""),
            "canonical_url": getattr(item, "canonical_url", ""),
            "item_type": getattr(item, "item_type", ""),
            "normalized_title": getattr(item, "normalized_title", ""),
            "text_fingerprint": getattr(item, "text_fingerprint", ""),
            "topic_clusters": _join_list(getattr(item, "topic_clusters", [])),
            "competency_families": _join_list(getattr(item, "competency_families", [])),
            "audience_segments": _join_list(getattr(item, "audience_segments", [])),
            "core_signals": _join_list(
                [CORE_SIGNAL_LABELS.get(x, x) for x in _as_str_list(getattr(item, "core_signals", []))]
            ),
            "format_signals": _join_list(getattr(item, "format_signals", [])),
            "outcome_signals": _join_list(getattr(item, "outcome_signals", [])),
            "support_signals": _join_list(getattr(item, "support_signals", [])),
            "intensity_signals": _join_list(getattr(item, "intensity_signals", [])),
            "value_props": _join_list(getattr(item, "value_props", [])),
            "duration_bucket": getattr(item, "duration_bucket", ""),
            "difficulty_bucket": getattr(item, "difficulty_bucket", ""),
            "quality_score": _safe_float(getattr(item, "quality_score", 0.0)),
            "is_noise": bool(getattr(item, "is_noise", False)),
            "noise_reasons": _join_list(getattr(item, "noise_reasons", [])),
            "evidence_text": getattr(item, "evidence_text", ""),
            "language": getattr(item, "language", ""),
            "extraction_confidence": _safe_float(getattr(item, "extraction_confidence", None), default=0.0),
            "extraction_notes": _join_list(getattr(item, "extraction_notes", [])),
        }
        for item in bundle.offer_features
    ]
    _write_csv(
        offers_csv_path,
        offer_rows,
        [
            "platform_name",
            "item_id",
            "title",
            "canonical_url",
            "item_type",
            "normalized_title",
            "text_fingerprint",
            "topic_clusters",
            "competency_families",
            "audience_segments",
            "core_signals",
            "format_signals",
            "outcome_signals",
            "support_signals",
            "intensity_signals",
            "value_props",
            "duration_bucket",
            "difficulty_bucket",
            "quality_score",
            "is_noise",
            "noise_reasons",
            "evidence_text",
            "language",
            "extraction_confidence",
            "extraction_notes",
        ],
    )

    positioning_rows = [
        {
            "platform_name": getattr(item, "platform_name", ""),
            "audience_focus": _join_list(
                [_translate_audience_label(x) for x in _as_str_list(getattr(item, "audience_focus", []))]
            ),
            "value_props": _join_list(getattr(item, "value_props", [])),
            "core_signals": _join_list(
                [CORE_SIGNAL_LABELS.get(x, x) for x in _as_str_list(getattr(item, "core_signals", []))]
            ),
            "pedagogy_style": _join_list(getattr(item, "pedagogy_style", [])),
            "career_signals": _join_list(getattr(item, "career_signals", [])),
            "academic_signals": _join_list(getattr(item, "academic_signals", [])),
            "execution_model": _join_list(getattr(item, "execution_model", [])),
            "dominant_topics": _join_list(
                [TOPIC_LABELS.get(x, x) for x in _as_str_list(getattr(item, "dominant_topics", []))]
            ),
            "dominant_competency_families": _join_list(
                [
                    COMPETENCY_FAMILY_LABELS.get(x, x)
                    for x in _as_str_list(getattr(item, "dominant_competency_families", []))
                ]
            ),
            "positioning_statement": getattr(item, "positioning_statement", ""),
        }
        for item in bundle.platform_positioning
    ]
    _write_csv(
        positioning_csv_path,
        positioning_rows,
        [
            "platform_name",
            "audience_focus",
            "value_props",
            "core_signals",
            "pedagogy_style",
            "career_signals",
            "academic_signals",
            "execution_model",
            "dominant_topics",
            "dominant_competency_families",
            "positioning_statement",
        ],
    )

    trend_rows = [
        {
            "trend_id": getattr(item, "trend_id", ""),
            "topic": _trend_topic_key(item),
            "trend_type": getattr(item, "trend_type", ""),
            "topic_label": _display_label(_trend_topic_key(item), getattr(item, "trend_type", "")),
            "platforms_count": getattr(item, "platforms_count", 0),
            "items_count": getattr(item, "items_count", 0),
            "platform_share": _safe_float(getattr(item, "platform_share", 0.0)),
            "signal_strength": _safe_float(getattr(item, "signal_strength", 0.0)),
            "representative_platforms": _join_list(getattr(item, "representative_platforms", [])),
            "evidence_item_ids": _join_list(getattr(item, "evidence_item_ids", [])),
            "interpretation": getattr(item, "interpretation", ""),
        }
        for item in bundle.trend_signals
    ]
    _write_csv(
        trends_csv_path,
        trend_rows,
        [
            "trend_id",
            "topic",
            "trend_type",
            "topic_label",
            "platforms_count",
            "items_count",
            "platform_share",
            "signal_strength",
            "representative_platforms",
            "evidence_item_ids",
            "interpretation",
        ],
    )

    gap_rows = [
        {
            "topic": _gap_topic_key(item),
            "gap_type": getattr(item, "gap_type", ""),
            "topic_label": _display_label(_gap_topic_key(item), getattr(item, "gap_type", "")),
            "platforms_count": getattr(item, "platforms_count", 0),
            "platform_share": _safe_float(getattr(item, "platform_share", 0.0)),
            "underrepresented_platforms": _join_list(getattr(item, "underrepresented_platforms", [])),
            "opportunity_score": _safe_float(getattr(item, "opportunity_score", 0.0)),
            "interpretation": getattr(item, "interpretation", ""),
            "evidence_item_ids": _join_list(getattr(item, "evidence_item_ids", [])),
        }
        for item in bundle.competitive_gaps
    ]
    _write_csv(
        gaps_csv_path,
        gap_rows,
        [
            "topic",
            "gap_type",
            "topic_label",
            "platforms_count",
            "platform_share",
            "underrepresented_platforms",
            "opportunity_score",
            "interpretation",
            "evidence_item_ids",
        ],
    )

    markdown_path.write_text(_build_markdown(bundle), encoding="utf-8")

    # RAG chunks для будущей системы поддержки решений
    rag_chunks = _build_rag_chunks(bundle)
    _write_json(rag_chunks_path, {"generated_at_utc": getattr(bundle, "generated_at_utc", ""), "chunks": rag_chunks})

    return {
        "json_report": str(json_path),
        "offer_features_csv": str(offers_csv_path),
        "platform_positioning_csv": str(positioning_csv_path),
        "trend_signals_csv": str(trends_csv_path),
        "competitive_gaps_csv": str(gaps_csv_path),
        "markdown_report": str(markdown_path),
        "rag_chunks_json": str(rag_chunks_path),
    }