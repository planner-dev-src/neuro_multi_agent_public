#!/usr/bin/env python
"""
Скрипт для скачивания видео с выступлением руководителя
Поддерживает: YouTube, Vimeo, Rutube, и другие платформы

Запуск:
    python scripts/download_video.py "https://www.youtube.com/watch?v=VIDEO_ID"
    python scripts/download_video.py "https://vimeo.com/123456789" --output "my_video.mp4"
    python scripts/download_video.py --list-formats "https://www.youtube.com/watch?v=VIDEO_ID"
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime


# ============================================================
# ПОСТОЯННАЯ ПАПКА ДЛЯ СКАЧИВАНИЯ
# ============================================================
DOWNLOAD_DIR = r"C:\Users\V\N_U_stidying\Dnld"


def download_video(
    url: str,
    output_dir: str = None,
    output_filename: str = None,
    quality: str = "best",
    list_formats: bool = False
) -> str:
    """
    Скачивает видео по URL
    
    Args:
        url: Ссылка на видео
        output_dir: Папка для сохранения (если None, используется DOWNLOAD_DIR)
        output_filename: Имя выходного файла (без расширения)
        quality: Качество (best, 1080p, 720p, 480p, worst)
        list_formats: Показать доступные форматы
    
    Returns:
        str: Путь к скачанному файлу
    """
    
    try:
        import yt_dlp
    except ImportError:
        print("❌ yt-dlp не установлен. Установите:")
        print("   pip install yt-dlp")
        sys.exit(1)
    
    # Определяем папку для загрузок
    if output_dir is None:
        output_dir = DOWNLOAD_DIR
    
    # Создаем папку
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 ПАПКА ДЛЯ ЗАГРУЗОК: {output_path}")
    
    # Определяем имя файла
    if output_filename:
        filename = output_filename
    else:
        # Генерируем имя из URL и даты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_id = _extract_video_id(url)
        if video_id:
            filename = f"{video_id}_{timestamp}"
        else:
            filename = f"video_{timestamp}"
    
    # Настройки для yt-dlp
    ydl_opts = {
        'outtmpl': str(output_path / f"{filename}.%(ext)s"),
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': True,
        'extract_flat': False,
    }
    
    # Настройка качества
    if quality == "best":
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    elif quality == "1080p":
        ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
    elif quality == "720p":
        ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
    elif quality == "480p":
        ydl_opts['format'] = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
    elif quality == "worst":
        ydl_opts['format'] = 'worstvideo+worstaudio/worst'
    else:
        ydl_opts['format'] = quality
    
    # Если нужно только показать форматы
    if list_formats:
        print(f"\n📋 Доступные форматы для {url}:")
        print("-" * 60)
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            for f in formats:
                format_id = f.get('format_id', 'N/A')
                resolution = f.get('resolution', 'N/A')
                ext = f.get('ext', 'N/A')
                filesize = f.get('filesize', 0)
                filesize_mb = filesize / (1024 * 1024) if filesize else 0
                print(f"  [{format_id}] {resolution} ({ext}) - {filesize_mb:.1f} MB")
        return ""
    
    # Скачиваем видео
    print(f"\n📥 Скачивание видео: {url}")
    print(f"📄 Имя: {filename}")
    print(f"⚙️  Качество: {quality}")
    print("-" * 60)
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            # Если имя файла с расширением
            if not os.path.exists(downloaded_file):
                # Ищем файл в папке
                for f in output_path.glob(f"{filename}.*"):
                    downloaded_file = str(f)
                    break
            
            print("\n" + "=" * 60)
            print("✅ ВИДЕО УСПЕШНО СКАЧАНО!")
            print("=" * 60)
            print(f"📁 Файл: {downloaded_file}")
            
            # Информация о видео
            title = info.get('title', 'Неизвестно')
            duration = info.get('duration', 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
            print(f"📺 Название: {title}")
            print(f"⏱️  Длительность: {duration_str}")
            
            return downloaded_file
            
    except Exception as e:
        print(f"\n❌ Ошибка при скачивании: {e}")
        return ""


def _extract_video_id(url: str) -> str:
    """Извлекает ID видео из URL"""
    import re
    
    # YouTube
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]+)',
        r'(?:youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)',
        r'(?:youtube\.com\/v\/)([\w-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Vimeo
    match = re.search(r'(?:vimeo\.com\/)(\d+)', url)
    if match:
        return f"vimeo_{match.group(1)}"
    
    # Rutube
    match = re.search(r'(?:rutube\.ru\/video\/)([\w-]+)', url)
    if match:
        return f"rutube_{match.group(1)}"
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Скачивание видео с выступлением руководителя",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python scripts/download_video.py "https://www.youtube.com/watch?v=abc123"
  python scripts/download_video.py "https://vimeo.com/123456789" --output "meeting"
  python scripts/download_video.py "https://www.youtube.com/watch?v=abc123" --quality 720p
  python scripts/download_video.py "https://www.youtube.com/watch?v=abc123" --list-formats
        """
    )
    
    parser.add_argument(
        "url",
        help="Ссылка на видео (YouTube, Vimeo, Rutube и др.)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Имя выходного файла (без расширения)"
    )
    parser.add_argument(
        "--dir",
        "-d",
        default=None,
        help=f"Папка для сохранения (по умолчанию: {DOWNLOAD_DIR})"
    )
    parser.add_argument(
        "--quality",
        "-q",
        default="best",
        choices=["best", "1080p", "720p", "480p", "worst"],
        help="Качество видео (по умолчанию: best)"
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="Показать доступные форматы и выйти"
    )
    
    args = parser.parse_args()
    
    # Скачиваем видео
    result = download_video(
        url=args.url,
        output_dir=args.dir,
        output_filename=args.output,
        quality=args.quality,
        list_formats=args.list_formats
    )
    
    if result:
        print(f"\n💡 Для использования в системе:")
        print(f"   python src/agents/secretary_agent/transcriber.py \"{result}\" --llm")


if __name__ == "__main__":
    main()