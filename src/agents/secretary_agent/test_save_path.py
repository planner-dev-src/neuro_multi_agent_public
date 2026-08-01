"""
Тестовый скрипт для проверки путей сохранения результатов
Запуск: python src/agents/secretary_agent/test_save_path.py
"""

import os
from pathlib import Path

def test_save_paths():
    """Проверяет пути сохранения результатов"""
    
    # Определяем корень проекта
    current = Path(__file__).resolve().parent
    project_root = None
    
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            project_root = parent
            break
        if (parent / "src" / "agents").exists():
            project_root = parent
            break
    
    if project_root is None:
        project_root = current.parent.parent.parent
    
    print("=" * 60)
    print("ПРОВЕРКА ПУТЕЙ СОХРАНЕНИЯ")
    print("=" * 60)
    
    print(f"\n📁 Текущая директория: {current}")
    print(f"📁 Корень проекта: {project_root}")
    
    # Путь для результатов
    results_dir = project_root / "src" / "agents" / "secretary_agent" / "transcription_results"
    
    print(f"\n📁 Папка для результатов: {results_dir}")
    print(f"   Существует: {results_dir.exists()}")
    
    if results_dir.exists():
        print(f"\n📄 Содержимое папки:")
        for item in results_dir.iterdir():
            if item.is_dir():
                print(f"  📁 {item.name}/")
                # Показываем файлы в подпапках
                for file in item.iterdir():
                    print(f"     📄 {file.name}")
            else:
                print(f"  📄 {item.name}")
    else:
        print("\n⚠️ Папка не существует. Будет создана при первом сохранении.")
        
    # Проверяем права на запись
    try:
        test_file = results_dir / "test_write.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Тест записи", encoding='utf-8')
        test_file.unlink()
        print("\n✅ Права на запись есть")
    except Exception as e:
        print(f"\n❌ Нет прав на запись: {e}")
    
    print("\n" + "=" * 60)
    print("ГОТОВО!")
    print("=" * 60)

if __name__ == "__main__":
    test_save_paths()