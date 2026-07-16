"""Reversible application of compiler-produced structured operations."""

import copy
import re

from .adapter import operation_kind, operation_value


_TOKEN = re.compile(
    r"""
    (?:
        ^|\.                           # attribute separator
    )
    (?P<attr>[A-Za-z_][A-Za-z0-9_]*)
    |
    \[
        (?:
            (?P<quote>["'])(?P<key>.*?)(?P=quote)
            |
            (?P<index>-?\d+)
        )
    \]
    """,
    re.VERBOSE,
)


class TransactionError(Exception):
    """Operation cannot be safely applied or restored."""


def _clone(value):
    if hasattr(value, "bl_rna"):
        return value
    copy_method = getattr(value, "copy", None)
    if callable(copy_method):
        try:
            return copy_method()
        except Exception:
            pass
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def _tokens(path):
    if not isinstance(path, str) or not path:
        raise TransactionError("Operation has no RNA path")
    result = []
    position = 0
    while position < len(path):
        match = _TOKEN.match(path, position)
        if not match:
            raise TransactionError(f"Unsafe or invalid RNA path: {path!r}")
        if match.group("attr") is not None:
            attribute = match.group("attr")
            if attribute.startswith("_"):
                raise TransactionError(f"Private RNA path is not allowed: {path!r}")
            result.append(("attr", attribute))
        elif match.group("index") is not None:
            result.append(("item", int(match.group("index"))))
        else:
            result.append(("item", match.group("key")))
        position = match.end()
    return result


def _read_member(owner, token):
    mode, key = token
    return getattr(owner, key) if mode == "attr" else owner[key]


def _write_member(owner, token, value):
    mode, key = token
    if mode == "attr":
        setattr(owner, key, value)
    else:
        owner[key] = value


def _delete_member(owner, token):
    mode, key = token
    if mode == "attr":
        delattr(owner, key)
    else:
        del owner[key]


def _leaf(target, path):
    tokens = _tokens(path)
    owner = target
    for token in tokens[:-1]:
        owner = _read_member(owner, token)
    return owner, tokens[-1]


def _data_collection(bpy_module, kind):
    key = str(kind).strip().lower().replace(" ", "_")
    aliases = {
        "object": "objects",
        "scene": "scenes",
        "world": "worlds",
        "collection": "collections",
        "material": "materials",
        "camera": "cameras",
        "image": "images",
        "text": "texts",
        "node_group": "node_groups",
        "view_layer": "scenes",
    }
    name = aliases.get(key, key)
    collection = getattr(bpy_module.data, name, None)
    if collection is None:
        raise TransactionError(f"Unsupported datablock type: {kind!r}")
    return collection


def resolve_target(operation, context, bpy_module):
    target = operation_value(operation, "target", default=None)
    if target is not None and not isinstance(target, (str, dict)):
        return target

    if isinstance(target, dict):
        kind = target.get("type") or target.get("id_type") or target.get("kind")
        name = target.get("name") or target.get("id") or target.get("target_name")
    else:
        kind = operation_value(
            operation,
            "target_type",
            "id_type",
            "datablock_type",
            default=None,
        )
        name = operation_value(
            operation,
            "target_name",
            "name",
            "id_name",
            default=None,
        )

    symbolic = target.lower() if isinstance(target, str) else ""
    if symbolic in ("", "scene") and not kind:
        return context.scene
    if symbolic == "active_object":
        if context.active_object is None:
            raise TransactionError("No active object")
        return context.active_object
    if symbolic == "world":
        if context.scene.world is None:
            raise TransactionError("Scene has no world")
        return context.scene.world
    if symbolic == "camera":
        if context.scene.camera is None:
            raise TransactionError("Scene has no camera")
        return context.scene.camera
    if symbolic == "view_layer":
        return context.view_layer

    if not kind and isinstance(target, str) and ":" in target:
        kind, name = target.split(":", 1)
    if not kind:
        raise TransactionError(f"Cannot resolve operation target: {target!r}")
    collection = _data_collection(bpy_module, kind)
    datablock = collection.get(name) if hasattr(collection, "get") else None
    if datablock is None:
        raise TransactionError(f"Datablock not found: {kind} {name!r}")
    return datablock


def _normalize_path(path, value, target, context, bpy_module):
    """Map compiler's stable paths to Blender RNA without executing code."""
    aliases = {
        "scene.camera": "camera",
        "scene.world": "world",
        "render.frame_start": "frame_start",
        "render.frame_end": "frame_end",
        "render.frame_step": "frame_step",
        "render.file_format": "render.image_settings.file_format",
        "eevee.samples": "eevee.taa_render_samples",
    }
    if path == "scene.view_layer":
        window = getattr(context, "window", None)
        if window is None:
            raise TransactionError("View-layer override requires a window")
        layer = context.scene.view_layers.get(str(value))
        if layer is None:
            raise TransactionError(f"View layer not found: {value!r}")
        return window, "view_layer", layer
    path = aliases.get(path, path)
    if path.startswith("scene."):
        path = path[len("scene.") :]
    if path == "camera" and isinstance(value, str):
        name = value
        value = bpy_module.data.objects.get(name) if name else None
        if name and value is None:
            raise TransactionError(f"Camera object not found: {name!r}")
    elif path == "world" and isinstance(value, str):
        name = value
        value = bpy_module.data.worlds.get(name) if name else None
        if name and value is None:
            raise TransactionError(f"World not found: {name!r}")
    return target, path, value


def _media_type_for_format(file_format):
    """Blender 5+ gates file_format by media_type."""
    if file_format == "OPEN_EXR_MULTILAYER":
        return "MULTI_LAYER_IMAGE"
    if file_format == "FFMPEG":
        return "VIDEO"
    return "IMAGE"


def _is_image_file_format_path(path):
    return path == "render.image_settings.file_format" or path.endswith(
        ".image_settings.file_format"
    )


class _Change:
    def __init__(self, owner, token, existed, old_value):
        self.owner = owner
        self.token = token
        self.existed = existed
        self.old_value = old_value

    def restore(self):
        if self.existed:
            _write_member(self.owner, self.token, self.old_value)
        else:
            _delete_member(self.owner, self.token)


class _ImageFileFormatChange:
    """Apply/restore file_format with matching media_type (Blender 5.2+)."""

    def __init__(self, image_settings, old_media_type, old_file_format):
        self.image_settings = image_settings
        self.old_media_type = old_media_type
        self.old_file_format = old_file_format

    def restore(self):
        if (
            self.old_media_type is not None
            and hasattr(self.image_settings, "media_type")
        ):
            self.image_settings.media_type = self.old_media_type
        self.image_settings.file_format = self.old_file_format


class _AnimationDataChange:
    def __init__(self, target, existed):
        self.target = target
        self.existed = existed

    def restore(self):
        if not self.existed and self.target.animation_data is not None:
            self.target.animation_data_clear()


class Transaction:
    """One reversible set of ordered RNA/datablock property changes."""

    def __init__(self, label="Render Nodes"):
        self.label = label
        self._changes = []
        self.active = False

    def apply(self, operations, context, bpy_module):
        if self.active:
            raise TransactionError("Transaction is already active")
        self.active = True
        try:
            for operation in operations:
                self._apply_one(operation, context, bpy_module)
        except Exception as exc:
            restore_error = self.restore()
            message = str(exc)
            if restore_error:
                message += f" (rollback failed: {restore_error})"
            if isinstance(exc, TransactionError):
                raise TransactionError(message) from exc
            raise TransactionError(f"Failed to apply override: {message}") from exc

    def _apply_one(self, operation, context, bpy_module):
        kind = operation_kind(operation)
        allowed = {
            "SET",
            "SET_ATTR",
            "SET_ATTRIBUTE",
            "SET_RNA",
            "SET_PROPERTY",
            "SET_ITEM",
            "DELETE",
            "DELETE_ITEM",
            "UNSET",
        }
        if kind not in allowed:
            raise TransactionError(f"Unsupported safe operation: {kind}")

        target = resolve_target(operation, context, bpy_module)
        path = operation_value(
            operation,
            "path",
            "rna_path",
            "data_path",
            "attribute",
            "key",
            default=None,
        )
        raw_value = operation_value(
            operation, "value", "new_value", default=None
        )
        target, path, raw_value = _normalize_path(
            path, raw_value, target, context, bpy_module
        )
        if path == "animation_data.action" and hasattr(
            target, "animation_data_create"
        ):
            animation_data_existed = target.animation_data is not None
            target.animation_data_create()
            self._changes.append(
                _AnimationDataChange(target, animation_data_existed)
            )
        if (
            kind not in {"DELETE", "DELETE_ITEM", "UNSET"}
            and _is_image_file_format_path(path)
        ):
            self._apply_image_file_format(target, path, raw_value)
            return
        owner, token = _leaf(target, path)
        try:
            old_value = _read_member(owner, token)
            existed = True
        except (AttributeError, KeyError, IndexError):
            old_value = None
            existed = False
        self._changes.append(_Change(owner, token, existed, _clone(old_value)))

        if kind in {"DELETE", "DELETE_ITEM", "UNSET"}:
            if not existed:
                raise TransactionError(f"Cannot delete missing property: {path}")
            _delete_member(owner, token)
            return
        _write_member(owner, token, raw_value)

    def _apply_image_file_format(self, target, path, file_format):
        owner, token = _leaf(target, path)
        old_file_format = _read_member(owner, token)
        old_media_type = getattr(owner, "media_type", None)
        self._changes.append(
            _ImageFileFormatChange(owner, old_media_type, _clone(old_file_format))
        )
        required_media = _media_type_for_format(file_format)
        if old_media_type is not None and old_media_type != required_media:
            owner.media_type = required_media
        _write_member(owner, token, file_format)

    def restore(self):
        errors = []
        for change in reversed(self._changes):
            try:
                change.restore()
            except Exception as exc:
                errors.append(str(exc))
        self._changes.clear()
        self.active = False
        return "; ".join(errors)

    @property
    def change_count(self):
        return len(self._changes)
