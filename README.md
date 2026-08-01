# Neuro Multi Agent Project

Мультиагентная система поддержки управленческих решений для AI/IT-компании

## Стек
- **Язык:** Python 3.10+
- **Веб-сервер:** FastAPI + Uvicorn
- **Интерфейс:** HTML5 + Bootstrap 5
- **База знаний:** ChromaDB (RAG)
- **Языковая модель:** Ollama (qwen2.5:7b)
- **Поиск:** DuckDuckGo Search API
- **Транскрипция:** OpenAI Whisper

## Быстрый старт

### 1. Создать виртуальное окружение
python -m venv .venv

### 2. Активировать
Windows:
.venv\Scripts\activate

### 3. Установить зависимости
pip install -r requirements.txt

### 4. Запуск полного пайплайна (терминал)
#### Только анализ рынка
python src/orchestrators/workflow.py --mode market_only

#### Полный цикл анализа
python src/orchestrators/workflow.py --mode full

#### Исследование по запросу
python src/orchestrators/workflow.py --mode research --research "тренды AI в образовании 2026"

### 5. Запуск веб-сервера
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000