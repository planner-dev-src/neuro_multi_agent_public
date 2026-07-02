# Neuro Multi Agent Project

MVP мультиагентного Python-проекта для анализа рынка AI-обучения и дальнейшего расширения другими агентами.

## Текущий статус
Сейчас реализуется первый агент:
- Market Agent

Планируемые агенты:
- Secretary Agent
- Planner Agent

## Стек
- Python
- FastAPI
- Streamlit
- Requests / HTTPX
- Trafilatura / BeautifulSoup
- Pandas
- Pytest

## Быстрый старт

### 1. Создать виртуальное окружение
python -m venv .venv

### 2. Активировать
Windows:
.venv\Scripts\activate

### 3. Установить зависимости
pip install -r requirements.txt

### 4. Запустить API
python run_api.py

### 5. Запустить scratch MVP
python scratch/market_agent_mvp.py