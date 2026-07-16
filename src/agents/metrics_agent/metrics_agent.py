"""
Metrics Agent - отвечает за сбор, агрегацию и анализ метрик
Работает с реестром метрик (MetricsRegistry)
"""

import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
import pandas as pd

from src.agents.metrics_agent.metrics_registry import (
    MetricsRegistry, 
    Metric, 
    MetricStatus, 
    MetricLevel
)


class MetricsAgent:
    """
    Агент для работы с метриками проекта
    Использует MetricsRegistry как источник данных
    """
    
    def __init__(self, registry_path: Optional[str] = None):
        """
        Args:
            registry_path: Путь к файлу реестра метрик (JSON)
        """
        self.registry = MetricsRegistry(registry_path)
        self.project_root = self._get_project_root()
        
        print(f"📊 Metrics Agent инициализирован")
        print(f"   Всего метрик: {len(self.registry.get_all_metrics())}")
    
    def _get_project_root(self) -> Path:
        """Определяет корень проекта"""
        current = Path(__file__).resolve().parent
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent
            if (parent / "src" / "agents").exists():
                return parent
        return current.parent.parent.parent
    
    def get_all_metrics(self) -> Dict[str, Metric]:
        """
        Получить все метрики из реестра
        
        Returns:
            Dict[str, Metric]: Все метрики
        """
        return self.registry.get_all_metrics()
    
    def get_level_metrics(self, level: str) -> Dict[str, Metric]:
        """
        Получить метрики уровня
        
        Args:
            level: Уровень метрик (strategic, market, products, competency, technical)
        
        Returns:
            Dict[str, Metric]: Метрики уровня
        """
        return self.registry.get_level_metrics(level)
    
    def get_metric(self, metric_id: str) -> Optional[Metric]:
        """
        Получить метрику по ID
        
        Args:
            metric_id: ID метрики
        
        Returns:
            Optional[Metric]: Метрика или None
        """
        return self.registry.get_metric(metric_id)
    
    def update_metric(self, metric_id: str, new_value: Any, note: str = "") -> bool:
        """
        Обновить значение метрики
        
        Args:
            metric_id: ID метрики
            new_value: Новое значение
            note: Примечание к изменению
        
        Returns:
            bool: True если обновление успешно
        """
        return self.registry.update_metric_value(metric_id, new_value, note)
    
    def add_metric(self, level: str, key: str, data: Dict[str, Any]) -> bool:
        """
        Добавить новую метрику
        
        Args:
            level: Уровень метрики
            key: Ключ метрики
            data: Данные метрики
        
        Returns:
            bool: True если добавление успешно
        """
        return self.registry.add_metric(level, key, data)
    
    def get_status_distribution(self) -> Dict[str, int]:
        """
        Получить распределение статусов
        
        Returns:
            Dict[str, int]: Количество метрик по статусам
        """
        return self.registry.get_status_distribution()
    
    def get_critical_metrics(self) -> List[Metric]:
        """
        Получить критические метрики
        
        Returns:
            List[Metric]: Список критических метрик
        """
        return self.registry.get_critical_metrics()
    
    def get_warning_metrics(self) -> List[Metric]:
        """
        Получить метрики с предупреждениями
        
        Returns:
            List[Metric]: Список метрик с предупреждениями
        """
        return self.registry.get_warning_metrics()
    
    def get_metrics_without_data(self) -> List[Metric]:
        """
        Получить метрики без данных
        
        Returns:
            List[Metric]: Список метрик без данных
        """
        return self.registry.get_metrics_without_data()
    
    def build_competency_map(self) -> Dict[str, Any]:
        """
        Строит карту компетенций из реестра
        
        Returns:
            Dict с картой компетенций
        """
        competency_metrics = self.get_level_metrics("competency")
        
        required_skills = []
        team_skills = {}
        gaps = []
        coverage = {}
        individuals = []
        
        for metric_id, metric in competency_metrics.items():
            skill_name = metric.name
            value = metric.value
            status = metric.status
            
            required_skills.append(skill_name)
            
            if value is not None:
                team_skills[skill_name] = value
                
                if status == MetricStatus.CRITICAL.value:
                    gaps.append(skill_name)
                    coverage[skill_name] = value
                elif status == MetricStatus.WARNING.value:
                    coverage[skill_name] = value
                else:
                    coverage[skill_name] = value
        
        return {
            "required_skills": required_skills,
            "team_skills": team_skills,
            "gaps": gaps,
            "coverage": coverage,
            "individuals": individuals,
            "source": "metrics_registry"
        }
    
    def analyze_criteria_coverage(self) -> Dict[str, Any]:
        """
        Анализирует покрытие критериев из реестра
        
        Returns:
            Dict с анализом покрытия
        """
        # Собираем метрики с target
        all_metrics = self.get_all_metrics()
        
        criteria = []
        met = 0
        partially_met = 0
        not_met = 0
        
        for metric_id, metric in all_metrics.items():
            if metric.target is not None and metric.value is not None:
                # Проверяем, что оба значения числовые
                if isinstance(metric.value, (int, float)) and isinstance(metric.target, (int, float)):
                    status = metric.status
                    
                    criteria.append({
                        "name": metric.name,
                        "target": metric.target,
                        "current": metric.value,
                        "status": status,
                        "gap": metric.target - metric.value,
                        "progress": (metric.value / metric.target) * 100 if metric.target > 0 else 0
                    })
                    
                    if status == MetricStatus.MET.value or status == MetricStatus.EXCEEDED.value:
                        met += 1
                    elif status == MetricStatus.WARNING.value:
                        partially_met += 1
                    elif status == MetricStatus.CRITICAL.value:
                        not_met += 1
        
        total = len(criteria)
        
        return {
            "total": total,
            "met": met,
            "partially_met": partially_met,
            "not_met": not_met,
            "overall_progress": (met / total) * 100 if total > 0 else 0,
            "criteria_details": criteria,
            "source": "metrics_registry"
        }
    
    def build_impact_map(self) -> Dict[str, Any]:
        """
        Строит карту влияния между метриками на основе реестра
        
        Returns:
            Dict с картой влияния
        """
        all_metrics = self.get_all_metrics()
        
        # Определяем узлы (метрики)
        nodes = []
        for metric_id, metric in all_metrics.items():
            if metric.value is not None:
                nodes.append({
                    "id": metric_id,
                    "label": metric.name,
                    "level": metric.level,
                    "value": metric.value,
                    "target": metric.target,
                    "unit": metric.unit,
                    "status": metric.status
                })
        
        # Определяем влияния (на основе логики)
        edges = self._build_influence_edges(all_metrics)
        
        # Генерируем выводы
        findings = self._generate_findings(all_metrics)
        
        # Генерируем рекомендации
        recommendations = self._generate_recommendations(all_metrics)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "findings": findings,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
            "source": "metrics_registry"
        }
    
    def _build_influence_edges(self, metrics: Dict[str, Metric]) -> List[Dict[str, Any]]:
        """
        Строит связи влияния между метриками
        """
        edges = []
        
        # Получаем значения метрик
        def get_value(metric_id: str) -> Any:
            m = metrics.get(metric_id)
            return m.value if m else None
        
        def get_status(metric_id: str) -> str:
            m = metrics.get(metric_id)
            return m.status if m else ""
        
        # Влияние компетенций на продукты
        comp_metrics = {k: v for k, v in metrics.items() if v.level == "competency"}
        prod_metrics = {k: v for k, v in metrics.items() if v.level == "products"}
        
        for comp_id, comp in comp_metrics.items():
            if comp.value is not None and isinstance(comp.value, (int, float)) and comp.value < 50:
                for prod_id, prod in prod_metrics.items():
                    if prod.value is not None:
                        edges.append({
                            "from": comp_id,
                            "to": prod_id,
                            "strength": -0.5 if comp.value < 30 else -0.3,
                            "direction": "negative",
                            "description": f"Низкий уровень компетенции {comp.name} влияет на продукт {prod.name}"
                        })
        
        # Влияние технических метрик на продукты
        tech_metrics = {k: v for k, v in metrics.items() if v.level == "technical"}
        
        for tech_id, tech in tech_metrics.items():
            if tech.value is not None and tech.target is not None:
                if isinstance(tech.value, (int, float)) and isinstance(tech.target, (int, float)):
                    if tech.value < tech.target:
                        for prod_id, prod in prod_metrics.items():
                            if prod.value is not None:
                                edges.append({
                                    "from": tech_id,
                                    "to": prod_id,
                                    "strength": -0.4,
                                    "direction": "negative",
                                    "description": f"Отставание по {tech.name} влияет на продукт {prod.name}"
                                })
        
        # Влияние продуктов на стратегические метрики
        strat_metrics = {k: v for k, v in metrics.items() if v.level == "strategic"}
        
        for prod_id, prod in prod_metrics.items():
            if prod.value is not None:
                for strat_id, strat in strat_metrics.items():
                    if strat.value is not None:
                        edges.append({
                            "from": prod_id,
                            "to": strat_id,
                            "strength": 0.3,
                            "direction": "positive",
                            "description": f"Развитие продукта {prod.name} поддерживает стратегическую цель {strat.name}"
                        })
        
        return edges[:10]  # Ограничиваем количество связей
    
    def _is_numeric(self, value: Any) -> bool:
        """Проверяет, является ли значение числовым"""
        return isinstance(value, (int, float))
    
    def _safe_compare(self, value1: Any, value2: Any, operator: str = "lt") -> bool:
        """
        Безопасно сравнивает два значения.
        
        Args:
            value1: Первое значение
            value2: Второе значение
            operator: Оператор сравнения: 'lt' (<), 'le' (<=), 'eq' (==), 'gt' (>), 'ge' (>=)
        
        Returns:
            bool: Результат сравнения или False, если значения не числовые
        """
        if not self._is_numeric(value1) or not self._is_numeric(value2):
            return False
        
        if operator == "lt":
            return value1 < value2
        elif operator == "le":
            return value1 <= value2
        elif operator == "eq":
            return value1 == value2
        elif operator == "gt":
            return value1 > value2
        elif operator == "ge":
            return value1 >= value2
        return False
    
    def _generate_findings(self, metrics: Dict[str, Metric]) -> List[str]:
        """
        Генерирует выводы на основе метрик
        """
        findings = []
        
        # Критические метрики
        critical = [m for m in metrics.values() if m.status == MetricStatus.CRITICAL.value]
        if critical:
            critical_names = ", ".join([m.name for m in critical[:3]])
            findings.append(f"🔴 Критические отклонения по: {critical_names}")
        
        # Метрики с предупреждениями
        warning = [m for m in metrics.values() if m.status == MetricStatus.WARNING.value]
        if warning:
            warning_names = ", ".join([m.name for m in warning[:3]])
            findings.append(f"🟡 Требуют внимания: {warning_names}")
        
        # Успешные метрики
        met = [m for m in metrics.values() if m.status == MetricStatus.MET.value]
        if met:
            met_names = ", ".join([m.name for m in met[:3]])
            findings.append(f"✅ Цели достигнуты по: {met_names}")
        
        # Превышения
        exceeded = [m for m in metrics.values() if m.status == MetricStatus.EXCEEDED.value]
        if exceeded:
            exceeded_names = ", ".join([m.name for m in exceeded[:3]])
            findings.append(f"📈 Превышение целей по: {exceeded_names}")
        
        # Метрики без данных
        no_data = [m for m in metrics.values() if m.status == MetricStatus.DATA_MISSING.value]
        if no_data:
            no_data_names = ", ".join([m.name for m in no_data[:3]])
            findings.append(f"⚪ Требуется ввод данных по: {no_data_names}")
        
        return findings
    
    def _generate_recommendations(self, metrics: Dict[str, Metric]) -> List[str]:
        """
        Генерирует рекомендации на основе метрик
        """
        recommendations = []
        
        # Критические компетенции
        comp_metrics = {k: v for k, v in metrics.items() if v.level == "competency"}
        critical_comp = [m for m in comp_metrics.values() if m.status == MetricStatus.CRITICAL.value]
        
        if critical_comp:
            comp_names = ", ".join([m.name for m in critical_comp])
            recommendations.append(
                f"🔧 Усильте компетенции: {comp_names}. Рассмотрите найм или обучение."
            )
        
        # Технические метрики с отставанием (только числовые)
        tech_metrics = {k: v for k, v in metrics.items() if v.level == "technical"}
        tech_warning = []
        for m in tech_metrics.values():
            if m.status == MetricStatus.WARNING.value:
                # Проверяем, что оба значения числовые
                if self._is_numeric(m.value) and self._is_numeric(m.target):
                    tech_warning.append(m)
        
        if tech_warning:
            for m in tech_warning:
                if self._is_numeric(m.value) and self._is_numeric(m.target):
                    recommendations.append(
                        f"📈 Улучшите {m.name}: текущее {m.value} при цели {m.target}"
                    )
        
        # Рыночные метрики (только числовые)
        market_metrics = {k: v for k, v in metrics.items() if v.level == "market"}
        for m in market_metrics.values():
            if m.status == MetricStatus.CRITICAL.value:
                if self._is_numeric(m.value) and self._is_numeric(m.target):
                    recommendations.append(
                        f"📊 Расширьте анализ {m.name}: охвачено {m.value} из {m.target}"
                    )
        
        # Стратегические метрики (только числовые)
        strat_metrics = {k: v for k, v in metrics.items() if v.level == "strategic"}
        for m in strat_metrics.values():
            if m.status == MetricStatus.CRITICAL.value:
                if self._is_numeric(m.value) and self._is_numeric(m.target):
                    recommendations.append(
                        f"🎯 Ускорьте достижение стратегической цели {m.name}: {m.value} из {m.target}"
                    )
        
        return recommendations[:5]  # Ограничиваем 5 рекомендациями
    
    def generate_rag_chunks(self) -> List[Dict[str, Any]]:
        """
        Генерирует RAG-чанки для контекста LLM
        
        Returns:
            List с RAG-чанками
        """
        chunks = []
        
        # 1. Чанк с общей информацией
        all_metrics = self.get_all_metrics()
        distribution = self.get_status_distribution()
        
        chunks.append({
            "chunk_id": "metrics_summary",
            "text": f"Всего метрик: {len(all_metrics)}. "
                    f"Распределение статусов: {distribution}. "
                    f"Критических: {distribution.get(MetricStatus.CRITICAL.value, 0)}. "
                    f"Предупреждений: {distribution.get(MetricStatus.WARNING.value, 0)}. "
                    f"Достигнуто: {distribution.get(MetricStatus.MET.value, 0)}.",
            "source": "metrics_agent",
            "section": "summary",
            "title": "Общая информация по метрикам",
            "metadata": {
                "type": "metrics_summary",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # 2. Чанк с критическими метриками
        critical = self.get_critical_metrics()
        if critical:
            critical_text = "Критические метрики:\n" + "\n".join([
                f"- {m.name}: {m.value} (цель: {m.target}) - {m.interpretation}"
                for m in critical
            ])
            chunks.append({
                "chunk_id": "metrics_critical",
                "text": critical_text,
                "source": "metrics_agent",
                "section": "critical",
                "title": "Критические метрики",
                "metadata": {
                    "type": "critical_metrics",
                    "count": len(critical),
                    "timestamp": datetime.now().isoformat()
                }
            })
        
        # 3. Чанк с картой компетенций
        competency = self.build_competency_map()
        gaps = competency.get("gaps", [])
        coverage = competency.get("coverage", {})
        
        competency_text = f"Карта компетенций:\n"
        competency_text += f"- Всего навыков: {len(competency.get('required_skills', []))}\n"
        if gaps:
            competency_text += f"- Пробелы в компетенциях: {', '.join(gaps)}\n"
        if coverage:
            competency_text += f"- Покрытие: {coverage}\n"
        
        chunks.append({
            "chunk_id": "metrics_competency",
            "text": competency_text,
            "source": "metrics_agent",
            "section": "competency",
            "title": "Карта компетенций",
            "metadata": {
                "type": "competency_map",
                "gaps_count": len(gaps),
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # 4. Чанк с критериями
        criteria = self.analyze_criteria_coverage()
        criteria_text = f"Покрытие критериев:\n"
        criteria_text += f"- Прогресс: {criteria.get('overall_progress', 0):.1f}%\n"
        criteria_text += f"- Выполнено: {criteria.get('met', 0)} из {criteria.get('total', 0)}\n"
        criteria_text += f"- Частично: {criteria.get('partially_met', 0)}\n"
        criteria_text += f"- Не выполнено: {criteria.get('not_met', 0)}"
        
        chunks.append({
            "chunk_id": "metrics_criteria",
            "text": criteria_text,
            "source": "metrics_agent",
            "section": "criteria",
            "title": "Покрытие критериев",
            "metadata": {
                "type": "criteria_coverage",
                "progress": criteria.get('overall_progress', 0),
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # 5. Чанк с выводами и рекомендациями
        impact = self.build_impact_map()
        findings = impact.get("findings", [])
        recommendations = impact.get("recommendations", [])
        
        insights_text = "Выводы и рекомендации:\n"
        if findings:
            insights_text += "Выводы:\n" + "\n".join([f"- {f}" for f in findings]) + "\n"
        if recommendations:
            insights_text += "Рекомендации:\n" + "\n".join([f"- {r}" for r in recommendations])
        
        chunks.append({
            "chunk_id": "metrics_insights",
            "text": insights_text,
            "source": "metrics_agent",
            "section": "insights",
            "title": "Выводы и рекомендации",
            "metadata": {
                "type": "findings_recommendations",
                "findings_count": len(findings),
                "recommendations_count": len(recommendations),
                "timestamp": datetime.now().isoformat()
            }
        })
        
        return chunks
    
    def get_full_report(self) -> Dict[str, Any]:
        """
        Возвращает полный отчет по всем метрикам
        
        Returns:
            Dict с полным отчетом
        """
        return {
            "metrics": {k: v.to_dict() for k, v in self.get_all_metrics().items()},
            "competency_map": self.build_competency_map(),
            "criteria_coverage": self.analyze_criteria_coverage(),
            "impact_map": self.build_impact_map(),
            "status_distribution": self.get_status_distribution(),
            "rag_chunks": self.generate_rag_chunks(),
            "timestamp": datetime.now().isoformat(),
            "source": "metrics_agent"
        }
    
    def reload(self) -> bool:
        """
        Перезагружает реестр
        
        Returns:
            bool: True если перезагрузка успешна
        """
        return self.registry.load()
    
    def save(self) -> bool:
        """
        Сохраняет реестр
        
        Returns:
            bool: True если сохранение успешно
        """
        return self.registry.save()


# ============================================================
# ФУНКЦИЯ ЗАПУСКА (для оркестратора)
# ============================================================

def run_metrics_agent(
    metrics_path: Optional[str] = None,
    gaps: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Запускает metrics_agent для сбора и агрегации метрик.
    
    Args:
        metrics_path: Путь к JSON-файлу с метриками (опционально)
        gaps: Данные о gap-зонах для дополнения (опционально)
        
    Returns:
        Dict: Результаты работы агента
    """
    print("📊 Запуск metrics_agent...")
    
    agent = MetricsAgent()
    
    # Если передан путь к файлу, загружаем метрики из него
    if metrics_path:
        try:
            with open(metrics_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Обновляем метрики из файла
            for key, value in data.get("metrics", {}).items():
                if isinstance(value, dict):
                    agent.update_metric(key, value.get("value"), value.get("note", ""))
            print(f"   Загружены метрики из {metrics_path}")
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки метрик из {metrics_path}: {e}")
    
    # Если есть gaps, добавляем их как метрики
    if gaps:
        for gap in gaps:
            if isinstance(gap, dict) and "topic_label" in gap:
                # Безопасное преобразование opportunity_score в число
                opportunity_score = gap.get("opportunity_score", 0)
                try:
                    opportunity_score = float(opportunity_score)
                except (ValueError, TypeError):
                    opportunity_score = 0
                
                agent.add_metric(
                    level="competency",
                    key=gap["topic_label"].replace(" ", "_").lower(),
                    data={
                        "name": gap["topic_label"],
                        "value": gap.get("opportunity_score", 0),
                        "target": 70,
                        "unit": "%",
                        "status": "warning" if opportunity_score < 50 else "met",
                        "interpretation": gap.get("interpretation", "")
                    }
                )
        print(f"   Добавлено {len(gaps)} gap-зон как метрики")
    
    # Собираем все данные
    all_metrics = agent.get_all_metrics()
    competency_map = agent.build_competency_map()
    criteria_coverage = agent.analyze_criteria_coverage()
    impact_map = agent.build_impact_map()
    rag_chunks = agent.generate_rag_chunks()
    
    # ⚠️ ВАЖНО: НЕ возвращаем объект agent, только данные!
    result = {
        "metrics_data": {
            "total": len(all_metrics),
            "critical": [m.to_dict() for m in agent.get_critical_metrics()],
            "warning": [m.to_dict() for m in agent.get_warning_metrics()],
            "no_data": [m.to_dict() for m in agent.get_metrics_without_data()]
        },
        "competency_map": competency_map,
        "criteria_assessment": criteria_coverage,
        "impact_map": impact_map,
        "rag_chunks": rag_chunks,
        "status": "completed",
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"   ✅ metrics_agent завершил работу")
    print(f"   Всего метрик: {len(all_metrics)}")
    print(f"   Критических: {len(agent.get_critical_metrics())}")
    print(f"   RAG-чанков: {len(rag_chunks)}")
    
    return result


# ============================================================
# ТОЧКА ВХОДА
# ============================================================

def main():
    """Тестовый запуск"""
    print("=" * 60)
    print("📊 METRICS AGENT - ТЕСТ С РЕЕСТРОМ")
    print("=" * 60)
    
    agent = MetricsAgent()
    
    # 1. Общая информация
    print("\n📊 ОБЩАЯ ИНФОРМАЦИЯ:")
    all_metrics = agent.get_all_metrics()
    print(f"  Всего метрик: {len(all_metrics)}")
    print(f"  Распределение статусов: {agent.get_status_distribution()}")
    
    # 2. Карта компетенций
    print("\n🗺️ КАРТА КОМПЕТЕНЦИЙ:")
    competency = agent.build_competency_map()
    print(f"  Требуемые навыки: {competency['required_skills']}")
    print(f"  Покрытие: {competency['coverage']}")
    print(f"  Пробелы: {competency['gaps']}")
    
    # 3. Покрытие критериев
    print("\n📋 ПОКРЫТИЕ КРИТЕРИЕВ:")
    criteria = agent.analyze_criteria_coverage()
    print(f"  Прогресс: {criteria['overall_progress']:.1f}%")
    print(f"  Выполнено: {criteria['met']} из {criteria['total']}")
    
    # 4. Карта влияния
    print("\n🗺️ КАРТА ВЛИЯНИЯ:")
    impact = agent.build_impact_map()
    
    print("\n  📌 ВЫВОДЫ:")
    for finding in impact['findings']:
        print(f"    {finding}")
    
    print("\n  💡 РЕКОМЕНДАЦИИ:")
    for rec in impact['recommendations']:
        print(f"    {rec}")
    
    # 5. Критические метрики
    print("\n🔴 КРИТИЧЕСКИЕ МЕТРИКИ:")
    critical = agent.get_critical_metrics()
    for m in critical:
        print(f"  • {m.name}: {m.value} (цель: {m.target})")
        print(f"    {m.interpretation}")
    
    # 6. RAG-чанки
    print("\n📄 RAG-ЧАНКИ:")
    chunks = agent.generate_rag_chunks()
    for chunk in chunks:
        print(f"  • {chunk['chunk_id']}: {len(chunk['text'])} символов")
    
    # 7. Полный отчет
    print("\n📊 ПОЛНЫЙ ОТЧЕТ:")
    report = agent.get_full_report()
    print(f"  Метрик: {len(report['metrics'])}")
    print(f"  Компетенций: {len(report['competency_map'].get('required_skills', []))}")
    print(f"  Критериев: {report['criteria_coverage']['total']}")
    print(f"  Выводов: {len(report['impact_map']['findings'])}")
    print(f"  Рекомендаций: {len(report['impact_map']['recommendations'])}")
    
    # 8. Тест функции run_metrics_agent
    print("\n🚀 ТЕСТ run_metrics_agent:")
    result = run_metrics_agent()
    print(f"  Статус: {result['status']}")
    print(f"  Метрик: {result['metrics_data']['total']}")
    print(f"  RAG-чанков: {len(result['rag_chunks'])}")
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТ ЗАВЕРШЕН!")
    print("=" * 60)


if __name__ == "__main__":
    main()