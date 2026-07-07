from __future__ import annotations

from math import log2

import pytest

from src.agents.market_agent.analyzer import (
    build_platform_analytics,
    build_platform_analytics_from_items,
    classify_catalog_item,
    compute_concentration_metrics,
    compute_coverage_metrics,
    detect_topics_from_text,
    normalize_catalog_items,
)
from src.agents.market_agent.models import CatalogItem, CourseRecord, ProgramRecord


def _catalog_item(
    *,
    item_id: str,
    title: str,
    description: str,
    item_type: str = "unknown",
    source_platform: str = "example_platform",
    source_url: str | None = None,
    canonical_url: str | None = None,
    difficulty_level: str | None = None,
    lessons_count: int | None = None,
    modules_count: int | None = None,
    duration_hours: float | None = None,
    certificate_available: bool | None = None,
    project_based: bool | None = None,
    mentor_support: bool | None = None,
    job_support: bool | None = None,
    language: str | None = "en",
    audience_types: list[str] | None = None,
    ai_topics: list[str] | None = None,
    parent_program_id: str | None = None,
    child_course_ids: list[str] | None = None,
    category_raw: str | None = None,
    extraction_confidence: float | None = 0.9,
) -> CatalogItem:
    return CatalogItem(
        item_id=item_id,
        item_type=item_type,
        source_platform=source_platform,
        source_url=source_url or f"https://example.com/{item_id}",
        canonical_url=canonical_url or f"https://example.com/{item_id}",
        title=title,
        description=description,
        category_raw=category_raw,
        difficulty_level=difficulty_level,
        lessons_count=lessons_count,
        modules_count=modules_count,
        duration_hours=duration_hours,
        certificate_available=certificate_available,
        project_based=project_based,
        mentor_support=mentor_support,
        job_support=job_support,
        language=language,
        audience_types=audience_types or [],
        ai_topics=ai_topics or [],
        parent_program_id=parent_program_id,
        child_course_ids=child_course_ids or [],
        extraction_confidence=extraction_confidence,
    )


def _course(
    *,
    course_id: str,
    topic_primary: str,
    ai_topics: list[str],
    difficulty_level: str = "unknown",
    lessons_count: int | None = None,
    modules_count: int | None = None,
    duration_hours: float | None = None,
) -> CourseRecord:
    return CourseRecord(
        course_id=course_id,
        source_platform="example_platform",
        source_url=f"https://example.com/{course_id}",
        canonical_url=f"https://example.com/{course_id}",
        title=course_id,
        short_description=f"{course_id} description",
        topic_primary=topic_primary,
        topic_secondary=ai_topics[1:] if len(ai_topics) > 1 else [],
        difficulty_level=difficulty_level,
        lessons_count=lessons_count,
        modules_count=modules_count,
        duration_hours=duration_hours,
        has_certificate=True,
        has_projects=True,
        has_assignments=None,
        has_mentor_support=False,
        has_job_support=False,
        self_paced=None,
        language="en",
        audience_types=["individual_learners"],
        ai_topics=ai_topics,
        parent_program_id=None,
        extracted_from_item_id=course_id,
        extraction_confidence=0.95,
    )


def _program(
    *,
    program_id: str,
    topic_primary: str,
    ai_topics: list[str],
    courses_count: int | None = None,
    lessons_count_estimated: int | None = None,
    duration_hours: float | None = None,
) -> ProgramRecord:
    return ProgramRecord(
        program_id=program_id,
        source_platform="example_platform",
        source_url=f"https://example.com/{program_id}",
        canonical_url=f"https://example.com/{program_id}",
        title=program_id,
        short_description=f"{program_id} description",
        program_type="specialization",
        topic_primary=topic_primary,
        topic_secondary=ai_topics[1:] if len(ai_topics) > 1 else [],
        courses_count=courses_count,
        lessons_count_estimated=lessons_count_estimated,
        duration_hours=duration_hours,
        has_certificate=True,
        has_projects=True,
        has_mentor_support=False,
        has_job_support=False,
        language="en",
        audience_types=["individual_learners"],
        ai_topics=ai_topics,
        child_course_ids=[],
        extracted_from_item_id=program_id,
        extraction_confidence=0.95,
    )


def test_detect_topics_from_text_matches_multiple_taxonomy_topics() -> None:
    text = """
    Learn GPT agents, prompt design, retrieval-augmented generation, and NLP workflows.
    Includes machine learning foundations and production deployment basics.
    """.strip()

    topics = detect_topics_from_text(text)

    assert "llm_agents" in topics
    assert "nlp" in topics
    assert "classical_ml" in topics
    assert "production_integration" in topics


def test_classify_catalog_item_uses_item_type_when_supported() -> None:
    item = _catalog_item(
        item_id="c1",
        item_type="course",
        title="Anything",
        description="Anything",
    )

    assert classify_catalog_item(item) == "course"


def test_classify_catalog_item_falls_back_to_text_markers() -> None:
    course_like = _catalog_item(
        item_id="c1",
        item_type="unknown",
        title="AI Course",
        description="Hands-on training with modules",
    )
    program_like = _catalog_item(
        item_id="p1",
        item_type="unknown",
        title="AI Specialization",
        description="Certificate learning path",
    )

    assert classify_catalog_item(course_like) == "course"
    assert classify_catalog_item(program_like) == "program"


def test_normalize_catalog_items_splits_courses_and_programs() -> None:
    items = [
        _catalog_item(
            item_id="course-1",
            item_type="course",
            title="GPT Agents Course",
            description="Prompt engineering, RAG, and assistant workflows",
            difficulty_level="beginner",
            lessons_count=12,
            modules_count=4,
            duration_hours=8.5,
            certificate_available=True,
            project_based=True,
            mentor_support=False,
            job_support=False,
            audience_types=["individual_learners"],
        ),
        _catalog_item(
            item_id="program-1",
            item_type="program",
            title="AI Engineering Specialization",
            description="Certificate path for machine learning and deployment",
            category_raw="specialization",
            lessons_count=40,
            duration_hours=30.0,
            certificate_available=True,
            project_based=True,
            mentor_support=True,
            job_support=False,
            audience_types=["professionals"],
            child_course_ids=["course-1", "course-2"],
        ),
        _catalog_item(
            item_id="misc-1",
            item_type="catalog_page",
            title="Catalog landing page",
            description="Overview page only",
        ),
    ]

    courses, programs = normalize_catalog_items(items)

    assert len(courses) == 1
    assert len(programs) == 1

    course = courses[0]
    assert course.course_id == "course-1"
    assert course.topic_primary == "llm_agents"
    assert "llm_agents" in course.ai_topics
    assert course.lessons_count == 12
    assert course.modules_count == 4

    program = programs[0]
    assert program.program_id == "program-1"
    assert program.program_type == "specialization"
    assert program.courses_count == 2


def test_compute_coverage_metrics_counts_taxonomy_coverage() -> None:
    courses = [
        _course(
            course_id="c1",
            topic_primary="llm_agents",
            ai_topics=["llm_agents", "nlp"],
            difficulty_level="advanced",
        ),
        _course(
            course_id="c2",
            topic_primary="classical_ml",
            ai_topics=["classical_ml", "production_integration"],
            difficulty_level="beginner",
        ),
        _course(
            course_id="c3",
            topic_primary="unknown",
            ai_topics=[],
            difficulty_level="advanced",
        ),
    ]
    programs = [
        _program(
            program_id="p1",
            topic_primary="llm_agents",
            ai_topics=["llm_agents"],
            courses_count=2,
        )
    ]

    coverage = compute_coverage_metrics(courses, programs)

    assert coverage["topic_coverage_map"]["llm_agents"] == 1
    assert coverage["topic_coverage_map"]["classical_ml"] == 1
    assert coverage["ai_topic_coverage_map"]["llm_agents"] == 1
    assert coverage["ai_topic_coverage_map"]["nlp"] == 1
    assert coverage["ai_topic_coverage_map"]["classical_ml"] == 1
    assert coverage["ai_topic_coverage_map"]["production_integration"] == 1
    assert coverage["program_topic_coverage_map"]["llm_agents"] == 1
    assert coverage["taxonomy_topics_total"] == 12
    assert coverage["taxonomy_topics_covered"] == 4
    assert coverage["ai_topic_coverage_ratio"] == pytest.approx(4 / 12)
    assert coverage["advanced_courses_total"] == 2
    assert coverage["advanced_topic_coverage_ratio"] == pytest.approx(1 / 3)


def test_compute_concentration_metrics_returns_expected_distribution_stats() -> None:
    courses = [
        _course(course_id="c1", topic_primary="llm_agents", ai_topics=["llm_agents"]),
        _course(course_id="c2", topic_primary="llm_agents", ai_topics=["llm_agents"]),
        _course(course_id="c3", topic_primary="nlp", ai_topics=["nlp"]),
        _course(course_id="c4", topic_primary="classical_ml", ai_topics=["classical_ml"]),
    ]

    concentration = compute_concentration_metrics(courses)

    expected_hhi = (2 / 4) ** 2 + (1 / 4) ** 2 + (1 / 4) ** 2
    expected_entropy = -(
        (2 / 4) * log2(2 / 4)
        + (1 / 4) * log2(1 / 4)
        + (1 / 4) * log2(1 / 4)
    )

    assert concentration["largest_topic_name"] == "llm_agents"
    assert concentration["largest_topic_share"] == pytest.approx(0.5)
    assert concentration["top_3_topics_share"] == pytest.approx(1.0)
    assert concentration["top_5_topics_share"] == pytest.approx(1.0)
    assert concentration["topic_hhi"] == pytest.approx(expected_hhi)
    assert concentration["topic_entropy"] == pytest.approx(expected_entropy)


def test_build_platform_analytics_aggregates_breadth_depth_coverage_and_concentration() -> None:
    courses = [
        _course(
            course_id="c1",
            topic_primary="llm_agents",
            ai_topics=["llm_agents", "nlp"],
            difficulty_level="beginner",
            lessons_count=10,
            modules_count=3,
            duration_hours=5.0,
        ),
        _course(
            course_id="c2",
            topic_primary="classical_ml",
            ai_topics=["classical_ml"],
            difficulty_level="advanced",
            lessons_count=20,
            modules_count=5,
            duration_hours=12.0,
        ),
        _course(
            course_id="c3",
            topic_primary="llm_agents",
            ai_topics=["llm_agents", "production_integration"],
            difficulty_level="advanced",
            lessons_count=30,
            modules_count=6,
            duration_hours=15.0,
        ),
    ]
    programs = [
        _program(
            program_id="p1",
            topic_primary="llm_agents",
            ai_topics=["llm_agents", "nlp"],
            courses_count=2,
            lessons_count_estimated=40,
            duration_hours=20.0,
        ),
        _program(
            program_id="p2",
            topic_primary="classical_ml",
            ai_topics=["classical_ml"],
            courses_count=1,
            lessons_count_estimated=20,
            duration_hours=12.0,
        ),
    ]

    analytics = build_platform_analytics(
        platform_name="Example Platform",
        courses=courses,
        programs=programs,
    )

    assert analytics["platform_name"] == "Example Platform"

    breadth = analytics["breadth"]
    assert breadth["programs_total"] == 2
    assert breadth["courses_total"] == 3
    assert breadth["distinct_topics_total"] == 2
    assert breadth["distinct_ai_topics_total"] == 4
    assert breadth["beginner_courses_total"] == 1
    assert breadth["advanced_courses_total"] == 2

    depth = analytics["depth"]
    assert depth["lessons_total"] == 60
    assert depth["modules_total"] == 14
    assert depth["avg_lessons_per_course"] == pytest.approx(20.0)
    assert depth["median_lessons_per_course"] == pytest.approx(20.0)
    assert depth["avg_modules_per_course"] == pytest.approx(14 / 3)
    assert depth["median_modules_per_course"] == pytest.approx(5.0)
    assert depth["avg_duration_hours_per_course"] == pytest.approx((5.0 + 12.0 + 15.0) / 3)
    assert depth["median_duration_hours_per_course"] == pytest.approx(12.0)
    assert depth["avg_courses_per_program"] == pytest.approx(1.5)

    coverage = analytics["coverage"]
    assert coverage["taxonomy_topics_covered"] == 4
    assert coverage["ai_topic_coverage_ratio"] == pytest.approx(4 / 12)
    assert coverage["advanced_courses_total"] == 2
    assert coverage["advanced_topic_coverage_ratio"] == pytest.approx(2 / 3)

    concentration = analytics["concentration"]
    assert concentration["largest_topic_name"] == "llm_agents"
    assert concentration["largest_topic_share"] == pytest.approx(2 / 3)
    assert concentration["top_3_topics_share"] == pytest.approx(1.0)

    summary = analytics["summary"]
    assert summary["programs_total"] == 2
    assert summary["courses_total"] == 3
    assert summary["lessons_total"] == 60
    assert summary["distinct_ai_topics_total"] == 4
    assert summary["advanced_courses_total"] == 2
    assert summary["largest_topic_name"] == "llm_agents"


def test_build_platform_analytics_from_items_normalizes_and_aggregates() -> None:
    items = [
        _catalog_item(
            item_id="course-1",
            item_type="course",
            title="GPT Agents Bootcamp",
            description="Build agent systems with prompt and assistant workflows",
            difficulty_level="beginner",
            lessons_count=10,
            modules_count=2,
            duration_hours=6.0,
            certificate_available=True,
            project_based=True,
            audience_types=["individual_learners"],
        ),
        _catalog_item(
            item_id="course-2",
            item_type="course",
            title="Machine Learning in Production",
            description="Machine learning deployment and mlops integration",
            difficulty_level="advanced",
            lessons_count=16,
            modules_count=4,
            duration_hours=10.0,
            certificate_available=True,
            project_based=True,
            audience_types=["professionals"],
        ),
        _catalog_item(
            item_id="program-1",
            item_type="program",
            title="AI Career Certificate",
            description="Certificate program covering GPT, NLP, and production skills",
            category_raw="certificate",
            lessons_count=30,
            duration_hours=20.0,
            certificate_available=True,
            project_based=True,
            mentor_support=True,
            audience_types=["professionals"],
            child_course_ids=["course-1", "course-2"],
        ),
    ]

    analytics = build_platform_analytics_from_items(
        platform_name="Example Platform",
        items=items,
    )

    assert analytics["platform_name"] == "Example Platform"

    normalized_entities = analytics["normalized_entities"]
    assert normalized_entities["catalog_items_total"] == 3
    assert normalized_entities["courses_total"] == 2
    assert normalized_entities["programs_total"] == 1

    breadth = analytics["breadth"]
    assert breadth["courses_total"] == 2
    assert breadth["programs_total"] == 1
    assert breadth["beginner_courses_total"] == 1
    assert breadth["advanced_courses_total"] == 1

    depth = analytics["depth"]
    assert depth["lessons_total"] == 26
    assert depth["modules_total"] == 6
    assert depth["avg_courses_per_program"] == pytest.approx(2.0)

    coverage = analytics["coverage"]
    assert coverage["taxonomy_topics_covered"] >= 3
    assert coverage["advanced_courses_total"] == 1

    concentration = analytics["concentration"]
    assert concentration["largest_topic_name"] in {"llm_agents", "classical_ml"}
    assert concentration["largest_topic_share"] == pytest.approx(0.5)