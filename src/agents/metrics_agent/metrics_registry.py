#!/usr/bin/env python
"""
Реестр метрик компании
Центральное хранилище всех метрик по уровням с возможностью чтения, записи и обновления
Поддерживает метрики, решения и векторы состояния
"""

import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum


class MetricStatus(Enum):
    """Статусы метрик"""
    CRITICAL = "critical"
    WARNING = "warning"
    MET = "met"
    EXCEEDED = "exceeded"
    DATA_MISSING = "data_missing"
    NEEDS_INPUT = "needs_input"


class MetricLevel(Enum):
    """Уровни метрик"""
    STRATEGIC = "strategic"
    MARKET = "market"
    PRODUCTS = "products"
    COMPETENCY = "competency"
    TECHNICAL = "technical"
    OPERATIONAL = "operational"


class DecisionSource(Enum):
    """Источники решений"""
    DIRECTIVE = "directive"
    SECRETARY = "secretary"
    RESEARCH = "research"
    MARKET_ANALYSIS = "market_analysis"
    PLANNER = "planner"


class DecisionStatus(Enum):
    """Статусы решений"""
    APPROVED = "approved"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REJECTED = "rejected"
    COMPLETED = "completed"


@dataclass
class MetricContext:
    """Контекст метрики"""
    product: Optional[str] = None
    module: Optional[str] = None
    measurement_date: Optional[str] = None
    measurement_tool: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = None
    tasks: Optional[List[str]] = field(default_factory=list)
    total_effort: Optional[float] = None
    available_effort: Optional[float] = None
    gap: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Metric:
    """Модель метрики"""
    id: str
    name: str
    level: str
    value: Any
    target: Any = None
    unit: str = ""
    status: str = "data_missing"
    interpretation: str = ""
    context: Optional[MetricContext] = None
    source: str = ""
    update_frequency: str = ""
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "value": self.value,
            "target": self.target,
            "unit": self.unit,
            "status": self.status,
            "interpretation": self.interpretation,
            "source": self.source,
            "update_frequency": self.update_frequency,
            "last_updated": self.last_updated,
            "history": self.history
        }
        if self.context:
            result["context"] = self.context.to_dict()
        return result


@dataclass
class Decision:
    """Модель решения руководителя"""
    id: str
    level: str
    description: str
    source: str
    status: str = "pending"
    priority: str = "medium"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metric_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    assignee: Optional[str] = None
    deadline: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsRegistry:
    """
    Реестр метрик и решений компании
    """
    
    DEFAULT_REGISTRY_PATH = "config/metrics_registry.json"
    
    RUSSIAN_NAMES = {
        "ai_projects": "AI проекты",
        "competitors": "Конкуренты",
        "directions": "Направления",
        "neuro_curator": "Нейро-куратор",
        "mlops": "MLOps",
        "code_coverage": "Покрытие кода",
        "quality": "Качество",
        "response_time": "Время ответа",
        "availability": "Доступность",
        "market_share": "Доля рынка",
        "revenue_growth": "Рост выручки",
        "customer_satisfaction": "Удовлетворенность клиентов",
        "competitive_position": "Конкурентная позиция",
        "trend_alignment": "Соответствие трендам"
    }
    
    LEVEL_ICONS = {
        "strategic": "🎯",
        "market": "🌍",
        "products": "📦",
        "competency": "🧠",
        "technical": "⚙️",
        "operational": "📌"
    }
    
    LEVEL_NAMES_RU = {
        "strategic": "Стратегический",
        "market": "Рыночный",
        "products": "Продуктовый",
        "competency": "Компетенции",
        "technical": "Технический",
        "operational": "Операционный"
    }
    
    def __init__(self, registry_path: Optional[str] = None):
        self.project_root = self._get_project_root()
        
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            self.registry_path = self.project_root / self.DEFAULT_REGISTRY_PATH
        
        self.registry_data: Dict[str, Any] = {}
        self.metrics_cache: Dict[str, Metric] = {}
        self.decisions_cache: List[Decision] = []
        
        self.load()
    
    def _get_project_root(self) -> Path:
        current = Path(__file__).resolve().parent
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent
            if (parent / "src" / "agents").exists():
                return parent
        return current.parent.parent.parent
    
    def _ensure_registry_dir(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _is_numeric(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value.replace(',', '.'))
                return True
            except (ValueError, TypeError):
                return False
        return False
    
    def _to_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(',', '.'))
            except (ValueError, TypeError):
                return None
        return None
    
    def load(self) -> bool:
        if not self.registry_path.exists():
            print(f"⚠️ Реестр не найден: {self.registry_path}")
            print("   Создаю новый реестр...")
            self._create_default()
            return True
        
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                self.registry_data = json.load(f)
            self._build_cache()
            print(f"✅ Реестр загружен: {self.registry_path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка загрузки реестра: {e}")
            self._create_default()
            return False
    
    def reload(self) -> None:
        """Перезагружает реестр из файла, обновляя кэш"""
        self.load()
    
    def save(self) -> bool:
        try:
            self._ensure_registry_dir()
            self.registry_data["last_updated"] = datetime.now().isoformat()
            self.registry_data["summary"] = self._calculate_summary()
            
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(self.registry_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Реестр сохранен: {self.registry_path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения реестра: {e}")
            return False
    
    def _create_default(self) -> None:
        self.registry_data = {
            "version": "2.0",
            "last_updated": datetime.now().isoformat(),
            "levels": {
                "strategic": {"schema": {}, "data": {}},
                "market": {"schema": {}, "data": {}},
                "products": {"schema": {}, "data": {}},
                "competency": {"schema": {}, "data": {}},
                "technical": {"schema": {}, "data": {}}
            },
            "decisions": [],
            "summary": {"total_metrics": 0, "total_decisions": 0, "status_distribution": {}}
        }
        self._build_cache()
        self.save()
    
    def _get_russian_name(self, key: str) -> str:
        return self.RUSSIAN_NAMES.get(key, key.replace("_", " ").title())
    
    def _build_cache(self) -> None:
        self.metrics_cache = {}
        
        for level_name, level_data in self.registry_data.get("levels", {}).items():
            data = level_data.get("data", {})
            
            for metric_key, metric_value in data.items():
                metric_id = f"{level_name}_{metric_key}"
                
                value, target, unit, context = self._extract_metric_data(metric_value, level_name)
                
                status = self._calculate_status(value, target, level_name, metric_value)
                interpretation = self._generate_interpretation(metric_value, status, level_name)
                
                if isinstance(value, str):
                    try:
                        value = float(value.replace(',', '.'))
                    except (ValueError, TypeError):
                        pass
                
                self.metrics_cache[metric_id] = Metric(
                    id=metric_id,
                    name=self._get_russian_name(metric_key),
                    level=level_name,
                    value=value,
                    target=target,
                    unit=unit,
                    status=status,
                    interpretation=interpretation,
                    context=context,
                    source=metric_value.get("source", ""),
                    update_frequency=metric_value.get("update_frequency", "")
                )
        
        self.decisions_cache = []
        for decision_data in self.registry_data.get("decisions", []):
            self.decisions_cache.append(Decision(**decision_data))
    
    def _extract_metric_data(self, metric_value: Dict, level: str) -> tuple:
        value = None
        target = None
        unit = ""
        context = None
        
        if level == "products":
            metrics = metric_value.get("metrics", {})
            for metric_name, metric_data in metrics.items():
                value = metric_data.get("value")
                target = metric_data.get("target")
                unit = metric_data.get("unit", "")
                context = MetricContext(
                    product=metric_value.get("description", ""),
                    measurement_date=metric_data.get("context", {}).get("measurement_date"),
                    measurement_tool=metric_data.get("context", {}).get("measurement_tool")
                )
                break
        
        elif level == "competency":
            value = metric_value.get("value") or metric_value.get("coverage")
            if value is None:
                pass
            target = metric_value.get("target")
            unit = metric_value.get("unit", "%")
            ctx = metric_value.get("context", {})
            context = MetricContext(
                tasks=ctx.get("tasks", []),
                total_effort=ctx.get("total_effort"),
                available_effort=ctx.get("available_effort"),
                gap=ctx.get("gap")
            )
        
        elif level == "technical":
            value = metric_value.get("value")
            target = metric_value.get("target")
            unit = metric_value.get("unit", "")
            ctx = metric_value.get("context", {})
            context = MetricContext(
                product=ctx.get("product"),
                module=ctx.get("module"),
                measurement_date=ctx.get("measurement_date"),
                measurement_tool=ctx.get("measurement_tool")
            )
        
        elif level == "strategic":
            value = metric_value.get("current")
            target = metric_value.get("target")
            unit = metric_value.get("unit", "проектов")
        
        elif level == "market":
            value = metric_value.get("analyzed")
            target = metric_value.get("total")
            unit = "из"
        
        return value, target, unit, context
    
    def _calculate_status(self, value: Any, target: Any, level: str, raw_data: Dict) -> str:
        if value is None:
            return MetricStatus.DATA_MISSING.value
        
        if "status" in raw_data:
            status_value = raw_data["status"]
            if isinstance(status_value, str):
                return status_value
            if isinstance(status_value, MetricStatus):
                return status_value.value
        
        target_float = self._to_float(target)
        value_float = self._to_float(value)
        
        if target_float is not None and value_float is not None:
            if target_float == 0:
                return MetricStatus.MET.value
            
            ratio = value_float / target_float
            
            if ratio >= 1.1:
                return MetricStatus.EXCEEDED.value
            elif ratio >= 0.95:
                return MetricStatus.MET.value
            elif ratio >= 0.75:
                return MetricStatus.WARNING.value
            else:
                return MetricStatus.CRITICAL.value
        
        if level == "competency" and value_float is not None:
            if value_float >= 80:
                return MetricStatus.MET.value
            elif value_float >= 50:
                return MetricStatus.WARNING.value
            else:
                return MetricStatus.CRITICAL.value
        
        if value is not None:
            return MetricStatus.MET.value
        
        return MetricStatus.MET.value
    
    def _generate_interpretation(self, metric_data: Dict, status: str, level: str) -> str:
        interpretations = {
            MetricStatus.CRITICAL.value: "Требуется немедленное внимание",
            MetricStatus.WARNING.value: "Требуется внимание",
            MetricStatus.MET.value: "Целевой показатель достигнут",
            MetricStatus.EXCEEDED.value: "Превышение целевого показателя",
            MetricStatus.DATA_MISSING.value: "Данные отсутствуют"
        }
        
        if "interpretation" in metric_data and metric_data["interpretation"]:
            return metric_data["interpretation"]
        
        base = interpretations.get(status, "Статус не определён")
        
        if level == "competency":
            coverage = metric_data.get("coverage") or metric_data.get("value")
            if coverage is not None:
                try:
                    cov_val = float(coverage.replace(',', '.')) if isinstance(coverage, str) else float(coverage)
                    if status == MetricStatus.CRITICAL.value:
                        return f"Критический пробел в компетенции (покрытие: {cov_val}%)"
                    elif status == MetricStatus.WARNING.value:
                        return f"Требуется усиление компетенции (покрытие: {cov_val}%)"
                    elif status == MetricStatus.MET.value:
                        return f"Компетенция в норме (покрытие: {cov_val}%)"
                except (ValueError, TypeError):
                    pass
        
        if level == "products":
            metrics = metric_data.get("metrics", {})
            for name, data in metrics.items():
                value = data.get("value")
                target = data.get("target")
                if value is not None and target is not None:
                    try:
                        v = float(value.replace(',', '.')) if isinstance(value, str) else float(value)
                        t = float(target.replace(',', '.')) if isinstance(target, str) else float(target)
                        return f"{base}. {self._get_russian_name(name)}: {v} (цель: {t})"
                    except (ValueError, TypeError):
                        pass
        
        return base
    
    def _calculate_summary(self) -> Dict[str, Any]:
        total_metrics = len(self.metrics_cache)
        total_decisions = len(self.decisions_cache)
        status_distribution = {}
        
        for metric in self.metrics_cache.values():
            status = metric.status
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        return {
            "total_metrics": total_metrics,
            "total_decisions": total_decisions,
            "status_distribution": status_distribution
        }
    
    def get_metric(self, metric_id: str) -> Optional[Metric]:
        return self.metrics_cache.get(metric_id)
    
    def get_level_metrics(self, level: str) -> Dict[str, Metric]:
        return {k: v for k, v in self.metrics_cache.items() if v.level == level}
    
    def get_all_metrics(self) -> Dict[str, Metric]:
        return self.metrics_cache
    
    def get_metric_value(self, metric_id: str) -> Any:
        metric = self.get_metric(metric_id)
        return metric.value if metric else None
    
    def update_metric_value(self, metric_id: str, new_value: Any, note: str = "") -> bool:
        if metric_id not in self.metrics_cache:
            print(f"❌ Метрика не найдена: {metric_id}")
            return False
        
        metric = self.metrics_cache[metric_id]
        old_value = metric.value
        
        if old_value is not None:
            metric.history.append({
                "date": datetime.now().isoformat(),
                "old_value": old_value,
                "new_value": new_value,
                "note": note
            })
        
        metric.value = new_value
        metric.last_updated = datetime.now().isoformat()
        metric.status = self._calculate_status(
            new_value, metric.target, metric.level, {}
        )
        
        self.save()
        print(f"✅ Метрика обновлена: {metric_id} = {new_value}")
        return True
    
    def add_metric(self, level: str, key: str, metric_data: Dict[str, Any]) -> bool:
        if level not in self.registry_data["levels"]:
            print(f"❌ Неизвестный уровень: {level}")
            return False
        
        level_data = self.registry_data["levels"][level]
        
        if key in level_data.get("data", {}):
            print(f"⚠️ Метрика уже существует: {level}_{key}")
            return False
        
        if "data" not in level_data:
            level_data["data"] = {}
        
        level_data["data"][key] = metric_data
        self._build_cache()
        self.save()
        
        print(f"✅ Метрика добавлена: {level}_{key}")
        return True
    
    def get_status_distribution(self) -> Dict[str, int]:
        return self._calculate_summary()["status_distribution"]
    
    def get_critical_metrics(self) -> List[Metric]:
        return [m for m in self.metrics_cache.values() if m.status == MetricStatus.CRITICAL.value]
    
    def get_warning_metrics(self) -> List[Metric]:
        return [m for m in self.metrics_cache.values() if m.status == MetricStatus.WARNING.value]
    
    def get_metrics_without_data(self) -> List[Metric]:
        return [m for m in self.metrics_cache.values() if m.status == MetricStatus.DATA_MISSING.value]
    
    def add_decision(
        self,
        level: str,
        description: str,
        source: str = "directive",
        priority: str = "medium",
        metric_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        assignee: Optional[str] = None,
        deadline: Optional[str] = None
    ) -> bool:
        if level not in self.LEVEL_NAMES_RU:
            print(f"❌ Неизвестный уровень: {level}")
            return False
        
        decision_id = f"dec_{len(self.decisions_cache) + 1:03d}"
        
        decision = Decision(
            id=decision_id,
            level=level,
            description=description,
            source=source,
            status=DecisionStatus.PENDING.value,
            priority=priority,
            metric_id=metric_id,
            details=details or {},
            assignee=assignee,
            deadline=deadline
        )
        
        self.decisions_cache.append(decision)
        self.registry_data["decisions"].append(decision.to_dict())
        self.save()
        
        print(f"✅ Решение добавлено: {decision_id}")
        return True
    
    def get_decisions_by_level(self, level: str) -> List[Decision]:
        return [d for d in self.decisions_cache if d.level == level]
    
    def get_decisions_by_status(self, status: str) -> List[Decision]:
        return [d for d in self.decisions_cache if d.status == status]
    
    def get_all_decisions(self) -> List[Decision]:
        return self.decisions_cache
    
    def update_decision_status(self, decision_id: str, new_status: str) -> bool:
        for decision in self.decisions_cache:
            if decision.id == decision_id:
                decision.status = new_status
                for d in self.registry_data["decisions"]:
                    if d["id"] == decision_id:
                        d["status"] = new_status
                        break
                self.save()
                print(f"✅ Статус решения обновлён: {decision_id} -> {new_status}")
                return True
        
        print(f"❌ Решение не найдено: {decision_id}")
        return False
    
    def get_decisions_summary(self) -> Dict[str, Any]:
        status_counts = {}
        level_counts = {}
        source_counts = {}
        
        for decision in self.decisions_cache:
            status_counts[decision.status] = status_counts.get(decision.status, 0) + 1
            level_counts[decision.level] = level_counts.get(decision.level, 0) + 1
            source_counts[decision.source] = source_counts.get(decision.source, 0) + 1
        
        return {
            "total": len(self.decisions_cache),
            "by_status": status_counts,
            "by_level": level_counts,
            "by_source": source_counts
        }
    
    def get_level_icon(self, level: str) -> str:
        return self.LEVEL_ICONS.get(level, "📌")
    
    def get_level_name_ru(self, level: str) -> str:
        return self.LEVEL_NAMES_RU.get(level, level)
    
    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(',', '.'))
            except (ValueError, TypeError):
                return None
        return None
    
    def build_state_vectors(self) -> Dict[str, Dict[str, Any]]:
        vectors = {}
        
        for level in MetricLevel:
            level_name = level.value
            metrics = self.get_level_metrics(level_name)
            decisions = self.get_decisions_by_level(level_name)
            
            vector = []
            interpretations = []
            
            for metric in metrics.values():
                deviation = None
                val_float = self._safe_float(metric.value)
                target_float = self._safe_float(metric.target)
                
                if val_float is not None and target_float is not None:
                    deviation = round(target_float - val_float, 2)
                
                vector.append({
                    "id": metric.id,
                    "name": metric.name,
                    "value": metric.value,
                    "target": metric.target,
                    "deviation": deviation,
                    "status": metric.status,
                    "unit": metric.unit
                })
                
                if metric.interpretation:
                    interpretations.append(metric.interpretation)
            
            vectors[level_name] = {
                "icon": self.get_level_icon(level_name),
                "name": self.get_level_name_ru(level_name),
                "vector": vector,
                "interpretation": "; ".join(interpretations) if interpretations else "Нет данных",
                "metrics_count": len(vector),
                "decisions_count": len(decisions),
                "decisions": [
                    {"id": d.id, "description": d.description, "status": d.status}
                    for d in decisions
                ]
            }
        
        return vectors
    
    def export_to_json(self) -> Dict[str, Any]:
        return self.registry_data
    
    def __str__(self) -> str:
        summary = self.registry_data.get("summary", {})
        return f"MetricsRegistry: {summary.get('total_metrics', 0)} метрик, {summary.get('total_decisions', 0)} решений"


def main():
    print("=" * 60)
    print("📊 METRICS REGISTRY - ТЕСТ С РЕШЕНИЯМИ")
    print("=" * 60)
    
    registry = MetricsRegistry()
    
    print("\n📊 ИНФОРМАЦИЯ О РЕЕСТРЕ:")
    print(f"  Всего метрик: {len(registry.get_all_metrics())}")
    print(f"  Всего решений: {len(registry.get_all_decisions())}")
    print(f"  Распределение статусов: {registry.get_status_distribution()}")
    
    print("\n🔴 КРИТИЧЕСКИЕ МЕТРИКИ:")
    for m in registry.get_critical_metrics():
        print(f"  • {m.name}: {m.value} ({m.interpretation})")
    
    print("\n📈 ВЕКТОРЫ СОСТОЯНИЯ:")
    vectors = registry.build_state_vectors()
    for level, data in vectors.items():
        icon = data["icon"]
        name = data["name"]
        print(f"\n{icon} {name}:")
        print(f"  Метрик: {data['metrics_count']}")
        print(f"  Решений: {data['decisions_count']}")
        for item in data['vector']:
            dev = f"(отклонение: {item['deviation']:.1f})" if item['deviation'] is not None else ""
            print(f"    • {item['name']}: {item['value']} {dev} [{item['status']}]")
        for decision in data['decisions']:
            print(f"    📌 {decision['description']} ({decision['status']})")
    
    print("\n✅ Тест завершен!")
    print(f"📁 Реестр сохранен: {registry.registry_path}")


if __name__ == "__main__":
    main()