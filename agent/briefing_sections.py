"""
agent/briefing_sections.py
==========================
Morning Briefing Section Registry & "Spice" Generators for AGENT 001 (Mark-LIV).

Sections:
1. on_this_day: Notable historical event for today's date via DDG search, with Gemini REST fallback.
2. fun_fact: Surprising technology/AI/space/science fact via Gemini REST fallback (alternates with word_of_day).
3. quote_joke: Alternates days between a short motivational quote and a clean one-line joke.
4. focus: Reads 'projects' and recent 'sessions' from memory/long_term.json (skips if no project).
5. word_of_day: Useful English word with meaning and example (alternates with fun_fact).

Properties:
- Variety: Picks at most 3 spice sections per day rotating by day-of-year.
- History: Prevents repeats within 30 days via data/briefing_history.json.
- Timeout & Resilience: Each section runs in its own 5-8s timeout; failures log to logs/agent_actions.jsonl and never crash briefing.
- Tone: Natural, warm, concise (1-2 sentences per section).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Coroutine, Dict, List, Optional

# Base directory
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.logger import ActionLogger
import memory.config_manager as config_manager

# Fallback models and paths
_HISTORY_PATH = _REPO_ROOT / "data" / "briefing_history.json"
_MEMORY_PATH = _REPO_ROOT / "memory" / "long_term.json"


@dataclass
class BriefingSection:
    """Represents an executed briefing section with spoken text and panel card content."""
    name: str
    spoken_text: str
    panel_text: str


# ── History & 30-Day Anti-Repeat Store ────────────────────────────────────────

class BriefingHistory:
    """Tracks recently used items (facts, quotes, jokes, words) to prevent 30-day repeats."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or _HISTORY_PATH

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data.get("history", []) if isinstance(data, dict) else []
        except Exception:
            return []

    def is_recently_used(
        self,
        item_type: str,
        item_key: str,
        max_days: int = 30,
        ref_date: Optional[datetime] = None,
    ) -> bool:
        now = ref_date or datetime.now()
        target = item_key.strip().lower()
        for entry in self.load():
            if entry.get("type") == item_type and entry.get("key", "").strip().lower() == target:
                try:
                    d = datetime.strptime(entry.get("date", ""), "%Y-%m-%d")
                    if (now - d).days < max_days:
                        return True
                except Exception:
                    continue
        return False

    def record_used(
        self,
        item_type: str,
        item_key: str,
        ref_date: Optional[datetime] = None,
    ) -> None:
        self._ensure_dir()
        history = self.load()
        now = ref_date or datetime.now()
        now_str = now.strftime("%Y-%m-%d")
        clean_key = item_key.strip().lower()

        # Prune entries older than 60 days to keep file lean
        pruned = []
        for e in history:
            try:
                d = datetime.strptime(e.get("date", ""), "%Y-%m-%d")
                if (now - d).days < 60:
                    pruned.append(e)
            except Exception:
                pruned.append(e)

        pruned.append({"type": item_type, "key": clean_key, "date": now_str})
        try:
            self.path.write_text(json.dumps({"history": pruned}, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[BriefingHistory] Failed to write history: {e}")


# ── Curated High-Quality Fallbacks (Offline & Resilient) ─────────────────────

_CURATED_FACTS = [
    ("Milky Way Trees", "There are more trees on Earth than stars in the Milky Way galaxy, with roughly three trillion trees compared to around four hundred billion stars."),
    ("Octopus Hearts", "An octopus possesses three separate hearts and blue, copper-rich blood that helps it transport oxygen efficiently in cold, deep water."),
    ("Apollo Computer", "The Apollo Guidance Computer that navigated humanity to the Moon operated with just four kilobytes of RAM and a clock speed under one megahertz."),
    ("Neutron Stars", "A single teaspoon of matter from a neutron star would weigh approximately six billion tons on Earth due to extreme gravitational compression."),
    ("Venus Day", "Venus rotates so slowly on its axis that a single day on Venus lasts longer than its entire year around the Sun."),
    ("Honey Preservation", "Pure honey sealed in ancient Egyptian tombs over three thousand years ago remains completely edible today because of its unique low-moisture chemistry."),
    ("DNA Length", "If you unraveled and joined all the DNA molecules in a single human body, the strand would stretch from Earth to Pluto and back."),
    ("Saturn Rings", "Although Saturn's rings are nearly three hundred thousand kilometers wide, they are remarkably thin, averaging only about ten meters in thickness."),
    ("First Computer Bug", "The original computer bug was an actual physical moth found trapped inside the Mark II computer relay at Harvard University in 1947."),
    ("ISS Speed", "The International Space Station orbits Earth at five miles per second, completing a full orbit every ninety minutes and experiencing sixteen sunrises a day."),
]

_CURATED_QUOTES = [
    ("Alan Kay", "The best way to predict the future is to invent it."),
    ("Grace Hopper", "The most dangerous phrase in the language is: we've always done it this way."),
    ("Steve Jobs", "The only way to do great work is to love what you do."),
    ("Marie Curie", "Nothing in life is to be feared, it is only to be understood. Now is the time to understand more, so that we may fear less."),
    ("Albert Einstein", "In the middle of difficulty lies opportunity."),
    ("Arthur C. Clarke", "Any sufficiently advanced technology is indistinguishable from magic."),
    ("Carl Sagan", "Somewhere, something incredible is waiting to be known."),
    ("Eleanor Roosevelt", "The future belongs to those who believe in the beauty of their dreams."),
]

_CURATED_JOKES = [
    ("Dark Mode", "Why do programmers prefer dark mode? Because light attracts bugs."),
    ("Cache Invalidation", "There are only 10 types of people in the world: those who understand binary, and those who don't."),
    ("Coffee to Code", "Why did the developer go broke? Because they used up all their cache."),
    ("Python Math", "Why was the JavaScript developer sad? Because they didn't know how to 'null' their feelings."),
    ("Network Toast", "Why did the router get an award? Because it gave such great packet service."),
    ("Git Commit", "Why was the git commit so confident? Because it had already pushed through its conflicts."),
]

_CURATED_WORDS = [
    ("Serendipity", "the occurrence of finding valuable or pleasant things by chance", "A fortunate bout of serendipity led to discovering the critical software solution."),
    ("Ephemeral", "lasting for a very short time; fleeting", "The colorful autumn sunrise was breathtaking but ephemeral."),
    ("Resilient", "able to withstand or recover quickly from difficult conditions", "Our architecture proved remarkably resilient during peak traffic."),
    ("Ubiquitous", "present, appearing, or found everywhere", "Smartphones have transitioned from novelties to ubiquitous tools."),
    ("Perspicacious", "having a ready insight into and understanding of things", "Her perspicacious analysis quickly revealed the root cause of the bug."),
    ("Eloquent", "fluent or persuasive in speaking or writing", "The team delivered an eloquent demonstration that impressed all stakeholders."),
    ("Tenacious", "tending to keep a firm hold of something; persistent", "His tenacious debugging cracked the elusive race condition."),
]


# ── REST Fallback Helper (gemini-2.5-flash-lite) ──────────────────────────────

def _gemini_rest_call(prompt: str, timeout_s: float = 3.5) -> Optional[str]:
    """Invoke Gemini REST with model ladder starting at gemini-2.5-flash-lite."""
    try:
        from core import gemini
        cl = gemini.client(timeout_ms=int(timeout_s * 1000))
        for model in ("gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-3.6-flash"):
            try:
                resp = cl.models.generate_content(model=model, contents=prompt)
                txt = (getattr(resp, "text", None) or "").strip()
                if txt:
                    clean = re.sub(r"^[`'\"]+|[`'\"]+$", "", txt).strip()
                    return clean
            except Exception as me:
                msg = str(me)
                if "404" in msg or "NOT_FOUND" in msg or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    continue
                break
        return None
    except Exception as e:
        print(f"[BriefingSections] Gemini REST fallback error: {e}")
        return None


# ── Section 1: On This Day ───────────────────────────────────────────────────

async def get_on_this_day(ref_date: Optional[datetime] = None) -> Optional[BriefingSection]:
    """
    On this day: One notable event for today's date.
    Fetches via DuckDuckGo search helper, with Gemini REST fallback (gemini-2.5-flash-lite).
    """
    now = ref_date or datetime.now()
    month_name = now.strftime("%B")
    day = now.day
    date_str = f"{month_name} {day}"

    event_summary = ""

    # 1. Attempt DuckDuckGo search
    try:
        from actions.web_search import _ddg_search
        query = f"on this day in history {date_str} notable event"
        results = await asyncio.to_thread(_ddg_search, query, max_results=4)
        if results and isinstance(results, list):
            for r in results:
                snippet = r.get("snippet", "").strip()
                title = r.get("title", "").strip()
                # Check for year pattern like (1969) or in 1969
                match = re.search(r"\b(in\s+)?(1[789]\d\d|20\d\d)\b[:,\s]+([^.]{20,120}\.)", snippet, re.IGNORECASE)
                if match:
                    event_summary = f"On this day {match.group(0).strip()}"
                    break
                elif len(snippet) > 30 and not snippet.lower().startswith("historical events for"):
                    # Use first clean informative sentence
                    first_sent = snippet.split(".")[0].strip()
                    if len(first_sent) > 25:
                        event_summary = f"On this day: {first_sent}."
                        break
    except Exception as e:
        print(f"[OnThisDay] DDG search error: {e}")

    # 2. Gemini REST fallback if search failed or produced generic text
    if not event_summary or len(event_summary) < 20:
        prompt = (
            f"Provide one notable, interesting historical event that occurred on {date_str}. "
            "Reply with exactly one concise sentence under 20 words starting with 'On this day in <year>...'. "
            "Do not include citations, markdown, or lists."
        )
        gen_text = await asyncio.to_thread(_gemini_rest_call, prompt, timeout_s=3.0)
        if gen_text and len(gen_text) > 15:
            event_summary = gen_text

    # 3. Final default safeguard
    if not event_summary:
        event_summary = f"On this day in {now.year}, we mark another productive step forward in science and exploration."

    # Safeguard concise length (1-2 short sentences, max ~25 words)
    words = event_summary.strip().split()
    if len(words) > 28:
        sentences = re.split(r'(?<=[.!?])\s+', event_summary)
        if sentences and len(sentences[0].split()) <= 28:
            event_summary = sentences[0]
        else:
            event_summary = " ".join(words[:25]) + "."

    spoken = event_summary
    panel = f"📅 ON THIS DAY ({date_str})\n{event_summary}"
    return BriefingSection(name="on_this_day", spoken_text=spoken, panel_text=panel)


# ── Section 2: Fun Fact ──────────────────────────────────────────────────────

async def get_fun_fact(
    ref_date: Optional[datetime] = None,
    history: Optional[BriefingHistory] = None,
) -> Optional[BriefingSection]:
    """
    Fun fact: One surprising fact about technology, AI, space or science.
    Generated by Gemini REST fallback with 30-day anti-repeat protection.
    """
    hist = history or BriefingHistory()
    now = ref_date or datetime.now()

    chosen_fact: Optional[str] = None
    chosen_key: Optional[str] = None

    # Attempt Gemini generation
    prompt = (
        "Provide one surprising and harmless fun fact about technology, AI, space, or science. "
        "State it in exactly one concise sentence under 20 words without preamble or citations."
    )
    gen_text = await asyncio.to_thread(_gemini_rest_call, prompt, timeout_s=3.0)
    if gen_text and len(gen_text) > 20 and not hist.is_recently_used("fun_fact", gen_text[:40], 30, now):
        chosen_fact = gen_text
        chosen_key = gen_text[:40]

    # Fallback pool with 30-day deduplication
    if not chosen_fact:
        for key, fact in _CURATED_FACTS:
            if not hist.is_recently_used("fun_fact", key, 30, now):
                chosen_fact = fact
                chosen_key = key
                break

    if not chosen_fact:
        # If all exhausted within 30 days, reuse first harmless fact
        chosen_key, chosen_fact = _CURATED_FACTS[0]

    # Safeguard concise length (1 sentence, max ~22 words)
    words = chosen_fact.strip().split()
    if len(words) > 24:
        sentences = re.split(r'(?<=[.!?])\s+', chosen_fact)
        if sentences and len(sentences[0].split()) <= 24:
            chosen_fact = sentences[0]
        else:
            chosen_fact = " ".join(words[:22]) + "."

    hist.record_used("fun_fact", chosen_key or "fact", now)
    spoken = f"Here's a quick fun fact: {chosen_fact}"
    panel = f"💡 FUN FACT\n{chosen_fact}"
    return BriefingSection(name="fun_fact", spoken_text=spoken, panel_text=panel)


# ── Section 3: Quote or Joke ─────────────────────────────────────────────────

async def get_quote_or_joke(
    ref_date: Optional[datetime] = None,
    history: Optional[BriefingHistory] = None,
) -> Optional[BriefingSection]:
    """
    Quote or joke: Alternates days between a short motivational quote and a clean one-line joke.
    Respects 30-day anti-repeat rules.
    """
    hist = history or BriefingHistory()
    now = ref_date or datetime.now()
    doy = now.timetuple().tm_yday
    is_quote_day = (doy % 2 == 0)

    if is_quote_day:
        # Quote day
        chosen_author, chosen_quote = None, None
        # Check Gemini REST
        prompt = (
            "Provide one inspiring, short motivational quote and its author. "
            "Format: \"<Quote>\" — <Author>. Exactly one line, no markdown."
        )
        gen = await asyncio.to_thread(_gemini_rest_call, prompt, timeout_s=3.0)
        if gen and "—" in gen:
            parts = gen.split("—")
            q = parts[0].strip(' "')
            a = parts[1].strip()
            if not hist.is_recently_used("quote", a, 30, now):
                chosen_author, chosen_quote = a, q

        if not chosen_quote:
            for author, quote in _CURATED_QUOTES:
                if not hist.is_recently_used("quote", author, 30, now):
                    chosen_author, chosen_quote = author, quote
                    break

        if not chosen_quote:
            chosen_author, chosen_quote = _CURATED_QUOTES[0]

        hist.record_used("quote", chosen_author, now)
        spoken = f"Thought for today: {chosen_quote} — {chosen_author}."
        panel = f"💬 QUOTE OF THE DAY\n\"{chosen_quote}\"\n— {chosen_author}"
        return BriefingSection(name="quote_joke", spoken_text=spoken, panel_text=panel)

    else:
        # Joke day
        chosen_key, chosen_joke = None, None
        prompt = "Provide one clean, witty, harmless one-line joke about technology or programming. Exactly one line."
        gen = await asyncio.to_thread(_gemini_rest_call, prompt, timeout_s=3.0)
        if gen and len(gen) > 15 and not hist.is_recently_used("joke", gen[:30], 30, now):
            chosen_key, chosen_joke = gen[:30], gen

        if not chosen_joke:
            for key, joke in _CURATED_JOKES:
                if not hist.is_recently_used("joke", key, 30, now):
                    chosen_key, chosen_joke = key, joke
                    break

        if not chosen_joke:
            chosen_key, chosen_joke = _CURATED_JOKES[0]

        hist.record_used("joke", chosen_key, now)
        spoken = f"Here's a quick morning chuckle: {chosen_joke}"
        panel = f"😄 JOKE OF THE DAY\n{chosen_joke}"
        return BriefingSection(name="quote_joke", spoken_text=spoken, panel_text=panel)


# ── Section 4: Today's Focus ─────────────────────────────────────────────────

async def get_todays_focus(
    ref_date: Optional[datetime] = None,
    memory_path: Optional[Path] = None,
) -> Optional[BriefingSection]:
    """
    Today's focus: Reads 'projects' and last 'sessions' from long_term.json.
    Skips cleanly if no projects are defined.
    """
    f = memory_path or _MEMORY_PATH
    if not f.exists():
        return None

    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None

    projects = data.get("projects", {})
    if not isinstance(projects, dict) or not projects:
        # Explicit rule: Skip if no project
        return None

    # Pick the most active project
    project_name = list(projects.keys())[0]
    proj_val = projects[project_name]
    summary_hint = ""
    if isinstance(proj_val, dict):
        summary_hint = str(proj_val.get("value") or proj_val.get("description") or "")
    elif isinstance(proj_val, str):
        summary_hint = proj_val

    # Check last session for yesterday context
    sessions = data.get("sessions", [])
    last_session = sessions[-1] if (isinstance(sessions, list) and sessions) else None
    when = "recently"
    if last_session and isinstance(last_session, dict):
        sess_date_str = last_session.get("date", "")
        now = ref_date or datetime.now()
        try:
            diff_days = (now - datetime.strptime(sess_date_str, "%Y-%m-%d")).days
            if diff_days == 1:
                when = "yesterday"
            elif diff_days == 0:
                when = "earlier today"
        except Exception:
            pass

    spoken = f"{when.capitalize()} you focused on {project_name}. Want to pick that back up today?"
    panel = (
        f"🎯 TODAY'S FOCUS\n"
        f"Project: {project_name}\n"
        f"{'Context: ' + summary_hint if summary_hint else 'Status: Active project'}"
    )
    return BriefingSection(name="focus", spoken_text=spoken, panel_text=panel)


# ── Section 5: Word of the Day ───────────────────────────────────────────────

async def get_word_of_day(
    ref_date: Optional[datetime] = None,
    history: Optional[BriefingHistory] = None,
) -> Optional[BriefingSection]:
    """
    Word of the day: One useful English word with short meaning and example.
    Alternates with fun_fact on different days; enforces 30-day anti-repeat.
    """
    hist = history or BriefingHistory()
    now = ref_date or datetime.now()

    chosen_word: Optional[str] = None
    chosen_meaning: Optional[str] = None
    chosen_example: Optional[str] = None

    # Check Gemini REST
    prompt = (
        "Provide one sophisticated, useful English vocabulary word with its short definition and an example sentence. "
        "Format: Word: <word> | Meaning: <meaning> | Example: <example>. Exactly one line."
    )
    gen = await asyncio.to_thread(_gemini_rest_call, prompt, timeout_s=3.0)
    if gen and "Meaning:" in gen and "Example:" in gen:
        try:
            parts = gen.split("|")
            w = parts[0].replace("Word:", "").strip()
            m = parts[1].replace("Meaning:", "").strip()
            ex = parts[2].replace("Example:", "").strip()
            if w and not hist.is_recently_used("word", w, 30, now):
                chosen_word, chosen_meaning, chosen_example = w, m, ex
        except Exception:
            pass

    if not chosen_word:
        for word, meaning, example in _CURATED_WORDS:
            if not hist.is_recently_used("word", word, 30, now):
                chosen_word, chosen_meaning, chosen_example = word, meaning, example
                break

    if not chosen_word:
        chosen_word, chosen_meaning, chosen_example = _CURATED_WORDS[0]

    hist.record_used("word", chosen_word, now)
    spoken = f"Today's word of the day is {chosen_word}, meaning {chosen_meaning}."
    panel = f"📖 WORD OF THE DAY\n{chosen_word.capitalize()}: {chosen_meaning}\nExample: \"{chosen_example}\""
    return BriefingSection(name="word_of_day", spoken_text=spoken, panel_text=panel)


# ── Section Registry & Daily Selection ───────────────────────────────────────

SECTION_REGISTRY: Dict[str, Callable[[Optional[datetime]], Coroutine[Any, Any, Optional[BriefingSection]]]] = {
    "on_this_day": get_on_this_day,
    "fun_fact": get_fun_fact,
    "quote_joke": get_quote_or_joke,
    "focus": get_todays_focus,
    "word_of_day": get_word_of_day,
}


def get_daily_spice_sections(ref_date: Optional[datetime] = None) -> List[str]:
    """
    Selects at most 3 spice sections per day rotating by day-of-year.
    Enforces alternation between fun_fact and word_of_day, and respects config flags.
    """
    now = ref_date or datetime.now()
    doy = now.timetuple().tm_yday

    # Alternation: fun_fact on even days, word_of_day on odd days
    fact_or_word = "fun_fact" if (doy % 2 == 0) else "word_of_day"

    # Eligible pool for today
    candidates = ["on_this_day", fact_or_word, "quote_joke", "focus"]

    # Filter by user configuration
    enabled = [sec for sec in candidates if config_manager.get_brief_section_enabled(sec)]

    # Cap at most 3 sections rotated by day-of-year
    if len(enabled) <= 3:
        return enabled

    offset = doy % len(enabled)
    rotated = [enabled[(offset + i) % len(enabled)] for i in range(3)]
    return rotated


async def run_spice_section(
    name: str,
    ref_date: Optional[datetime] = None,
    timeout_s: float = 7.0,
) -> Optional[BriefingSection]:
    """
    Executes a single briefing section inside a 5-8s timeout, logging events to
    ActionLogger (section_started, section_ok, section_skipped, section_failed).
    Never raises an uncaught exception.
    """
    handler = SECTION_REGISTRY.get(name)
    if not handler:
        ActionLogger.log_event(
            tool="morning_briefing",
            action="section_skipped",
            parameters={"section": name, "reason": "Unknown section name"},
        )
        return None

    # 1. Log started
    print(f"[Briefing] ⏳ [section_started] Section: '{name}'")
    try:
        ActionLogger.log_event(
            tool="morning_briefing",
            action="section_started",
            parameters={"section": name},
        )
    except Exception:
        pass

    # 2. Execute with timeout
    try:
        sec = await asyncio.wait_for(handler(ref_date), timeout=timeout_s)
        if sec and isinstance(sec, BriefingSection) and sec.spoken_text:
            print(f"[Briefing] ✅ [section_ok] Section: '{name}'")
            try:
                ActionLogger.log_event(
                    tool="morning_briefing",
                    action="section_ok",
                    parameters={"section": name},
                    result=sec.spoken_text[:120],
                    verified=True,
                )
            except Exception:
                pass
            return sec
        else:
            print(f"[Briefing] ⏭️ [section_skipped] Section: '{name}' (no data)")
            try:
                ActionLogger.log_event(
                    tool="morning_briefing",
                    action="section_skipped",
                    parameters={"section": name, "reason": "No data or criteria not met"},
                )
            except Exception:
                pass
            return None

    except Exception as exc:
        err_msg = str(exc) if str(exc) else (f"{type(exc).__name__}: {timeout_s}s timeout exceeded" if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) else type(exc).__name__)
        print(f"[Briefing] ⚠️ [section_failed] Section: '{name}' — {err_msg}")
        try:
            ActionLogger.log_event(
                tool="morning_briefing",
                action="section_failed",
                parameters={"section": name},
                error=err_msg,
                verified=False,
            )
        except Exception:
            pass
        return None


async def run_daily_spice_sections(ref_date: Optional[datetime] = None) -> List[BriefingSection]:
    """
    Gathers and runs all rotated spice sections for today.
    A failure in any individual section never halts the others.
    """
    selected_names = get_daily_spice_sections(ref_date)
    results: List[BriefingSection] = []

    for name in selected_names:
        sec = await run_spice_section(name, ref_date=ref_date)
        if sec:
            results.append(sec)

    return results
