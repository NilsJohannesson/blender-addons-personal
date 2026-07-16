"""Safe output-path token expansion. No eval/exec.

Supports RenderSpine ``{token}`` forms and upstream RenderNode ``$token`` forms
(e.g. ``$V``, ``$res``, ``$camera``, ``$F4``, ``$T{%m-%d}``).
"""

import re
import time


_BRACE_TOKEN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_DOLLAR_TIME = re.compile(r"\$T\{([^}]*)\}")
_DOLLAR_FRAME = re.compile(r"\$F(\d)")
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Short names for common override RNA paths.
PATH_TOKEN_ALIASES = {
    "camera": "camera",
    "world": "world",
    "render.engine": "engine",
    "render.filepath": "path",
    "render.image_settings.file_format": "format",
    "render.resolution_x": "width",
    "render.resolution_y": "height",
    "render.resolution_percentage": "percent",
    "frame_start": "frame_start",
    "frame_end": "frame_end",
    "frame_step": "frame_step",
    "cycles.samples": "samples",
    "cycles.preview_samples": "cycles_viewport",
    "eevee.taa_render_samples": "eevee_samples",
    "eevee.taa_samples": "eevee_viewport",
    "render.film_transparent": "transparent",
    "render.use_motion_blur": "motion_blur",
    "render.motion_blur_shutter": "motion_blur_shutter",
    "view_settings.view_transform": "view_transform",
    "view_settings.look": "look",
    "render.use_simplify": "simplify",
    "render.simplify_subdivision_render": "simplify_subdiv",
    "data.energy": "intensity",
    "data.color": "color",
    "data.spread": "spread",
    "data.size": "size",
}

# Upstream RenderNode $names → token dict keys (longest first for scanning).
_DOLLAR_NAMES = (
    ("view_layer", "view_layer"),
    ("resolution", "resolution"),
    ("version", "version"),
    ("camera", "camera"),
    ("engine", "engine"),
    ("label", "name"),
    ("blend", "blend"),
    ("scene", "scene"),
    ("frame", "frame"),
    ("width", "width"),
    ("height", "height"),
    ("name", "name"),
    ("task", "name"),
    ("job", "name"),
    ("res", "resolution"),
    ("vl", "view_layer"),
    ("collection", "collection"),
    ("col", "collection"),
    ("ev", "ev"),
    ("V", "version"),
)

# Display names for the Output Path insert menu.
PATH_TOKEN_MENU = (
    ("File Name", "$blend"),
    ("Version", "$V"),
    ("Task Label", "$label"),
    ("Render Engine", "$engine"),
    ("Camera Name", "$camera"),
    ("Resolution XxY", "$res"),
    ("View Layer", "$vl"),
    ("Frame 4 digits", "$F4"),
    ("Date month-day", "$T{%m-%d}"),
    ("Time Hour-Minute", "$T{%H-%M}"),
    ("Folder separator", "/"),
    ("Brace: camera", "{camera}"),
    ("Brace: resolution", "{resolution}"),
    ("Brace: collection", "{collection}"),
    ("Brace: variant_index", "{variant_index}"),
)


class PathTemplateError(ValueError):
    """Unknown or invalid path template token."""


def token_value(value):
    if value is None:
        return ""
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return "{:g}".format(value)
    if isinstance(value, (tuple, list)):
        return "x".join(token_value(item) for item in value)
    return str(value)


def sanitize_token_value(value):
    """Make a substituted value safe to embed in a filename segment."""
    text = token_value(value).strip().replace("\\", "_").replace("/", "_")
    return _UNSAFE.sub("_", text)


# Named anchors for path {color}: RGB/CMY corners + literal in-between pairs.
_COLOR_ANCHORS = (
    ("red", (1.0, 0.0, 0.0)),
    ("red-yellow", (1.0, 0.5, 0.0)),
    ("yellow", (1.0, 1.0, 0.0)),
    ("green-yellow", (0.5, 1.0, 0.0)),
    ("green", (0.0, 1.0, 0.0)),
    ("green-cyan", (0.0, 1.0, 0.5)),
    ("cyan", (0.0, 1.0, 1.0)),
    ("blue-cyan", (0.0, 0.5, 1.0)),
    ("blue", (0.0, 0.0, 1.0)),
    ("blue-red", (0.5, 0.0, 1.0)),
    ("magenta", (1.0, 0.0, 1.0)),
    ("red-magenta", (1.0, 0.0, 0.5)),
    ("white", (1.0, 1.0, 1.0)),
    ("black", (0.0, 0.0, 0.0)),
)


def _as_rgb_triplet(value):
    """Parse RGB from a 3+ vector or an ``r x g x b`` token string."""
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return None
    if isinstance(value, str) and "x" in value:
        parts = value.split("x")
        if len(parts) >= 3:
            try:
                return (float(parts[0]), float(parts[1]), float(parts[2]))
            except ValueError:
                return None
    return None


def format_color_token(value):
    """Map an RGB color to the nearest named anchor for paths."""
    rgb = _as_rgb_triplet(value)
    if rgb is None:
        return sanitize_token_value(value)
    best_name = "black"
    best_dist = None
    for name, ref in _COLOR_ANCHORS:
        dist = (
            (rgb[0] - ref[0]) ** 2
            + (rgb[1] - ref[1]) ** 2
            + (rgb[2] - ref[2]) ** 2
        )
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def coerce_to_string(value, sanitize=True):
    """String socket coercion. Existing strings pass through unchanged."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if sanitize:
        return sanitize_token_value(value)
    return token_value(value)


def alias_for_override_path(path):
    if path in PATH_TOKEN_ALIASES:
        return PATH_TOKEN_ALIASES[path]
    if path.startswith('view_layers["') and path.endswith('"].use'):
        return None
    cleaned = path.replace(".", "_").replace('"', "").replace("[", "_").replace("]", "")
    cleaned = re.sub(r"_+", "_", cleaned).strip("_").lower()
    return cleaned or None


def format_version_token(value):
    """Zero-pad version to 3 digits (1 → 001). Non-numeric values sanitize as-is."""
    try:
        return "{:03d}".format(int(float(token_value(value))))
    except (TypeError, ValueError):
        return sanitize_token_value(value)


def _require_token(tokens, key):
    if key not in tokens:
        available = sorted(tokens)
        raise PathTemplateError(
            "Unknown path token {!r}. Available: {}".format(
                key, ", ".join(available) if available else "(none)"
            )
        )
    if key == "version":
        return format_version_token(tokens[key])
    if key == "color":
        return format_color_token(tokens[key])
    return sanitize_token_value(tokens[key])


def expand_path_template(template, tokens):
    """Replace ``{token}`` placeholders. Unknown tokens raise PathTemplateError."""
    if not isinstance(template, str) or "{" not in template:
        return template

    def replacer(match):
        return _require_token(tokens, match.group(1))

    return _BRACE_TOKEN.sub(replacer, template)


def expand_path_expression(template, tokens, hash_frames=False):
    """Expand ``$token`` / ``$F4`` / ``$T{...}`` and ``{token}`` forms."""
    if not isinstance(template, str):
        return template
    if "$" not in template and "{" not in template:
        return template

    text = template

    def replace_time(match):
        fmt = match.group(1)
        try:
            return time.strftime(fmt, time.localtime())
        except (TypeError, ValueError) as exc:
            raise PathTemplateError(
                "Invalid time format $T{{{}}}: {}".format(fmt, exc)
            ) from exc

    text = _DOLLAR_TIME.sub(replace_time, text)

    def replace_frame(match):
        width = int(match.group(1))
        if hash_frames:
            return "#" * width
        raw = tokens.get("frame", "0")
        try:
            frame = int(float(token_value(raw)))
        except (TypeError, ValueError):
            frame = 0
        return "{:0{width}d}".format(frame, width=width)

    text = _DOLLAR_FRAME.sub(replace_frame, text)

    # Longest-first scan for $names so $view_layer beats $vl ambiguity, etc.
    index = 0
    pieces = []
    length = len(text)
    while index < length:
        if text[index] != "$":
            pieces.append(text[index])
            index += 1
            continue
        matched = None
        for dollar_name, token_key in _DOLLAR_NAMES:
            token = "$" + dollar_name
            if text.startswith(token, index):
                # Prefer longer matches; list is longest-first.
                matched = (token, token_key)
                break
        if matched is None:
            raise PathTemplateError(
                "Unknown path token starting at {!r}".format(text[index : index + 8])
            )
        token, token_key = matched
        pieces.append(_require_token(tokens, token_key))
        index += len(token)
    text = "".join(pieces)

    return expand_path_template(text, tokens)


def find_path_tokens(template):
    if not isinstance(template, str):
        return ()
    found = list(_BRACE_TOKEN.findall(template))
    found.extend(_DOLLAR_FRAME.findall(template))
    for dollar_name, _key in _DOLLAR_NAMES:
        needle = "$" + dollar_name
        if needle in template:
            found.append(dollar_name)
    return tuple(dict.fromkeys(found))


# Back-compat alias used by older call sites.
expand_path_template_legacy = expand_path_template
