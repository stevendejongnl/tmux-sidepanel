"""Configuration: defaults, parsing, validation and loading.

The file is TOML. Unknown keys are errors, so a typo does not pass silently, and every error
names the key it is about, for example ``sections[1].rules[0].pattern``.
"""

import os
import re
import stat
import string
import tomllib
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any

from tmux_sidepanel.services import DEFAULT_RULES, Rule, RuleError, compile_rule, strip_shims

MAXIMUM_FILE_BYTES = 64 * 1024
RESERVED_MENU_KEYS = frozenset("jkqh")  # move up, move down, quit, close the menu
DEFAULT_SECTION_TYPES = ("panes", "subagents", "services", "other-services", "zombies")
CONFIGURATION_FILE_NAMES = ("configuration.toml", "config.toml")

SECTION_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
PLACEHOLDER_NAME_PATTERN = re.compile(r"^[a-z_]+$")
CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class ConfigurationError(ValueError):
    """The configuration is not valid. The message names the key and says what is wrong."""


@dataclass(frozen=True)
class Panel:
    width: int = 30
    refresh_seconds: float = 0.5
    position: str = "left"
    open_with_agent: bool = True


@dataclass(frozen=True)
class AgentSettings:
    names: tuple[str, ...] = ("claude",)
    ignored_arguments: tuple[str, ...] = ("--chrome-native-host",)


@dataclass(frozen=True)
class Menu:
    disabled_actions: frozenset[str]
    keys: dict[str, str]  # every action of the section, with its key


@dataclass(frozen=True)
class Section:
    section_type: str
    identifier: str
    title: str
    enabled: bool
    hide_when_empty: bool
    empty_text: str
    row_format: str
    menu: Menu
    options: dict[str, Any]


@dataclass(frozen=True)
class Configuration:
    panel: Panel
    agents: AgentSettings
    sections: tuple[Section, ...]


@dataclass(frozen=True)
class SectionSpecification:
    title: str
    row_format: str
    actions: dict[str, str]  # action name -> default key
    placeholders: tuple[str, ...]  # names a row format may use


@dataclass(frozen=True)
class Placeholder:
    literal_text: str
    name: str | None
    format_specification: str | None
    conversion: str | None


SERVICE_PLACEHOLDERS = ("letter", "kind", "command", "age", "mark")

SECTION_SPECIFICATIONS = {
    "panes": SectionSpecification(
        "PANES",
        "{mark} {label}",
        {"go": "g", "zoom": "z", "interrupt": "x", "directory": "o", "close": "X"},
        ("mark", "label", "directory", "command", "state"),
    ),
    "subagents": SectionSpecification(
        "AGENTS",
        "{mark} {label}",
        {"go": "g", "tasks": "t"},
        ("mark", "label", "kind", "identifier"),
    ),
    "services": SectionSpecification(
        "SERVICES",
        "{letter} {command} {age}",
        {"go": "g", "stop": "x", "restart": "r", "logs": "l", "directory": "o", "kill": "X"},
        SERVICE_PLACEHOLDERS,
    ),
    "other-services": SectionSpecification(
        "OTHER SERVICES",
        "{letter} {command} {age}",
        {"stop": "x", "restart": "r", "logs": "l", "directory": "o", "kill": "X"},
        SERVICE_PLACEHOLDERS,
    ),
    "zombies": SectionSpecification(
        "ZOMBIES",
        "Z {name} {process_identifier} {reason} {age}",
        {"open": "o", "terminate": "x", "directory": "d", "kill": "X"},
        ("name", "process_identifier", "reason", "age", "directory"),
    ),
    "custom": SectionSpecification("", "{text}", {}, ("text",)),
}

COMMON_SECTION_KEYS = (
    "type",
    "identifier",
    "title",
    "enabled",
    "hide_when_empty",
    "empty_text",
    "row_format",
    "menu",
)
EXTRA_SECTION_KEYS = {
    "services": ("rules", "shims", "letters"),
    "custom": ("command", "timeout_seconds"),
}
KEYS_OF_OTHER_SECTION_TYPES = frozenset(chain.from_iterable(EXTRA_SECTION_KEYS.values()))


# ---- small checks -------------------------------------------------------------------------


def require(condition: bool, key_path: str, message: str) -> None:
    if not condition:
        raise ConfigurationError(f"{key_path}: {message}")


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_plain_text(value: Any, maximum_length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= maximum_length
        and not CONTROL_CHARACTER_PATTERN.search(value)
    )


def is_printable_character(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 1 and 33 <= ord(value) <= 126


def as_table(value: Any, key_path: str) -> dict[str, Any]:
    require(isinstance(value, dict), key_path, "must be a table")
    return value


def require_known_keys(table: dict[str, Any], allowed_keys: tuple[str, ...], key_path: str) -> None:
    unknown = sorted(set(table) - set(allowed_keys))
    allowed_text = ", ".join(sorted(allowed_keys))
    require(not unknown, key_path, f"unknown key {', '.join(unknown)} (allowed: {allowed_text})")


def validated_text(value: Any, key_path: str, maximum_length: int) -> str:
    description = f"text of at most {maximum_length} characters"
    require(is_plain_text(value, maximum_length), key_path, f"must be {description}")
    return value


def validated_boolean(value: Any, key_path: str) -> bool:
    require(isinstance(value, bool), key_path, "must be true or false")
    return value


def validated_text_list(value: Any, key_path: str, allow_empty: bool) -> tuple[str, ...]:
    suffix = "" if allow_empty else " with at least one item"
    description = f"a list of non-empty text{suffix}"
    require(isinstance(value, list | tuple), key_path, f"must be {description}")
    require(allow_empty or bool(value), key_path, f"must be {description}")
    all_text = all(isinstance(item, str) and item for item in value)
    require(all_text, key_path, f"must be {description}")
    return tuple(value)


# ---- panel and agents ---------------------------------------------------------------------


def validated_panel_width(value: Any, key_path: str) -> int:
    is_valid = is_integer(value) and 10 <= value <= 120
    require(is_valid, key_path, "must be an integer from 10 to 120")
    return value


def validated_panel_refresh(value: Any, key_path: str) -> float:
    is_valid = is_number(value) and 0.1 <= value <= 60
    require(is_valid, key_path, "must be a number of seconds from 0.1 to 60")
    return float(value)


def validated_panel_position(value: Any, key_path: str) -> str:
    require(value in ("left", "right"), key_path, 'must be "left" or "right"')
    return value


def parse_panel(data: Any) -> Panel:
    table = as_table(data, "panel")
    keys = ("width", "refresh_seconds", "position", "open_with_agent")
    require_known_keys(table, keys, "panel")
    default = Panel()
    return Panel(
        validated_panel_width(table.get("width", default.width), "panel.width"),
        validated_panel_refresh(
            table.get("refresh_seconds", default.refresh_seconds), "panel.refresh_seconds"
        ),
        validated_panel_position(table.get("position", default.position), "panel.position"),
        validated_boolean(
            table.get("open_with_agent", default.open_with_agent), "panel.open_with_agent"
        ),
    )


def parse_agent_settings(data: Any) -> AgentSettings:
    table = as_table(data, "agents")
    require_known_keys(table, ("names", "ignored_arguments"), "agents")
    default = AgentSettings()
    return AgentSettings(
        validated_text_list(table.get("names", default.names), "agents.names", allow_empty=False),
        validated_text_list(
            table.get("ignored_arguments", default.ignored_arguments),
            "agents.ignored_arguments",
            allow_empty=True,
        ),
    )


# ---- row format ---------------------------------------------------------------------------


def formatter_parts(text: str) -> list[Any]:
    return list(string.Formatter().parse(text))


def split_format_placeholders(text: str, key_path: str) -> list[Placeholder]:
    try:
        parts = formatter_parts(text)
    except ValueError as error:
        raise ConfigurationError(f"{key_path}: invalid format string ({error})") from error
    return [Placeholder(*part) for part in parts]


def require_valid_placeholder(
    placeholder: Placeholder, specification: SectionSpecification, key_path: str
) -> None:
    if placeholder.name is None:
        return
    is_plain = not placeholder.format_specification and not placeholder.conversion
    require(is_plain, key_path, "only plain {name} placeholders are allowed")
    is_name = bool(PLACEHOLDER_NAME_PATTERN.match(placeholder.name))
    require(is_name, key_path, f"{placeholder.name!r} is not a plain placeholder name")
    allowed = ", ".join(specification.placeholders)
    is_known = placeholder.name in specification.placeholders
    require(is_known, key_path, f"unknown placeholder {placeholder.name!r} (allowed: {allowed})")


def validated_row_format(text: Any, specification: SectionSpecification, key_path: str) -> str:
    require(is_plain_text(text, 200), key_path, "must be text of at most 200 characters")
    for placeholder in split_format_placeholders(text, key_path):
        require_valid_placeholder(placeholder, specification, key_path)
    return text


# ---- menu ---------------------------------------------------------------------------------


def validated_menu_key(value: Any, key_path: str) -> str:
    reserved = ", ".join(sorted(RESERVED_MENU_KEYS))
    is_valid = is_printable_character(value) and value not in RESERVED_MENU_KEYS
    require(is_valid, key_path, f"must be one printable character, not one of {reserved}")
    return value


def allowed_actions_text(specification: SectionSpecification) -> str:
    return ", ".join(specification.actions) or "none"


def require_known_actions(
    action_names: tuple[str, ...], specification: SectionSpecification, key_path: str
) -> None:
    unknown = sorted(set(action_names) - set(specification.actions))
    allowed = allowed_actions_text(specification)
    require(not unknown, key_path, f"unknown action {', '.join(unknown)} (allowed: {allowed})")


def require_known_action(
    action_name: str, specification: SectionSpecification, key_path: str
) -> None:
    allowed = allowed_actions_text(specification)
    is_known = action_name in specification.actions
    require(is_known, f"{key_path}.{action_name}", f"unknown action (allowed: {allowed})")


def read_key_overrides(
    data: Any, specification: SectionSpecification, key_path: str
) -> dict[str, str]:
    table = as_table(data, key_path)
    for action_name in table:
        require_known_action(action_name, specification, key_path)
    return {name: validated_menu_key(key, f"{key_path}.{name}") for name, key in table.items()}


def claim_menu_key(
    key_owners: dict[str, str],
    action_name: str,
    key: str,
    disabled_actions: tuple[str, ...],
    key_path: str,
) -> None:
    if action_name in disabled_actions:
        return
    owner = key_owners.get(key)
    require(owner is None, f"{key_path}.{action_name}", f"key {key!r} is already used by {owner!r}")
    key_owners[key] = action_name


def require_unique_keys(
    keys: dict[str, str], disabled_actions: tuple[str, ...], key_path: str
) -> None:
    key_owners: dict[str, str] = {}
    for action_name, key in keys.items():
        claim_menu_key(key_owners, action_name, key, disabled_actions, key_path)


def parse_menu(data: Any, specification: SectionSpecification, key_path: str) -> Menu:
    table = as_table(data, key_path)
    require_known_keys(table, ("disabled_actions", "keys"), key_path)
    disabled_path = f"{key_path}.disabled_actions"
    disabled_actions = validated_text_list(table.get("disabled_actions", []), disabled_path, True)
    require_known_actions(disabled_actions, specification, disabled_path)
    overrides = read_key_overrides(table.get("keys", {}), specification, f"{key_path}.keys")
    keys = {**specification.actions, **overrides}
    require_unique_keys(keys, disabled_actions, f"{key_path}.keys")
    return Menu(frozenset(disabled_actions), keys)


# ---- section options: services and custom -------------------------------------------------


def compile_service_rule(kind: str, pattern: str, key_path: str) -> Rule:
    try:
        return compile_rule(kind, pattern)
    except RuleError as error:
        raise ConfigurationError(f"{key_path}: {error}") from error


def parse_service_rule(item: Any, key_path: str) -> Rule:
    entry = as_table(item, key_path)
    require_known_keys(entry, ("kind", "pattern"), key_path)
    require("kind" in entry and "pattern" in entry, key_path, "'kind' and 'pattern' are required")
    require(isinstance(entry["kind"], str), key_path, "kind must be text")
    require(isinstance(entry["pattern"], str), key_path, "pattern must be text")
    return compile_service_rule(entry["kind"], entry["pattern"], key_path)


def parse_service_rules(data: Any, key_path: str) -> tuple[Rule, ...]:
    require(isinstance(data, list), f"{key_path}.rules", "must be a list of tables")
    return tuple(
        parse_service_rule(item, f"{key_path}.rules[{index}]") for index, item in enumerate(data)
    )


def service_rules(table: dict[str, Any], key_path: str) -> tuple[Rule, ...]:
    has_rules = "rules" in table
    return parse_service_rules(table["rules"], key_path) if has_rules else DEFAULT_RULES


def require_valid_shim(pattern: str, key_path: str) -> None:
    try:
        strip_shims("", [pattern])
    except RuleError as error:
        raise ConfigurationError(f"{key_path}: {error}") from error


def parse_shims(data: Any, key_path: str) -> tuple[str, ...]:
    shims = validated_text_list(data, key_path, allow_empty=True)
    for index, pattern in enumerate(shims):
        require_valid_shim(pattern, f"{key_path}[{index}]")
    return shims


def validated_letter(value: Any, key_path: str) -> str:
    require(is_printable_character(value), key_path, "must be one printable character")
    return value


def parse_letters(data: Any, key_path: str) -> dict[str, str]:
    table = as_table(data, key_path)
    return {kind: validated_letter(letter, f"{key_path}.{kind}") for kind, letter in table.items()}


def first_letters(rules: tuple[Rule, ...]) -> dict[str, str]:
    return {rule.kind: rule.kind[0].upper() for rule in rules}


def parse_services_options(table: dict[str, Any], key_path: str) -> dict[str, Any]:
    rules = service_rules(table, key_path)
    explicit_letters = parse_letters(table.get("letters", {}), f"{key_path}.letters")
    shims = parse_shims(table.get("shims", []), f"{key_path}.shims")
    return {"rules": rules, "shims": shims, "letters": {**first_letters(rules), **explicit_letters}}


def parse_custom_options(table: dict[str, Any], key_path: str) -> dict[str, Any]:
    require("command" in table, f"{key_path}.command", "is required for custom sections")
    command = validated_text_list(table["command"], f"{key_path}.command", allow_empty=False)
    timeout_seconds = table.get("timeout_seconds", 2)
    is_valid = is_number(timeout_seconds) and 0.1 <= timeout_seconds <= 30
    require(is_valid, f"{key_path}.timeout_seconds", "must be a number of seconds from 0.1 to 30")
    return {"command": command, "timeout_seconds": float(timeout_seconds)}


def no_options(table: dict[str, Any], key_path: str) -> dict[str, Any]:
    return {}


OPTION_PARSERS = {"services": parse_services_options, "custom": parse_custom_options}


# ---- sections -----------------------------------------------------------------------------


def read_section_type(table: dict[str, Any], key_path: str) -> str:
    section_type = table.get("type")
    is_valid = isinstance(section_type, str) and section_type in SECTION_SPECIFICATIONS
    allowed = ", ".join(SECTION_SPECIFICATIONS)
    require(is_valid, f"{key_path}.type", f"must be one of {allowed}")
    return section_type


def require_valid_section_keys(table: dict[str, Any], section_type: str, key_path: str) -> None:
    allowed_keys = COMMON_SECTION_KEYS + EXTRA_SECTION_KEYS.get(section_type, ())
    unknown = set(table) - set(allowed_keys)
    misplaced = sorted(unknown & KEYS_OF_OTHER_SECTION_TYPES)
    message = f"key {', '.join(misplaced)} is not valid for type {section_type!r}"
    require(not misplaced, key_path, message)
    require_known_keys(table, allowed_keys, key_path)


def validated_section_identifier(
    table: dict[str, Any], section_type: str, seen_identifiers: set[str], key_path: str
) -> str:
    identifier_path = f"{key_path}.identifier"
    has_identifier = "identifier" in table or section_type != "custom"
    require(has_identifier, identifier_path, "is required for custom sections")
    identifier = table.get("identifier", section_type)
    shape = "lowercase letters, digits, - or _, starting with a letter, at most 32 characters"
    is_valid = isinstance(identifier, str) and bool(SECTION_IDENTIFIER_PATTERN.match(identifier))
    require(is_valid, identifier_path, f"must be {shape}")
    is_new = identifier not in seen_identifiers
    require(is_new, identifier_path, f"duplicate identifier {identifier!r}")
    seen_identifiers.add(identifier)
    return identifier


def parse_section(data: Any, index: int, seen_identifiers: set[str]) -> Section:
    key_path = f"sections[{index}]"
    table = as_table(data, key_path)
    section_type = read_section_type(table, key_path)
    specification = SECTION_SPECIFICATIONS[section_type]
    require_valid_section_keys(table, section_type, key_path)
    identifier = validated_section_identifier(table, section_type, seen_identifiers, key_path)
    default_title = specification.title or identifier.upper()
    row_format = table.get("row_format", specification.row_format)
    return Section(
        section_type,
        identifier,
        validated_text(table.get("title", default_title), f"{key_path}.title", 40),
        validated_boolean(table.get("enabled", True), f"{key_path}.enabled"),
        validated_boolean(table.get("hide_when_empty", False), f"{key_path}.hide_when_empty"),
        validated_text(table.get("empty_text", "none"), f"{key_path}.empty_text", 60),
        validated_row_format(row_format, specification, f"{key_path}.row_format"),
        parse_menu(table.get("menu", {}), specification, f"{key_path}.menu"),
        OPTION_PARSERS.get(section_type, no_options)(table, key_path),
    )


def default_section_tables() -> list[dict[str, str]]:
    return [{"type": name} for name in DEFAULT_SECTION_TYPES]


def parse_sections(data: Any) -> tuple[Section, ...]:
    tables = default_section_tables() if data is None else data
    require(isinstance(tables, list), "sections", "must be a list of tables, [[sections]]")
    seen_identifiers: set[str] = set()
    return tuple(parse_section(item, index, seen_identifiers) for index, item in enumerate(tables))


# ---- parsing ------------------------------------------------------------------------------


def load_toml_text(text: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(str(error)) from error


def parse_configuration(text: str) -> Configuration:
    """Parse and validate configuration text. Empty text gives the defaults."""
    data = load_toml_text(text)
    require_known_keys(data, ("panel", "agents", "sections"), "configuration")
    return Configuration(
        parse_panel(data.get("panel", {})),
        parse_agent_settings(data.get("agents", {})),
        parse_sections(data.get("sections")),
    )


def default_configuration() -> Configuration:
    return parse_configuration("")


# ---- locating and loading the file --------------------------------------------------------


def configuration_home(environment: dict[str, str]) -> str:
    """The folder named by XDG_CONFIG_HOME, or an empty string when it is unset or relative."""
    folder = environment.get("XDG_CONFIG_HOME", "")
    return folder if os.path.isabs(folder) else ""


def configuration_folder(environment: dict[str, str] | None = None) -> Path:
    """The folder of the configuration file: $XDG_CONFIG_HOME/tmux-sidepanel, or ~/.config/..."""
    environment = os.environ if environment is None else environment
    home_folder = configuration_home(environment)
    if home_folder:
        return Path(home_folder) / "tmux-sidepanel"
    home = environment.get("HOME", "")
    require(bool(home), "configuration", "cannot find the configuration folder: HOME is not set")
    return Path(home) / ".config" / "tmux-sidepanel"


def configuration_path(environment: dict[str, str] | None = None) -> Path:
    """The preferred path of the configuration file."""
    return configuration_folder(environment) / CONFIGURATION_FILE_NAMES[0]


def existing_configuration_files(folder: Path) -> list[Path]:
    candidates = [folder / name for name in CONFIGURATION_FILE_NAMES]
    return list(filter(Path.exists, candidates))


def find_configuration_path(environment: dict[str, str] | None = None) -> Path:
    """The configuration file to read: configuration.toml, or else config.toml if it exists."""
    folder = configuration_folder(environment)
    existing = existing_configuration_files(folder)
    return existing[0] if existing else folder / CONFIGURATION_FILE_NAMES[0]


def read_file_status(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ConfigurationError(f"{path}: {error.strerror}") from error


def require_safe_file(path: Path, file_status: os.stat_result) -> None:
    location = str(path)
    require(stat.S_ISREG(file_status.st_mode), location, "not a file")
    require(file_status.st_uid == os.geteuid(), location, "not owned by you")
    is_writable_by_others = bool(file_status.st_mode & 0o022)
    advice = "writable by the group or others, run chmod go-w on it"
    require(not is_writable_by_others, location, advice)
    is_small_enough = file_status.st_size <= MAXIMUM_FILE_BYTES
    require(is_small_enough, location, f"too large (the limit is {MAXIMUM_FILE_BYTES} bytes)")


def read_configuration_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ConfigurationError(f"{path}: cannot read the file ({error})") from error


def parse_configuration_file(path: Path, text: str) -> Configuration:
    try:
        return parse_configuration(text)
    except ConfigurationError as error:
        raise ConfigurationError(f"{path}: {error}") from error


def load_configuration(path: Path) -> Configuration:
    """Read the configuration file. A missing file gives the defaults.

    Custom sections run commands from this file, so a file that someone else owns or can
    write to is refused.
    """
    path = Path(path)
    file_status = read_file_status(path)
    if file_status is None:
        return default_configuration()
    require_safe_file(path, file_status)
    return parse_configuration_file(path, read_configuration_text(path))
