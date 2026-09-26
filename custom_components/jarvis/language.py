"""
JARVIS — Household-language directive (single source of truth).

Both the conversation path (``agent.run_agent``) and every task prompt built
via ``directive_helper.build_system_prompt`` (status briefs, camera analysis,
sentinel notices, …) use :func:`language_directive`, so JARVIS's spoken and
generated output follows the home's configured language consistently rather
than only in chat replies.

This is a leaf module with no package imports, so it is cheap to import from
anywhere without pulling in heavier chains.
"""
from __future__ import annotations

# Language names keyed by the primary ISO-639 subtag of Home Assistant's
# configured language.
_LANG_NAMES = {
    "fr": "French", "de": "German", "es": "Spanish", "it": "Italian",
    "nl": "Dutch", "pt": "Portuguese", "pl": "Polish", "sv": "Swedish",
    "nb": "Norwegian", "no": "Norwegian", "da": "Danish", "fi": "Finnish",
    "cs": "Czech", "ru": "Russian", "uk": "Ukrainian", "tr": "Turkish",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
    "he": "Hebrew", "el": "Greek", "hu": "Hungarian", "ro": "Romanian",
    "sk": "Slovak", "ca": "Catalan", "id": "Indonesian", "th": "Thai",
    "vi": "Vietnamese",
}


def configured_language(hass, lang: str | None = None) -> str:
    """The language JARVIS should answer in, as a primary ISO-639 subtag
    (e.g. ``"de"`` for ``"de-DE"``), ``"en"`` when unset or on error.

    ``lang`` is an optional per-request override — the conversation / voice
    pipeline language (``user_input.language``). When given it wins over Home
    Assistant's global setting, so a request coming through a German satellite
    is answered in German even in a household whose global language is Russian
    (the case that produced wrong-language, garbled voice replies). Never
    raises."""
    try:
        raw = lang or getattr(hass.config, "language", None) or "en"
        return (raw or "en").split("-")[0].lower()
    except Exception:
        return "en"


def language_name(hass, lang: str | None = None) -> str:
    """The display name of the effective language (e.g. ``"German"``), or ``""``
    for English / unset — i.e. non-empty exactly when JARVIS should steer output
    to a non-English language. ``lang`` overrides the global setting as in
    :func:`configured_language`. Never raises."""
    code = configured_language(hass, lang)
    if not code or code == "en":
        return ""
    return _LANG_NAMES.get(code, code)


def language_directive(hass, lang: str | None = None) -> str:
    """A system-prompt block steering output to the effective language.

    Uses Home Assistant's ``language`` so a non-English household gets JARVIS's
    output in its own language. ``lang`` is an optional per-request override
    (the conversation / voice-pipeline language) that wins over the global
    setting, so replies follow the language the request actually came in on.
    Returns ``""`` for English (which is therefore completely unaffected). The
    user's own input language still wins if they write in something else. Never
    raises.
    """
    lname = language_name(hass, lang)
    if not lname:
        return ""
    return (
        f"## Language\n"
        f"Respond in {lname} by default. If the user clearly writes to you in "
        f"another language, reply in that language instead. Keep entity names and "
        f"proper nouns unchanged.\n"
    )
