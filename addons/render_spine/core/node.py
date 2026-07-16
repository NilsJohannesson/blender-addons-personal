"""Reusable node contracts. Blender-facing but compilation remains read-only."""

import bpy

from .model import JobSpec


def apply_engine_samples(values, engine, samples):
    """Map one Samples value onto the selected engine's render samples."""
    if engine == "BLENDER_EEVEE":
        values["eevee.taa_render_samples"] = samples
    elif engine == "CYCLES":
        values["cycles.samples"] = samples
    else:
        values["cycles.samples"] = samples
        values["eevee.taa_render_samples"] = samples


class RSP_NodeBase:
    """Common behavior for every render graph node."""

    @classmethod
    def poll(cls, node_tree):
        return node_tree.bl_idname == "RenderSpineNodeTree"

    def init(self, context):
        for socket_type, name in getattr(self, "rsp_inputs", ()):
            self.inputs.new(socket_type, name)
        for socket_type, name in getattr(self, "rsp_outputs", ()):
            self.outputs.new(socket_type, name)


class RSP_ValueNodeBase(RSP_NodeBase):
    rsp_inputs = ()

    def rsp_compile(self, context, socket):
        return getattr(self, "value", None)


class RSP_JobTransformNodeBase(RSP_NodeBase):
    rsp_inputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = ()

    def rsp_compile(self, context, socket):
        job = context.input(self, "Job", required=True)
        if not isinstance(job, JobSpec):
            raise TypeError("Job input requires JobSpec")
        values = {}
        for input_name, path in self.rsp_overrides:
            values[path] = context.input(self, input_name)
        return job.with_overrides(values)


def datablock_name(value):
    if value is None:
        return ""
    return value.name_full


def scene_snapshot(scene):
    """Read current scene settings into a pure override map."""
    if scene is None:
        return {}
    image = scene.render.image_settings
    values = {
        "camera": scene.camera,
        "world": scene.world,
        "render.engine": scene.render.engine,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "frame_step": scene.frame_step,
        "render.resolution_x": scene.render.resolution_x,
        "render.resolution_y": scene.render.resolution_y,
        "render.resolution_percentage": scene.render.resolution_percentage,
        "render.filepath": scene.render.filepath,
        "render.image_settings.file_format": image.file_format,
        "render.film_transparent": scene.render.film_transparent,
        "render.use_simplify": scene.render.use_simplify,
        "view_settings.look": scene.view_settings.look,
        "view_settings.view_transform": scene.view_settings.view_transform,
    }
    if hasattr(scene, "cycles"):
        values["cycles.samples"] = scene.cycles.samples
        values["cycles.preview_samples"] = scene.cycles.preview_samples
    if hasattr(scene, "eevee"):
        values["eevee.taa_render_samples"] = scene.eevee.taa_render_samples
        values["eevee.taa_samples"] = scene.eevee.taa_samples
    return values


def register_classes(classes):
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_classes(classes):
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
