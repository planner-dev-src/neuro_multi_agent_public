import requests
import json

# Короткий промпт
prompt = """
Ты — профессиональный аналитик. Напиши краткий анализ рынка AI-образования в России.

ДАННЫЕ:
- Проанализировано 6 платформ: hse, karpov-courses, otus, skillbox, yandex-practicum, netology
- Всего курсов: 560
- Компания является лидером в области AI

Напиши 2-3 абзаца.
"""

print("🧠 Отправка запроса к Ollama...")

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:7b",
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3,
        "options": {"num_predict": 2000}
    },
    timeout=60
)

print(f"Статус: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    narrative = result.get("response", "")
    print(f"Длина: {len(narrative)} символов")
    print("\n" + "=" * 60)
    print(narrative)
    print("=" * 60)
else:
    print(f"Ошибка: {response.text}")