"""Streamlit-дашборд для руководителя.

Запуск:
    streamlit run src/orchestrators/dashboard_app.py

Показывает:
- Аналитический обзор рынка (от market_narrative_agent)
- Графики: топ трендов, gap-зоны, позиционирование платформ
- Данные из последнего прогона market_analysis_agent
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

_MARKET_ANALYSIS_DIR = Path("data/reports/market_analysis_agent")
_NARRATIVE_DIR = Path("data/reports/market_narrative_agent")

st.set_page_config(
    page_title="AI Market Intelligence",
    page_icon="📊",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Загрузка данных
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _load_data():
    """Загружает последние CSV из market_analysis_agent."""
    gaps_file = sorted(_MARKET_ANALYSIS_DIR.glob("competitive_gaps_*.csv"), key=lambda p: p.stat().st_mtime)
    trends_file = sorted(_MARKET_ANALYSIS_DIR.glob("trend_signals_*.csv"), key=lambda p: p.stat().st_mtime)
    pos_file = sorted(_MARKET_ANALYSIS_DIR.glob("platform_positioning_*.csv"), key=lambda p: p.stat().st_mtime)
    narrative_file = sorted(_NARRATIVE_DIR.glob("market_narrative_*.json"), key=lambda p: p.stat().st_mtime)

    gaps = pd.read_csv(gaps_file[-1]) if gaps_file else pd.DataFrame()
    trends = pd.read_csv(trends_file[-1]) if trends_file else pd.DataFrame()
    positioning = pd.read_csv(pos_file[-1]) if pos_file else pd.DataFrame()

    narrative = ""
    if narrative_file:
        import json
        narrative = json.loads(narrative_file[-1].read_text(encoding="utf-8")).get("narrative", "")

    return gaps, trends, positioning, narrative


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def main():
    st.title("📊 AI Market Intelligence")
    st.caption(f"Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    gaps, trends, positioning, narrative = _load_data()

    if gaps.empty and trends.empty:
        st.warning("Данные не найдены. Запустите market_analysis_agent.")
        return

    # ---- Вкладки ----
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Обзор", "📈 Тренды", "🎯 Gap-зоны", "🏢 Платформы"])

    # ---- Обзор ----
    with tab1:
        if narrative:
            st.markdown(narrative)
        else:
            st.info("Аналитический обзор ещё не сгенерирован. Запустите market_narrative_agent.")

    # ---- Тренды ----
    with tab2:
        st.subheader("Топ-10 трендов по силе сигнала")

        if not trends.empty:
            top = trends.nlargest(10, "signal_strength")

            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.bar(
                    top,
                    x="signal_strength",
                    y="topic_label",
                    orientation="h",
                    color="signal_strength",
                    color_continuous_scale="Blues",
                    text="items_count",
                )
                fig.update_traces(
                    texttemplate="%{text} курсов",
                    textposition="outside",
                )
                fig.update_layout(
                    xaxis_title="Сила сигнала",
                    yaxis_title="",
                    height=400,
                    margin=dict(l=0, r=0, t=0, b=0),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.metric("Всего трендов", len(trends))
                st.metric("Доминирующее направление", top.iloc[0]["topic_label"])
                st.metric("Макс. сила сигнала", f"{top.iloc[0]['signal_strength']:.2f}")

            with st.expander("📋 Таблица трендов"):
                st.dataframe(top[["topic_label", "platforms_count", "items_count", "signal_strength"]],
                             use_container_width=True)

    # ---- Gap-зоны ----
    with tab3:
        st.subheader("Топ-10 gap-зон по потенциалу")

        if not gaps.empty:
            top_gaps = gaps.nlargest(10, "opportunity_score")

            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.bar(
                    top_gaps,
                    x="opportunity_score",
                    y="topic_label",
                    orientation="h",
                    color="opportunity_score",
                    color_continuous_scale="Reds",
                    text="platform_share",
                )
                fig.update_traces(
                    texttemplate="охват: %{text:.0%}",
                    textposition="outside",
                )
                fig.update_layout(
                    xaxis_title="Потенциал gap",
                    yaxis_title="",
                    height=400,
                    margin=dict(l=0, r=0, t=0, b=0),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.metric("Всего gap-зон", len(gaps))
                top_gap = top_gaps.iloc[0]
                st.metric("Макс. потенциал", f"{top_gap['opportunity_score']:.2f}")
                st.metric("Лидер gap", top_gap["topic_label"])

            with st.expander("📋 Таблица gap-зон"):
                st.dataframe(
                    top_gaps[["topic_label", "platform_share", "opportunity_score", "interpretation"]],
                    use_container_width=True,
                )

    # ---- Платформы ----
    with tab4:
        st.subheader("Позиционирование платформ")

        if not positioning.empty:
            st.dataframe(
                positioning[[
                    "platform_name", "dominant_topics", "dominant_competency_families",
                    "positioning_statement",
                ]],
                use_container_width=True,
            )

            # Радар конкуренции: считаем топ-темы
            all_topics = []
            for t in positioning["dominant_topics"].dropna():
                all_topics.extend([x.strip() for x in str(t).split("|")])

            if all_topics:
                from collections import Counter
                topic_counts = Counter(all_topics)
                topic_df = pd.DataFrame(topic_counts.most_common(10), columns=["topic", "count"])

                fig = px.pie(
                    topic_df,
                    values="count",
                    names="topic",
                    title="Распределение ключевых тем по платформам",
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()