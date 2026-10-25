"""Settings loaded from environment variables.

Deputy never reads secrets from files. The API key comes from the
environment (or from Claude Code's plugin secure storage, which is passed
in as an environment variable).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "https://api.deepinfra.com/v1/openai"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4.1-Flash-1017"
DEFAULT_EFFORT = "high"
# review and consult lenses think less by default: in the review benchmark, low caught every
# planted bug that high caught, with similar false alarms, in less than half the time.
DEFAULT_LENS_EFFORT = "low"
EFFORTS = ("none", "low", "medium", "high", "max")
# accuracy: Claude writes all code; Deputy only gives second opinions and reviews.
# lean: as few Claude tokens as possible with little accuracy loss (Deputy reads and takes
# larger well-specified work). balanced: Deputy also takes low-risk mechanical work.
# partner: Deputy does all low-level work and gives ideas; Claude verifies everything.
# savings: Deputy takes most coding work.
MODES = ("accuracy", "lean", "balanced", "partner", "savings")
DEFAULT_MODE = "accuracy"

XAI_BASE_URL = "https://api.x.ai/v1"
XAI_DEFAULT_MODEL = "grok-4.3"  # fast, strong tool calling, documented reasoning_effort

# Provider presets: (display name, base URL, default model). DEPUTY_BASE_URL and DEPUTY_MODEL
# override the last two. "grok" is an alias for "xai".
PROVIDERS = {
    "deepinfra": ("DeepInfra", DEFAULT_BASE_URL, DEFAULT_MODEL),
    "xai": ("xAI", XAI_BASE_URL, XAI_DEFAULT_MODEL),
}
PROVIDER_ALIASES = {"grok": "xai"}
DEFAULT_PROVIDER = "deepinfra"

# Key variables per API host. A provider's key is only sent to that provider's own host, so a
# DeepInfra key never reaches xAI or the other way round; other endpoints use DEPUTY_API_KEY.
# OPENAI_API_KEY is deliberately never read: sending someone's real OpenAI key to another
# provider would leak it.
HOST_KEY_VARS = {
    "api.deepinfra.com": ("DEEPINFRA_API_KEY", "DEEPINFRA_TOKEN"),
    "api.x.ai": ("XAI_API_KEY",),
    "us.api.x.ai": ("XAI_API_KEY",),
}

# USD per 1M tokens (input, cached input, output), October 2026. Prices change; override with
# DEPUTY_PRICE_INPUT / _CACHED / _OUTPUT. xAI bills prompts of 200k tokens or more at double rate.
_GROK_PRICES = {
    ("grok-4.3", "grok-4.3-latest", "grok-4.20", "grok-4.20-reasoning", "grok-4.20-0309-reasoning",
     "grok-4.20-0309-non-reasoning"): (1.25, 0.20, 2.50),
    ("grok-build-0.1", "grok-code-fast-1", "grok-code-fast"): (1.00, 0.20, 2.00),
    ("grok-4.5", "grok-4.5-latest"): (2.00, 0.30, 6.00),
    ("grok-4.6", "grok-4.7"): (2.00, 0.50, 6.00),
}
KNOWN_PRICES = {
    (DEFAULT_BASE_URL, DEFAULT_MODEL): (0.098, 0.0029, 0.294),
    **{(XAI_BASE_URL, model): price for models, price in _GROK_PRICES.items() for model in models},
}

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Lead models for the savings estimate: (display name, USD per 1M input, cached input, output).
# Anthropic first-party API list prices, October 2026. Haiku's cached price is an assumption
# (10% of input). Override with DEPUTY_LEAD_PRICE_INPUT / _CACHED / _OUTPUT.
LEAD_MODELS = {
    "opus": ("Claude Opus 5.5", 4.0, 0.20, 20.0),
    "sonnet": ("Claude Sonnet 5.5", 2.0, 0.20, 10.0),
    "haiku": ("Claude Haiku 5.5", 0.10, 0.01, 0.50),
    "fable": ("Claude Fable 5.1", 10.0, 0.25, 50.0),
}
DEFAULT_LEAD = "opus"


class ConfigError(RuntimeError):
    """Raised when the environment holds an invalid setting."""


def _get(env: Mapping[str, str], name: str) -> str:
    value = (env.get(name) or "").strip()
    # An unsubstituted plugin placeholder such as "${user_config.x}" means
    # "not set", not a literal value.
    if not value or "${" in value:
        return ""
    return value


def _int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = _get(env, name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if not low <= value <= high:
        raise ConfigError(f"{name} must be between {low} and {high}, got {value}")
    return value


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = _get(env, name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if value < 0:
        raise ConfigError(f"{name} must not be negative")
    return value


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _get(env, name).lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false, got {raw!r}")


def validate_base_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host:
        raise ConfigError(f"DEPUTY_BASE_URL has no host: {url!r}")
    if parts.username or parts.password:
        raise ConfigError("DEPUTY_BASE_URL must not contain credentials")
    if parts.scheme == "https":
        return url.rstrip("/")
    if parts.scheme == "http" and host in LOOPBACK_HOSTS:
        return url.rstrip("/")
    raise ConfigError("DEPUTY_BASE_URL must use https (http is allowed only for localhost)")


def is_deepseek_api(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "deepseek.com" or host.endswith(".deepseek.com")


def is_xai_api(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "x.ai" or host.endswith(".x.ai")


def key_vars_for(url: str) -> tuple[str, ...]:
    """The variables that may hold the key for this endpoint, in the order they are checked."""
    return ("DEPUTY_API_KEY", *HOST_KEY_VARS.get((urlsplit(url).hostname or "").lower(), ()))


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    key_source: str
    base_url: str
    model: str
    effort: str
    mode: str
    workspace: Path
    max_turns: int
    max_run_tokens: int
    max_output_tokens: int
    run_timeout: int
    command_timeout: int
    keep_reasoning: bool
    price_input: float
    price_cached: float
    price_output: float
    lead_name: str = "Claude Opus 5.5"
    lead_price_input: float = 4.0
    lead_price_cached: float = 0.20
    lead_price_output: float = 20.0
    stats_enabled: bool = True
    data_dir: Path = field(default_factory=lambda: Path.home() / ".deputy")
    provider: str = DEFAULT_PROVIDER
    # Per-lens caps for review and consult: a lens that runs into one writes up what it has.
    lens_timeout: int = 300
    lens_max_output: int = 32_000
    lens_effort: str = DEFAULT_LENS_EFFORT

    @property
    def has_prices(self) -> bool:
        return self.price_input > 0 or self.price_output > 0

    @property
    def key_hint(self) -> str:
        """The variable to tell users to set when the key is missing: the provider's own key
        variable (DEEPINFRA_API_KEY, XAI_API_KEY), or DEPUTY_API_KEY for other endpoints."""
        names = key_vars_for(self.base_url)
        return names[1] if len(names) > 1 else names[0]

    def describe(self) -> dict:
        """A summary that is safe to show: it never contains the key."""
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "endpoint": self.base_url,
            "thinking": f"{self.effort} (delegate, investigate), {self.lens_effort} (review, consult)",
            "api_key": f"set (from {self.key_source})" if self.api_key else "MISSING",
            "workspace": str(self.workspace),
            "max_turns": self.max_turns,
            "max_tokens_per_run": self.max_run_tokens,
            "per_lens_limit": f"{self.lens_timeout}s or {self.lens_max_output:,} output tokens",
        }


def read_mode(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    mode = (_get(env, "DEPUTY_MODE") or DEFAULT_MODE).lower()
    if mode not in MODES:
        raise ConfigError(f"DEPUTY_MODE must be one of {', '.join(MODES)}, got {mode!r}")
    return mode


def workspace_pinned(env: Mapping[str, str] | None = None) -> bool:
    """True when the user fixed the workspace explicitly with DEPUTY_WORKSPACE."""
    return bool(_get(os.environ if env is None else env, "DEPUTY_WORKSPACE"))


def _lead(env: Mapping[str, str]) -> tuple[str, float, float, float]:
    key = (_get(env, "DEPUTY_LEAD_MODEL") or DEFAULT_LEAD).lower()
    if key in LEAD_MODELS:
        name, p_in, p_cached, p_out = LEAD_MODELS[key]
    elif key == "custom":
        name, p_in, p_cached, p_out = "your lead model", 0.0, 0.0, 0.0
    else:
        raise ConfigError(f"DEPUTY_LEAD_MODEL must be one of {', '.join([*LEAD_MODELS, 'custom'])}")
    return (name, _float(env, "DEPUTY_LEAD_PRICE_INPUT", p_in),
            _float(env, "DEPUTY_LEAD_PRICE_CACHED", p_cached),
            _float(env, "DEPUTY_LEAD_PRICE_OUTPUT", p_out))


def _data_dir(env: Mapping[str, str]) -> Path:
    for name in ("DEPUTY_DATA_DIR", "CLAUDE_PLUGIN_DATA"):
        value = _get(env, name)
        if value:
            return Path(value).expanduser()
    return Path.home() / ".deputy"


def _workspace(env: Mapping[str, str], cwd: Path | None) -> Path:
    for name in ("DEPUTY_WORKSPACE", "CLAUDE_PROJECT_DIR"):
        value = _get(env, name)
        if value:
            return Path(value).expanduser().resolve()
    return (cwd or Path.cwd()).resolve()


def load_settings(env: Mapping[str, str] | None = None, cwd: Path | None = None) -> Settings:
    env = os.environ if env is None else env
    provider = (_get(env, "DEPUTY_PROVIDER") or DEFAULT_PROVIDER).lower()
    provider = PROVIDER_ALIASES.get(provider, provider)
    if provider not in PROVIDERS:
        raise ConfigError(f"DEPUTY_PROVIDER must be one of {', '.join([*PROVIDERS, *PROVIDER_ALIASES])}, "
                          f"got {provider!r}")
    _, preset_url, preset_model = PROVIDERS[provider]
    base_url = validate_base_url(_get(env, "DEPUTY_BASE_URL") or preset_url)
    model = _get(env, "DEPUTY_MODEL") or preset_model

    api_key, key_source = "", ""
    for name in key_vars_for(base_url):
        value = _get(env, name)
        if value:
            api_key, key_source = value, name
            break
    effort = (_get(env, "DEPUTY_THINKING") or DEFAULT_EFFORT).lower()
    if effort not in EFFORTS:
        raise ConfigError(f"DEPUTY_THINKING must be one of {', '.join(EFFORTS)}, got {effort!r}")
    lens_effort = (_get(env, "DEPUTY_LENS_THINKING") or DEFAULT_LENS_EFFORT).lower()
    if lens_effort not in EFFORTS:
        raise ConfigError(f"DEPUTY_LENS_THINKING must be one of {', '.join(EFFORTS)}, "
                          f"got {lens_effort!r}")
    mode = read_mode(env)
    lead_name, lead_in, lead_cached, lead_out = _lead(env)

    known = KNOWN_PRICES.get((base_url, model), (0.0, 0.0, 0.0))
    return Settings(
        api_key=api_key,
        key_source=key_source,
        base_url=base_url,
        model=model,
        effort=effort,
        mode=mode,
        workspace=_workspace(env, cwd),
        max_turns=_int(env, "DEPUTY_MAX_TURNS", 40, 1, 200),
        max_run_tokens=_int(env, "DEPUTY_MAX_RUN_TOKENS", 2_000_000, 10_000, 50_000_000),
        max_output_tokens=_int(env, "DEPUTY_MAX_OUTPUT_TOKENS", 16_384, 256, 65_536),
        run_timeout=_int(env, "DEPUTY_RUN_TIMEOUT", 1_800, 30, 86_400),
        command_timeout=_int(env, "DEPUTY_COMMAND_TIMEOUT", 180, 5, 3_600),
        keep_reasoning=_bool(env, "DEPUTY_KEEP_REASONING", True),
        price_input=_float(env, "DEPUTY_PRICE_INPUT", known[0]),
        price_cached=_float(env, "DEPUTY_PRICE_CACHED", known[1]),
        price_output=_float(env, "DEPUTY_PRICE_OUTPUT", known[2]),
        lead_name=lead_name,
        lead_price_input=lead_in,
        lead_price_cached=lead_cached,
        lead_price_output=lead_out,
        stats_enabled=_bool(env, "DEPUTY_STATS", True),
        data_dir=_data_dir(env),
        provider=provider,
        lens_timeout=_int(env, "DEPUTY_LENS_TIMEOUT", 300, 30, 86_400),
        lens_max_output=_int(env, "DEPUTY_LENS_MAX_OUTPUT_TOKENS", 32_000, 1_000, 2_000_000),
        lens_effort=lens_effort,
    )
