"""research_analyzer.py — Расширенный аналитический слой для веб-интерфейса.

Новые возможности:
- PDF экспорт с профессиональным оформлением
- Визуализация данных (графики, диаграммы)
- Интерактивный чат с отчётом
- Автоматическое обновление данных по расписанию
- Мультиязычность (RU/EN)
- Временные периоды
- REST API для веб-интерфейса
"""

from __future__ import annotations

import asyncio
import json
import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Literal, List, Dict
from enum import Enum
from collections import defaultdict
import base64
from io import BytesIO


# ============================================================================
# 1. РАСШИРЕННЫЕ МОДЕЛИ ДАННЫХ
# ============================================================================

class ReportPeriod(Enum):
    """Периоды для отчётов."""
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class Language(Enum):
    """Языки отчётов."""
    RU = "ru"
    EN = "en"
    BILINGUAL = "bilingual"  # Двуязычный вывод


@dataclass
class TimeFilter:
    """Фильтр по времени."""
    period: ReportPeriod
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    def get_date_range(self) -> tuple[datetime, datetime]:
        """Возвращает диапазон дат."""
        now = datetime.now()
        
        if self.period == ReportPeriod.TODAY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif self.period == ReportPeriod.WEEK:
            start = now - timedelta(days=7)
            end = now
        elif self.period == ReportPeriod.MONTH:
            start = now - timedelta(days=30)
            end = now
        elif self.period == ReportPeriod.QUARTER:
            start = now - timedelta(days=90)
            end = now
        elif self.period == ReportPeriod.YEAR:
            start = now - timedelta(days=365)
            end = now
        elif self.period == ReportPeriod.CUSTOM:
            if self.start_date and self.end_date:
                start = self.start_date
                end = self.end_date
            else:
                start = now - timedelta(days=7)
                end = now
        else:
            start = now - timedelta(days=7)
            end = now
        
        return start, end


@dataclass
class VisualData:
    """Данные для визуализации."""
    chart_type: Literal["bar", "line", "pie", "scatter", "heatmap"]
    title: str
    data: dict[str, Any]
    labels: list[str]
    values: list[float]
    colors: Optional[list[str]] = None
    
    def to_chartjs(self) -> dict:
        """Конвертирует в формат Chart.js."""
        return {
            "type": self.chart_type,
            "data": {
                "labels": self.labels,
                "datasets": [{
                    "label": self.title,
                    "data": self.values,
                    "backgroundColor": self.colors or [
                        "rgba(54, 162, 235, 0.8)",
                        "rgba(255, 99, 132, 0.8)",
                        "rgba(255, 206, 86, 0.8)",
                        "rgba(75, 192, 192, 0.8)",
                        "rgba(153, 102, 255, 0.8)",
                    ],
                    "borderColor": "rgba(54, 162, 235, 1)",
                    "borderWidth": 1
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": self.title
                    }
                }
            }
        }


@dataclass
class ResearchReportExtended(ResearchReport):
    """Расширенный отчёт с дополнительными возможностями."""
    # Новые поля
    period: ReportPeriod = ReportPeriod.WEEK
    language: Language = Language.RU
    visualizations: list[VisualData] = field(default_factory=list)
    interactive_chat_id: Optional[str] = None
    update_schedule: Optional[str] = None  # Cron-выражение
    original_sources: list[dict] = field(default_factory=list)  # Оригинальные тексты
    bilingual_summary: Optional[dict[str, str]] = None  # Резюме на двух языках
    timeline_events: list[dict] = field(default_factory=list)  # События по времени
    
    def get_summary(self, lang: Language = Language.RU) -> str:
        """Возвращает резюме на нужном языке."""
        if lang == Language.RU:
            return self.executive_summary
        elif lang == Language.EN and self.bilingual_summary:
            return self.bilingual_summary.get("en", self.executive_summary)
        return self.executive_summary


# ============================================================================
# 2. PDF ГЕНЕРАТОР
# ============================================================================

class PDFGenerator:
    """Генерация профессиональных PDF отчётов."""
    
    @staticmethod
    def generate(report: ResearchReportExtended, filename: str | Path) -> Path:
        """Генерирует PDF с красивым оформлением."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak, Image, ListFlowable, ListItem
            )
            from reportlab.graphics.shapes import Drawing
            from reportlab.graphics.charts.barcharts import VerticalBarChart
            from reportlab.graphics.charts.linecharts import HorizontalLineChart
            
            filename = Path(filename)
            if not filename.suffix:
                filename = filename.with_suffix('.pdf')
            
            doc = SimpleDocTemplate(
                str(filename),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm,
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            # Заголовок
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=30,
                alignment=1,  # Center
            )
            story.append(Paragraph(f"Аналитический отчёт: {report.query}", title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Мета-информация
            meta_style = ParagraphStyle(
                'Meta',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#7f8c8d'),
            )
            story.append(Paragraph(f"Дата: {report.generated_at}", meta_style))
            story.append(Paragraph(f"Период: {report.period.value}", meta_style))
            story.append(Paragraph(f"Уверенность: {report.confidence_score:.1%}", meta_style))
            story.append(Spacer(1, 0.3*inch))
            
            # Резюме
            story.append(Paragraph("Резюме для руководства", styles['Heading2']))
            story.append(Paragraph(report.executive_summary, styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            
            # Ключевые выводы
            story.append(Paragraph("Ключевые выводы", styles['Heading2']))
            for i, finding in enumerate(report.key_findings[:5], 1):
                story.append(Paragraph(
                    f"{i}. {finding.trend}",
                    styles['Heading3']
                ))
                story.append(Paragraph(finding.description, styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
            
            # Графики (если есть)
            if report.visualizations:
                story.append(PageBreak())
                story.append(Paragraph("Визуализация данных", styles['Heading2']))
                
                for vis in report.visualizations[:2]:
                    try:
                        # Создаём простой бар-чарт для PDF
                        drawing = Drawing(400, 200)
                        bc = VerticalBarChart()
                        bc.x = 50
                        bc.y = 50
                        bc.width = 300
                        bc.height = 150
                        bc.data = [vis.values]
                        bc.categoryAxis.categoryNames = vis.labels
                        bc.valueAxis.valueMin = 0
                        drawing.add(bc)
                        story.append(drawing)
                        story.append(Spacer(1, 0.2*inch))
                    except Exception as e:
                        print(f"Ошибка создания графика: {e}")
            
            # Рекомендации
            story.append(PageBreak())
            story.append(Paragraph("Рекомендации", styles['Heading2']))
            
            rec_items = []
            for rec in report.recommendations:
                rec_items.append(ListItem(Paragraph(rec, styles['Normal'])))
            story.append(ListFlowable(rec_items, bulletType='bullet'))
            story.append(Spacer(1, 0.2*inch))
            
            # Источники
            story.append(Paragraph("Источники", styles['Heading2']))
            for source in report.sources[:10]:
                source_text = f"{source.title} - {source.url}"
                story.append(Paragraph(f"• {source_text}", styles['Normal']))
                if source.key_points:
                    for point in source.key_points[:2]:
                        story.append(Paragraph(f"  - {point[:100]}...", styles['Normal']))
            
            # Футер
            story.append(Spacer(1, 0.5*inch))
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#95a5a6'),
                alignment=1,
            )
            story.append(
                Paragraph(
                    f"Сгенерировано системой AI Research • {datetime.now().year}",
                    footer_style
                )
            )
            
            # Сборка PDF
            doc.build(story)
            return filename
            
        except ImportError:
            print("ReportLab не установлен. Установите: pip install reportlab")
            # Создаём простой текстовый PDF через fpdf
            return PDFGenerator._generate_simple_pdf(report, filename)
    
    @staticmethod
    def _generate_simple_pdf(report: ResearchReportExtended, filename: Path) -> Path:
        """Простая генерация PDF через fpdf."""
        try:
            from fpdf import FPDF
            
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            
            # Заголовок
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, f"Отчёт: {report.query[:50]}", ln=True, align='C')
            pdf.ln(10)
            
            # Резюме
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 10, "Резюме", ln=True)
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(190, 10, report.executive_summary)
            pdf.ln(10)
            
            # Выводы
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 10, "Ключевые выводы", ln=True)
            for i, finding in enumerate(report.key_findings[:5], 1):
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(200, 10, f"{i}. {finding.trend}", ln=True)
                pdf.set_font("Arial", size=12)
                pdf.multi_cell(190, 10, finding.description[:150] + "...")
                pdf.ln(5)
            
            # Сохраняем
            pdf.output(str(filename))
            return filename
            
        except ImportError:
            print("FPDF не установлен. Установите: pip install fpdf")
            # Сохраняем как текстовый файл
            txt_path = filename.with_suffix('.txt')
            txt_path.write_text(ReportExporter.to_markdown(report), encoding='utf-8')
            return txt_path


# ============================================================================
# 3. ВИЗУАЛИЗАТОР
# ============================================================================

class Visualizer:
    """Генерация визуализаций для отчётов."""
    
    def __init__(self):
        self._plotly_available = False
        
        try:
            import plotly.express as px
            import plotly.graph_objects as go
            self._plotly = px
            self._plotly_go = go
            self._plotly_available = True
        except ImportError:
            print("Plotly не установлен. Используйте: pip install plotly")
    
    def create_timeline(self, events: list[dict]) -> Optional[VisualData]:
        """Создаёт таймлайн событий."""
        if not events:
            return None
        
        dates = [e.get('date', '') for e in events]
        descriptions = [e.get('description', '')[:50] for e in events]
        
        return VisualData(
            chart_type="line",
            title="Хронология событий",
            data={"dates": dates, "events": descriptions},
            labels=dates,
            values=list(range(len(dates))),
        )
    
    def create_trend_chart(self, trends: dict[str, list]) -> VisualData:
        """Создаёт график трендов."""
        labels = list(trends.keys())
        values = [len(v) for v in trends.values()]
        
        return VisualData(
            chart_type="bar",
            title="Распределение трендов",
            data=trends,
            labels=labels,
            values=values,
            colors=["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]
        )
    
    def create_confidence_matrix(self, findings: list[Finding]) -> VisualData:
        """Создаёт матрицу уверенности."""
        labels = [f.trend[:20] for f in findings[:8]]
        values = [f.confidence * 100 for f in findings[:8]]
        
        return VisualData(
            chart_type="bar",
            title="Уверенность в выводах (%)",
            data={"findings": labels, "confidence": values},
            labels=labels,
            values=values,
            colors=["#2ecc71" if v > 70 else "#f39c12" if v > 50 else "#e74c3c" 
                    for v in values]
        )
    
    def generate_html_charts(self, report: ResearchReportExtended) -> str:
        """Генерирует HTML с интерактивными графиками."""
        if not self._plotly_available:
            return "<p>Визуализация недоступна (установите plotly)</p>"
        
        html_parts = []
        
        for vis in report.visualizations:
            try:
                fig = self._create_plotly_figure(vis)
                if fig:
                    html_parts.append(fig.to_html(full_html=False))
            except Exception as e:
                print(f"Ошибка создания графика: {e}")
        
        return "\n".join(html_parts) if html_parts else "<p>Нет данных для визуализации</p>"
    
    def _create_plotly_figure(self, vis: VisualData):
        """Создаёт фигуру Plotly."""
        import plotly.graph_objects as go
        
        if vis.chart_type == "bar":
            fig = go.Figure(data=[
                go.Bar(x=vis.labels, y=vis.values, marker_color=vis.colors)
            ])
        elif vis.chart_type == "line":
            fig = go.Figure(data=[
                go.Scatter(x=vis.labels, y=vis.values, mode='lines+markers')
            ])
        elif vis.chart_type == "pie":
            fig = go.Figure(data=[
                go.Pie(labels=vis.labels, values=vis.values)
            ])
        else:
            return None
        
        fig.update_layout(
            title=vis.title,
            template="plotly_white",
            height=400,
        )
        return fig


# ============================================================================
# 4. ИНТЕРАКТИВНЫЙ ЧАТ С ОТЧЁТОМ
# ============================================================================

class ReportChat:
    """Интерактивный чат для работы с отчётом."""
    
    def __init__(self, report: ResearchReportExtended, llm=None):
        self.report = report
        self.llm = llm
        self.chat_id = report.interactive_chat_id or hashlib.md5(
            f"{report.query}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]
        self.history: list[dict] = []
        
    def ask(self, question: str, language: Language = Language.RU) -> dict:
        """Задаёт вопрос по отчёту."""
        # Ищем ответ в самом отчёте
        answer = self._search_in_report(question)
        
        if answer:
            return {
                "question": question,
                "answer": answer,
                "source": "report",
                "confidence": 0.9,
                "language": language.value,
            }
        
        # Если не нашли и есть LLM - генерируем ответ
        if self.llm:
            return self._ask_llm(question, language)
        
        return {
            "question": question,
            "answer": "Извините, не могу найти ответ в отчёте. Попробуйте уточнить вопрос.",
            "source": "none",
            "confidence": 0.0,
            "language": language.value,
        }
    
    def _search_in_report(self, question: str) -> Optional[str]:
        """Ищет ответ в отчёте по ключевым словам."""
        question_lower = question.lower()
        
        # Ищем в выводах
        for finding in self.report.key_findings:
            if any(word in finding.trend.lower() for word in question_lower.split()):
                return f"{finding.trend}\n{finding.description}"
        
        # Ищем в рекомендациях
        for rec in self.report.recommendations:
            if any(word in rec.lower() for word in question_lower.split()):
                return f"Рекомендация: {rec}"
        
        return None
    
    def _ask_llm(self, question: str, language: Language) -> dict:
        """Задаёт вопрос LLM на основе отчёта."""
        if not self.llm:
            return {
                "question": question,
                "answer": "LLM не настроен для ответов на вопросы.",
                "source": "none",
                "confidence": 0.0,
                "language": language.value,
            }
        
        # Формируем контекст из отчёта
        context = f"""
Отчёт: {self.report.query}
Резюме: {self.report.executive_summary}

Ключевые выводы:
{chr(10).join([f"- {f.trend}: {f.description}" for f in self.report.key_findings[:5]])}

Рекомендации:
{chr(10).join([f"- {r}" for r in self.report.recommendations[:5]])}
"""
        
        prompt = f"""
Отвечай на вопрос пользователя, используя только информацию из отчёта.

Контекст отчёта:
{context}

Вопрос пользователя: {question}

Ответь на языке: {'русском' if language == Language.RU else 'английском'}

Если информация есть в отчёте - дай точный ответ.
Если нет - скажи, что информация отсутствует.
"""
        
        try:
            response = self.llm.generate(prompt)
            return {
                "question": question,
                "answer": response,
                "source": "llm",
                "confidence": 0.7,
                "language": language.value,
            }
        except Exception as e:
            return {
                "question": question,
                "answer": f"Ошибка при генерации ответа: {e}",
                "source": "error",
                "confidence": 0.0,
                "language": language.value,
            }
    
    def get_chat_history(self) -> list[dict]:
        """Возвращает историю чата."""
        return self.history
    
    def clear_history(self):
        """Очищает историю чата."""
        self.history = []


# ============================================================================
# 5. АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ ДАННЫХ
# ============================================================================

class ReportScheduler:
    """Планировщик автоматического обновления отчётов."""
    
    def __init__(self, analyzer: ResearchAnalyzer):
        self.analyzer = analyzer
        self.jobs: dict[str, dict] = {}
        
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self.scheduler = BackgroundScheduler()
            self.scheduler.start()
            self._apscheduler_available = True
        except ImportError:
            print("APScheduler не установлен. Установите: pip install apscheduler")
            self._apscheduler_available = False
    
    def schedule_report(
        self,
        report_id: str,
        query: str,
        schedule: str,  # Cron-выражение или "daily", "weekly", "monthly"
        report_type: str = "executive",
        save_path: Optional[str] = None,
    ):
        """Планирует автоматическое обновление отчёта."""
        if not self._apscheduler_available:
            print("Планировщик недоступен")
            return
        
        # Конвертируем строку в cron
        cron = self._parse_schedule(schedule)
        
        # Добавляем задачу
        self.scheduler.add_job(
            func=self._update_report,
            trigger="cron",
            **cron,
            args=[report_id, query, report_type, save_path],
            id=report_id,
            replace_existing=True,
        )
        
        self.jobs[report_id] = {
            "query": query,
            "schedule": schedule,
            "report_type": report_type,
            "save_path": save_path,
            "last_update": None,
        }
        
        print(f"[Scheduler] Отчёт '{report_id}' запланирован: {schedule}")
    
    def _update_report(self, report_id: str, query: str, report_type: str, save_path: str):
        """Обновляет отчёт."""
        print(f"[Scheduler] Обновление отчёта '{report_id}'...")
        
        try:
            report = self.analyzer.generate_report(
                query=query,
                report_type=report_type,
                force_refresh=True,
                save_to_file=save_path,
            )
            
            if report_id in self.jobs:
                self.jobs[report_id]["last_update"] = datetime.now().isoformat()
            
            print(f"[Scheduler] Отчёт '{report_id}' обновлён")
            
        except Exception as e:
            print(f"[Scheduler] Ошибка обновления '{report_id}': {e}")
    
    def _parse_schedule(self, schedule: str) -> dict:
        """Парсит строку расписания."""
        if schedule == "daily":
            return {"hour": 9, "minute": 0}
        elif schedule == "weekly":
            return {"day_of_week": "mon", "hour": 9, "minute": 0}
        elif schedule == "monthly":
            return {"day": 1, "hour": 9, "minute": 0}
        else:
            # Пытаемся распарсить как cron
            parts = schedule.split()
            if len(parts) == 5:
                return {
                    "minute": parts[0],
                    "hour": parts[1],
                    "day": parts[2],
                    "month": parts[3],
                    "day_of_week": parts[4],
                }
            return {"hour": 9, "minute": 0}
    
    def stop_scheduler(self):
        """Останавливает планировщик."""
        if self._apscheduler_available:
            self.scheduler.shutdown()
    
    def get_scheduled_reports(self) -> dict:
        """Возвращает список запланированных отчётов."""
        return self.jobs


# ============================================================================
# 6. ОСНОВНОЙ КЛАСС - РАСШИРЕННЫЙ АНАЛИЗАТОР
# ============================================================================

class ResearchAnalyzerExtended(ResearchAnalyzer):
    """Расширенный аналитический слой со всеми новыми функциями."""
    
    def __init__(
        self,
        llm=None,
        rag_store=None,
        research_agent=None,
        config: Optional[dict] = None,
    ):
        super().__init__(llm, rag_store, research_agent, config)
        
        self.visualizer = Visualizer()
        self.scheduler = ReportScheduler(self)
        self._active_chats: dict[str, ReportChat] = {}
    
    # ====================================================================
    # Генерация отчёта с расширенными возможностями
    # ====================================================================
    
    def generate_extended_report(
        self,
        query: str,
        report_type: Literal["executive", "detailed", "technical", "presentation"] = "executive",
        period: ReportPeriod = ReportPeriod.WEEK,
        language: Language = Language.RU,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_visualizations: bool = True,
        use_cache: bool = True,
        force_refresh: bool = False,
        save_to_file: Optional[str | Path] = None,
        max_sources: int = 10,
    ) -> ResearchReportExtended:
        """Генерирует расширенный отчёт с визуализациями и мультиязычностью."""
        
        print(f"\n{'='*70}")
        print(f"[Analyzer] РАСШИРЕННАЯ ГЕНЕРАЦИЯ ОТЧЁТА")
        print(f"[Analyzer] Запрос: {query}")
        print(f"[Analyzer] Период: {period.value}")
        print(f"[Analyzer] Язык: {language.value}")
        print(f"{'='*70}\n")
        
        # Получаем базовый отчёт
        base_report = self.generate_report(
            query=query,
            report_type=report_type,
            use_cache=use_cache,
            force_refresh=force_refresh,
            save_to_file=None,  # Сохраним позже
            max_sources=max_sources,
        )
        
        # Создаём расширенную версию
        extended_report = ResearchReportExtended(
            query=base_report.query,
            report_type=base_report.report_type,
            generated_at=base_report.generated_at,
            executive_summary=base_report.executive_summary,
            key_findings=base_report.key_findings,
            market_insights=base_report.market_insights,
            recommendations=base_report.recommendations,
            sources=base_report.sources,
            confidence_score=base_report.confidence_score,
            gaps=base_report.gaps,
            raw_data=base_report.raw_data,
            # Новые поля
            period=period,
            language=language,
            bilingual_summary=self._generate_bilingual_summary(base_report),
            original_sources=self._get_original_sources(base_report),
        )
        
        # Добавляем визуализации
        if include_visualizations:
            extended_report.visualizations = self._generate_visualizations(extended_report)
        
        # Генерируем таймлайн
        extended_report.timeline_events = self._generate_timeline(extended_report)
        
        # Создаём ID для чата
        extended_report.interactive_chat_id = hashlib.md5(
            f"{query}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]
        
        # Сохраняем в кэш
        cache_key = hashlib.md5(f"{query}_{period.value}_{language.value}".encode()).hexdigest()
        if self.config["enable_caching"]:
            self._cache[cache_key] = extended_report
        
        # Сохраняем в файл
        if save_to_file:
            self._save_extended_report(extended_report, save_to_file)
        
        print(f"[Analyzer] ✅ Расширенный отчёт готов!")
        print(f"[Analyzer]   - Визуализаций: {len(extended_report.visualizations)}")
        print(f"[Analyzer]   - Чат ID: {extended_report.interactive_chat_id}")
        
        return extended_report
    
    # ====================================================================
    # Вспомогательные методы для расширенного отчёта
    # ====================================================================
    
    def _generate_bilingual_summary(self, report: ResearchReport) -> dict[str, str]:
        """Генерирует резюме на двух языках."""
        if not self.llm:
            return {
                "ru": report.executive_summary,
                "en": report.executive_summary,
            }
        
        prompt = f"""
Переведи следующее резюме на английский язык. Сохрани стиль и структуру.

Резюме (русский):
{report.executive_summary}

Ответь в формате JSON:
{{"ru": "...", "en": "..."}}
"""
        try:
            response = self.llm.generate(prompt)
            return json.loads(response)
        except:
            return {
                "ru": report.executive_summary,
                "en": report.executive_summary,
            }
    
    def _get_original_sources(self, report: ResearchReport) -> list[dict]:
        """Возвращает оригинальные тексты источников."""
        originals = []
        for source in report.sources[:5]:
            # Пытаемся загрузить оригинальный текст
            try:
                page = self.research_agent.crawl_page(source.url)
                if not page.get("error"):
                    originals.append({
                        "url": source.url,
                        "title": source.title,
                        "original_text": page.get("text", "")[:500],
                        "language": self._detect_language(page.get("text", "")),
                    })
            except:
                pass
        return originals
    
    def _detect_language(self, text: str) -> str:
        """Определяет язык текста."""
        if not text:
            return "unknown"
        
        # Простая эвристика
        cyrillic = len(re.findall(r'[а-яА-Я]', text))
        latin = len(re.findall(r'[a-zA-Z]', text))
        
        if cyrillic > latin:
            return "ru"
        elif latin > cyrillic:
            return "en"
        return "unknown"
    
    def _generate_visualizations(self, report: ResearchReportExtended) -> list[VisualData]:
        """Генерирует визуализации для отчёта."""
        visualizations = []
        
        # 1. График уверенности по выводам
        if report.key_findings:
            vis = self.visualizer.create_confidence_matrix(report.key_findings)
            if vis:
                visualizations.append(vis)
        
        # 2. Распределение по категориям
        categories = defaultdict(int)
        for finding in report.key_findings:
            categories[finding.category] += 1
        
        if categories:
            visualizations.append(VisualData(
                chart_type="pie",
                title="Распределение выводов по категориям",
                data=dict(categories),
                labels=list(categories.keys()),
                values=list(categories.values()),
            ))
        
        # 3. Тренды по времени (если есть данные)
        if report.timeline_events:
            vis = self.visualizer.create_timeline(report.timeline_events)
            if vis:
                visualizations.append(vis)
        
        return visualizations
    
    def _generate_timeline(self, report: ResearchReportExtended) -> list[dict]:
        """Генерирует таймлайн событий из данных."""
        events = []
        
        # Извлекаем даты из источников
        for source in report.sources:
            if hasattr(source, 'publication_date') and source.publication_date:
                events.append({
                    "date": source.publication_date,
                    "description": f"Публикация: {source.title}",
                    "source": source.url,
                })
        
        return events
    
    def _save_extended_report(self, report: ResearchReportExtended, path: str | Path):
        """Сохраняет расширенный отчёт во всех форматах."""
        path = Path(path)
        
        # Markdown
        ReportExporter.save_report(report, path.with_suffix('.md'))
        
        # JSON
        ReportExporter.save_report(report, path.with_suffix('.json'), format='json')
        
        # PDF
        PDFGenerator.generate(report, path.with_suffix('.pdf'))
        
        # HTML с графиками (если есть визуализации)
        if report.visualizations:
            html_path = path.with_suffix('.html')
            html_content = self._generate_html_report(report)
            html_path.write_text(html_content, encoding='utf-8')
            print(f"[Analyzer] HTML отчёт: {html_path}")
    
    def _generate_html_report(self, report: ResearchReportExtended) -> str:
        """Генерирует HTML-версию отчёта с интерактивными графиками."""
        charts_html = self.visualizer.generate_html_charts(report)
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчёт: {report.query}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; }}
        .summary {{ background: #ecf0f1; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .findings {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .finding {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; }}
        .chart {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .recommendations {{ background: #e8f5e9; padding: 20px; border-radius: 8px; }}
        .sources {{ background: #f5f5f5; padding: 20px; border-radius: 8px; }}
        .confidence-high {{ color: #2ecc71; }}
        .confidence-medium {{ color: #f39c12; }}
        .confidence-low {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 {report.query}</h1>
        <p>Тип: {report.report_type} | Период: {report.period.value} | Уверенность: {report.confidence_score:.1%}</p>
    </div>
    
    <div class="summary">
        <h2>📋 Резюме</h2>
        <p>{report.executive_summary}</p>
    </div>
    
    <div class="charts">
        <h2>📈 Визуализации</h2>
        <div id="charts-container">
            {charts_html}
        </div>
    </div>
    
    <div class="findings">
        <h2>🔍 Ключевые выводы</h2>
        {''.join([f'''
        <div class="finding">
            <h3>{f.trend}</h3>
            <p>{f.description}</p>
            <span class="confidence-{'high' if f.confidence > 0.7 else 'medium' if f.confidence > 0.5 else 'low'}">
                Уверенность: {f.confidence:.1%}
            </span>
        </div>
        ''' for f in report.key_findings[:6]])}
    </div>
    
    <div class="recommendations">
        <h2>💡 Рекомендации</h2>
        <ul>
            {''.join([f'<li>{r}</li>' for r in report.recommendations])}
        </ul>
    </div>
    
    <div class="sources">
        <h2>📚 Источники</h2>
        {''.join([f'''
        <div style="margin: 10px 0; padding: 10px; background: white; border-radius: 4px;">
            <a href="{s.url}" target="_blank"><strong>{s.title}</strong></a>
            <p style="color: #666; font-size: 0.9em;">Релевантность: {s.relevance_score:.1%}</p>
        </div>
        ''' for s in report.sources[:5]])}
    </div>
    
    <div style="text-align: center; color: #999; margin-top: 40px; font-size: 0.8em;">
        Сгенерировано AI Research • {datetime.now().year}
    </div>
</body>
</html>
"""
    
    # ====================================================================
    # Интерактивный чат с отчётом
    # ====================================================================
    
    def create_chat(self, report_id: str) -> ReportChat:
        """Создаёт чат для общения с отчётом."""
        # Ищем отчёт в кэше
        report = None
        for cached in self._cache.values():
            if hasattr(cached, 'interactive_chat_id') and cached.interactive_chat_id == report_id:
                report = cached
                break
        
        if not report:
            raise ValueError(f"Отчёт с ID {report_id} не найден")
        
        chat = ReportChat(report, self.llm)
        self._active_chats[report_id] = chat
        return chat
    
    def chat_ask(self, chat_id: str, question: str, language: Language = Language.RU) -> dict:
        """Задаёт вопрос в чате."""
        if chat_id not in self._active_chats:
            raise ValueError(f"Чат с ID {chat_id} не активен")
        
        return self._active_chats[chat_id].ask(question, language)
    
    def get_chat_history(self, chat_id: str) -> list[dict]:
        """Возвращает историю чата."""
        if chat_id not in self._active_chats:
            raise ValueError(f"Чат с ID {chat_id} не активен")
        
        return self._active_chats[chat_id].get_chat_history()
    
    # ====================================================================
    # Методы для API
    # ====================================================================
    
    def get_report_status(self, report_id: str) -> dict:
        """Возвращает статус отчёта."""
        for cached in self._cache.values():
            if hasattr(cached, 'interactive_chat_id') and cached.interactive_chat_id == report_id:
                return {
                    "id": report_id,
                    "query": cached.query,
                    "generated_at": cached.generated_at,
                    "confidence": cached.confidence_score,
                    "findings_count": len(cached.key_findings),
                    "sources_count": len(cached.sources),
                    "visualizations_count": len(cached.visualizations),
                    "chat_active": report_id in self._active_chats,
                }
        return {"error": "Отчёт не найден"}
    
    def export_report(
        self,
        report_id: str,
        format: Literal["json", "markdown", "pdf", "html"]
    ) -> str | bytes:
        """Экспортирует отчёт в указанном формате."""
        # Ищем отчёт
        report = None
        for cached in self._cache.values():
            if hasattr(cached, 'interactive_chat_id') and cached.interactive_chat_id == report_id:
                report = cached
                break
        
        if not report:
            raise ValueError(f"Отчёт с ID {report_id} не найден")
        
        if format == "json":
            return ReportExporter.to_json(report)
        elif format == "markdown":
            return ReportExporter.to_markdown(report)
        elif format == "pdf":
            # Сохраняем во временный файл и читаем
            temp_path = Path(f"/tmp/report_{report_id}.pdf")
            PDFGenerator.generate(report, temp_path)
            return temp_path.read_bytes()
        elif format == "html":
            return self._generate_html_report(report)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")


# ============================================================================
# 7. ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("РАСШИРЕННЫЙ RESEARCH ANALYZER - ДЕМОНСТРАЦИЯ")
    print("="*70)
    
    # Инициализация
    analyzer = ResearchAnalyzerExtended()
    
    # Генерация расширенного отчёта
    report = analyzer.generate_extended_report(
        query="Тренды искусственного интеллекта в корпоративном секторе 2026",
        report_type="executive",
        period=ReportPeriod.MONTH,
        language=Language.BILINGUAL,
        include_visualizations=True,
        save_to_file="reports/ai_trends_2026"
    )
    
    print("\n" + "="*70)
    print("ОТЧЁТ СГЕНЕРИРОВАН")
    print("="*70)
    print(f"Чат ID: {report.interactive_chat_id}")
    print(f"Визуализаций: {len(report.visualizations)}")
    print(f"Источников: {len(report.sources)}")
    
    # Создаём чат
    print("\n" + "="*70)
    print("ИНТЕРАКТИВНЫЙ ЧАТ")
    print("="*70)
    
    chat = analyzer.create_chat(report.interactive_chat_id)
    
    questions = [
        "Какие главные тренды в AI?",
        "Что рекомендуется внедрить в первую очередь?",
        "Какие риски упоминаются?",
    ]
    
    for q in questions:
        print(f"\n👤 Вопрос: {q}")
        response = chat.ask(q)
        print(f"🤖 Ответ: {response['answer'][:150]}...")
        print(f"   Уверенность: {response['confidence']:.1%}")
    
    # Планирование обновлений
    print("\n" + "="*70)
    print("ПЛАНИРОВЩИК ОБНОВЛЕНИЙ")
    print("="*70)
    
    analyzer.scheduler.schedule_report(
        report_id="weekly_ai_trends",
        query="Тренды AI в корпоративном секторе",
        schedule="weekly",
        report_type="executive",
        save_path="reports/weekly_ai_trends"
    )
    
    print(f"Запланированные отчёты: {list(analyzer.scheduler.get_scheduled_reports().keys())}")
    
    print("\n✅ Демонстрация завершена!")
    print("\nСгенерированные файлы:")
    print("  - reports/ai_trends_2026.md")
    print("  - reports/ai_trends_2026.json")
    print("  - reports/ai_trends_2026.pdf")
    print("  - reports/ai_trends_2026.html")