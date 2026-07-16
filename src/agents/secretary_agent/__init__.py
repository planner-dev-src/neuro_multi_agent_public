# src/agents/secretary_agent/__init__.py

"""
Secretary Agent - обработка аудио и транскрибация
"""

from .secretary_agent import (
    SecretaryAgent,
    run_secretary_agent,
    transcribe_file,
    analyze_transcript,
    process_audio_file
)

__all__ = [
    "SecretaryAgent",
    "run_secretary_agent",
    "transcribe_file",
    "analyze_transcript",
    "process_audio_file"
]# Secretary agent package.