import json
import requests

prompt = """
Ты — профессиональный аналитик. Напиши краткий аналитический нарратив.

ДАННЫЕ:
- Компания — лидер в AI
- 12 базовых направлений
- Анализ рынка показывает 6 конкурентов

Напиши текст объёмом 500-1000 слов на русском языке.
"""

print("🧠 Отправка запроса к Ollama...")

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:7b",
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3,
        "options": {"num_predict": 4096}
    },
    timeout=120
)

if response.status_code == 200:
    result = response.json()
    narrative = result.get("response", "")
    print(f"\n📄 Длина ответа: {len(narrative)} символов")
    print("\n" + "=" * 60)
    print(narrative[:1000] + "..." if len(narrative) > 1000 else narrative)
    print("=" * 60)
else:
    print(f"❌ Ошибка: {response.status_code}")
    print(response.text)