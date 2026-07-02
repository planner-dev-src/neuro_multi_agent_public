from __future__ import annotations

from collections import Counter
from math import log2
from statistics import median
from typing import Iterable

from src.agents.market_agent.models import CatalogItem, CourseRecord, ProgramRecord


DEFAULT_AI_TOPIC_TAXONOMY: dict[str, list[str]] = {
    "llm_agents": ["llm", "agent", "agents", "gpt", "rag", "prompt", "assistant"],
    "nlp": ["nlp", "natural language", "language model", "text"],
    "cv": ["computer vision", "vision", "image", "cnn"],
    "speech_audio": ["speech", "audio", "asr", "tts"],
    "classical_ml": ["machine learning", "ml", "regression", "classification"],
    "rl": ["reinforcement learning", "rl"],
    "timeseries": ["time series", "forecasting"],
    "gan": ["gan", "generative adversarial"],
    "automl": ["automl"],
    "production_integration": ["production", "deployment", "mlops", "integration"],
    "ai_pm_sales": ["product", "management", "sales", "business"],
    "genetic_algorithms": ["genetic algorithm", "evolutionary"],
}


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def safe_mean(values: Iterable[float | int | None]) -> float:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return 0.0
    return sum(nums) / len(nums)


def safe_median(values: Iterable[float | int | None]) -> float:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return 0.0
    return float(median(nums))


def ratio(part: int | float, whole: int | float) -> float:
    if not whole:
        return 0.0
    return float(part) / float(whole)


def compute_hhi(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return sum((count / total) ** 2 for count in counter.values())


def compute_entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in counter.values():
        p = count / total
        if p > 0:
            entropy -= p * log2(p)
    return entropy


def top_share(counter: Counter[str], top_n: int) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    top_total = sum(count for _, count in counter.most_common(top_n))
    return top_total / total


def detect_topics_from_text(
    text: str,
    taxonomy: dict[str, list[str]] | None = None,
) -> list[str]:
    taxonomy = taxonomy or DEFAULT_AI_TOPIC_TAXONOMY
    text_norm = normalize_text(text)

    matched_topics: list[str] = []
    for topic_name, keywords in taxonomy.items():
        for keyword in keywords:
            if normalize_text(keyword) in text_norm:
                matched_topics.append(topic_name)
                break

    return matched_topics


def classify_catalog_item(item: CatalogItem) -> str:
    item_type = normalize_text(getattr(item, "item_type", None))
    title = normalize_text(getattr(item, "title", None))
    description = normalize_text(getattr(item, "description", None))
    full_text = f"{title} {description}".strip()

    if item_type in {"course", "program", "lesson", "catalog_page"}:
        return item_type

    program_markers = [
        "specialization",
        "certificate",
        "bootcamp",
        "learning path",
        "program",
    ]
    course_markers = ["course", "module", "learn", "training"]

    if any(marker in full_text for marker in program_markers):
        return "program"
    if any(marker in full_text for marker in course_markers):
        return "course"
    return "unknown"


def _copy_list(value: list[str] | None) -> list[str]:
    return list(value) if value else []


def _coalesce_unknown(value: str | None) -> str:
    normalized = (value or "").strip()
    return normalized if normalized else "unknown"


def catalog_item_to_course(item: CatalogItem) -> CourseRecord:
    ai_topics = item.ai_topics or detect_topics_from_text(
        f"{item.title} {item.description}"
    )

    topic_primary = ai_topics[0] if ai_topics else "unknown"
    topic_secondary = ai_topics[1:] if len(ai_topics) > 1 else []

    return CourseRecord(
        course_id=item.item_id,
        source_platform=item.source_platform,
        source_url=item.source_url,
        canonical_url=item.canonical_url,
        title=item.title,
        short_description=item.description,
        topic_primary=topic_primary,
        topic_secondary=topic_secondary,
        difficulty_level=_coalesce_unknown(item.difficulty_level),
        lessons_count=item.lessons_count,
        modules_count=item.modules_count,
        duration_hours=item.duration_hours,
        has_certificate=item.certificate_available,
        has_projects=item.project_based,
        has_assignments=None,
        has_mentor_support=item.mentor_support,
        has_job_support=item.job_support,
        self_paced=None,
        language=item.language,
        audience_types=_copy_list(item.audience_types),
        ai_topics=ai_topics,
        parent_program_id=item.parent_program_id,
        extracted_from_item_id=item.item_id,
        extraction_confidence=item.extraction_confidence,
    )


def catalog_item_to_program(item: CatalogItem) -> ProgramRecord:
    ai_topics = item.ai_topics or detect_topics_from_text(
        f"{item.title} {item.description}"
    )

    topic_primary = ai_topics[0] if ai_topics else "unknown"
    topic_secondary = ai_topics[1:] if len(ai_topics) > 1 else []

    return ProgramRecord(
        program_id=item.item_id,
        source_platform=item.source_platform,
        source_url=item.source_url,
        canonical_url=item.canonical_url,
        title=item.title,
        short_description=item.description,
        program_type=item.category_raw or "unknown",
        topic_primary=topic_primary,
        topic_secondary=topic_secondary,
        courses_count=len(item.child_course_ids) if item.child_course_ids else None,
        lessons_count_estimated=item.lessons_count,
        duration_hours=item.duration_hours,
        has_certificate=item.certificate_available,
        has_projects=item.project_based,
        has_mentor_support=item.mentor_support,
        has_job_support=item.job_support,
        language=item.language,
        audience_types=_copy_list(item.audience_types),
        ai_topics=ai_topics,
        child_course_ids=_copy_list(item.child_course_ids),
        extracted_from_item_id=item.item_id,
        extraction_confidence=item.extraction_confidence,
    )


def normalize_catalog_items(
    items: list[CatalogItem],
) -> tuple[list[CourseRecord], list[ProgramRecord]]:
    courses: list[CourseRecord] = []
    programs: list[ProgramRecord] = []

    for item in items:
        resolved_type = classify_catalog_item(item)

        if resolved_type == "course":
            courses.append(catalog_item_to_course(item))
        elif resolved_type == "program":
            programs.append(catalog_item_to_program(item))

    return courses, programs


def compute_breadth_metrics(
    courses: list[CourseRecord],
    programs: list[ProgramRecord],
) -> dict:
    primary_topics = [c.topic_primary for c in courses if c.topic_primary != "unknown"]

    ai_topics: list[str] = []
    for course in courses:
        ai_topics.extend(course.ai_topics)

    difficulty_counter = Counter(
        _coalesce_unknown(c.difficulty_level) for c in courses
    )

    return {
        "programs_total": len(programs),
        "courses_total": len(courses),
        "distinct_topics_total": len(set(primary_topics)),
        "distinct_ai_topics_total": len(set(ai_topics)),
        "beginner_courses_total": difficulty_counter.get("beginner", 0),
        "intermediate_courses_total": difficulty_counter.get("intermediate", 0),
        "advanced_courses_total": difficulty_counter.get("advanced", 0),
        "mixed_courses_total": difficulty_counter.get("mixed", 0),
        "unknown_level_courses_total": difficulty_counter.get("unknown", 0),
    }


def compute_depth_metrics(
    courses: list[CourseRecord],
    programs: list[ProgramRecord],
) -> dict:
    lesson_counts = [c.lessons_count for c in courses if c.lessons_count is not None]
    module_counts = [c.modules_count for c in courses if c.modules_count is not None]
    duration_values = [c.duration_hours for c in courses if c.duration_hours is not None]

    explicit_program_course_counts = [
        p.courses_count for p in programs if p.courses_count is not None
    ]

    if explicit_program_course_counts:
        avg_courses_per_program = safe_mean(explicit_program_course_counts)
    else:
        avg_courses_per_program = ratio(len(courses), len(programs)) if programs else 0.0

    return {
        "lessons_total": sum(lesson_counts) if lesson_counts else 0,
        "modules_total": sum(module_counts) if module_counts else 0,
        "avg_lessons_per_course": safe_mean(lesson_counts),
        "median_lessons_per_course": safe_median(lesson_counts),
        "avg_modules_per_course": safe_mean(module_counts),
        "median_modules_per_course": safe_median(module_counts),
        "avg_duration_hours_per_course": safe_mean(duration_values),
        "median_duration_hours_per_course": safe_median(duration_values),
        "avg_courses_per_program": avg_courses_per_program,
    }


def compute_coverage_metrics(
    courses: list[CourseRecord],
    programs: list[ProgramRecord],
    taxonomy: dict[str, list[str]] | None = None,
) -> dict:
    taxonomy = taxonomy or DEFAULT_AI_TOPIC_TAXONOMY

    topic_counter = Counter(
        c.topic_primary for c in courses if c.topic_primary and c.topic_primary != "unknown"
    )

    ai_topic_counter: Counter[str] = Counter()
    for course in courses:
        ai_topic_counter.update(course.ai_topics)

    program_topic_counter = Counter(
        p.topic_primary for p in programs if p.topic_primary and p.topic_primary != "unknown"
    )

    covered_taxonomy_topics = {
        topic for topic in taxonomy.keys() if ai_topic_counter.get(topic, 0) > 0
    }

    advanced_courses_total = sum(
        1 for c in courses if _coalesce_unknown(c.difficulty_level) == "advanced"
    )
    advanced_ai_courses_total = sum(
        1
        for c in courses
        if _coalesce_unknown(c.difficulty_level) == "advanced"
        and c.topic_primary != "unknown"
    )

    return {
        "topic_coverage_map": dict(topic_counter),
        "ai_topic_coverage_map": dict(ai_topic_counter),
        "program_topic_coverage_map": dict(program_topic_counter),
        "taxonomy_topics_total": len(taxonomy),
        "taxonomy_topics_covered": len(covered_taxonomy_topics),
        "ai_topic_coverage_ratio": ratio(len(covered_taxonomy_topics), len(taxonomy)),
        "advanced_courses_total": advanced_courses_total,
        "advanced_topic_coverage_ratio": ratio(advanced_ai_courses_total, len(courses)),
    }


def compute_concentration_metrics(
    courses: list[CourseRecord],
) -> dict:
    topic_counter = Counter(
        c.topic_primary for c in courses if c.topic_primary and c.topic_primary != "unknown"
    )

    if not topic_counter:
        return {
            "largest_topic_name": "unknown",
            "largest_topic_share": 0.0,
            "top_3_topics_share": 0.0,
            "top_5_topics_share": 0.0,
            "topic_hhi": 0.0,
            "topic_entropy": 0.0,
        }

    largest_topic_name, largest_topic_count = topic_counter.most_common(1)[0]
    total = sum(topic_counter.values())

    return {
        "largest_topic_name": largest_topic_name,
        "largest_topic_share": ratio(largest_topic_count, total),
        "top_3_topics_share": top_share(topic_counter, 3),
        "top_5_topics_share": top_share(topic_counter, 5),
        "topic_hhi": compute_hhi(topic_counter),
        "topic_entropy": compute_entropy(topic_counter),
    }


def build_platform_analytics(
    platform_name: str,
    courses: list[CourseRecord],
    programs: list[ProgramRecord],
    taxonomy: dict[str, list[str]] | None = None,
) -> dict:
    breadth = compute_breadth_metrics(courses, programs)
    depth = compute_depth_metrics(courses, programs)
    coverage = compute_coverage_metrics(courses, programs, taxonomy=taxonomy)
    concentration = compute_concentration_metrics(courses)

    return {
        "platform_name": platform_name,
        "breadth": breadth,
        "depth": depth,
        "coverage": coverage,
        "concentration": concentration,
        "summary": {
            "programs_total": breadth["programs_total"],
            "courses_total": breadth["courses_total"],
            "lessons_total": depth["lessons_total"],
            "distinct_ai_topics_total": breadth["distinct_ai_topics_total"],
            "ai_topic_coverage_ratio": coverage["ai_topic_coverage_ratio"],
            "advanced_courses_total": coverage["advanced_courses_total"],
            "largest_topic_name": concentration["largest_topic_name"],
            "largest_topic_share": concentration["largest_topic_share"],
        },
    }


def build_platform_analytics_from_items(
    platform_name: str,
    items: list[CatalogItem],
    taxonomy: dict[str, list[str]] | None = None,
) -> dict:
    courses, programs = normalize_catalog_items(items)
    analytics = build_platform_analytics(
        platform_name=platform_name,
        courses=courses,
        programs=programs,
        taxonomy=taxonomy,
    )

    analytics["normalized_entities"] = {
        "catalog_items_total": len(items),
        "courses_total": len(courses),
        "programs_total": len(programs),
    }
    return analytics