from __future__ import annotations

from collections import Counter

from .taxonomy import COMPETENCY_FAMILY_LABELS, CORE_SIGNAL_LABELS, TOPIC_LABELS
from .types import OfferFeatures, PlatformAggregate, PlatformPositioning, PlatformReportInput


CAREER_SIGNAL_KEYS = {
    "job_outcome",
    "project_based",
    "mentor_support",
    "custom_training",
    "b2b_enablement",
    "production_readiness",
    "llm_agent_readiness",
}


ACADEMIC_SIGNAL_KEYS = {
    "academic_depth",
}


EXECUTION_MODEL_KEYS = {
    "cohort",
    "self_paced",
    "hybrid",
    "enterprise_delivery",
    "mentor_support",
    "project_based",
    "short_intensive",
    "custom_training",
}


PEDAGOGY_SIGNAL_KEYS = {
    "project_based",
    "mentor_support",
    "academic_depth",
    "short_intensive",
    "independent_assignments",
    "webinars_and_free_content",
    "ai_curator_chatgpt",
}


VALUE_PROP_KEYS = {
    "job_outcome",
    "project_based",
    "mentor_support",
    "certificate",
    "academic_depth",
    "short_intensive",
    "custom_training",
    "b2b_enablement",
    "production_readiness",
    "llm_agent_readiness",
}


CANONICAL_AI_DIFFERENTIATION_AXES_MD = """
## Canonical AI differentiation axes

This section defines the canonical differentiation axes used to normalize platform positioning across AI and IT education offers. These axes provide a stable comparison layer above raw course copy, local phrasing, and inconsistent marketing terminology.

### Why this layer exists

Different providers often describe similar learning mechanics with different wording. The canonical axis layer maps those wording variants into a normalized set of signals so that cross-platform comparison remains transparent, reproducible, and interpretable.

### Axis list

- `independent_assignments` — the offer includes homework, самостоятельные задания, practical exercises, or structured take-home work.
- `flexible_schedule` — the offer emphasizes flexible pacing, гибкий график, learn-anytime access, or schedule adaptability.
- `lifetime_access` — the offer promises бессрочный доступ, unlimited access, or permanent access to materials.
- `recorded_lessons` — the offer includes recorded lectures, записи занятий, on-demand lessons, or access to a video archive.
- `live_sessions` — the offer includes live classes, webinars, workshops, or synchronous expert sessions.
- `mentor_support` — the offer provides mentorship, куратор, наставник, mentor guidance, or individual support.
- `expert_feedback` — the offer explicitly promises homework feedback, code review, project review, or reviewer comments.
- `project_portfolio` — the offer includes portfolio projects, capstones, кейсы, pet projects, or demonstrable project outcomes.
- `career_support` — the offer includes CV help, mock interviews, career center services, job support, or employment assistance.
- `community_access` — the offer includes peer groups, cohort chat, Discord/Slack/Telegram access, or alumni community access.
- `cohort_based` — the offer is run as a cohort, group intake, batch model, or fixed-start learning format.
- `self_paced` — the offer is explicitly asynchronous, self-paced, or designed for independent progression.
- `certificate` — the offer includes a certificate, diploma, or formal completion credential.
- `foundation_depth` — the offer emphasizes fundamentals, theory, mathematics, or deep conceptual grounding.
- `tooling_relevance` — the offer highlights modern AI tooling, production stack, MLOps tooling, cloud workflows, or current industry practice.

### Interpretation rules

The canonical axes do not replace topic classification. Topic clusters explain what the platform teaches, competency families explain which capability domain the learner develops, and canonical differentiation axes explain how the offer is operationalized and experienced.

### Platform-level use

Each course or catalog item may map to zero or more canonical axes. At the platform level, repeated item-level signals are aggregated into a ranked `core_signals` list, which becomes part of the positioning layer and can also be reused for trend analysis or competitive gap detection.

### Reporting guidance

In platform comparison sections, `core_signals` should be interpreted as the most stable operational differentiators of the offer. They are especially useful when multiple competitors cover similar AI topics but differ in support intensity, delivery mechanics, portfolio emphasis, flexibility, or career conversion model.
""".strip()


def _top(counter: Counter[str], n: int) -> list[str]:
    return [key for key, _ in counter.most_common(n)]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _humanize_topic(topic: str) -> str:
    return TOPIC_LABELS.get(topic, topic.replace("_", " ").title())


def _humanize_competency(family: str) -> str:
    return COMPETENCY_FAMILY_LABELS.get(family, family.replace("_", " ").title())


def _humanize_core_signal(signal: str) -> str:
    return CORE_SIGNAL_LABELS.get(signal, signal.replace("_", " ").title())


def _humanize_audience(audience: str) -> str:
    mapping = {
        "beginners": "начинающие",
        "career_switchers": "специалисты, меняющие профессию",
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
    return mapping.get(audience, audience)


def _humanize_value_prop(value: str) -> str:
    mapping = {
        "job_outcome": "ориентация на трудоустройство",
        "project_based": "проектная практика",
        "mentor_support": "менторская поддержка",
        "certificate": "сертификат",
        "academic_depth": "академическая глубина",
        "short_intensive": "интенсивный формат",
        "custom_training": "кастомное обучение",
        "b2b_enablement": "B2B-ориентированный формат",
        "production_readiness": "подготовка к production-среде",
        "llm_agent_readiness": "подготовка к работе с LLM-агентами",
    }
    return mapping.get(value, value)


def _humanize_pedagogy(signal: str) -> str:
    mapping = {
        "project_based": "проектный подход",
        "mentor_support": "менторское сопровождение",
        "academic_depth": "академическая база",
        "short_intensive": "интенсивный формат",
        "independent_assignments": "самостоятельные задания",
        "webinars_and_free_content": "вебинары и бесплатный контент",
        "ai_curator_chatgpt": "AI-куратор на базе ChatGPT",
    }
    return mapping.get(signal, signal)


def _angle_label(career_signals: list[str], academic_signals: list[str]) -> str:
    if career_signals and not academic_signals:
        return "карьерно-ориентированный"
    if academic_signals and not career_signals:
        return "академически ориентированный"
    if career_signals and academic_signals:
        return "гибридный академический-и-карьерный"
    return "универсальный"


def _build_positioning_statement(
    *,
    platform_name: str,
    dominant_topics: list[str],
    dominant_competency_families: list[str],
    audience_focus: list[str],
    value_props: list[str],
    core_signals: list[str],
    pedagogy_style: list[str],
    career_signals: list[str],
    academic_signals: list[str],
) -> str:
    topic_text = ", ".join(_humanize_topic(x) for x in dominant_topics[:2])
    competency_text = ", ".join(_humanize_competency(x) for x in dominant_competency_families[:2])
    focus_text = topic_text or competency_text or "специализированные AI-направления"
    audience_text = ", ".join(_humanize_audience(x) for x in audience_focus[:2]) or "широкую аудиторию учащихся"
    value_text = ", ".join(_humanize_value_prop(x) for x in value_props[:3]) or "развитие прикладных навыков"
    pedagogy_text = ", ".join(_humanize_pedagogy(x) for x in pedagogy_style[:2]) or "смешанную модель обучения"
    core_text = ", ".join(_humanize_core_signal(x) for x in core_signals[:3])
    angle = _angle_label(career_signals, academic_signals)

    if core_text:
        return (
            f"{platform_name} выступает как {angle} провайдер AI-образования "
            f"с максимальной концентрацией в {focus_text}, ориентированный на {audience_text} "
            f"и делающий акцент на {value_text} через {pedagogy_text}. "
            f"Ключевые осевые точки сравнения: {core_text}."
        )

    return (
        f"{platform_name} выступает как {angle} провайдер AI-образования "
        f"с максимальной концентрацией в {focus_text}, ориентированный на {audience_text} "
        f"и делающий акцент на {value_text} через {pedagogy_text}."
    )


def _collect_features_for_platform(
    platform_name: str,
    features: list[OfferFeatures],
) -> list[OfferFeatures]:
    return [item for item in features if item.platform_name == platform_name]


def build_platform_positioning_profiles(
    *,
    platform_reports: list[PlatformReportInput],
    platform_aggregates: list[PlatformAggregate],
    offer_features: list[OfferFeatures],
) -> list[PlatformPositioning]:
    aggregate_map = {item.platform_name: item for item in platform_aggregates}
    result: list[PlatformPositioning] = []

    for report in platform_reports:
        platform_name = report.platform_name
        platform_features = _collect_features_for_platform(platform_name, offer_features)
        aggregate = aggregate_map.get(platform_name)

        audience_counter: Counter[str] = Counter()
        value_counter: Counter[str] = Counter()
        core_counter: Counter[str] = Counter()
        pedagogy_counter: Counter[str] = Counter()
        career_counter: Counter[str] = Counter()
        academic_counter: Counter[str] = Counter()
        execution_counter: Counter[str] = Counter()
        topic_counter: Counter[str] = Counter()
        competency_counter: Counter[str] = Counter()
        evidence_items: list[str] = []

        for item in platform_features:
            audience_counter.update(item.audience_segments)
            topic_counter.update(item.topic_clusters)
            competency_counter.update(item.competency_families)
            core_counter.update(item.core_signals)

            all_signals = (
                item.support_signals
                + item.outcome_signals
                + item.intensity_signals
                + item.format_signals
                + item.value_props
                + item.core_signals
            )

            for signal in all_signals:
                if signal in VALUE_PROP_KEYS:
                    value_counter[signal] += 1
                if signal in PEDAGOGY_SIGNAL_KEYS:
                    pedagogy_counter[signal] += 1
                if signal in CAREER_SIGNAL_KEYS:
                    career_counter[signal] += 1
                if signal in ACADEMIC_SIGNAL_KEYS:
                    academic_counter[signal] += 1
                if signal in EXECUTION_MODEL_KEYS:
                    execution_counter[signal] += 1

            if item.item_id:
                evidence_items.append(item.item_id)
            elif item.canonical_url:
                evidence_items.append(item.canonical_url)

        dominant_topics = _top(topic_counter, 6)
        dominant_competency_families = _top(competency_counter, 6)
        audience_focus = _top(audience_counter, 5)
        value_props = _top(value_counter, 6)
        core_signals = _top(core_counter, 8)
        pedagogy_style = _top(pedagogy_counter, 5)
        career_signals = _top(career_counter, 5)
        academic_signals = _top(academic_counter, 5)
        execution_model = _top(execution_counter, 5)

        if aggregate and not dominant_topics:
            dominant_topics = list(aggregate.top_topics[:6])
        if aggregate and not dominant_competency_families:
            dominant_competency_families = list(aggregate.top_competency_families[:6])
        if aggregate and not audience_focus:
            audience_focus = list(aggregate.top_audiences[:5])
        if aggregate and not value_props:
            value_props = list(aggregate.top_value_props[:6])
        if aggregate and not core_signals:
            core_signals = list(aggregate.top_core_signals[:8])
        if aggregate and not execution_model:
            execution_model = list(aggregate.top_format_signals[:5])

        positioning_statement = _build_positioning_statement(
            platform_name=platform_name,
            dominant_topics=dominant_topics,
            dominant_competency_families=dominant_competency_families,
            audience_focus=audience_focus,
            value_props=value_props,
            core_signals=core_signals,
            pedagogy_style=pedagogy_style,
            career_signals=career_signals,
            academic_signals=academic_signals,
        )

        result.append(
            PlatformPositioning(
                platform_name=platform_name,
                audience_focus=audience_focus,
                value_props=value_props,
                core_signals=core_signals,
                pedagogy_style=pedagogy_style,
                career_signals=career_signals,
                academic_signals=academic_signals,
                execution_model=execution_model,
                dominant_topics=dominant_topics,
                dominant_competency_families=dominant_competency_families,
                positioning_statement=positioning_statement,
                evidence_items=_dedupe_preserve_order(evidence_items)[:20],
                metadata={
                    "source_items_count": len(platform_features),
                    "used_aggregate_fallback": bool(aggregate),
                    "canonical_ai_differentiation_axes_md": CANONICAL_AI_DIFFERENTIATION_AXES_MD,
                },
            )
        )

    result.sort(key=lambda x: x.platform_name.lower())
    return result