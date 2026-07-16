"""
Planner Agent - отвечает за формирование плана действий и рекомендаций
на основе метрик, рыночного анализа, нарратива и вводных от руководителя
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict

from src.agents.metrics_agent.metrics_registry import (
    MetricsRegistry, 
    Metric, 
    MetricStatus, 
    MetricLevel
)


@dataclass
class ActionItem:
    """Модель действия/задачи"""
    id: str
    type: str  # hire, improve, market, research, training, process, strategic, decision, task, risk
    description: str
    priority: str  # critical, high, medium, low
    status: str = "pending"
    source: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    deadline: Optional[str] = None
    assignee: Optional[str] = None
    context: Optional[str] = None  # контекст: к чему относится


@dataclass
class Plan:
    """Модель плана"""
    actions: List[ActionItem]
    summary: str
    priorities: Dict[str, List[str]]
    timeline: Dict[str, List[str]]
    risks: List[str]
    success_criteria: List[str]
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class PlannerAgent:
    """
    Агент для формирования плана действий на основе метрик и анализа
    """
    
    # Карта уровней с иконками и русскими названиями
    LEVEL_CONFIG = {
        "strategic": {"icon": "🎯", "name": "Уровень стратегический"},
        "market": {"icon": "🌍", "name": "Уровень рыночный"},
        "products": {"icon": "📦", "name": "Уровень продуктовый"},
        "competency": {"icon": "🧠", "name": "Уровень компетенций"},
        "technical": {"icon": "⚙️", "name": "Уровень технический"}
    }
    
    # Карта приоритетов на русские названия
    PRIORITY_RU = {
        "critical": "КРИТИЧЕСКИЙ",
        "high": "ВЫСОКИЙ",
        "medium": "СРЕДНИЙ",
        "low": "НИЗКИЙ"
    }
    
    # Карта временных периодов на русские названия
    TIMELINE_RU = {
        "immediate": "НЕМЕДЛЕННО",
        "1-2 weeks": "1-2 НЕДЕЛИ",
        "1 month": "1 МЕСЯЦ",
        "2-3 months": "2-3 МЕСЯЦА"
    }
    
    def __init__(self, registry_path: Optional[str] = None):
        self.project_root = self._get_project_root()
        self.results_dir = self.project_root / "src" / "agents" / "planner_agent" / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.registry = MetricsRegistry(registry_path)
        
        print(f"📋 Planner Agent инициализирован")
        print(f"   Метрик в реестре: {len(self.registry.get_all_metrics())}")
    
    def _get_project_root(self) -> Path:
        current = Path(__file__).resolve().parent
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent
            if (parent / "src" / "agents").exists():
                return parent
        return current.parent.parent.parent
    
    def _get_level_prefix(self, level: str) -> str:
        """Возвращает префикс уровня с иконкой и названием"""
        config = self.LEVEL_CONFIG.get(level, {})
        icon = config.get("icon", "")
        name = config.get("name", level)
        return f"{icon} {name}"
    
    def _is_numeric(self, value: Any) -> bool:
        """Проверяет, является ли значение числовым"""
        return isinstance(value, (int, float))
    
    def _safe_get_value(self, data: Dict, key: str, default: Any = 0) -> Any:
        """Безопасно получает значение из словаря"""
        value = data.get(key, default)
        if value is None:
            return default
        return value
    
    def plan(
        self,
        metrics_data: Dict[str, Any],
        market_analysis: Dict[str, Any],
        narrative: str,
        transcript_analysis: Optional[Dict[str, Any]] = None
    ) -> Plan:
        """
        Формирует план действий на основе всех данных
        
        Args:
            metrics_data: Данные от Metrics Agent
            market_analysis: Данные от Market Analysis Agent
            narrative: Нарратив от Market Narrative Agent
            transcript_analysis: Анализ транскрипта от Secretary Agent (ВВОДНЫЕ ОТ РУКОВОДИТЕЛЯ)
        """
        print("📋 Формирование плана действий...")
        
        actions: List[ActionItem] = []
        
        # 1. Вводные от руководителя (из транскрипта) - САМЫЙ ВАЖНЫЙ ИСТОЧНИК
        if transcript_analysis:
            actions.extend(self._generate_transcript_actions(transcript_analysis))
        
        # 2. Действия из реестра метрик (все уровни)
        actions.extend(self._generate_actions_from_registry())
        
        # 3. Действия на основе пробелов в компетенциях
        actions.extend(self._generate_competency_actions(metrics_data))
        
        # 4. Действия на основе покрытия критериев
        actions.extend(self._generate_criteria_actions(metrics_data))
        
        # 5. Действия на основе выводов и рекомендаций
        actions.extend(self._generate_findings_actions(metrics_data))
        
        # 6. Действия на основе рыночного анализа
        actions.extend(self._generate_market_actions(market_analysis))
        
        # 7. Действия на основе нарратива (если есть)
        if narrative and narrative.strip():
            actions.extend(self._generate_narrative_actions(narrative))
        
        # Сортируем по приоритету
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        actions.sort(key=lambda x: priority_order.get(x.priority, 99))
        
        plan = Plan(
            actions=actions,
            summary=self._generate_summary(actions),
            priorities=self._get_priorities(actions),
            timeline=self._generate_timeline(actions),
            risks=self._identify_risks(metrics_data, market_analysis, transcript_analysis),
            success_criteria=self._define_success_criteria(metrics_data, transcript_analysis)
        )
        
        print(f"✅ План сформирован: {len(actions)} действий")
        return plan
    
    def _generate_transcript_actions(self, transcript_analysis: Dict) -> List[ActionItem]:
        """
        Генерирует действия на основе транскрипта (вводные от руководителя)
        """
        actions = []
        
        # 1. Основные тезисы руководителя (информационные, не требуют действий)
        main_theses = transcript_analysis.get("main_theses", [])
        for i, thesis in enumerate(main_theses):
            actions.append(ActionItem(
                id=f"thesis_{i}",
                type="process",
                description=f"📌 Тезис руководителя: {thesis}",
                priority="high",
                source="transcript",
                context="вводные от руководителя"
            ))
        
        # 2. Принятые решения
        decisions = transcript_analysis.get("decisions", [])
        for decision in decisions:
            who = decision.get("who", "не указан")
            deadline = decision.get("deadline")
            actions.append(ActionItem(
                id=f"decision_{len(actions)}",
                type="decision",
                description=f"📋 Решение: {decision.get('decision', '')}",
                priority="high",
                source="transcript",
                context=f"кто: {who}",
                details={"who": who, "deadline": deadline},
                deadline=deadline
            ))
        
        # 3. Поручения и задачи
        action_items = transcript_analysis.get("action_items", [])
        for item in action_items:
            assignee = item.get("assignee", "не назначен")
            deadline = item.get("deadline")
            actions.append(ActionItem(
                id=f"task_{len(actions)}",
                type="task",
                description=f"📋 Поручение: {item.get('task', '')}",
                priority="high",
                source="transcript",
                context=f"исполнитель: {assignee}",
                details={"assignee": assignee, "deadline": deadline},
                deadline=deadline,
                assignee=assignee
            ))
        
        # 4. Риски
        risks = transcript_analysis.get("risks", [])
        for risk in risks:
            owner = risk.get("owner", "не указан")
            severity = risk.get("severity", "medium")
            actions.append(ActionItem(
                id=f"risk_{len(actions)}",
                type="risk",
                description=f"⚠️ Риск: {risk.get('risk', '')}",
                priority="critical" if severity == "high" else "high",
                source="transcript",
                context=f"ответственный: {owner}",
                details={"owner": owner, "severity": severity}
            ))
        
        # 5. Ключевые темы
        topics = transcript_analysis.get("key_topics", [])
        if topics:
            actions.append(ActionItem(
                id="topics_summary",
                type="process",
                description=f"📌 Ключевые темы обсуждения: {', '.join(topics)}",
                priority="medium",
                source="transcript",
                context="темы совещания"
            ))
        
        # 6. Тональность
        tone = transcript_analysis.get("tone_and_mood", "")
        if tone:
            actions.append(ActionItem(
                id="tone_info",
                type="process",
                description=f"📊 Тональность встречи: {tone}",
                priority="low",
                source="transcript",
                context="общая атмосфера"
            ))
        
        return actions
    
    def _generate_actions_from_registry(self) -> List[ActionItem]:
        """
        Генерирует действия на основе реестра метрик с разделением по уровням
        """
        actions = []
        
        for level in ["strategic", "market", "products", "competency", "technical"]:
            level_metrics = self.registry.get_level_metrics(level)
            level_prefix = self._get_level_prefix(level)
            
            for metric_id, metric in level_metrics.items():
                if metric.value is None:
                    continue
                
                if metric.target is None and metric.level != "competency":
                    continue
                
                context = self._get_metric_context(metric)
                action = self._create_action_for_metric(metric, level_prefix, context)
                if action:
                    actions.append(action)
        
        return actions
    
    def _get_metric_context(self, metric: Metric) -> str:
        """Получает контекст метрики"""
        if metric.context:
            if metric.context.product:
                return f"продукт: {metric.context.product}"
            elif metric.context.module:
                return f"модуль: {metric.context.module}"
            elif metric.context.tasks:
                return f"задачи: {', '.join(metric.context.tasks[:2])}"
        return ""
    
    def _create_action_for_metric(self, metric: Metric, level_prefix: str, context: str) -> Optional[ActionItem]:
        """Создает действие для метрики на основе её статуса и уровня"""
        if metric.status == MetricStatus.CRITICAL.value:
            return self._create_critical_action(metric, level_prefix, context)
        elif metric.status == MetricStatus.WARNING.value:
            return self._create_warning_action(metric, level_prefix, context)
        elif metric.status == MetricStatus.DATA_MISSING.value:
            return self._create_data_missing_action(metric, level_prefix, context)
        return None
    
    def _create_critical_action(self, metric: Metric, level_prefix: str, context: str) -> ActionItem:
        """Создает действие для критической метрики"""
        if metric.level == "strategic":
            # Безопасное форматирование значения
            value_str = str(metric.value) if metric.value is not None else "?"
            target_str = str(metric.target) if metric.target is not None else "?"
            return ActionItem(
                id=f"reg_crit_strat_{metric.id}",
                type="strategic",
                description=f"{level_prefix}: Достичь стратегической цели: {metric.name} (текущее {value_str} из {target_str})",
                priority="critical",
                source="metrics_registry",
                context=context or "стратегическая цель компании",
                details={"metric_id": metric.id, "value": metric.value, "target": metric.target}
            )
        elif metric.level == "competency":
            value_str = str(metric.value) if metric.value is not None else "?"
            return ActionItem(
                id=f"reg_crit_comp_{metric.id}",
                type="hire",
                description=f"{level_prefix}: Закрыть критический пробел в компетенции: {metric.name} (покрытие {value_str}%)",
                priority="critical",
                source="metrics_registry",
                context=context or f"компетенция {metric.name}",
                details={"skill": metric.name, "coverage": metric.value}
            )
        elif metric.level == "market":
            value_str = str(metric.value) if metric.value is not None else "?"
            target_str = str(metric.target) if metric.target is not None else "?"
            return ActionItem(
                id=f"reg_crit_market_{metric.id}",
                type="market",
                description=f"{level_prefix}: Расширить анализ: {metric.name} (охвачено {value_str} из {target_str})",
                priority="high",
                source="metrics_registry",
                context=context or "рыночный анализ",
                details={"metric_id": metric.id, "value": metric.value, "target": metric.target}
            )
        elif metric.level == "products":
            value_str = str(metric.value) if metric.value is not None else "?"
            target_str = str(metric.target) if metric.target is not None else "?"
            return ActionItem(
                id=f"reg_crit_prod_{metric.id}",
                type="improve",
                description=f"{level_prefix}: Улучшить продукт: {metric.name} (текущее {value_str} при цели {target_str})",
                priority="high",
                source="metrics_registry",
                context=context or f"продукт {metric.name}",
                details={"metric_id": metric.id, "value": metric.value, "target": metric.target}
            )
        elif metric.level == "technical":
            value_str = str(metric.value) if metric.value is not None else "?"
            target_str = str(metric.target) if metric.target is not None else "?"
            return ActionItem(
                id=f"reg_crit_tech_{metric.id}",
                type="improve",
                description=f"{level_prefix}: Улучшить техническую метрику: {metric.name} (текущее {value_str} при цели {target_str})",
                priority="critical",
                source="metrics_registry",
                context=context or f"техническая метрика {metric.name}",
                details={"metric_id": metric.id, "value": metric.value, "target": metric.target}
            )
        return None
    
    def _create_warning_action(self, metric: Metric, level_prefix: str, context: str) -> ActionItem:
        """Создает действие для метрики с предупреждением"""
        if metric.level == "technical":
            value_str = str(metric.value) if metric.value is not None else "?"
            target_str = str(metric.target) if metric.target is not None else "?"
            return ActionItem(
                id=f"reg_warn_tech_{metric.id}",
                type="improve",
                description=f"{level_prefix}: Улучшить: {metric.name} (текущее {value_str} при цели {target_str})",
                priority="medium",
                source="metrics_registry",
                context=context or f"техническая метрика {metric.name}",
                details={"metric_id": metric.id, "value": metric.value, "target": metric.target}
            )
        elif metric.level == "products":
            value_str = str(metric.value) if metric.value is not None else "?"
            target_str = str(metric.target) if metric.target is not None else "?"
            return ActionItem(
                id=f"reg_warn_prod_{metric.id}",
                type="improve",
                description=f"{level_prefix}: Доработать продукт: {metric.name} (текущее {value_str} при цели {target_str})",
                priority="medium",
                source="metrics_registry",
                context=context or f"продукт {metric.name}",
                details={"metric_id": metric.id, "value": metric.value, "target": metric.target}
            )
        return None
    
    def _create_data_missing_action(self, metric: Metric, level_prefix: str, context: str) -> ActionItem:
        """Создает действие для метрики без данных"""
        return ActionItem(
            id=f"reg_nodata_{metric.id}",
            type="process",
            description=f"{level_prefix}: Ввести данные по метрике: {metric.name}",
            priority="low",
            source="metrics_registry",
            context=context or f"метрика {metric.name}",
            details={"metric_id": metric.id}
        )
    
    def _generate_competency_actions(self, metrics_data: Dict) -> List[ActionItem]:
        """Генерирует действия на основе пробелов в компетенциях"""
        actions = []
        competency_map = metrics_data.get("competency_map", {})
        gaps = competency_map.get("gaps", [])
        
        if not gaps:
            return actions
        
        level_prefix = self._get_level_prefix("competency")
        priority_map = {
            "MLOps": "critical",
            "NLP": "critical",
            "PyTorch": "high",
            "TensorFlow": "high",
            "Docker": "high",
            "Kubernetes": "high",
            "React": "medium",
            "SQL": "medium",
            "FastAPI": "medium"
        }
        
        for gap in gaps:
            priority = priority_map.get(gap, "medium")
            actions.append(ActionItem(
                id=f"comp_{gap.lower()}",
                type="hire",
                description=f"{level_prefix}: Нанять специалиста по {gap}",
                priority=priority,
                source="competency_gap",
                context=f"компетенция {gap}",
                details={"skill": gap, "coverage": competency_map.get("coverage", {}).get(gap, 0)}
            ))
            
            actions.append(ActionItem(
                id=f"train_{gap.lower()}",
                type="training",
                description=f"{level_prefix}: Организовать обучение команды по {gap}",
                priority=self._lower_priority(priority),
                source="competency_gap_alternative",
                context=f"компетенция {gap}",
                details={"skill": gap, "type": "internal_training"}
            ))
        
        return actions
    
    def _generate_criteria_actions(self, metrics_data: Dict) -> List[ActionItem]:
        """Генерирует действия на основе покрытия критериев"""
        actions = []
        criteria_coverage = metrics_data.get("criteria_coverage", {})
        details = criteria_coverage.get("criteria_details", [])
        level_prefix = self._get_level_prefix("technical")
        
        for detail in details:
            status = detail.get("status")
            name = detail.get("name", "")
            
            # Определяем, относится ли критерий к техническому уровню
            tech_keywords = ["покрытие", "код", "точность", "инференс", "скорость", "время", "модели", "api"]
            is_tech = any(kw in name.lower() for kw in tech_keywords)
            
            prefix = level_prefix if is_tech else "📋 Критерий"
            
            # Безопасное получение значений
            current = detail.get("current", 0)
            target = detail.get("target", 0)
            gap = detail.get("gap", 0)
            
            if status == "not_met":
                actions.append(ActionItem(
                    id=f"criteria_{name.replace(' ', '_').lower()}",
                    type="improve",
                    description=f"{prefix}: Улучшить: {name} (текущее {current} при цели {target})",
                    priority="high" if gap > 10 else "medium",
                    source="criteria_gap",
                    context=name,
                    details=detail
                ))
            elif status == "partially_met":
                actions.append(ActionItem(
                    id=f"criteria_{name.replace(' ', '_').lower()}_partial",
                    type="improve",
                    description=f"{prefix}: Довести до выполнения: {name}",
                    priority="medium",
                    source="criteria_partial",
                    context=name,
                    details=detail
                ))
        
        return actions
    
    def _generate_findings_actions(self, metrics_data: Dict) -> List[ActionItem]:
        """Генерирует действия на основе выводов и рекомендаций из метрик"""
        actions = []
        impact_map = metrics_data.get("impact_map", {})
        findings = impact_map.get("findings", [])
        recommendations = impact_map.get("recommendations", [])
        level_prefix = self._get_level_prefix("technical")
        
        for finding in findings:
            # Очищаем finding от артефактов
            clean_finding = finding
            if "1.2" in clean_finding:
                clean_finding = clean_finding.replace("1.2", "1,2")
            if "метрик" in clean_finding and "1,2" in clean_finding:
                clean_finding = clean_finding.replace("1,2 метрик", "1,2")
                clean_finding = clean_finding.replace("1.2 метрик", "1,2")
            
            if "ключевой драйвер" in finding.lower():
                actions.append(ActionItem(
                    id="focus_driver",
                    type="process",
                    description=f"{level_prefix}: Сфокусироваться на ключевом драйвере: {clean_finding}",
                    priority="high",
                    source="finding",
                    context="анализ влияния",
                    details={"finding": finding}
                ))
            elif "риск" in finding.lower() or "ниже" in finding.lower() or "покрытие кода" in finding.lower():
                actions.append(ActionItem(
                    id="risk_mitigation",
                    type="process",
                    description=f"{level_prefix}: Устранить риск: {clean_finding}",
                    priority="critical",
                    source="finding",
                    context="управление рисками",
                    details={"finding": finding}
                ))
            else:
                actions.append(ActionItem(
                    id=f"finding_{len(actions)}",
                    type="process",
                    description=f"{level_prefix}: {clean_finding}",
                    priority="high",
                    source="finding",
                    context="вывод из метрик",
                    details={"finding": finding}
                ))
        
        for rec in recommendations:
            actions.append(ActionItem(
                id=f"rec_{len(actions)}",
                type="process",
                description=f"{level_prefix}: {rec}",
                priority="high" if "срочно" in rec.lower() else "medium",
                source="recommendation",
                context="рекомендация из метрик",
                details={"recommendation": rec}
            ))
        
        return actions
    
    def _generate_market_actions(self, market_analysis: Dict) -> List[ActionItem]:
        """Генерирует действия на основе рыночного анализа"""
        actions = []
        level_prefix = self._get_level_prefix("market")
        
        market_recs = market_analysis.get("recommendations", [])
        for rec in market_recs:
            actions.append(ActionItem(
                id=f"market_{len(actions)}",
                type="market",
                description=f"{level_prefix}: {rec}",
                priority="medium",
                source="market_analysis",
                context="рыночный анализ",
                details={"recommendation": rec}
            ))
        
        advantages = market_analysis.get("impact_from_metrics", {}).get("competitive_advantages", [])
        for adv in advantages:
            actions.append(ActionItem(
                id=f"advantage_{len(actions)}",
                type="market",
                description=f"{level_prefix}: Усилить конкурентное преимущество: {adv}",
                priority="high",
                source="competitive_advantage",
                context="конкурентные преимущества",
                details={"advantage": adv}
            ))
        
        return actions
    
    def _generate_narrative_actions(self, narrative: str) -> List[ActionItem]:
        """Генерирует действия на основе нарратива"""
        actions = []
        keywords = ["рекомендуется", "необходимо", "следует", "важно", "требуется"]
        
        sentences = narrative.split(".")
        for sentence in sentences:
            for keyword in keywords:
                if keyword in sentence.lower():
                    actions.append(ActionItem(
                        id=f"narrative_{len(actions)}",
                        type="process",
                        description=f"📄 Аналитический обзор: {sentence.strip()}",
                        priority="medium",
                        source="narrative",
                        context="из аналитического обзора",
                        details={"keyword": keyword}
                    ))
                    break
        
        return actions[:5]
    
    def _lower_priority(self, priority: str) -> str:
        order = ["critical", "high", "medium", "low"]
        if priority in order:
            idx = min(order.index(priority) + 1, len(order) - 1)
            return order[idx]
        return "low"
    
    def _generate_summary(self, actions: List[ActionItem]) -> str:
        if not actions:
            return "Нет действий для выполнения"
        
        priority_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        type_counts = {}
        
        for action in actions:
            priority_counts[action.priority] = priority_counts.get(action.priority, 0) + 1
            type_counts[action.type] = type_counts.get(action.type, 0) + 1
        
        summary = f"Всего действий: {len(actions)}\n"
        summary += f"Критические: {priority_counts.get('critical', 0)}, "
        summary += f"Высокий приоритет: {priority_counts.get('high', 0)}, "
        summary += f"Средний: {priority_counts.get('medium', 0)}, "
        summary += f"Низкий: {priority_counts.get('low', 0)}\n"
        
        type_desc = ", ".join([f"{k}: {v}" for k, v in type_counts.items()])
        summary += f"Типы действий: {type_desc}"
        
        return summary
    
    def _get_priorities(self, actions: List[ActionItem]) -> Dict[str, List[str]]:
        result = {"critical": [], "high": [], "medium": [], "low": []}
        for action in actions:
            if action.priority in result:
                result[action.priority].append(action.description)
        return result
    
    def _generate_timeline(self, actions: List[ActionItem]) -> Dict[str, List[str]]:
        timeline = {"immediate": [], "1-2 weeks": [], "1 month": [], "2-3 months": []}
        for action in actions:
            if action.priority == "critical":
                timeline["immediate"].append(action.description)
            elif action.priority == "high":
                timeline["1-2 weeks"].append(action.description)
            elif action.priority == "medium":
                timeline["1 month"].append(action.description)
            else:
                timeline["2-3 months"].append(action.description)
        return timeline
    
    def _identify_risks(self, metrics_data: Dict, market_analysis: Dict, transcript_analysis: Optional[Dict] = None) -> List[str]:
        """Идентифицирует риски из всех источников"""
        risks = []
        
        # Риски из метрик
        impact_map = metrics_data.get("impact_map", {})
        findings = impact_map.get("findings", [])
        for finding in findings:
            if "риск" in finding.lower() or "ниже" in finding.lower():
                risks.append(finding)
        
        # Риски из пробелов в компетенциях
        gaps = metrics_data.get("competency_map", {}).get("gaps", [])
        if gaps:
            risks.append(f"Отсутствие экспертизы в: {', '.join(gaps[:3])}")
        
        # Риски из рыночного анализа
        market_risks = market_analysis.get("impact_from_metrics", {}).get("market_risks", [])
        risks.extend(market_risks[:3])
        
        # Риски из транскрипта (вводные от руководителя)
        if transcript_analysis:
            for risk in transcript_analysis.get("risks", []):
                risks.append(risk.get("risk", ""))
        
        return risks[:5]
    
    def _define_success_criteria(self, metrics_data: Dict, transcript_analysis: Optional[Dict] = None) -> List[str]:
        """Определяет критерии успеха"""
        criteria = []
        
        # На основе покрытия критериев
        criteria_coverage = metrics_data.get("criteria_coverage", {})
        total = criteria_coverage.get("total", 0)
        if total > 0:
            criteria.append(f"Выполнить все {total} критериев качества")
        
        # На основе компетенций
        competency_map = metrics_data.get("competency_map", {})
        gaps = competency_map.get("gaps", [])
        if gaps:
            criteria.append(f"Закрыть пробелы в компетенциях: {', '.join(gaps)}")
        
        # На основе решений руководителя
        if transcript_analysis:
            decisions = transcript_analysis.get("decisions", [])
            for decision in decisions[:2]:
                criteria.append(f"Реализовать решение: {decision.get('decision', '')[:50]}")
        
        return criteria[:5]
    
    def save_plan(self, plan: Plan, filename: Optional[str] = None) -> str:
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"plan_{timestamp}.json"
        
        filepath = self.results_dir / filename
        
        plan_dict = {
            "actions": [asdict(a) for a in plan.actions],
            "summary": plan.summary,
            "priorities": plan.priorities,
            "timeline": plan.timeline,
            "risks": plan.risks,
            "success_criteria": plan.success_criteria,
            "generated_at": plan.generated_at
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(plan_dict, f, ensure_ascii=False, indent=2)
        
        txt_path = filepath.with_suffix('.txt')
        self._save_text_plan(plan, txt_path)
        
        print(f"💾 План сохранен: {filepath}")
        return str(filepath)
    
    def _save_text_plan(self, plan: Plan, filepath: Path):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("ПЛАН ДЕЙСТВИЙ\n")
            f.write("=" * 80 + "\n")
            f.write(f"Сгенерирован: {plan.generated_at}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("📋 РЕЗЮМЕ:\n")
            f.write("-" * 40 + "\n")
            f.write(plan.summary + "\n\n")
            
            f.write("📌 ВВОДНЫЕ ОТ РУКОВОДИТЕЛЯ:\n")
            f.write("-" * 40 + "\n")
            # Выводим действия из транскрипта
            transcript_actions = [a for a in plan.actions if a.source == "transcript"]
            for action in transcript_actions[:10]:
                f.write(f"  • {action.description}\n")
            if not transcript_actions:
                f.write("  • Нет данных\n")
            f.write("\n")
            
            f.write("🎯 ПРИОРИТЕТЫ:\n")
            f.write("-" * 40 + "\n")
            for priority, actions in plan.priorities.items():
                if actions:
                    priority_ru = self.PRIORITY_RU.get(priority, priority.upper())
                    f.write(f"\n{priority_ru}:\n")
                    for action in actions[:5]:
                        f.write(f"  • {action}\n")
            
            f.write("\n📅 ВРЕМЕННАЯ ШКАЛА:\n")
            f.write("-" * 40 + "\n")
            for period, actions in plan.timeline.items():
                if actions:
                    period_ru = self.TIMELINE_RU.get(period, period)
                    f.write(f"\n{period_ru}:\n")
                    for action in actions[:3]:
                        f.write(f"  • {action}\n")
            
            f.write("\n⚠️ РИСКИ:\n")
            f.write("-" * 40 + "\n")
            for risk in plan.risks:
                f.write(f"  • {risk}\n")
            
            f.write("\n✅ КРИТЕРИИ УСПЕХА:\n")
            f.write("-" * 40 + "\n")
            for criterion in plan.success_criteria:
                f.write(f"  • {criterion}\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("ДЕТАЛИ ЗАДАЧ (с контекстом)\n")
            f.write("=" * 80 + "\n\n")
            
            for action in plan.actions[:15]:
                priority_emoji = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢"
                }.get(action.priority, "⚪")
                
                priority_ru = self.PRIORITY_RU.get(action.priority, action.priority.upper())
                
                f.write(f"{priority_emoji} [{priority_ru}] {action.description}\n")
                if action.context:
                    f.write(f"  📌 Контекст: {action.context}\n")
                f.write(f"  📂 Тип: {action.type} | Источник: {action.source}\n")
                if action.assignee:
                    f.write(f"  👤 Исполнитель: {action.assignee}\n")
                if action.deadline:
                    f.write(f"  📅 Дедлайн: {action.deadline}\n")
                f.write("\n")
    
    def reload_registry(self) -> bool:
        return self.registry.load()


# ============================================================
# ФУНКЦИЯ ЗАПУСКА (для оркестратора)
# ============================================================

def run_planner(
    metrics=None,
    gaps_csv_path: Optional[str] = None,
    trends_csv_path: Optional[str] = None
):
    """
    Запускает planner_agent для формирования рекомендаций.
    
    Args:
        metrics: Объект метрик от metrics_agent
        gaps_csv_path: Путь к CSV с gap-зонами
        trends_csv_path: Путь к CSV с трендами
        
    Returns:
        Any: Результаты работы агента
    """
    print("📋 Запуск planner_agent...")
    
    agent = PlannerAgent()
    
    # Подготавливаем данные
    metrics_data = {}
    market_analysis = {}
    narrative = ""
    transcript_analysis = None
    
    # Если передан metrics, извлекаем данные
    if metrics:
        # Если metrics - это словарь с данными
        if isinstance(metrics, dict):
            metrics_data = metrics
        # Если metrics - это объект MetricsAgent
        elif hasattr(metrics, 'build_competency_map'):
            metrics_data = {
                "competency_map": metrics.build_competency_map(),
                "criteria_coverage": metrics.analyze_criteria_coverage(),
                "impact_map": metrics.build_impact_map()
            }
        # Если metrics - это результат run_metrics_agent
        elif isinstance(metrics, dict) and "competency_map" in metrics:
            metrics_data = metrics
        # Если metrics - это объект с аттрибутами
        elif hasattr(metrics, 'competency_map'):
            metrics_data = {
                "competency_map": getattr(metrics, 'competency_map', {}),
                "criteria_coverage": getattr(metrics, 'criteria_coverage', {}),
                "impact_map": getattr(metrics, 'impact_map', {})
            }
    
    # Загружаем gaps из CSV если передан
    if gaps_csv_path:
        try:
            import csv
            with open(gaps_csv_path, 'r', encoding='utf-8-sig') as f:
                gaps_data = list(csv.DictReader(f))
            if "gaps" not in metrics_data:
                metrics_data["gaps"] = []
            if isinstance(gaps_data, list):
                for g in gaps_data:
                    if isinstance(g, dict):
                        topic = g.get("topic_label", "")
                        if topic:
                            metrics_data["gaps"].append(topic)
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки gaps из {gaps_csv_path}: {e}")
    
    # Загружаем trends из CSV если передан
    if trends_csv_path:
        try:
            import csv
            with open(trends_csv_path, 'r', encoding='utf-8-sig') as f:
                trends_data = list(csv.DictReader(f))
            market_analysis["trends"] = trends_data
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки trends из {trends_csv_path}: {e}")
    
    # Загружаем narrative из файла если есть
    narrative_file = Path("src/agents/market_narrative_agent/results/narrative_latest.txt")
    if narrative_file.exists():
        try:
            with open(narrative_file, 'r', encoding='utf-8') as f:
                narrative = f.read()
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки narrative: {e}")
    
    # Загружаем вводные от руководителя из secretary_agent
    transcript_file = Path("data/input/meeting_transcript.json")
    if transcript_file.exists():
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
            transcript_analysis = {
                "main_theses": transcript_data.get("main_theses", []),
                "decisions": transcript_data.get("decisions", []),
                "action_items": transcript_data.get("action_items", []),
                "risks": transcript_data.get("risks", [])
            }
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки транскрипта: {e}")
    
    # Формируем план
    plan = agent.plan(
        metrics_data=metrics_data,
        market_analysis=market_analysis,
        narrative=narrative,
        transcript_analysis=transcript_analysis
    )
    
    # Сохраняем план
    agent.save_plan(plan)
    
    # Возвращаем результат с аттрибутами, ожидаемыми в workflow
    # Создаём объект с нужными полями
    class PlannerResult:
        def __init__(self, plan_obj):
            self.role_recommendations = []
            self.product_recommendations = []
            self.rag_chunks = []
            self.executive_summary = plan_obj.summary
            self.plan = plan_obj
            
            # Конвертируем действия в ожидаемый формат
            for action in plan_obj.actions:
                if action.type == "hire" or "компетенц" in action.description:
                    self.role_recommendations.append({
                        "role": action.description,
                        "urgency": action.priority,
                        "narrative": action.context or ""
                    })
                elif action.type == "improve" or "продукт" in action.description:
                    self.product_recommendations.append({
                        "product_name": action.context or "",
                        "action": action.description,
                        "reason": action.details.get("value", "")
                    })
            
            # Генерируем RAG-чанки из плана (с плоскими метаданными)
            # Используем плоские значения вместо словаря
            priority_counts = plan_obj.priorities
            self.rag_chunks = [
                {
                    "chunk_id": f"plan_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "text": plan_obj.summary,
                    "source": "planner_agent",
                    "section": "summary",
                    "title": "План действий",
                    "metadata": {
                        "critical_count": len(priority_counts.get("critical", [])),
                        "high_count": len(priority_counts.get("high", [])),
                        "medium_count": len(priority_counts.get("medium", [])),
                        "low_count": len(priority_counts.get("low", [])),
                        "total_actions": len(plan_obj.actions),
                        "generated_at": plan_obj.generated_at
                    }
                }
            ]
    
    result = PlannerResult(plan)
    
    print(f"   ✅ planner_agent завершил работу")
    print(f"   Всего действий: {len(plan.actions)}")
    print(f"   Рекомендаций по ролям: {len(result.role_recommendations)}")
    print(f"   Рекомендаций по продуктам: {len(result.product_recommendations)}")
    
    return result


# ============================================================
# ТОЧКА ВХОДА
# ============================================================

def main():
    """Тестовый запуск"""
    print("=" * 60)
    print("📋 PLANNER AGENT - ТЕСТ С РЕЕСТРОМ И ВВОДНЫМИ ОТ РУКОВОДИТЕЛЯ")
    print("=" * 60)
    
    agent = PlannerAgent()
    
    # ============================================================
    # 1. ВВОДНЫЕ ОТ РУКОВОДИТЕЛЯ (из транскрипта)
    # ============================================================
    transcript_analysis = {
        "meeting_date": None,
        "main_theses": [
            "Мы начинаем школу разработки агентов в университете искусственного интеллекта.",
            "У нас богатый опыт преподавания и разработки проектов."
        ],
        "decisions": [
            {
                "decision": "Провести три живых занятия и бонусное занятие в записи",
                "who": "Руководитель",
                "deadline": None
            },
            {
                "decision": "Рассмотреть монологовые и диалоговые промты на следующем занятии",
                "who": "Руководитель",
                "deadline": None
            }
        ],
        "action_items": [
            {
                "task": "Создать проекты на Google As-2D, использовать промты для обучения агентов",
                "assignee": "Участники школы",
                "deadline": None
            },
            {
                "task": "Ответить на вопросы участников в режиме вопросов и ответов",
                "assignee": "Дмитрий Романов",
                "deadline": None
            }
        ],
        "risks": [
            {
                "risk": "Нехватка времени для всех вопросов из-за большого количества участников",
                "owner": "Дмитрий Романов",
                "severity": "medium"
            }
        ],
        "key_topics": ["Обучение агентам", "Использование промтов"],
        "tone_and_mood": "Уверенность, открытость для вопросов и взаимодействия",
        "summary": "Руководитель начал школу разработки агентов с обещанием делиться практическим опытом"
    }
    
    # ============================================================
    # 2. ДАННЫЕ ИЗ РЕЕСТРА МЕТРИК
    # ============================================================
    competency_data = {
        "competency_map": {
            "gaps": ["MLOps", "Docker"],
            "coverage": {"Python": 100, "NLP": 50}
        }
    }
    
    criteria_data = {
        "criteria_coverage": {
            "total": 5,
            "met": 1,
            "partially_met": 2,
            "not_met": 2,
            "overall_progress": 20,
            "criteria_details": [
                {
                    "name": "Точность модели >= 95%",
                    "status": "partially_met",
                    "target": 95,
                    "current": 94.2,
                    "gap": 0.8
                },
                {
                    "name": "Покрытие кода >= 80%",
                    "status": "partially_met",
                    "target": 80,
                    "current": 78.5,
                    "gap": 1.5
                },
                {
                    "name": "Интеграция с источниками",
                    "status": "not_met",
                    "target": 3,
                    "current": 2,
                    "gap": 1
                }
            ]
        }
    }
    
    # ============================================================
    # 3. РЫНОЧНЫЙ АНАЛИЗ
    # ============================================================
    market_analysis = {
        "recommendations": [
            "Усилить маркетинговую активность в сегменте Enterprise",
            "Сфокусироваться на развитии MLOps-компетенций"
        ],
        "impact_from_metrics": {
            "competitive_advantages": ["Скорость разработки", "Гибкость"],
            "market_risks": ["Отставание от конкурентов в области MLOps"]
        }
    }
    
    # ============================================================
    # 4. НАРРАТИВ
    # ============================================================
    narrative = ""
    narrative_file = Path("src/agents/market_narrative_agent/results/narrative_latest.txt")
    if narrative_file.exists():
        try:
            with open(narrative_file, 'r', encoding='utf-8') as f:
                narrative = f.read()
            print(f"📄 Загружен narrative из: {narrative_file}")
        except Exception as e:
            print(f"⚠️ Не удалось загрузить narrative: {e}")
    else:
        print("ℹ️ Narrative не найден, используется пустая строка")
    
    # ============================================================
    # 5. ФОРМИРУЕМ metrics_data
    # ============================================================
    metrics_data = {
        **competency_data,
        **criteria_data,
    }
    
    # ============================================================
    # 6. ЗАПУСК
    # ============================================================
    plan = agent.plan(metrics_data, market_analysis, narrative, transcript_analysis)
    
    print("\n📊 ПЛАН:")
    print("-" * 60)
    print(f"Всего действий: {len(plan.actions)}")
    print(f"\n📌 РЕЗЮМЕ:\n{plan.summary}")
    
    print("\n🎯 ПРИОРИТЕТЫ:")
    for priority, actions in plan.priorities.items():
        if actions:
            priority_ru = agent.PRIORITY_RU.get(priority, priority.upper())
            print(f"  {priority_ru}: {len(actions)}")
            for action in actions[:2]:
                print(f"    • {action[:80]}...")
    
    print("\n⚠️ РИСКИ:")
    for risk in plan.risks:
        print(f"  • {risk}")
    
    print("\n✅ КРИТЕРИИ УСПЕХА:")
    for criterion in plan.success_criteria:
        print(f"  • {criterion}")
    
    agent.save_plan(plan)
    
    # ============================================================
    # 7. ТЕСТ run_planner
    # ============================================================
    print("\n🚀 ТЕСТ run_planner:")
    result = run_planner(metrics=metrics_data)
    print(f"  Рекомендаций по ролям: {len(result.role_recommendations)}")
    print(f"  Рекомендаций по продуктам: {len(result.product_recommendations)}")
    print(f"  RAG-чанков: {len(result.rag_chunks)}")
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТ ЗАВЕРШЕН!")
    print("=" * 60)


if __name__ == "__main__":
    main()