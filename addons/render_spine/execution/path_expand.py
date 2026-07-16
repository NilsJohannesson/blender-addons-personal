"""Expand job output-path templates using compiled overrides + scene state."""

from dataclasses import replace

from ..core.model import Override
from ..core.path_template import (
    PathTemplateError,
    alias_for_override_path,
    expand_path_template,
    token_value,
)

# Re-export for callers.
__all__ = (
    "PathTemplateError",
    "build_path_tokens",
    "expand_job_filepath",
    "resolved_job_overrides",
    "validate_output_filepath",
)


_FILEPATH_PATHS = frozenset(
    ("render.filepath", "scene.render.filepath")
)


def validate_output_filepath(path):
    """Reject Windows UNC typos that were meant as blend-relative // paths."""
    if not isinstance(path, str) or not path:
        return path
    # Actual string starts with \\ (logged as \\\\ in Blender info).
    if path.startswith("\\\\") and not path.startswith("\\\\?\\"):
        rest = path[2:].replace("/", "\\")
        parts = [part for part in rest.split("\\") if part]
        # \\server\share\... is real UNC. \\renders\file.png is almost always
        # a mistaken blend-relative path (wanted //renders/file.png).
        if len(parts) < 2 or (
            len(parts) == 2 and "." in parts[-1]
        ):
            raise PathTemplateError(
                "Output path {!r} looks like a Windows network (UNC) path. "
                "For a folder next to the .blend file use "
                "//renders/{{view_layer}}_{{camera}}_{{resolution}}.png "
                "(two forward slashes)."
                .format(path)
            )
    return path


def _override_path(override):
    return getattr(override, "path", None) or (
        override.get("path") if isinstance(override, dict) else None
    )


def _override_value(override):
    if isinstance(override, dict):
        return override.get("value", override.get("new_value"))
    return getattr(override, "value", None)


def _job_overrides(job):
    return tuple(getattr(job, "overrides", ()) or ())


def _job_name(job):
    value = getattr(job, "name", None)
    return str(value) if value not in (None, "") else "Render"


def _job_source_scene(job):
    value = getattr(job, "source_scene", "") or ""
    if not isinstance(value, str):
        value = getattr(value, "name", value)
    return str(value or "")


def _metadata_map(job):
    metadata = getattr(job, "metadata", ()) or ()
    if isinstance(metadata, dict):
        return dict(metadata)
    return {str(key): value for key, value in metadata}


def build_path_tokens(job, scene):
    """Build ``{token}`` values for a job against a concrete scene."""
    tokens = {
        "name": _job_name(job),
        "job": _job_name(job),
    }
    source = _job_source_scene(job)
    tokens["scene"] = source or (scene.name if scene is not None else "")

    overrides = {}
    for override in _job_overrides(job):
        path = _override_path(override)
        if not path:
            continue
        overrides[path] = _override_value(override)
        alias = alias_for_override_path(path)
        if alias and alias != "path":
            tokens[alias] = token_value(overrides[path])

    metadata = _metadata_map(job)
    if metadata.get("view_layer"):
        tokens["view_layer"] = token_value(metadata["view_layer"])

    if scene is not None:
        if "camera" not in tokens or not tokens["camera"]:
            camera = overrides.get("camera", scene.camera)
            tokens["camera"] = token_value(camera)
        if "world" not in tokens or not tokens["world"]:
            world = overrides.get("world", scene.world)
            tokens["world"] = token_value(world)
        if "view_layer" not in tokens:
            if scene.view_layers:
                active = getattr(scene.view_layers, "active", None)
                tokens["view_layer"] = (
                    active.name if active is not None else scene.view_layers[0].name
                )
            else:
                tokens["view_layer"] = ""
        if "engine" not in tokens:
            tokens["engine"] = scene.render.engine
        if "format" not in tokens:
            tokens["format"] = scene.render.image_settings.file_format
        if "width" not in tokens:
            tokens["width"] = token_value(scene.render.resolution_x)
        if "height" not in tokens:
            tokens["height"] = token_value(scene.render.resolution_y)
        if "percent" not in tokens:
            tokens["percent"] = token_value(scene.render.resolution_percentage)
        if "frame_start" not in tokens:
            tokens["frame_start"] = token_value(scene.frame_start)
        if "frame_end" not in tokens:
            tokens["frame_end"] = token_value(scene.frame_end)
        if "frame_step" not in tokens:
            tokens["frame_step"] = token_value(scene.frame_step)
        tokens["frame"] = token_value(scene.frame_current)

    width = tokens.get("width", "")
    height = tokens.get("height", "")
    if width != "" and height != "":
        tokens["resolution"] = "{}x{}".format(width, height)
    else:
        tokens.setdefault("resolution", "")

    # Always expose empty string defaults for common keys so templates validate.
    for key in (
        "camera",
        "world",
        "view_layer",
        "engine",
        "format",
        "width",
        "height",
        "percent",
        "frame_start",
        "frame_end",
        "frame_step",
        "frame",
        "samples",
        "cycles_viewport",
        "eevee_samples",
        "eevee_viewport",
        "view_transform",
        "look",
        "transparent",
        "motion_blur",
        "motion_blur_shutter",
        "simplify",
        "simplify_subdiv",
    ):
        tokens.setdefault(key, "")

    return tokens


def expand_job_filepath(template, job, scene):
    expanded = expand_path_template(template, build_path_tokens(job, scene))
    return validate_output_filepath(expanded)


def resolved_job_overrides(job, scene):
    """Return overrides with filepath templates expanded."""
    tokens = build_path_tokens(job, scene)
    resolved = []
    for override in _job_overrides(job):
        path = _override_path(override)
        value = _override_value(override)
        if path in _FILEPATH_PATHS and isinstance(value, str):
            if "{" in value:
                value = expand_path_template(value, tokens)
            value = validate_output_filepath(value)
            if isinstance(override, Override):
                resolved.append(replace(override, value=value))
                continue
            if isinstance(override, dict):
                item = dict(override)
                item["value"] = value
                resolved.append(item)
                continue
        resolved.append(override)
    return tuple(resolved)
