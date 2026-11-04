"""
⚙️ Jarvis Settings Window

Auto-generated settings UI driven by config metadata.
Reads/writes config.json directly and groups settings by category.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QScrollArea, QGroupBox, QFormLayout, QPushButton,
    QMessageBox, QSizePolicy, QListWidget, QListWidgetItem,
    QStackedWidget, QSplitter, QInputDialog, QFrame,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from jarvis.config import (
    get_default_config, load_config,
    default_config_path, _save_json, _load_json,
    SUPPORTED_CHAT_MODELS,
)
from jarvis.debug import debug_log
from desktop_app.themes import apply_theme
from desktop_app.mcp_catalogue import CATALOGUE, CATALOGUE_BY_NAME, MCPEntry


# ---------------------------------------------------------------------------
# Config field metadata
# ---------------------------------------------------------------------------

@dataclass
class FieldMeta:
    """Metadata for a single config field."""
    key: str
    label: str
    description: str
    category: str
    field_type: str  # "bool", "int", "float", "str", "choice", "device", "list"
    choices: Optional[List[tuple[str, str]]] = None  # [(value, display), ...]
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    suffix: Optional[str] = None
    nullable: bool = False  # Whether None/"" is a valid value (shows "Default" option)


# Categories and their display order
CATEGORIES = [
    ("llm", "🤖 LLM та моделі ШІ"),
    ("llm_provider", "🔌 Провайдер LLM"),
    ("tts", "🔊 Синтез мовлення"),
    ("piper", "🎵 Piper TTS"),
    ("chatterbox", "🎭 Chatterbox TTS"),
    ("voice_input", "🎤 Голосове введення"),
    ("wake", "👂 Слово-активатор"),
    ("whisper", "🗣️ Розпізнавання мовлення"),
    ("vad", "📊 Виявлення голосу (VAD)"),
    ("timing", "⏱️ Таймінги та вікна"),
    ("memory", "🧠 Пам'ять і діалог"),
    ("location", "📍 Локація"),
    ("features", "✨ Функції"),
    ("mcps", "🔌 MCP-сервери"),
    ("advanced", "🔧 Додатково"),
]


def _is_default_value(val: Any, default_val: Any) -> bool:
    """True when ``val`` should be treated as the default and omitted from
    ``config.json`` (the minimal-config invariant).

    A value equal to the default is omitted. An emptied nullable field reads
    back as ``None``; treat that as the default when the default is itself
    empty (``""`` or ``None``) so we never persist a ``null`` for a field
    that would just fall back anyway.
    """
    if val == default_val:
        return True
    return val is None and default_val in (None, "")


def _dictation_hotkey_choices() -> list:
    """Build platform-aware dictation hotkey dropdown choices."""
    from jarvis.dictation.dictation_engine import format_hotkey_display
    from jarvis.config import _default_dictation_hotkey
    default = _default_dictation_hotkey()
    options = [
        ("ctrl+alt", format_hotkey_display("ctrl+alt")),
        ("ctrl+cmd", format_hotkey_display("ctrl+cmd")),
        ("ctrl+shift+d", format_hotkey_display("ctrl+shift+d")),
        ("ctrl+shift", format_hotkey_display("ctrl+shift")),
    ]
    return [
        (val, f"{label} (за замовчуванням)" if val == default else label)
        for val, label in options
    ]


def _build_field_metadata() -> List[FieldMeta]:
    """Build the metadata registry for all user-facing config fields."""
    fields = []

    def f(key, label, desc, cat, ftype, **kw):
        fields.append(FieldMeta(key=key, label=label, description=desc,
                                category=cat, field_type=ftype, **kw))

    # --- LLM & AI Models ---
    model_choices = [(mid, info["name"]) for mid, info in SUPPORTED_CHAT_MODELS.items()]
    f("ollama_chat_model", "Модель чату", "Основна LLM-модель для розмов",
      "llm", "choice", choices=model_choices)
    f("ollama_embed_model", "Embedding-модель", "Модель для векторних уявлень тексту",
      "llm", "str")
    f("ollama_base_url", "Адреса Ollama", "Базова адреса сервера Ollama",
      "llm", "str")
    f("llm_chat_timeout_sec", "Тайм-аут чату", "Максимальна кількість секунд для відповідей чату",
      "llm", "float", min_val=10, max_val=600, step=10, suffix="s")
    f("llm_tools_timeout_sec", "Тайм-аут інструментів", "Максимальна кількість секунд для викликів інструментів",
      "llm", "float", min_val=10, max_val=600, step=10, suffix="s")
    f("llm_embedding_timeout_sec", "Тайм-аут ембедингів", "Максимальна кількість секунд для ембедингів",
      "llm", "float", min_val=5, max_val=300, step=5, suffix="s")
    f("llm_profile_select_timeout_sec", "Тайм-аут вибору профілю",
      "Максимальна кількість секунд для вибору профілю",
      "llm", "float", min_val=5, max_val=120, step=5, suffix="s")
    f("intent_judge_model", "Модель визначення наміру",
      "Модель для класифікації намірів",
      "llm", "choice", choices=model_choices)
    f("intent_judge_timeout_sec", "Тайм-аут визначення наміру",
      "Максимальна кількість секунд для оцінки наміру",
      "llm", "float", min_val=1, max_val=30, step=0.5, suffix="s")
    f("llm_thinking_enabled", "Режим роздумів чату",
      "Дозволити моделі чату роздумувати перед відповіддю (повільніше, але може підвищити якість)",
      "llm", "bool")
    f("intent_judge_thinking_enabled", "Режим роздумів визначення наміру",
      "Дозволити моделі наміру роздумувати перед класифікацією (додає затримку до розпізнавання активації)",
      "llm", "bool")

    # --- LLM Provider ---
    # Selects which local runtime serves the LLM. The connection and model
    # fields below are nullable: leaving them empty falls back to the Ollama
    # settings on the "LLM & AI Models" page, so a default (Ollama) install
    # never needs to touch this page.
    f("llm_provider", "Провайдер", "Який локальний рушій обслуговує LLM",
      "llm_provider", "choice",
      choices=[("ollama", "Ollama (локально)"),
               ("openai_compatible", "OpenAI-сумісний сервер")])
    f("llm_base_url", "Базова адреса",
      "Базова адреса API провайдера (напр. http://localhost:1234/v1 для LM Studio). "
      "Залиш порожнім, щоб використовувати адресу Ollama.",
      "llm_provider", "str", nullable=True)
    f("llm_api_key", "API-ключ",
      "Bearer-токен для провайдера, якщо він його вимагає. Залиш порожнім, якщо не потрібен.",
      "llm_provider", "password", nullable=True)
    f("llm_chat_model", "Модель чату",
      "Назва моделі у провайдера. Залиш порожнім, щоб використовувати модель чату Ollama.",
      "llm_provider", "str", nullable=True)
    f("embedding_provider", "Провайдер ембедингів",
      "Рушій для ембедингів. Залиш «Як у провайдера чату», якщо рушій чату "
      "має endpoint ембедингів (інакше направ їх на Ollama).",
      "llm_provider", "choice",
      choices=[("", "Як у провайдера чату"),
               ("ollama", "Ollama (локально)"),
               ("openai_compatible", "OpenAI-сумісний сервер")])
    f("embedding_base_url", "Базова адреса ембедингів",
      "Перевизначена базова адреса для ембедингів. Залиш порожнім, щоб "
      "успадкувати від провайдера чату (або адреси Ollama).",
      "llm_provider", "str", nullable=True)
    f("embedding_api_key", "API-ключ ембедингів",
      "Перевизначений bearer-токен для ембедингів. Залиш порожнім, щоб успадкувати ключ чату.",
      "llm_provider", "password", nullable=True)
    f("embedding_model", "Embedding-модель",
      "Назва моделі ембедингів. Залиш порожнім, щоб використовувати модель Ollama.",
      "llm_provider", "str", nullable=True)

    # --- Text-to-Speech ---
    f("tts_enabled", "Увімкнути TTS", "Увімкнути синтез мовлення",
      "tts", "bool")
    f("tts_engine", "Рушій TTS", "Рушій синтезу мовлення",
      "tts", "choice", choices=[("piper", "Piper (нейронний)"), ("chatterbox", "Chatterbox (клонування голосу)")])
    f("tts_rate", "Темп мовлення", "Слів за хвилину (200 = нормально)",
      "tts", "int", min_val=80, max_val=400, step=10, suffix="сл/хв", nullable=True)

    # --- Piper TTS ---
    f("tts_piper_length_scale", "Коефіцієнт швидкості",
      "Швидкість мовлення: <1.0 швидше, >1.0 повільніше",
      "piper", "float", min_val=0.1, max_val=3.0, step=0.05)
    f("tts_piper_noise_scale", "Варіативність звуку",
      "Вище = більш виразно",
      "piper", "float", min_val=0.0, max_val=2.0, step=0.05)
    f("tts_piper_noise_w", "Варіативність фонем",
      "Вище = жвавіший ритм",
      "piper", "float", min_val=0.0, max_val=2.0, step=0.05)
    f("tts_piper_sentence_silence", "Пауза між реченнями",
      "Пауза після кожного речення",
      "piper", "float", min_val=0.0, max_val=2.0, step=0.05, suffix="s")
    f("tts_piper_model_path", "Власна модель голосу",
      "Шлях до голосової моделі .onnx (залиш порожнім для типової)",
      "piper", "str", nullable=True)
    f("tts_piper_speaker", "ID диктора",
      "Індекс диктора для багатоголосих моделей",
      "piper", "int", min_val=0, max_val=99, nullable=True)

    # --- Chatterbox TTS ---
    f("tts_chatterbox_device", "Пристрій",
      "Обчислювальний пристрій для Chatterbox",
      "chatterbox", "choice",
      choices=[("cuda", "CUDA (GPU)"), ("auto", "Авто"), ("cpu", "CPU")])
    f("tts_chatterbox_exaggeration", "Перебільшення",
      "Перебільшення емоцій (0.0–1.0+)",
      "chatterbox", "float", min_val=0.0, max_val=2.0, step=0.05)
    f("tts_chatterbox_cfg_weight", "Вага CFG",
      "Баланс між якістю та швидкістю",
      "chatterbox", "float", min_val=0.0, max_val=2.0, step=0.05)
    f("tts_chatterbox_audio_prompt", "Аудіо для клонування голосу",
      "Шлях до аудіофайлу для клонування голосу (залиш порожнім, щоб вимкнути)",
      "chatterbox", "str", nullable=True)

    # --- Voice Input ---
    f("voice_device", "Пристрій введення",
      "Мікрофон (назва або індекс). Залиш порожнім для типового системного.",
      "voice_input", "device")
    f("sample_rate", "Частота дискретизації",
      "Частота дискретизації звуку в Гц",
      "voice_input", "choice",
      choices=[("16000", "16000 Гц"), ("44100", "44100 Гц"), ("48000", "48000 Гц")])
    f("voice_min_energy", "Мінімальна енергія",
      "Мінімальна енергія звуку, щоб зарахувати голос",
      "voice_input", "float", min_val=0.0, max_val=1.0, step=0.005)

    # --- Wake Word ---
    f("wake_word", "Слово-активатор",
      "Основне слово-активатор для запуску Джарвіса",
      "wake", "str")
    f("wake_fuzzy_ratio", "Нечіткий збіг",
      "Наскільки нечітко порівнювати слово-активатор (0.0–1.0)",
      "wake", "float", min_val=0.5, max_val=1.0, step=0.01)
    # --- Whisper ---
    f("whisper_model", "Розмір моделі",
      "Розмір моделі Whisper (tiny/base/small/medium/large)",
      "whisper", "choice",
      choices=[("tiny", "Крихітна"), ("base", "Базова"), ("small", "Мала"),
               ("medium", "Середня"), ("large-v3", "Large v3")])
    f("whisper_backend", "Рушій",
      "Рушій розпізнавання мовлення",
      "whisper", "choice",
      choices=[("auto", "Авто"), ("mlx", "MLX (Apple Silicon)"),
               ("faster-whisper", "Faster Whisper")])
    f("whisper_device", "Обчислювальний пристрій",
      "Пристрій для інференсу Whisper",
      "whisper", "choice",
      choices=[("auto", "Авто"), ("cuda", "CUDA (GPU)"), ("cpu", "CPU")])
    f("whisper_compute_type", "Тип обчислень",
      "Рівень квантизації для інференсу",
      "whisper", "choice",
      choices=[("int8", "INT8 (швидко)"), ("float16", "Float16"), ("float32", "Float32")])
    f("whisper_vad", "Фільтр VAD",
      "Фільтрувати звук через VAD перед транскрипцією",
      "whisper", "bool")
    f("whisper_min_confidence", "Мінімальна впевненість",
      "Відкидувати сегменти з низькою впевненістю (захист від галюцинацій)",
      "whisper", "float", min_val=0.0, max_val=1.0, step=0.05)
    f("whisper_no_speech_threshold", "Поріг тиші",
      "Відкидувати сегменти, де no_speech_prob не нижче цього значення (фільтрує галюцинації під час тиші)",
      "whisper", "float", min_val=0.0, max_val=1.0, step=0.05)

    # --- VAD ---
    f("vad_enabled", "Увімкнути VAD",
      "Використовувати виявлення голосу (VAD)",
      "vad", "bool")
    f("vad_aggressiveness", "Агресивність",
      "Агресивність VAD (0=наймякша, 3=найагресивніша)",
      "vad", "int", min_val=0, max_val=3)
    f("endpoint_silence_ms", "Тиша для завершення",
      "Тривалість тиші, щоб завершити фразу",
      "vad", "int", min_val=100, max_val=5000, step=50, suffix="ms")
    f("max_utterance_ms", "Максимальна фраза",
      "Максимальна тривалість однієї фрази",
      "vad", "int", min_val=1000, max_val=60000, step=1000, suffix="ms")
    f("tts_max_utterance_ms", "Максимальна фраза під час TTS",
      "Коротший тайм-аут під час TTS для швидкого виявлення зупинки",
      "vad", "int", min_val=500, max_val=10000, step=500, suffix="ms")

    # --- Timing & Windows ---
    f("voice_block_seconds", "Розмір блоку звуку",
      "Розмір блоку звуку для обробки",
      "timing", "float", min_val=0.5, max_val=10.0, step=0.5, suffix="s")
    f("voice_collect_seconds", "Вікно збору мовлення",
      "Час на збір мовлення після слова-активатора",
      "timing", "float", min_val=1.0, max_val=30.0, step=0.5, suffix="s")
    f("voice_max_collect_seconds", "Максимальне вікно збору",
      "Максимальний час збору безперервного мовлення",
      "timing", "float", min_val=10.0, max_val=600.0, step=10, suffix="s")
    f("hot_window_enabled", "Гаряче вікно",
      "Увімкнути вікно для уточнення після відповідей",
      "timing", "bool")
    f("hot_window_seconds", "Тривалість гарячого вікна",
      "Тривалість вікна для уточнення",
      "timing", "float", min_val=1.0, max_val=30.0, step=0.5, suffix="s")
    f("transcript_buffer_duration_sec", "Буфер транскрипту",
      "Тривалість історії транскрипту для визначення наміру",
      "timing", "float", min_val=10, max_val=600, step=10, suffix="s")

    # --- Memory & Dialogue ---
    f("dialogue_memory_timeout", "Вікно пам'яті та щоденника",
      "Тривалість пам'яті діалогу та примусових оновлень щоденника",
      "memory", "float", min_val=30, max_val=3600, step=30, suffix="s")
    f("memory_enrichment_max_results", "Результати збагачення",
      "Максимум результатів пам'яті для збагачення контексту",
      "memory", "int", min_val=1, max_val=50)
    f("memory_enrichment_source", "Джерело збагачення",
      "Яка система пам'яті збагачує відповіді: уся (щоденник + граф), лише щоденник або лише граф",
      "memory", "choice", choices=[("diary", "Лише щоденник"), ("graph", "Лише граф"), ("all", "Усе (щоденник + граф)")])
    f("tool_carryover_max_turns", "Перенесення результатів інструментів",
      "Скільки останніх відповідей із результатами інструментів тримати видимими для уточнень",
      "memory", "int", min_val=0, max_val=10)
    f("tool_carryover_per_entry_chars", "Довжина перенесених результатів",
      "Символів на кожен перенесений результат інструменту (маркери UNTRUSTED зберігаються)",
      "memory", "int", min_val=200, max_val=8000, step=100)
    f("agentic_max_turns", "Максимум кроків агента",
      "Максимальна кількість кроків у циклах використання інструментів",
      "memory", "int", min_val=1, max_val=30)

    # --- Location ---
    f("location_enabled", "Увімкнути локацію",
      "Дозволити відповіді з урахуванням локації",
      "location", "bool")
    f("location_auto_detect", "Автовизначення",
      "Автоматично визначати локацію за IP",
      "location", "bool")
    f("location_cache_minutes", "Час кешування",
      "Хвилини кешування даних локації",
      "location", "int", min_val=1, max_val=1440, step=5, suffix="хв")
    f("location_ip_address", "IP-адреса вручну",
      "Ручна IP-адреса для геолокації (залиш порожнім для авто)",
      "location", "str", nullable=True)
    f("location_cgnat_resolve_public_ip", "Визначення за CGNAT",
      "Визначати публічну IP-адресу, коли мережа за CGNAT",
      "location", "bool")

    # --- Features ---
    f("web_search_enabled", "Пошук в інтернеті",
      "Увімкнути інструмент веб-пошуку",
      "features", "bool")
    f("brave_search_api_key", "API-ключ Brave Search",
      "Необов'язково. Якщо задано, Brave стає основним резервом, коли "
      "DuckDuckGo заблоковано. Безкоштовний ліміт: 2000 запитів/міс на api.search.brave.com.",
      "features", "str", nullable=True)
    f("wikipedia_fallback_enabled", "Резерв Wikipedia",
      "Використовувати Wikipedia як джерело останнього шансу, коли інші "
      "пошуковики не спрацювали. Без ключа й акаунта, майже без передачі даних.",
      "features", "bool")
    f("tune_enabled", "Стартова мелодія",
      "Програвати звук під час запуску",
      "features", "bool")
    f("dictation_enabled", "Режим диктування",
      "Затисни гарячу клавішу, щоб записати мовлення; відпусти, щоб вставити транскрипцію в будь-яку програму",
      "features", "bool")
    f("dictation_hotkey", "Гаряча клавіша диктування",
      "Комбінація клавіш, яку затискаєш під час диктування. Подвійне натискання вмикає режим без рук.",
      "features", "choice", choices=_dictation_hotkey_choices())
    f("dictation_filler_removal", "Вилучення слів-паразитів",
      "Використовувати локальну LLM, щоб вилучати слова-паразити з результату диктування",
      "features", "bool")
    f("dictation_thinking_enabled", "Режим роздумів для диктування",
      "Дозволити LLM роздумувати під час чистки диктування (додає затримку після кожного диктування)",
      "features", "bool")
    f("dictation_custom_dictionary", "Власний словник",
      "Правила виправлення для диктування. Формат 'неправильно -> правильно' (напр. 'Джарвес -> Джарвіс')",
      "features", "list")

    # --- Advanced ---
    f("echo_energy_threshold", "Поріг енергії луни",
      "Поріг для виявлення луни",
      "advanced", "float", min_val=0.0, max_val=10.0, step=0.1)
    f("echo_tolerance", "Допуск луни",
      "Допуск за часом для виявлення луни",
      "advanced", "float", min_val=0.0, max_val=2.0, step=0.05, suffix="s")

    return fields


FIELD_METADATA = _build_field_metadata()


# ---------------------------------------------------------------------------
# Audio device enumeration
# ---------------------------------------------------------------------------

def get_input_devices() -> List[tuple[str, str]]:
    """Return list of (value, display_name) for available audio input devices.

    Returns [("", "System Default")] if sounddevice is not available.
    """
    devices: List[tuple[str, str]] = [("", "🔧 Системний типовий")]
    try:
        import sounddevice as sd
        for idx, dev in enumerate(sd.query_devices()):
            try:
                max_in = int(dev.get("max_input_channels", 0))
            except Exception:
                max_in = 0
            if max_in > 0:
                name = dev.get("name", f"Пристрій {idx}")
                devices.append((str(idx), f"🎤 {name}"))
    except Exception as e:
        debug_log(f"could not enumerate audio devices: {e}", "settings")
    return devices


# ---------------------------------------------------------------------------
# Widget builders
# ---------------------------------------------------------------------------

class SettingsWindow(QDialog):
    """Auto-generated settings UI driven by config field metadata."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Налаштування Jarvis")
        self.setMinimumSize(780, 560)
        self.resize(840, 620)
        self._widgets: Dict[str, Any] = {}  # key -> widget
        self._config_path = default_config_path()
        self._current_config = _load_json(self._config_path)
        self._defaults = get_default_config()
        self._merged = {**self._defaults, **self._current_config}

        apply_theme(self)
        self._build_ui()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("⚙️ Налаштування")
        header.setObjectName("title")
        layout.addWidget(header)

        subtitle = QLabel("Зміни зберігаються у config.json. Перезапусти Jarvis, щоб застосувати.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        # Sidebar + content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # Category sidebar
        self._sidebar = QListWidget()
        self._sidebar.setFixedWidth(200)
        self._sidebar.setIconSize(QSize(0, 0))
        content_layout.addWidget(self._sidebar)

        # Stacked content pages
        self._pages = QStackedWidget()
        content_layout.addWidget(self._pages, 1)

        # Build pages from categories
        fields_by_cat: Dict[str, List[FieldMeta]] = {}
        for fm in FIELD_METADATA:
            fields_by_cat.setdefault(fm.category, []).append(fm)

        for cat_key, cat_label in CATEGORIES:
            if cat_key == "mcps":
                page = self._build_mcp_page()
            else:
                cat_fields = fields_by_cat.get(cat_key, [])
                if not cat_fields:
                    continue
                page = self._build_category_tab(cat_fields)
            self._pages.addWidget(page)

            item = QListWidgetItem(cat_label)
            item.setSizeHint(QSize(0, 40))
            self._sidebar.addItem(item)

        self._sidebar.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        layout.addLayout(content_layout, 1)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)

        reset_btn = QPushButton("↩️ Скинути до типових")
        reset_btn.setObjectName("danger")
        reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Зберегти")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _build_category_tab(self, fields: List[FieldMeta]) -> QWidget:
        """Build a scrollable form for a category's fields."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        for fm in fields:
            widget = self._create_widget(fm)
            self._widgets[fm.key] = widget

            # Label with tooltip
            label = QLabel(fm.label)
            label.setToolTip(fm.description)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

            form.addRow(label, widget)

        # Spacer at bottom
        form.addRow(QLabel(""), QLabel(""))

        scroll.setWidget(container)
        return scroll

    def _create_widget(self, fm: FieldMeta) -> QWidget:
        """Create the appropriate input widget for a field."""
        current = self._merged.get(fm.key)

        if fm.field_type == "bool":
            w = QCheckBox()
            w.setChecked(bool(current))
            w.setToolTip(fm.description)
            return w

        if fm.field_type == "int":
            if fm.nullable:
                return self._create_nullable_int(fm, current)
            w = QSpinBox()
            w.setMinimum(int(fm.min_val) if fm.min_val is not None else -999999)
            w.setMaximum(int(fm.max_val) if fm.max_val is not None else 999999)
            w.setSingleStep(int(fm.step) if fm.step else 1)
            if fm.suffix:
                w.setSuffix(f" {fm.suffix}")
            try:
                w.setValue(int(current) if current is not None else 0)
            except (TypeError, ValueError):
                w.setValue(0)
            w.setToolTip(fm.description)
            return w

        if fm.field_type == "float":
            w = QDoubleSpinBox()
            w.setDecimals(3)
            w.setMinimum(fm.min_val if fm.min_val is not None else -999999.0)
            w.setMaximum(fm.max_val if fm.max_val is not None else 999999.0)
            w.setSingleStep(fm.step if fm.step else 0.1)
            if fm.suffix:
                w.setSuffix(f" {fm.suffix}")
            try:
                w.setValue(float(current) if current is not None else 0.0)
            except (TypeError, ValueError):
                w.setValue(0.0)
            w.setToolTip(fm.description)
            return w

        if fm.field_type == "choice":
            w = QComboBox()
            for val, display in (fm.choices or []):
                w.addItem(display, val)
            # Set current value
            cur_str = str(current) if current is not None else ""
            idx = w.findData(cur_str)
            if idx >= 0:
                w.setCurrentIndex(idx)
            w.setToolTip(fm.description)
            return w

        if fm.field_type == "device":
            w = QComboBox()
            devices = get_input_devices()
            for val, display in devices:
                w.addItem(display, val)
            cur_str = str(current) if current not in (None, "") else ""
            idx = w.findData(cur_str)
            if idx >= 0:
                w.setCurrentIndex(idx)
            w.setToolTip(fm.description)
            return w

        if fm.field_type == "list":
            return self._create_list_widget(fm, current)

        if fm.field_type == "password":
            w = QLineEdit()
            w.setEchoMode(QLineEdit.EchoMode.Password)
            w.setText(str(current) if current not in (None, "") else "")
            if fm.nullable:
                w.setPlaceholderText("Залиш порожнім, якщо немає")
            w.setToolTip(fm.description)
            return w

        # Default: string field
        w = QLineEdit()
        w.setText(str(current) if current not in (None, "") else "")
        if fm.nullable:
            w.setPlaceholderText("Залиш порожнім для типового")
        w.setToolTip(fm.description)
        return w

    def _create_nullable_int(self, fm: FieldMeta, current: Any) -> QWidget:
        """Create a combo + spinbox for an int field that can be None."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        check = QCheckBox("Власне значення")
        spin = QSpinBox()
        spin.setMinimum(int(fm.min_val) if fm.min_val is not None else 0)
        spin.setMaximum(int(fm.max_val) if fm.max_val is not None else 999999)
        spin.setSingleStep(int(fm.step) if fm.step else 1)
        if fm.suffix:
            spin.setSuffix(f" {fm.suffix}")

        has_value = current is not None
        check.setChecked(has_value)
        spin.setEnabled(has_value)
        try:
            spin.setValue(int(current) if has_value else 0)
        except (TypeError, ValueError):
            spin.setValue(0)

        check.toggled.connect(spin.setEnabled)

        layout.addWidget(check)
        layout.addWidget(spin, 1)

        # Store both widgets for value extraction
        container._check = check  # type: ignore[attr-defined]
        container._spin = spin  # type: ignore[attr-defined]
        container.setToolTip(fm.description)
        return container

    def _create_list_widget(self, fm: FieldMeta, current: Any) -> QWidget:
        """Create a list editor with add/remove buttons."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        list_w = QListWidget()
        list_w.setMinimumHeight(100)
        list_w.setMaximumHeight(160)
        list_w.setToolTip(fm.description)

        # Populate with current values
        if isinstance(current, list):
            for item in current:
                if isinstance(item, str) and item.strip():
                    list_w.addItem(item.strip())

        layout.addWidget(list_w)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        add_btn = QPushButton("+ Додати")
        edit_btn = QPushButton("✏️ Редагувати")
        remove_btn = QPushButton("− Вилучити")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        def _on_add():
            text, ok = QInputDialog.getText(
                self, f"Додати: {fm.label}",
                "Введи значення (напр. 'неправильно -> правильно'):",
            )
            if ok and text.strip():
                list_w.addItem(text.strip())

        def _on_edit():
            item = list_w.currentItem()
            if item is None:
                return
            text, ok = QInputDialog.getText(
                self, f"Редагувати: {fm.label}",
                "Відредагуй значення:",
                text=item.text(),
            )
            if ok and text.strip():
                item.setText(text.strip())

        def _on_remove():
            row = list_w.currentRow()
            if row >= 0:
                list_w.takeItem(row)

        add_btn.clicked.connect(_on_add)
        edit_btn.clicked.connect(_on_edit)
        remove_btn.clicked.connect(_on_remove)

        # Store the list widget for value extraction
        container._list_widget = list_w  # type: ignore[attr-defined]
        return container

    # -- MCP management page ------------------------------------------------

    def _build_mcp_page(self) -> QWidget:
        """Build the MCP servers management page."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        desc = QLabel(
            "MCP-сервери (Model Context Protocol) дають Джарвіс додаткові "
            "інструменти: доступ до файлів, веб-пошук, бази даних тощо."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        layout.addWidget(desc)

        # Server list
        self._mcp_list = QListWidget()
        self._mcp_list.setMinimumHeight(180)
        self._mcp_list.setMaximumHeight(300)
        layout.addWidget(self._mcp_list)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        add_catalogue_btn = QPushButton("📦 Додати з каталогу")
        add_catalogue_btn.setToolTip("Обрати зі списку популярних MCP-серверів")
        add_catalogue_btn.clicked.connect(self._on_mcp_add_catalogue)
        btn_layout.addWidget(add_catalogue_btn)

        add_custom_btn = QPushButton("+ Додати власний")
        add_custom_btn.setToolTip("Налаштувати MCP-сервер вручну")
        add_custom_btn.clicked.connect(self._on_mcp_add_custom)
        btn_layout.addWidget(add_custom_btn)

        edit_btn = QPushButton("✏️ Редагувати")
        edit_btn.clicked.connect(self._on_mcp_edit)
        btn_layout.addWidget(edit_btn)

        remove_btn = QPushButton("− Вилучити")
        remove_btn.clicked.connect(self._on_mcp_remove)
        btn_layout.addWidget(remove_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Details panel for selected server
        self._mcp_detail = QLabel("")
        self._mcp_detail.setWordWrap(True)
        self._mcp_detail.setStyleSheet(
            "background-color: #12141a; border: 1px solid #27272a; "
            "border-radius: 8px; padding: 12px; color: #a1a1aa; font-size: 12px;"
        )
        self._mcp_detail.setMinimumHeight(60)
        layout.addWidget(self._mcp_detail)

        self._mcp_list.currentRowChanged.connect(self._on_mcp_selection_changed)

        # Populate from current config
        self._mcp_configs: Dict[str, Dict] = dict(self._merged.get("mcps", {}) or {})
        self._refresh_mcp_list()

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _refresh_mcp_list(self) -> None:
        """Refresh the MCP server list widget from the in-memory dict."""
        self._mcp_list.clear()
        for name, cfg in self._mcp_configs.items():
            catalogue_entry = CATALOGUE_BY_NAME.get(name)
            if catalogue_entry:
                display = f"{catalogue_entry.display_name}  ({name})"
            else:
                display = f"🔌 {name}"
            self._mcp_list.addItem(display)
        if self._mcp_list.count() == 0:
            self._mcp_detail.setText("MCP-сервери не налаштовано. Додай, щоб розширити можливості Джарвіса.")
        else:
            self._mcp_list.setCurrentRow(0)

    def _on_mcp_selection_changed(self, row: int) -> None:
        """Update the detail panel when an MCP server is selected."""
        if row < 0 or row >= len(self._mcp_configs):
            self._mcp_detail.setText("")
            return
        name = list(self._mcp_configs.keys())[row]
        cfg = self._mcp_configs[name]
        command = cfg.get("command", "")
        args = " ".join(str(a) for a in cfg.get("args", []))
        env_keys = ", ".join(cfg.get("env", {}).keys()) if cfg.get("env") else "немає"
        self._mcp_detail.setText(
            f"<b>Назва:</b> {name}<br>"
            f"<b>Команда:</b> {command}<br>"
            f"<b>Аргументи:</b> {args}<br>"
            f"<b>Змінні оточення:</b> {env_keys}"
        )

    def _on_mcp_add_catalogue(self) -> None:
        """Show a dialog to pick from the curated catalogue."""
        dlg = _MCPCatalogueDialog(self._mcp_configs, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for entry, extra_env in dlg.selected_entries_with_env():
                self._mcp_configs[entry.name] = entry.to_config(extra_env=extra_env)
            self._refresh_mcp_list()

    def _on_mcp_add_custom(self) -> None:
        """Show a dialog to manually add an MCP server."""
        dlg = _MCPEditDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, cfg = dlg.get_result()
            if name:
                self._mcp_configs[name] = cfg
                self._refresh_mcp_list()

    def _on_mcp_edit(self) -> None:
        """Edit the selected MCP server."""
        row = self._mcp_list.currentRow()
        if row < 0:
            return
        name = list(self._mcp_configs.keys())[row]
        cfg = self._mcp_configs[name]
        dlg = _MCPEditDialog(name=name, config=cfg, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_name, new_cfg = dlg.get_result()
            if new_name:
                if new_name != name:
                    del self._mcp_configs[name]
                self._mcp_configs[new_name] = new_cfg
                self._refresh_mcp_list()

    def _on_mcp_remove(self) -> None:
        """Remove the selected MCP server."""
        row = self._mcp_list.currentRow()
        if row < 0:
            return
        name = list(self._mcp_configs.keys())[row]
        reply = QMessageBox.question(
            self, "🔌 Вилучити MCP-сервер",
            f"Вилучити '{name}'?\n\nЙого завжди можна додати знову.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self._mcp_configs[name]
            self._refresh_mcp_list()

    # -- Value extraction ---------------------------------------------------

    def _get_value(self, fm: FieldMeta) -> Any:
        """Extract the current value from a widget."""
        w = self._widgets[fm.key]

        if fm.field_type == "bool":
            return w.isChecked()

        if fm.field_type == "int" and fm.nullable:
            if hasattr(w, '_check') and not w._check.isChecked():
                return None
            return w._spin.value()

        if fm.field_type == "int":
            return w.value()

        if fm.field_type == "float":
            return round(w.value(), 3)

        if fm.field_type in ("choice", "device"):
            val = w.currentData()
            # For sample_rate, convert back to int
            if fm.key == "sample_rate":
                try:
                    return int(val)
                except (TypeError, ValueError):
                    return 16000
            return val if val != "" else None

        if fm.field_type == "list":
            list_w = w._list_widget
            return [list_w.item(i).text() for i in range(list_w.count())]

        # str
        text = w.text().strip()
        if fm.nullable and text == "":
            return None
        return text

    # -- Actions ------------------------------------------------------------

    def _on_save(self) -> None:
        """Collect values from widgets and save to config.json."""
        # Start from existing config (preserves keys we don't show in UI)
        config = dict(self._current_config)

        for fm in FIELD_METADATA:
            val = self._get_value(fm)
            default_val = self._defaults.get(fm.key)

            # Only write non-default values to keep config.json clean.
            if _is_default_value(val, default_val):
                config.pop(fm.key, None)
            else:
                config[fm.key] = val

        # Save MCP configs (empty dict = no MCPs, omit from config)
        if self._mcp_configs:
            config["mcps"] = dict(self._mcp_configs)
        else:
            config.pop("mcps", None)

        if _save_json(self._config_path, config):
            debug_log("settings saved to config.json", "settings")
            QMessageBox.information(
                self, "✅ Збережено",
                "Налаштування збережено. Перезапусти Jarvis, щоб зміни застосувалися."
            )
            self.accept()
        else:
            QMessageBox.warning(
                self, "⚠️ Помилка",
                f"Не вдалося зберегти налаштування до:\n{self._config_path}"
            )

    def _on_reset(self) -> None:
        """Reset all fields to defaults."""
        reply = QMessageBox.question(
            self, "↩️ Скинути до типових",
            "Скинути всі налаштування до типових значень?\n\n"
            "Це перезапише твій config.json.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._merged = dict(self._defaults)
        self._current_config = {}

        # Refresh all widgets
        for fm in FIELD_METADATA:
            self._set_widget_value(fm, self._defaults.get(fm.key))

        # Clear MCP configs
        self._mcp_configs = {}
        self._refresh_mcp_list()

        debug_log("settings reset to defaults", "settings")

    def _set_widget_value(self, fm: FieldMeta, value: Any) -> None:
        """Set a widget's value from a config value."""
        w = self._widgets.get(fm.key)
        if w is None:
            return

        if fm.field_type == "bool":
            w.setChecked(bool(value))

        elif fm.field_type == "int" and fm.nullable:
            has_val = value is not None
            w._check.setChecked(has_val)
            w._spin.setEnabled(has_val)
            try:
                w._spin.setValue(int(value) if has_val else 0)
            except (TypeError, ValueError):
                w._spin.setValue(0)

        elif fm.field_type == "int":
            try:
                w.setValue(int(value) if value is not None else 0)
            except (TypeError, ValueError):
                w.setValue(0)

        elif fm.field_type == "float":
            try:
                w.setValue(float(value) if value is not None else 0.0)
            except (TypeError, ValueError):
                w.setValue(0.0)

        elif fm.field_type in ("choice", "device"):
            cur_str = str(value) if value not in (None, "") else ""
            idx = w.findData(cur_str)
            if idx >= 0:
                w.setCurrentIndex(idx)

        elif fm.field_type == "list":
            list_w = w._list_widget
            list_w.clear()
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        list_w.addItem(item.strip())

        else:  # str
            w.setText(str(value) if value not in (None, "") else "")


# ---------------------------------------------------------------------------
# MCP dialogue windows
# ---------------------------------------------------------------------------

class _MCPCatalogueDialog(QDialog):
    """Dialog for picking MCP servers from the curated catalogue."""

    def __init__(self, existing: Dict[str, Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("📦 Каталог MCP-серверів")
        self.setMinimumSize(480, 420)
        apply_theme(self)

        self._existing = existing
        self._checkboxes: Dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        desc = QLabel("Обери MCP-сервери для додавання. Уже налаштовані позначено галочкою.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        layout.addWidget(desc)

        # Node.js availability warning
        node_warning = QLabel(
            "⚠️  <b>Node.js не знайдено.</b> Більшість MCP-серверів потребує Node.js. "
            "<a href='https://nodejs.org/' style='color: #f59e0b;'>Завантаж Node.js</a> "
            "і перезапусти Джарвіса, щоб ними користуватися."
        )
        node_warning.setOpenExternalLinks(True)
        node_warning.setWordWrap(True)
        node_warning.setStyleSheet(
            "background: rgba(239, 68, 68, 0.12);"
            "border: 1px solid rgba(239, 68, 68, 0.35);"
            "border-radius: 8px; padding: 10px 14px; color: #fca5a5; font-size: 12px;"
        )
        node_warning.setVisible(not self._is_node_available())
        layout.addWidget(node_warning)

        # Scrollable list of catalogue entries
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(8)

        for entry in CATALOGUE:
            card = QFrame()
            card.setObjectName("card")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(12)

            cb = QCheckBox()
            already_added = entry.name in existing
            cb.setChecked(already_added)
            if already_added:
                cb.setEnabled(False)
                cb.setToolTip("Вже налаштовано")
            self._checkboxes[entry.name] = cb
            card_layout.addWidget(cb)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)

            name_label = QLabel(entry.display_name)
            name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            text_layout.addWidget(name_label)

            desc_label = QLabel(entry.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
            text_layout.addWidget(desc_label)

            if entry.needs_api_key:
                key_label = QLabel(f"🔑 Потрібен {entry.api_key_env_var}")
                key_label.setStyleSheet("color: #fbbf24; font-size: 11px;")
                text_layout.addWidget(key_label)

            card_layout.addLayout(text_layout, 1)
            inner_layout.addWidget(card)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        add_btn = QPushButton("🔌 Додати обрані")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._on_add)
        btn_layout.addWidget(add_btn)
        layout.addLayout(btn_layout)

    def _on_add(self) -> None:
        """Prompt for API keys if needed, then accept."""
        self._collected_env: Dict[str, Dict[str, str]] = {}
        for entry in self._selected_new_entries():
            if entry.needs_api_key and entry.api_key_env_var:
                key, ok = QInputDialog.getText(
                    self,
                    f"🔑 API-ключ {entry.display_name}",
                    f"Введи свій {entry.api_key_env_var}:\n"
                    f"({entry.api_key_hint or ''})",
                )
                if ok and key.strip():
                    self._collected_env[entry.name] = {entry.api_key_env_var: key.strip()}
                else:
                    # User cancelled key entry — skip this entry
                    self._checkboxes[entry.name].setChecked(False)
                    continue
        self.accept()

    @staticmethod
    def _is_node_available() -> bool:
        """Check if Node.js (npx) is available on the system."""
        try:
            from jarvis.tools.external.mcp_client import _resolve_command
            _resolve_command("npx")
            return True
        except (FileNotFoundError, Exception):
            return False

    def _selected_new_entries(self) -> List[MCPEntry]:
        """Return catalogue entries the user selected (excluding already-configured)."""
        result = []
        for name, cb in self._checkboxes.items():
            if cb.isChecked() and cb.isEnabled():
                result.append(CATALOGUE_BY_NAME[name])
        return result

    def selected_entries_with_env(self) -> List[tuple]:
        """Return list of (MCPEntry, extra_env_dict) for each selected entry."""
        collected = getattr(self, "_collected_env", {})
        return [
            (entry, collected.get(entry.name, {}))
            for entry in self._selected_new_entries()
        ]


class _MCPEditDialog(QDialog):
    """Dialog for adding or editing a single MCP server configuration."""

    def __init__(self, name: str = "", config: Optional[Dict] = None, parent=None):
        super().__init__(parent)
        self._is_edit = bool(name)
        self.setWindowTitle("✏️ Редагувати MCP-сервер" if self._is_edit else "🔌 Додати власний MCP-сервер")
        self.setMinimumSize(440, 340)
        apply_theme(self)

        config = config or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._name_edit = QLineEdit(name)
        self._name_edit.setPlaceholderText("напр. filesystem, my-server")
        if self._is_edit:
            self._name_edit.setEnabled(False)
        form.addRow("Назва", self._name_edit)

        self._command_edit = QLineEdit(str(config.get("command", "")))
        self._command_edit.setPlaceholderText("напр. npx, node, python")
        form.addRow("Команда", self._command_edit)

        self._args_edit = QLineEdit(" ".join(str(a) for a in config.get("args", [])))
        self._args_edit.setPlaceholderText("напр. -y @modelcontextprotocol/server-filesystem ~")
        self._args_edit.setToolTip("Аргументи через пробіл")
        form.addRow("Аргументи", self._args_edit)

        env = config.get("env") or {}
        env_str = " ".join(f"{k}={v}" for k, v in env.items())
        self._env_edit = QLineEdit(env_str)
        self._env_edit.setPlaceholderText("напр. API_KEY=abc123 (KEY=VALUE через пробіл)")
        form.addRow("Змінні оточення", self._env_edit)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        save_btn = QPushButton("💾 Зберегти")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        command = self._command_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "⚠️ Немає назви", "Введи назву сервера.")
            return
        if not command:
            QMessageBox.warning(self, "⚠️ Немає команди", "Введи команду.")
            return
        self.accept()

    def get_result(self) -> tuple:
        """Return (name, config_dict) from the dialog fields."""
        name = self._name_edit.text().strip()
        command = self._command_edit.text().strip()
        args_text = self._args_edit.text().strip()
        args = args_text.split() if args_text else []
        env_text = self._env_edit.text().strip()
        env = {}
        if env_text:
            for pair in env_text.split():
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    env[k] = v

        cfg = {"transport": "stdio", "command": command, "args": args}
        if env:
            cfg["env"] = env
        return name, cfg
