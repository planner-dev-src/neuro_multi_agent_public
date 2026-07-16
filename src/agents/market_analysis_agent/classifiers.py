from __future__ import annotations

import re
from urllib.parse import urlparse

# Импортируем общие ключевые слова
from src.agents.common.keywords import (
    COMPANY_DIRECTIONS,
    FILTER_KEYWORDS,
    UNIQUE_KEYWORDS,
    is_relevant_text,
    get_direction_by_keyword
)

from .taxonomy import (
    AUDIENCE_RULES,
    COMPETENCY_FAMILY_RULES,
    CORE_SIGNAL_KEYS,
    CORE_SIGNAL_RULES,
    FORMAT_SIGNAL_RULES,
    TOPIC_CLUSTER_RULES,
    TOPIC_KEYS,
    VALUE_PROP_RULES,
)
from .types import CatalogItemInput, OfferFeatures, PlatformReportInput


# ============================================================
# АЛГОРИТМИЧЕСКАЯ ОЧИСТКА (вместо хардкода)
# ============================================================

# Технические ключевые слова для проверки
TECH_KEYWORDS = [
    # Языки программирования
    "python", "pytorch", "tensorflow", "keras", "scikit-learn",
    "numpy", "pandas", "sql", "r", "java", "cpp", "c++", "go", "rust",
    "javascript", "typescript", "react", "node.js", "django", "flask",
    "fastapi", "streamlit", "gradio",
    # Инструменты и платформы
    "docker", "kubernetes", "k8s", "mlops", "ci/cd", "devops",
    "git", "github", "gitlab", "jupyter", "colab", "airflow",
    "kubeflow", "mlflow", "jenkins", "ansible", "terraform",
    # Библиотеки и фреймворки
    "transformers", "huggingface", "langchain", "llamaindex",
    "spacy", "nltk", "gensim", "openai", "anthropic",
    # Облачные платформы
    "aws", "gcp", "azure", "yandex cloud", "cloud",
    # Базы данных
    "postgresql", "mongodb", "redis", "elasticsearch",
    # Русские термины
    "алгоритм", "модель", "нейросеть", "машинное обучение",
    "глубокое обучение", "обработка данных", "анализ данных",
    "библиотека", "фреймворк", "инструмент", "платформа",
]

# Индикаторы программы/курса
PROGRAM_INDICATORS = [
    "курс", "программа", "профессия", "специализация",
    "course", "program", "profession", "specialization",
    "bootcamp", "track", "обучение", "тренинг",
    "training", "workshop", "интенсив", "практикум",
]

# Индикаторы AI/ML/DS (для проверки близости к программе)
AI_INDICATORS = [
    "ai", "ml", "data", "analytics", "анализ", "аналитика",
    "машинное обучение", "нейросеть", "искусственный интеллект",
    "computer vision", "nlp", "llm", "gpt",
    "компьютерное зрение", "обработка естественного языка",
    "временные ряды", "обучение с подкреплением",
    "генеративные сети", "генетические алгоритмы",
]

# CTA-заголовки (шум)
CTA_TITLES = {
    "подробнее", "читать далее", "узнать больше", "learn more",
    "оставить заявку", "записаться", "регистрация",
    "sign up", "enroll now", "start now", "get started",
}

# Паттерны для проверки структуры программы
PROGRAM_PATTERNS = [
    r"(?:курс|программа|профессия|специализация|обучение).{0,50}(?:ai|ml|data|анализ|нейросеть|машинное|искусственный)",
    r"(?:course|program|profession|specialization|bootcamp).{0,50}(?:machine learning|deep learning|data science|ai|ml)",
    r"(?:нейросеть|искусственный интеллект|ai|ml).{0,50}(?:курс|программа|обучение)",
]

SPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-zа-я0-9]+")
WORD_RE = re.compile(r"[a-zа-я0-9]+")


CORE_TO_VALUE_PROP_MAP: dict[str, list[str]] = {
    "mentor_support": ["mentor_support"],
    "project_based_learning": ["project_based"],
    "portfolio_building": ["project_based"],
    "career_support": ["job_outcome"],
    "job_outcome_focus": ["job_outcome"],
    "practical_focus": ["project_based"],
    "theory_depth": ["academic_depth"],
    "certification": ["certificate"],
}

CORE_TO_FORMAT_SIGNAL_MAP: dict[str, list[str]] = {
    "flexible_schedule": ["self_paced"],
    "live_feedback": ["live_sessions"],
}

CORE_TO_SUPPORT_SIGNAL_MAP: dict[str, list[str]] = {
    "mentor_support": ["mentor_support", "mentor_layer"],
    "career_support": ["career_support"],
    "live_feedback": ["live_sessions"],
    "community_access": ["community_access"],
    "certification": ["certificate"],
}

CORE_TO_OUTCOME_SIGNAL_MAP: dict[str, list[str]] = {
    "project_based_learning": ["project_based"],
    "portfolio_building": ["project_based"],
    "career_support": ["job_outcome"],
    "job_outcome_focus": ["job_outcome"],
}

CORE_TO_INTENSITY_SIGNAL_MAP: dict[str, list[str]] = {
    "practical_focus": ["practice_intensity"],
    "theory_depth": ["academic_depth"],
}


def _normalize_text(value: str) -> str:
    value = (value or "").strip().lower().replace("ё", "е")
    return SPACE_RE.sub(" ", value)


def _normalize_title(value: str) -> str:
    return _normalize_text(value)


def _fingerprint_text(value: str) -> str:
    value = _normalize_title(value)
    return NON_ALNUM_RE.sub("", value)


def _dedupe_list(values: list[str]) -> list[str]:
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


def _contains_keyword(text: str, keyword: str) -> bool:
    keyword = _normalize_text(keyword)
    if not keyword:
        return False

    if " " in keyword or "-" in keyword or "/" in keyword:
        return keyword in text

    tokens = set(WORD_RE.findall(text))
    return keyword in tokens or keyword in text


def _match_rules(text: str, rules: dict[str, list[str]]) -> list[str]:
    matched: list[str] = []
    for label, keywords in rules.items():
        if any(_contains_keyword(text, keyword) for keyword in keywords):
            matched.append(label)
    return matched


def _text_blob(item: CatalogItemInput) -> str:
    parts = [
        item.title,
        item.description,
        item.category_hint,
        item.category_raw,
        " ".join(item.tags_raw),
        " ".join(item.ai_topics),
        " ".join(item.audience_types),
        item.duration_text,
        item.difficulty_level,
        item.provider_name,
    ]
    return _normalize_text(" ".join(part for part in parts if part))


def _normalize_item_type(item: CatalogItemInput, text: str) -> str:
    raw = _normalize_text(item.item_type or "")

    if raw in {"course", "program", "profession", "specialization", "track", "bootcamp"}:
        return raw

    title = _normalize_text(item.title or "")

    if "профес" in title:
        return "profession"
    if "специализац" in title or "specialization" in title:
        return "specialization"
    if "программа" in title or "program" in title:
        return "program"
    if "курс" in title or "course" in title:
        return "course"
    if "bootcamp" in title or "буткемп" in title:
        return "bootcamp"
    if "track" in title:
        return "track"

    if any(h in text for h in PROGRAM_INDICATORS):
        return "course"

    return raw or "unknown"


def _duration_bucket(item: CatalogItemInput) -> str:
    h = item.duration_hours

    if h is None:
        text = _normalize_text(item.duration_text or "")
        if not text:
            return "unknown"
        if any(x in text for x in ["час", "hours", "hour", "день", "day", "days"]):
            return "short"
        if any(x in text for x in ["нед", "week", "weeks", "месяц", "month", "months"]):
            return "medium"
        return "unknown"

    if h < 20:
        return "short"
    if h < 80:
        return "medium"
    if h < 180:
        return "long"
    return "extended"


def _difficulty_bucket(item: CatalogItemInput) -> str:
    value = _normalize_text(item.difficulty_level or "")
    if not value:
        return "unknown"

    if value in {"beginner", "junior", "easy", "basic", "начальный", "для начинающих"}:
        return "beginner"
    if value in {"middle", "intermediate", "средний"}:
        return "intermediate"
    if value in {"advanced", "senior", "expert", "hard", "продвинутый"}:
        return "advanced"

    if "начин" in value:
        return "beginner"
    if "сред" in value:
        return "intermediate"
    if "продвин" in value:
        return "advanced"

    return value


def _bool_value_props(item: CatalogItemInput) -> list[str]:
    result: list[str] = []
    if item.certificate_available is True:
        result.append("certificate")
    if item.project_based is True:
        result.append("project_based")
    if item.mentor_support is True:
        result.append("mentor_support")
    if item.job_support is True:
        result.append("job_outcome")
    return result


def _core_signals(item: CatalogItemInput, text: str) -> list[str]:
    result = _match_rules(text, CORE_SIGNAL_RULES)

    title = _normalize_text(item.title or "")
    provider = _normalize_text(item.provider_name or "")
    combined = f"{title} {provider} {text}"

    if item.project_based is True:
        result.extend(
            [
                "project_based_learning",
                "practical_focus",
            ]
        )

    if item.mentor_support is True:
        result.append("mentor_support")

    if item.job_support is True:
        result.extend(
            [
                "career_support",
                "job_outcome_focus",
            ]
        )

    if item.certificate_available is True:
        result.append("certification")

    if any(
        x in combined
        for x in [
            "портфолио",
            "portfolio",
            "github portfolio",
            "case studies",
            "showcase projects",
        ]
    ):
        result.append("portfolio_building")

    if any(
        x in combined
        for x in [
            "живая обратная связь",
            "live feedback",
            "live sessions",
            "office hours",
            "weekly calls",
            "разбор с преподавателем",
            "созвоны с экспертом",
        ]
    ):
        result.append("live_feedback")

    if any(
        x in combined
        for x in [
            "сообщество",
            "комьюнити",
            "community",
            "student chat",
            "peer community",
            "networking",
            "нетворкинг",
        ]
    ):
        result.append("community_access")

    if any(
        x in combined
        for x in [
            "фундаментальная подготовка",
            "математическая база",
            "deep theory",
            "fundamentals",
            "theoretical foundation",
            "research depth",
        ]
    ):
        result.append("theory_depth")

    if any(
        x in combined
        for x in [
            "в своем темпе",
            "гибкий график",
            "self-paced",
            "learn at your own pace",
            "asynchronous",
            "study anytime",
        ]
    ):
        result.append("flexible_schedule")

    if any(
        x in combined
        for x in [
            "самостоятельные задания",
            "самостоятельная работа",
            "домашние задания",
            "homework",
            "assignments",
            "independent assignments",
        ]
    ):
        result.append("independent_assignments")

    return [x for x in _dedupe_list(result) if x in CORE_SIGNAL_KEYS]


def _format_signals(
    item: CatalogItemInput,
    normalized_item_type: str,
    text: str,
    core_signals: list[str],
) -> list[str]:
    result = _match_rules(text, FORMAT_SIGNAL_RULES)

    if normalized_item_type and normalized_item_type != "unknown":
        result.append(normalized_item_type)

    if "online" in text or "онлайн" in text:
        result.append("online")
    if "live" in text or "вживую" in text or "с преподавателем" in text:
        result.append("live_sessions")
    if "ментор" in text or "mentor" in text or "наставник" in text or "куратор" in text:
        result.append("mentor_layer")
    if (
        "project" in text
        or "projects" in text
        or "проект" in text
        or "проектная работа" in text
        or "кейсы" in text
    ):
        result.append("project_work")

    for core in core_signals:
        result.extend(CORE_TO_FORMAT_SIGNAL_MAP.get(core, []))

    return _dedupe_list(result)


def _value_props(
    item: CatalogItemInput,
    text: str,
    core_signals: list[str],
) -> list[str]:
    taxonomy_value_props = _match_rules(text, VALUE_PROP_RULES)
    bool_value_props = _bool_value_props(item)

    derived_from_core: list[str] = []
    for core in core_signals:
        derived_from_core.extend(CORE_TO_VALUE_PROP_MAP.get(core, []))

    result = _dedupe_list(taxonomy_value_props + bool_value_props + derived_from_core)

    redundant_pairs = {
        "mentor_support": {"mentor_support"},
        "certificate": {"certification"},
        "job_outcome": {"career_support", "job_outcome_focus"},
        "project_based": {"project_based_learning", "portfolio_building", "practical_focus"},
        "academic_depth": {"theory_depth"},
    }

    cleaned: list[str] = []
    for value in result:
        blockers = redundant_pairs.get(value, set())
        if any(core in core_signals for core in blockers):
            cleaned.append(value)
        else:
            cleaned.append(value)

    return _dedupe_list(cleaned)


def _support_signals(
    value_props: list[str],
    format_signals: list[str],
    core_signals: list[str],
) -> list[str]:
    result: list[str] = []

    for signal in value_props:
        if signal in {"mentor_support", "certificate", "custom_training", "b2b_enablement"}:
            result.append(signal)

    for signal in format_signals:
        if signal in {"cohort", "hybrid", "enterprise_delivery", "mentor_layer", "live_sessions"}:
            result.append(signal)

    for core in core_signals:
        result.extend(CORE_TO_SUPPORT_SIGNAL_MAP.get(core, []))

    return _dedupe_list(result)


def _outcome_signals(
    value_props: list[str],
    core_signals: list[str],
) -> list[str]:
    result = [
        v
        for v in value_props
        if v in {"job_outcome", "project_based", "production_readiness", "llm_agent_readiness"}
    ]

    for core in core_signals:
        result.extend(CORE_TO_OUTCOME_SIGNAL_MAP.get(core, []))

    return _dedupe_list(result)


def _intensity_signals(
    value_props: list[str],
    duration_bucket: str,
    core_signals: list[str],
) -> list[str]:
    result: list[str] = []

    for signal in value_props:
        if signal in {"academic_depth", "short_intensive"}:
            result.append(signal)

    for core in core_signals:
        result.extend(CORE_TO_INTENSITY_SIGNAL_MAP.get(core, []))

    if duration_bucket in {"long", "extended"}:
        result.append("long_form_learning")
    if duration_bucket == "short":
        result.append("short_form_learning")

    return _dedupe_list(result)


# ============================================================
# АЛГОРИТМИЧЕСКАЯ ПРОВЕРКА НА ШУМ (вместо хардкода)
# ============================================================

def _is_ai_relevant(text: str) -> bool:
    """Проверяет, релевантен ли текст AI/ML/DS тематике"""
    text_lower = text.lower()
    
    # Проверка по общим ключевым словам
    for keyword in UNIQUE_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    
    # Проверка по 12 направлениям компании
    for direction in COMPANY_DIRECTIONS.values():
        for keyword in direction.get("keywords", []):
            if keyword.lower() in text_lower:
                return True
    
    return False


def _has_technical_keywords(text: str) -> bool:
    """Проверяет наличие технических ключевых слов"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in TECH_KEYWORDS)


def _looks_like_ai_program(text: str) -> bool:
    """Проверяет, похоже ли на AI/ML программу"""
    text_lower = text.lower()
    
    # 1. Проверяем наличие индикаторов программы
    if not any(ind in text_lower for ind in PROGRAM_INDICATORS):
        return False
    
    # 2. Проверяем наличие AI/ML индикаторов
    if not any(ind in text_lower for ind in AI_INDICATORS):
        return False
    
    # 3. Проверяем близость AI-индикаторов к индикаторам программы
    program_positions = []
    ai_positions = []
    
    for ind in PROGRAM_INDICATORS:
        for match in re.finditer(ind, text_lower):
            program_positions.append(match.start())
    
    for ind in AI_INDICATORS:
        for match in re.finditer(ind, text_lower):
            ai_positions.append(match.start())
    
    for p_pos in program_positions:
        for a_pos in ai_positions:
            if abs(p_pos - a_pos) < 50:
                return True
    
    # 4. Проверка по регулярным выражениям
    for pattern in PROGRAM_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False


def _is_noise(item: CatalogItemInput, text: str) -> tuple[bool, list[str]]:
    """
    Определяет, является ли элемент шумом с использованием алгоритмической проверки
    (без хардкода)
    """
    reasons: list[str] = []
    title = _normalize_text(item.title or "")
    description = _normalize_text(item.description or "")

    # 1. Проверка по длине
    if len(title) < 4:
        reasons.append("title_too_short")

    if len(description) < 20:
        reasons.append("description_too_short")

    # 2. Проверка на CTA-заголовки
    if title in CTA_TITLES:
        reasons.append("generic_cta_title")

    # 3. Проверка на релевантность AI/ML/DS
    if not _is_ai_relevant(text):
        reasons.append("not_ai_relevant")

    # 4. Проверка на технические ключевые слова
    if not _has_technical_keywords(text):
        reasons.append("no_technical_keywords")

    # 5. Проверка на структуру программы/курса
    if not _looks_like_ai_program(text):
        reasons.append("not_program_like")

    return (len(reasons) > 0, reasons)


def _quality_score(
    *,
    item: CatalogItemInput,
    normalized_item_type: str,
    topic_clusters: list[str],
    competency_families: list[str],
    audience_segments: list[str],
    value_props: list[str],
    core_signals: list[str],
    format_signals: list[str],
    is_noise: bool,
) -> float:
    score = 0.0

    if item.title:
        score += 0.12
    if item.description and len(item.description) >= 80:
        score += 0.18
    if item.canonical_url or item.source_url:
        score += 0.10
    if normalized_item_type and normalized_item_type != "unknown":
        score += 0.10
    if topic_clusters:
        score += 0.10
    if competency_families:
        score += 0.10
    if audience_segments:
        score += 0.05
    if value_props:
        score += 0.07
    if core_signals:
        score += min(0.12, len(core_signals) * 0.02)
    if format_signals:
        score += 0.05
    if item.duration_hours is not None or item.duration_text:
        score += 0.03
    if item.difficulty_level:
        score += 0.02

    if is_noise:
        score -= 0.40

    return max(0.0, min(1.0, round(score, 4)))


def classify_catalog_items(platform_reports: list[PlatformReportInput]) -> list[OfferFeatures]:
    """
    Классифицирует элементы каталога, используя общие ключевые слова
    """
    result: list[OfferFeatures] = []

    for report in platform_reports:
        for item in report.items:
            text = _text_blob(item)
            normalized_title = _normalize_title(item.title)
            normalized_item_type = _normalize_item_type(item, text)

            # Используем общие ключевые слова для определения направлений
            topic_clusters = _dedupe_list(_match_rules(text, TOPIC_CLUSTER_RULES))
            topic_clusters = [t for t in topic_clusters if t in TOPIC_KEYS]

            # Дополнительные топики из общих ключевых слов
            for direction_key, direction in COMPANY_DIRECTIONS.items():
                direction_name = direction["name"]
                if direction_name in text or any(kw in text for kw in direction.get("keywords", [])):
                    if direction_name not in topic_clusters:
                        topic_clusters.append(direction_name)

            competency_families = _dedupe_list(_match_rules(text, COMPETENCY_FAMILY_RULES))
            audience_segments = _dedupe_list(_match_rules(text, AUDIENCE_RULES))

            core_signals = _core_signals(item, text)
            value_props = _value_props(item, text, core_signals)
            format_signals = _format_signals(item, normalized_item_type, text, core_signals)

            duration_bucket = _duration_bucket(item)
            difficulty_bucket = _difficulty_bucket(item)

            support_signals = _support_signals(value_props, format_signals, core_signals)
            outcome_signals = _outcome_signals(value_props, core_signals)
            intensity_signals = _intensity_signals(value_props, duration_bucket, core_signals)

            is_noise, noise_reasons = _is_noise(item, text)
            quality_score = _quality_score(
                item=item,
                normalized_item_type=normalized_item_type,
                topic_clusters=topic_clusters,
                competency_families=competency_families,
                audience_segments=audience_segments,
                value_props=value_props,
                core_signals=core_signals,
                format_signals=format_signals,
                is_noise=is_noise,
            )

            parsed_url = urlparse(item.canonical_url or item.source_url or "")
            url_fp = (parsed_url.netloc + parsed_url.path).strip()

            text_fingerprint = url_fp or _fingerprint_text(
                " ".join(
                    [
                        item.title or "",
                        (item.description or "")[:160],
                        normalized_item_type,
                        " ".join(topic_clusters[:3]),
                        " ".join(competency_families[:3]),
                        " ".join(core_signals[:4]),
                    ]
                )
            )

            result.append(
                OfferFeatures(
                    platform_name=report.platform_name,
                    item_id=item.item_id,
                    title=item.title,
                    description=item.description,
                    canonical_url=item.canonical_url or item.source_url,
                    item_type=normalized_item_type,
                    normalized_title=normalized_title,
                    text_fingerprint=text_fingerprint,
                    topic_clusters=topic_clusters,
                    competency_families=competency_families,
                    audience_segments=audience_segments,
                    value_props=value_props,
                    core_signals=core_signals,
                    support_signals=support_signals,
                    outcome_signals=outcome_signals,
                    intensity_signals=intensity_signals,
                    format_signals=format_signals,
                    duration_bucket=duration_bucket,
                    difficulty_bucket=difficulty_bucket,
                    quality_score=quality_score,
                    is_noise=is_noise,
                    noise_reasons=noise_reasons,
                    evidence_text=(f"{item.title} {item.description}".strip())[:500],
                )
            )

    return result