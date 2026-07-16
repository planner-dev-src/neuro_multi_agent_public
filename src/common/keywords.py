"""
Единый список ключевых слов для всей системы
Используется во всех агентах для фильтрации, классификации и анализа
"""

# ============================================================
# 12 НАПРАВЛЕНИЙ КОМПАНИИ (база знаний)
# ============================================================

COMPANY_DIRECTIONS = {
    "cv": {
        "name": "Компьютерное зрение",
        "en": ["computer vision", "cv"],
        "ru": ["компьютерное зрение", "компьютерное зрение"],
        "keywords": ["computer vision", "cv", "opencv", "image recognition", "object detection", "segmentation"]
    },
    "nlp": {
        "name": "Обработка естественного языка",
        "en": ["natural language processing", "nlp"],
        "ru": ["обработка естественного языка", "nlp"],
        "keywords": ["nlp", "natural language processing", "text mining", "sentiment analysis", "tokenization", "bert", "transformer"]
    },
    "ts": {
        "name": "Временные ряды",
        "en": ["time series", "ts"],
        "ru": ["временные ряды", "ts"],
        "keywords": ["time series", "ts", "forecasting", "prophet", "arima", "lstm", "predictive analytics"]
    },
    "rl": {
        "name": "Обучение с подкреплением",
        "en": ["reinforcement learning", "rl"],
        "ru": ["обучение с подкреплением", "rl"],
        "keywords": ["reinforcement learning", "rl", "q-learning", "policy gradient", "deep rl", "dqn"]
    },
    "s2t": {
        "name": "Аудио и распознавание речи",
        "en": ["speech to text", "s2t", "audio"],
        "ru": ["аудио", "распознавание речи", "s2t"],
        "keywords": ["speech recognition", "audio processing", "whisper", "speech-to-text", "s2t", "voice"]
    },
    "gan": {
        "name": "Генеративно-состязательные нейросети",
        "en": ["generative adversarial", "gan"],
        "ru": ["генеративно-состязательные нейросети", "gan"],
        "keywords": ["gan", "generative adversarial", "diffusion", "stable diffusion", "generative ai"]
    },
    "ml": {
        "name": "Классическое машинное обучение",
        "en": ["machine learning", "ml"],
        "ru": ["машинное обучение", "ml"],
        "keywords": ["machine learning", "ml", "scikit-learn", "regression", "classification", "clustering", "decision tree", "random forest"]
    },
    "ga": {
        "name": "Генетические алгоритмы",
        "en": ["genetic algorithm", "ga"],
        "ru": ["генетические алгоритмы", "ga"],
        "keywords": ["genetic algorithm", "ga", "evolutionary", "optimization"]
    },
    "project_management": {
        "name": "Управление AI проектами",
        "en": ["ai project management", "project management"],
        "ru": ["управление ai проектами", "управление проектами", "pm"],
        "keywords": ["project management", "pm", "agile", "scrum", "ai project", "product management"]
    },
    "production": {
        "name": "Интеграция в PRODUCTION",
        "en": ["production", "mlops", "deployment"],
        "ru": ["интеграция в production", "mlops", "деплой"],
        "keywords": ["mlops", "production", "deployment", "ci/cd", "model serving", "kubernetes", "docker"]
    },
    "llm_agents": {
        "name": "AI-агенты на базе LLM",
        "en": ["llm", "gpt", "agents", "llm agents"],
        "ru": ["ai-агенты", "llm", "gpt", "агенты"],
        "keywords": ["llm", "gpt", "agent", "autonomous agent", "langchain", "llamaindex", "chain-of-thought", "rag"]
    },
    "automl": {
        "name": "AUTOML",
        "en": ["automl", "auto ml"],
        "ru": ["automl", "auto ml"],
        "keywords": ["automl", "auto ml", "hyperopt", "optuna", "automated machine learning"]
    }
}

# ============================================================
# ОБЩИЕ КЛЮЧЕВЫЕ СЛОВА ДЛЯ ПОИСКА И ФИЛЬТРАЦИИ
# ============================================================

# Все ключевые слова (плоский список для быстрой проверки)
ALL_KEYWORDS = []
for direction in COMPANY_DIRECTIONS.values():
    ALL_KEYWORDS.extend(direction.get("keywords", []))
    ALL_KEYWORDS.extend(direction.get("en", []))
    ALL_KEYWORDS.extend(direction.get("ru", []))

# Уникальные ключевые слова
UNIQUE_KEYWORDS = list(set([kw.lower() for kw in ALL_KEYWORDS if kw]))

# ============================================================
# КЛЮЧЕВЫЕ СЛОВА ДЛЯ FILTERING (отсев постороннего)
# ============================================================

FILTER_KEYWORDS = [
    # Русские
    "искусственный интеллект", "нейросеть", "нейронная сеть",
    "машинное обучение", "глубокое обучение", "обработка данных",
    "компьютерное зрение", "обработка естественного языка",
    "временные ряды", "обучение с подкреплением",
    "распознавание речи", "генеративные сети",
    "генетические алгоритмы", "автоматическое машинное обучение",
    "ai-агенты", "нейро-",
    "анализ данных", "data science", "big data",
    "chatgpt", "нейро-куратор", "нейро-продажник",
    # Английские
    "artificial intelligence", "machine learning", "deep learning",
    "neural network", "computer vision", "natural language processing",
    "reinforcement learning", "generative adversarial", "time series",
    "speech recognition", "genetic algorithm", "automl", "mlops",
    "llm", "gpt", "agent", "neural",
    "data science", "analytics", "predictive",
    "pytorch", "tensorflow", "keras", "scikit-learn",
    # Сокращения
    "ai", "ml", "dl", "nlp", "cv", "rl", "gan", "ts", "s2t", "ga"
]

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def get_direction_by_keyword(keyword: str) -> str:
    """Возвращает название направления по ключевому слову"""
    keyword_lower = keyword.lower()
    for key, direction in COMPANY_DIRECTIONS.items():
        all_terms = direction.get("keywords", []) + direction.get("en", []) + direction.get("ru", [])
        if any(keyword_lower in term.lower() or term.lower() in keyword_lower for term in all_terms):
            return key
    return None

def get_all_direction_names() -> list[str]:
    """Возвращает список всех названий направлений"""
    return [d["name"] for d in COMPANY_DIRECTIONS.values()]

def is_relevant_text(text: str) -> bool:
    """Проверяет, релевантен ли текст AI/ML/DS тематике"""
    text_lower = text.lower()
    for keyword in FILTER_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False