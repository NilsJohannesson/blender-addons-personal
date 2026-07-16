"""Safe output-path token expansion. No eval/exec."""

import re


_TOKEN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
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
}


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
        return str(value)
    return str(value)


def sanitize_token_value(value):
    """Make a substituted value safe to embed in a filename segment."""
    text = token_value(value).strip().replace("\\", "_").replace("/", "_")
    return _UNSAFE.sub("_", text)


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


def expand_path_template(template, tokens):
    """Replace ``{token}`` placeholders. Unknown tokens raise PathTemplateError."""
    if not isinstance(template, str) or "{" not in template:
        return template

    available = sorted(tokens)

    def replacer(match):
        key = match.group(1)
        if key not in tokens:
            raise PathTemplateError(
                "Unknown path token {{{}}}. Available: {}".format(
                    key, ", ".join(available) if available else "(none)"
                )
            )
        return sanitize_token_value(tokens[key])

    return _TOKEN.sub(replacer, template)


def find_path_tokens(template):
    if not isinstance(template, str):
        return ()
    return tuple(dict.fromkeys(_TOKEN.findall(template)))
