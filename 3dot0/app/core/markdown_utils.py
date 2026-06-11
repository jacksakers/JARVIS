"""
Markdown rendering utilities.
Converts LLM-produced Markdown to safe HTML for serving to the frontend.
"""
import markdown as _md

# Extensions that make LLM output look great in a browser
_EXTENSIONS = [
    "tables",           # | col | col | tables
    "fenced_code",      # ```python blocks
    "codehilite",       # syntax highlighting for fenced code
    "nl2br",            # single newlines become <br>
    "sane_lists",       # better list handling
    "pymdownx.tasklist",        # - [x] task lists
    "pymdownx.superfences",     # nested fenced blocks
    "pymdownx.highlight",       # improved code highlighting
    "pymdownx.smartsymbols",    # arrows, em-dashes, etc.
    "admonition",       # !!! note / warning blocks
    "attr_list",        # {.class} attributes on elements
]

_EXTENSION_CONFIGS = {
    "codehilite": {
        "guess_lang": False,
        "use_pygments": True,
    },
    "pymdownx.highlight": {
        "use_pygments": True,
        "auto_title": True,
    },
    "pymdownx.tasklist": {
        "custom_checkbox": True,
    },
}


def render_markdown(text: str) -> str:
    """
    Convert Markdown to HTML.  Falls back gracefully if pymdownx extensions
    are not installed (they're optional; the base markdown extensions always work).
    """
    if not text or not text.strip():
        return ""

    # Try the full extension list first; strip pymdownx extensions if unavailable
    try:
        return _md.markdown(
            text,
            extensions=_EXTENSIONS,
            extension_configs=_EXTENSION_CONFIGS,
            output_format="html",
        )
    except ImportError:
        # pymdownx not installed — fall back to base extensions only
        base_extensions = [e for e in _EXTENSIONS if not e.startswith("pymdownx")]
        return _md.markdown(
            text,
            extensions=base_extensions,
            extension_configs={
                k: v for k, v in _EXTENSION_CONFIGS.items()
                if not k.startswith("pymdownx")
            },
            output_format="html",
        )


def extract_title(markdown_text: str, fallback: str = "Report") -> str:
    """
    Extract the first H1 heading from markdown as a title string.
    Falls back to the provided default if no heading is found.
    """
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback
