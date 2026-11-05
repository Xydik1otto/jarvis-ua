"""
Base system prompt constants shared across all model sizes.

These prompts are language-agnostic and focus on core assistant behavior.
"""

from dataclasses import dataclass
from typing import Optional


# Voice/ASR clarification - accounts for transcription noise
ASR_NOTE = (
    "Вхід це голосова транскрипція, у якій можуть бути: помилки, пропущені слова, "
    "слова-паразити («ем», «ну», «типу») або стороння мова, записана до того, як "
    "користувач звернувся до тебе. Витягни реальний запит або запитання користувача, "
    "адресовані тобі, і проігноруй попередню балаканину чи обривки чужих розмов. "
    "Пріоритет: намір користувача, а не дослівна форма."
)

# General inference guidance - prefer action over clarification
INFERENCE_GUIDANCE = (
    "Надавай перевагу розумному висновку з наявного контексту, пам'яті й усталених "
    "звичок замість уточнювальних запитань. Коли робиш припущення чи висновки, "
    "говори про це відверто. Уточнювальні запитання став лише тоді, коли запит "
    "справді двозначний і висновок, найімовірніше, буде хибним."
)

# Voice assistant communication style - concise, conversational
VOICE_STYLE = (
    "Відповідай стисло й розмовно, бо це голосовий асистент. Максимум два-три "
    "речення. Пріоритет: ясність і стислість, користувач слухає, а не читає. "
    "Не розводь подробиці без явного прохання. "
    "НЕ пропонуй варіанти продовження і не питай, чи потрібна ще якась інформація: "
    "просто відповідай прямо. "
    "ВАЖЛИВО: завжди відповідай природною мовою, ніколи не видавай JSON, код чи "
    "структуровані дані як свою відповідь. "
    "НІКОЛИ не використовуй markdown-форматування у відповідях: без зірочок для "
    "виділення (**жирний**, *курсив*), без решіток для заголовків, без маркованих "
    "чи нумерованих списків, без зворотних апострофів. "
    "Текст, який ти пишеш, озвучує TTS-двигун, і він читає ці символи буквально: "
    "зірочки прочитаються як «зірочка зірочка». Пиши лише прості речення."
)


@dataclass
class PromptComponents:
    """
    Collection of all prompt components for a specific model size.

    All components are combined in _build_initial_system_message() to form
    the complete system message.
    """
    asr_note: str
    inference_guidance: str
    tool_incentives: str
    voice_style: str
    tool_guidance: str
    tool_constraints: Optional[str] = None  # Only for small models

    def to_list(self) -> list[str]:
        """Convert to list of non-empty prompt strings."""
        components = [
            self.asr_note,
            self.inference_guidance,
            self.tool_incentives,
            self.voice_style,
            self.tool_guidance,
        ]
        if self.tool_constraints:
            components.append(self.tool_constraints)
        return [c for c in components if c]
