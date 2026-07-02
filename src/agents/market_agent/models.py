from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CatalogItemType = Literal["course", "program", "lesson", "catalog_page", "unknown"]
DifficultyLevel = Literal["beginner", "intermediate", "advanced", "mixed", "unknown"]


@dataclass(slots=True)
class CatalogItem:
    item_id: str
    source_platform: str
    source_url: str
    canonical_url: str

    item_type: CatalogItemType = "unknown"
    title: str = ""
    description: str = ""

    provider_name: str = ""
    language: str = ""
    category_raw: str = ""
    tags_raw: list[str] = field(default_factory=list)

    difficulty_level: DifficultyLevel = "unknown"
    duration_text: str = ""
    duration_hours: float | None = None

    lessons_count: int | None = None
    modules_count: int | None = None

    certificate_available: bool | None = None
    project_based: bool | None = None
    mentor_support: bool | None = None
    job_support: bool | None = None

    ai_topics: list[str] = field(default_factory=list)
    audience_types: list[str] = field(default_factory=list)

    parent_program_id: str | None = None
    child_course_ids: list[str] = field(default_factory=list)

    crawl_depth: int = 0
    extraction_confidence: float = 0.0
    extraction_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CourseRecord:
    course_id: str
    source_platform: str
    source_url: str
    canonical_url: str

    title: str
    short_description: str = ""

    topic_primary: str = "unknown"
    topic_secondary: list[str] = field(default_factory=list)

    difficulty_level: DifficultyLevel = "unknown"

    lessons_count: int | None = None
    modules_count: int | None = None
    duration_hours: float | None = None

    has_certificate: bool | None = None
    has_projects: bool | None = None
    has_assignments: bool | None = None
    has_mentor_support: bool | None = None
    has_job_support: bool | None = None
    self_paced: bool | None = None

    language: str = ""
    audience_types: list[str] = field(default_factory=list)
    ai_topics: list[str] = field(default_factory=list)

    parent_program_id: str | None = None

    extracted_from_item_id: str | None = None
    extraction_confidence: float = 0.0


@dataclass(slots=True)
class ProgramRecord:
    program_id: str
    source_platform: str
    source_url: str
    canonical_url: str

    title: str
    short_description: str = ""

    program_type: str = "unknown"
    topic_primary: str = "unknown"
    topic_secondary: list[str] = field(default_factory=list)

    courses_count: int | None = None
    lessons_count_estimated: int | None = None
    duration_hours: float | None = None

    has_certificate: bool | None = None
    has_projects: bool | None = None
    has_mentor_support: bool | None = None
    has_job_support: bool | None = None

    language: str = ""
    audience_types: list[str] = field(default_factory=list)
    ai_topics: list[str] = field(default_factory=list)

    child_course_ids: list[str] = field(default_factory=list)

    extracted_from_item_id: str | None = None
    extraction_confidence: float = 0.0