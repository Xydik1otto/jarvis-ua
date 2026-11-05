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


# Ground-truth context rule: the [Context: ...] line prepended to the system
# message each turn carries the live local time, date, weekday and location.
# Field testing (qwen2.5:7b-instruct) showed the model ignoring that line and
# answering a time question with an invented date, so the authority of the
# line is stated firmly, as its own component, rather than left implicit.
CONTEXT_GROUND_TRUTH = (
    "ДЖЕРЕЛО ПРАВДИ ПРО ЧАС І ЛОКАЦІЮ:\n"
    "Рядок [Context: ...] на початку цього системного повідомлення оновлюється "
    "кожного ходу і є єдиним авторитетним джерелом поточної дати, дня тижня, "
    "часу й локації. Відповідаючи на питання про час, дату чи день тижня, "
    "використовуй ЛИШЕ значення з цього рядка, сформульоване природною мовою "
    "користувача. НІКОЛИ не вигадуй дату, час, день тижня чи рік і не бери їх "
    "із попередніх знань, навіть якщо здається, що ти знаєш: твої внутрішні "
    "уявлення про «сьогодні» застарілі й хибні. Якщо рядок [Context: ...] "
    "присутній, точна відповідь у тебе вже є, і вигадане значення часу це "
    "заборонена відповідь. Ніколи не кажи, що не маєш доступу до годинника "
    "або що тобі потрібна локація користувача: вони в тебе вже є."
)

# Recall-first rule: the recent dialogue already sits in the message list,
# yet the model answered a recall question («Який мій улюблений колір?») by
# promising to look the answer up later instead of reading the turn right
# above. Stated as an absolute ban on announced-but-not-executed actions.
RECALL_FIRST = (
    "ВІДПОВІДАЙ З ТОГО, ЩО ВЖЕ Є:\n"
    "Якщо відповідь на запитання користувача вже є в історії розмови вище або "
    "в блоках пам'яті в цьому системному повідомленні, відповідай нею ОДРАЗУ "
    "в цьому самому ході. НІКОЛИ не відповідай обіцянкою майбутньої дії на "
    "кшталт «зараз завантажу», «зараз знайду», «дай перевірю», «зараз "
    "подивлюся»: або відповідай прямо, або виклич відповідний інструмент у "
    "цьому самому ході. Оголосити дію, не виконавши її, це заборонена "
    "відповідь. Коли користувач розповів факт у попередньому ході (наприклад, "
    "назвав свій улюблений колір), цей факт уже відомий тобі: у пізніших "
    "ходах згадуй його з історії чи пам'яті, без пошуків у зовнішніх "
    "джерелах."
)


@dataclass
class PromptComponents:
    """
    Collection of all prompt components for a specific model size.

    All components are combined in _build_initial_system_message() to form
    the complete system message.
    """
    context_ground_truth: str
    recall_first: str
    asr_note: str
    inference_guidance: str
    tool_incentives: str
    voice_style: str
    tool_guidance: str
    tool_constraints: Optional[str] = None  # Only for small models

    def to_list(self) -> list[str]:
        """Convert to list of non-empty prompt strings.

        The grounding and recall rules come first: they read immediately
        after the persona prose, before the long tool sections, so a small
        model meets them while its attention is still at the top of the
        prompt (primacy).
        """
        components = [
            self.context_ground_truth,
            self.recall_first,
            self.asr_note,
            self.inference_guidance,
            self.tool_incentives,
            self.voice_style,
            self.tool_guidance,
        ]
        if self.tool_constraints:
            components.append(self.tool_constraints)
        return [c for c in components if c]
