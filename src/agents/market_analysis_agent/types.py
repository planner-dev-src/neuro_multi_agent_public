from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


TrendType = Literal["topic_cluster", "competency_family", "core_signal"]
GapType = Literal["topic_cluster", "competency_family", "core_signal"]


@dataclass(slots=True)
class CatalogItem:
    """
    Нормализованный элемент каталога, извлечённый с платформы.

    Хранит базовые данные карточки курса, программы, профессии или другого
    образовательного предложения до этапа классификации и агрегации.
    """

    platform_name: str
    """Название платформы-источника."""

    item_id: str = ""
    """Стабильный идентификатор элемента внутри пайплайна."""

    title: str = ""
    """Заголовок карточки или название программы."""

    description: str = ""
    """Краткое текстовое описание предложения."""

    canonical_url: str = ""
    """Канонический URL карточки или посадочной страницы."""

    source_url: str = ""
    """Исходный URL, если канонический адрес ещё не выделен отдельно."""

    category_hint: str = ""
    """Необязательная исходная категория, если она была извлечена с сайта."""

    category_raw: str = ""
    """Сырая категория из исходного источника, если доступна."""

    item_type: str = ""
    """Исходный тип сущности: course, program, profession, specialization и т.д."""

    provider_name: str = ""
    """Имя провайдера, школы или бренда, если оно передавалось отдельно."""

    tags_raw: list[str] = field(default_factory=list)
    """Сырые теги карточки, если были извлечены парсером."""

    ai_topics: list[str] = field(default_factory=list)
    """Предварительно извлечённые AI/IT-темы, если upstream уже их определил."""

    audience_types: list[str] = field(default_factory=list)
    """Предварительные признаки аудитории, если они были извлечены отдельно."""

    duration_text: str = ""
    """Человекочитаемая длительность, например '6 месяцев' или '24 hours'."""

    duration_hours: float | None = None
    """Нормализованная длительность в часах, если upstream смог её вычислить."""

    difficulty_level: str = ""
    """Уровень сложности, например beginner / intermediate / advanced."""

    certificate_available: bool | None = None
    """Есть ли сертификат по завершении."""

    project_based: bool | None = None
    """Есть ли явный акцент на проектах и практике."""

    mentor_support: bool | None = None
    """Есть ли наставник, ревью или кураторская поддержка."""

    job_support: bool | None = None
    """Есть ли карьерная поддержка или помощь с трудоустройством."""

    language: str = ""
    """Язык контента (ru, en и т.д.), если был определён при сборе."""

    extraction_confidence: float | None = None
    """Уверенность парсера в качестве извлечения (0.0–1.0)."""

    extraction_notes: list[str] = field(default_factory=list)
    """Служебные заметки парсера: source, heuristic, selector."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Произвольные дополнительные поля, полученные при сборе данных."""


CatalogItemInput = CatalogItem
"""Временный alias для обратной совместимости со старым импортом."""


@dataclass(slots=True)
class PlatformReportInput:
    """
    Входной объект для анализа одной платформы.

    Содержит платформенное имя и список уже нормализованных элементов каталога,
    которые будут переданы в классификаторы и агрегаторы.

    Canonical field: items
    Compatibility alias: catalog_items
    """

    platform_name: str
    """Название анализируемой платформы."""

    items: list[CatalogItem] = field(default_factory=list)
    """Список элементов каталога платформы в canonical contract."""

    source_url: str = ""
    """Основной URL платформы или входной URL набора данных."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Служебные метаданные по источнику, выгрузке или прогону."""

    @property
    def catalog_items(self) -> list[CatalogItem]:
        """
        Совместимый alias для старого naming.

        Возвращает canonical field `items`, чтобы старый код, который ещё
        читает `platform.catalog_items`, не требовал ручной миграции.
        """
        return self.items


@dataclass(slots=True, init=False)
class OfferFeatures:
    """
    Нормализованный набор признаков одного образовательного предложения.

    Это центральная единица аналитики. Объект используется в aggregations,
    positioning, trend_builder, gap_builder и report_builder.

    Canonical field: title
    Compatibility aliases:
    - item_title (attribute/property access)
    - constructor accepts both title=... and item_title=...
    """

    item_id: str
    """Стабильный идентификатор элемента каталога."""

    platform_name: str
    """Название платформы, к которой относится предложение."""

    title: str
    """Название курса, программы или другого предложения в canonical naming."""

    description: str
    """Нормализованное текстовое описание предложения."""

    canonical_url: str
    """Канонический URL предложения."""

    source_url: str
    """Исходный URL предложения, если нужен для трассировки."""

    item_type: str
    """Нормализованный тип предложения: course, program, profession и т.д."""

    normalized_title: str
    """Нормализованный заголовок, удобный для дедупликации и сравнения."""

    text_fingerprint: str
    """Текстовый отпечаток для дедупликации и explainability."""

    topic_clusters: list[str]
    """Canonical topic cluster keys, например generative_ai или data_science."""

    competency_families: list[str]
    """Canonical competency family keys, например ai_engineering или data_workflows."""

    audience_segments: list[str]
    """Canonical audience segment keys."""

    value_props: list[str]
    """Canonical value proposition keys."""

    core_signals: list[str]
    """Canonical AI differentiation axes, используемые end-to-end в positioning/trends/gaps."""

    support_signals: list[str]
    """Сигналы поддержки обучения: наставники, сопровождение, ревью и подобные признаки."""

    outcome_signals: list[str]
    """Сигналы результата: трудоустройство, сертификат, портфолио, карьерный трек."""

    intensity_signals: list[str]
    """Сигналы интенсивности и формата нагрузки: интенсив, буткемп, длинная программа."""

    format_signals: list[str]
    """Сигналы формата поставки: cohort, self_paced, hybrid, online и другие."""

    monetization_signals: list[str]
    """Сигналы монетизации: subscription, one_time, freemium, installment и т.д."""

    duration_bucket: str
    """Корзина длительности: short, medium, long, extended, unknown."""

    difficulty_bucket: str
    """Нормализованная корзина сложности: beginner, intermediate, advanced, unknown."""

    quality_score: float
    """Эвристическая оценка качества и полноты классификации элемента."""

    confidence_score: float
    """Дополнительная оценка уверенности классификации."""

    is_noise: bool
    """Был ли элемент помечен как шумовой на этапе классификации."""

    noise_reasons: list[str]
    """Причины, по которым элемент может считаться шумом."""

    evidence_text: str
    """Короткий explainability-фрагмент, полезный для отладки и отчётов."""

    raw_text_evidence: list[str]
    """Набор текстовых explainability-фрагментов для downstream-слоя."""

    language: str
    """Язык контента (ru, en и т.д.)."""

    extraction_confidence: float | None
    """Уверенность парсера в качестве извлечения (0.0–1.0)."""

    extraction_notes: list[str]
    """Служебные заметки парсера: source, heuristic, selector."""

    metadata: dict[str, Any]
    """Дополнительные поля для трассировки, explainability и отладки."""

    def __init__(
        self,
        *,
        item_id: str,
        platform_name: str,
        title: str = "",
        item_title: str = "",
        description: str = "",
        canonical_url: str = "",
        source_url: str = "",
        item_type: str = "",
        normalized_title: str = "",
        text_fingerprint: str = "",
        topic_clusters: list[str] | None = None,
        competency_families: list[str] | None = None,
        audience_segments: list[str] | None = None,
        value_props: list[str] | None = None,
        core_signals: list[str] | None = None,
        support_signals: list[str] | None = None,
        outcome_signals: list[str] | None = None,
        intensity_signals: list[str] | None = None,
        format_signals: list[str] | None = None,
        monetization_signals: list[str] | None = None,
        duration_bucket: str = "unknown",
        difficulty_bucket: str = "unknown",
        quality_score: float = 0.0,
        confidence_score: float = 0.0,
        is_noise: bool = False,
        noise_reasons: list[str] | None = None,
        evidence_text: str = "",
        raw_text_evidence: list[str] | None = None,
        language: str = "",
        extraction_confidence: float | None = None,
        extraction_notes: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        canonical_title = title or item_title

        self.item_id = item_id
        self.platform_name = platform_name
        self.title = canonical_title
        self.description = description
        self.canonical_url = canonical_url
        self.source_url = source_url
        self.item_type = item_type
        self.normalized_title = normalized_title
        self.text_fingerprint = text_fingerprint

        self.topic_clusters = list(topic_clusters or [])
        self.competency_families = list(competency_families or [])
        self.audience_segments = list(audience_segments or [])
        self.value_props = list(value_props or [])
        self.core_signals = list(core_signals or [])
        self.support_signals = list(support_signals or [])
        self.outcome_signals = list(outcome_signals or [])
        self.intensity_signals = list(intensity_signals or [])
        self.format_signals = list(format_signals or [])
        self.monetization_signals = list(monetization_signals or [])

        self.duration_bucket = duration_bucket
        self.difficulty_bucket = difficulty_bucket
        self.quality_score = quality_score
        self.confidence_score = confidence_score
        self.is_noise = is_noise
        self.noise_reasons = list(noise_reasons or [])
        self.evidence_text = evidence_text
        self.raw_text_evidence = list(raw_text_evidence or [])
        self.language = language
        self.extraction_confidence = extraction_confidence
        self.extraction_notes = list(extraction_notes or [])
        self.metadata = dict(metadata or {})

    @property
    def item_title(self) -> str:
        """
        Совместимый alias для нового positioning/reporting naming.

        Возвращает canonical field `title`, чтобы downstream-код мог читать
        `offer.item_title` без ручной миграции.
        """
        return self.title


@dataclass(slots=True)
class PlatformAggregate:
    """
    Агрегированная сводка по одной платформе на основе набора OfferFeatures.

    Используется как компактный слой платформенной аналитики для positioning,
    report_builder и сравнительных таблиц.
    """

    platform_name: str
    """Название платформы."""

    offers_count: int = 0
    """Количество предложений, оставшихся после фильтрации."""

    raw_items_count: int = 0
    """Количество сырых элементов до дедупликации и фильтрации."""

    deduped_items_count: int = 0
    """Количество элементов после дедупликации."""

    filtered_items_count: int = 0
    """Количество элементов после финальной фильтрации."""

    dropped_as_noise_count: int = 0
    """Сколько элементов было отброшено как шум."""

    dropped_as_duplicates_count: int = 0
    """Сколько элементов было удалено как дубликаты."""

    top_topics: list[str] = field(default_factory=list)
    """Наиболее частые canonical topic cluster keys платформы."""

    top_competency_families: list[str] = field(default_factory=list)
    """Наиболее частые canonical competency family keys платформы."""

    top_value_props: list[str] = field(default_factory=list)
    """Наиболее частые canonical value proposition keys платформы."""

    top_core_signals: list[str] = field(default_factory=list)
    """Наиболее частые canonical core-signals платформы."""

    top_audiences: list[str] = field(default_factory=list)
    """Наиболее частые canonical audience segment keys."""

    top_format_signals: list[str] = field(default_factory=list)
    """Наиболее частые сигналы формата и delivery-модели."""

    evidence_items: list[str] = field(default_factory=list)
    """Идентификаторы или URL элементов, служащих опорой для агрегата."""

    source_items_count: int = 0
    """Количество элементов, реально вошедших в агрегацию по платформе."""

    source_items_count_raw: int = 0
    """Общее количество сырых элементов в прогоне."""

    source_items_deduped_removed: int = 0
    """Сколько элементов было удалено как дубликаты в рамках прогона."""

    source_items_noise_removed: int = 0
    """Сколько элементов было удалено как шум в рамках прогона."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Дополнительные служебные метаданные агрегата."""


@dataclass(slots=True)
class PlatformPositioning:
    """
    Профиль позиционирования платформы.

    positioning_statement формируется в positioning.py как финальный русский
    текст и далее только отображается downstream-слоем.
    """

    platform_name: str
    """Название платформы."""

    audience_focus: list[str] = field(default_factory=list)
    """Ключевые аудитории платформы."""

    value_props: list[str] = field(default_factory=list)
    """Ключевые ценностные обещания платформы."""

    core_signals: list[str] = field(default_factory=list)
    """Ключевые canonical core-signals платформы как маркеры дифференциации."""

    pedagogy_style: list[str] = field(default_factory=list)
    """Ключевые педагогические и delivery-паттерны."""

    career_signals: list[str] = field(default_factory=list)
    """Сигналы карьерной ориентации платформы."""

    academic_signals: list[str] = field(default_factory=list)
    """Сигналы академической глубины платформы."""

    execution_model: list[str] = field(default_factory=list)
    """Сигналы модели поставки: cohort, self_paced, hybrid, enterprise и т.д."""

    dominant_topics: list[str] = field(default_factory=list)
    """Доминирующие canonical topic clusters."""

    dominant_competency_families: list[str] = field(default_factory=list)
    """Доминирующие canonical competency families."""

    positioning_statement: str = ""
    """Готовая русская формулировка позиционирования."""

    evidence_items: list[str] = field(default_factory=list)
    """Идентификаторы или URL элементов, поддерживающих профиль позиционирования."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Дополнительные служебные метаданные позиционирования."""


@dataclass(slots=True)
class TrendSignal:
    """
    Сигнал рыночного тренда по тематике, семейству компетенций или core-сигналу.

    Поле topic хранит canonical string key, а не display label. Это единый
    stable slot для topic_cluster, competency_family и core_signal.
    Interpretation считается финальным текстом аналитического слоя.
    """

    trend_id: str
    """Стабильный идентификатор тренда, например topic_cluster::generative_ai."""

    topic: str
    """Canonical key темы, семейства компетенций или core-сигнала, к которому относится тренд."""

    trend_type: TrendType
    """Тип тренда: topic_cluster, competency_family или core_signal."""

    platforms_count: int = 0
    """Сколько платформ покрывают данный тренд."""

    items_count: int = 0
    """Сколько элементов каталога попало в данный тренд."""

    platform_share: float = 0.0
    """Доля платформ, где обнаружен данный тренд."""

    signal_strength: float = 0.0
    """Итоговая сила сигнала тренда по внутренней эвристике."""

    representative_platforms: list[str] = field(default_factory=list)
    """Платформы, наиболее явно представляющие данный тренд."""

    evidence_item_ids: list[str] = field(default_factory=list)
    """Идентификаторы элементов, на которых основан тренд."""

    core_signals: list[str] = field(default_factory=list)
    """Связанные canonical core-signals, если тренд агрегировался с их участием."""

    interpretation: str = ""
    """Готовая русская интерпретация тренда; presentation-layer не должен её изменять."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Дополнительные служебные метаданные тренда."""


@dataclass(slots=True)
class CompetitiveGap:
    """
    Сигнал конкурентного разрыва или недопредставленной зоны.

    Поле topic хранит canonical string key и использует тот же contract,
    что и TrendSignal.topic. Interpretation считается финальным выводом
    аналитического слоя и не должен переписываться downstream-слоем.
    """

    topic: str
    """Canonical key темы, семейства компетенций или core-сигнала, по которому найден gap."""

    gap_type: GapType
    """Тип gap: topic_cluster, competency_family или core_signal."""

    platforms_count: int = 0
    """Сколько платформ уже покрывают этот сигнал."""

    platform_share: float = 0.0
    """Доля платформ, где этот сигнал уже присутствует."""

    underrepresented_platforms: list[str] = field(default_factory=list)
    """Платформы, у которых данный сигнал не найден и где есть пространство для усиления."""

    opportunity_score: float = 0.0
    """Оценка потенциала как зоны роста или точки дифференциации."""

    interpretation: str = ""
    """Готовая русская интерпретация конкурентного gap."""

    evidence_item_ids: list[str] = field(default_factory=list)
    """Идентификаторы элементов, подтверждающих наличие сигнала у текущих игроков."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Дополнительные служебные метаданные gap-сигнала."""


@dataclass(slots=True)
class MarketAnalysisBundle:
    """
    Финальный bundle рыночного анализа.

    Объединяет все слои пайплайна: нормализованные предложения, агрегаты платформ,
    тренды, gap-сигналы и профили позиционирования.
    """

    generated_at_utc: str
    """UTC-время генерации bundle в ISO-формате."""

    source_run_path: str = ""
    """Путь или идентификатор прогона, если он нужен для трассировки."""

    platforms_total: int = 0
    """Количество платформ в анализе."""

    catalog_items_total_raw: int = 0
    """Количество сырых элементов каталога до очистки."""

    catalog_items_total_after_dedup: int = 0
    """Количество элементов, оставшихся после дедупликации."""

    catalog_items_total_kept: int = 0
    """Количество элементов, сохранённых после фильтрации."""

    catalog_items_total_noise: int = 0
    """Количество элементов, удалённых как шум."""

    catalog_items_total_deduped: int = 0
    """Количество элементов, удалённых как дубликаты."""

    offer_features: list[OfferFeatures] = field(default_factory=list)
    """Нормализованные признаки предложений, сохранённые после очистки."""

    platform_aggregates: list[PlatformAggregate] = field(default_factory=list)
    """Платформенные агрегаты."""

    platform_positioning: list[PlatformPositioning] = field(default_factory=list)
    """Профили позиционирования платформ."""

    trend_signals: list[TrendSignal] = field(default_factory=list)
    """Сигналы рыночных трендов с готовыми русскими интерпретациями."""

    competitive_gaps: list[CompetitiveGap] = field(default_factory=list)
    """Сигналы конкурентных gap-зон с готовыми русскими интерпретациями."""

    summary: dict[str, Any] = field(default_factory=dict)
    """Краткая техническая сводка по ключевым объектам bundle."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Дополнительные служебные метаданные bundle."""