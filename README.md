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
### 1. Клонировать репозиторий
```bash
git clone https://github.com/planner-dev-src/neuro_multi_agent_public.git
cd neuro_multi_agent_public
```

### 2. Создать виртуальное окружение
```python -m venv .venv```

### 3. Активировать
Windows:
```.venv\Scripts\activate```

### 4. Установить зависимости
```pip install -r requirements.txt```

### 5. Установить и запустить Ollama
Скачайте с https://ollama.com и установите. Затем загрузите модель:
```bash
ollama pull qwen2.5:7b
```

### 6. Запуск полного пайплайна (терминал)
#### Только анализ рынка
```python src/orchestrators/workflow.py --mode market_only```

#### Полный цикл анализа
```python src/orchestrators/workflow.py --mode full```

#### Исследование по запросу
```python src/orchestrators/workflow.py --mode research --research "тренды AI в образовании 2026"```

### 7. Запуск веб-сервера
```bash
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000```

Страницы
| Страница | URL |
|----------|-----|
| Обзор | `/` |
| Исследование | `/research` |
| Задачи | `/tasks` |
| Чат | `/chat` |
| Презентация | `/presentation` |

## Примечание
Для работы Чата и Аналитического обзора требуется Ollama с моделью qwen2.5:7b. Остальные страницы работают без языковой модели.
