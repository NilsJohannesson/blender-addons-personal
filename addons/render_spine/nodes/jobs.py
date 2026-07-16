"""Job creation, collection, indexing, and output nodes."""

import bpy

from ..core.model import JobList, JobSpec
from ..core.node import RSP_NodeBase, apply_engine_samples


def _apply_view_layer(job, layer_name):
    """Enable one view layer and disable the others on the job's scene."""
    if not layer_name:
        return job
    if '"' in layer_name or "\\" in layer_name:
        raise ValueError("View layer name cannot contain quotes or backslashes")
    source = job.source_scene
    scene = source if isinstance(source, bpy.types.Scene) else bpy.data.scenes.get(source)
    scene = scene or bpy.context.scene
    if scene.view_layers.get(layer_name) is None:
        raise ValueError("View layer not found: {}".format(layer_name))
    result = job.with_metadata("view_layer", layer_name)
    for layer in sorted(scene.view_layers, key=lambda item: item.name):
        result = result.with_override(
            'view_layers["{}"].use'.format(layer.name),
            layer.name == layer_name,
        )
    return result


class RSP_JobSeedNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeJobSeed"
    bl_label = "Job Seed"
    rsp_inputs = (
        ("RenderSpineNodeSocketString", "Name"),
        ("RenderSpineNodeSocketScene", "Scene"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)

    def init(self, context):
        super().init(context)
        self.inputs["Name"].default_value = "Render"

    def rsp_compile(self, context, socket):
        return JobSpec(
            name=context.input(self, "Name") or "Render",
            source_scene=context.input(self, "Scene") or "",
        )


class RSP_RenderJobNode(RSP_NodeBase, bpy.types.Node):
    """Anchor job: defaults on the node, optional chain in/out.

    Works standalone (Blender-like). Optional Job input and downstream
    Render Settings / small nodes override. Job Output + Render ops execute.
    """

    bl_idname = "RenderSpineNodeRenderJob"
    bl_label = "Render Job"
    bl_width_default = 240
    rsp_inputs = (
        ("RenderSpineNodeSocketJob", "Job"),
        ("RenderSpineNodeSocketString", "Name"),
        ("RenderSpineNodeSocketScene", "Scene"),
        ("RenderSpineNodeSocketObject", "Camera"),
        ("RenderSpineNodeSocketWorld", "World"),
        ("RenderSpineNodeSocketViewLayer", "View Layer"),
        ("RenderSpineNodeSocketEngine", "Engine"),
        ("RenderSpineNodeSocketInt", "Samples"),
        ("RenderSpineNodeSocketInt", "Frame Start"),
        ("RenderSpineNodeSocketInt", "Frame End"),
        ("RenderSpineNodeSocketInt", "Frame Step"),
        ("RenderSpineNodeSocketInt", "Width"),
        ("RenderSpineNodeSocketInt", "Height"),
        ("RenderSpineNodeSocketInt", "Percent"),
        ("RenderSpineNodeSocketFilePath", "Path"),
        ("RenderSpineNodeSocketImageFormat", "Format"),
        ("RenderSpineNodeSocketBool", "Transparent"),
        ("RenderSpineNodeSocketBool", "Motion Blur"),
        ("RenderSpineNodeSocketFloat", "Motion Blur Shutter"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_defaults = {
        "Name": "Render",
        "Engine": "CYCLES",
        "Samples": 128,
        "Frame Start": 1,
        "Frame End": 250,
        "Frame Step": 1,
        "Width": 1920,
        "Height": 1080,
        "Percent": 100,
        "Format": "PNG",
        "Motion Blur Shutter": 0.5,
    }
    rsp_simple_overrides = (
        ("Engine", "render.engine"),
        ("Frame Start", "frame_start"),
        ("Frame End", "frame_end"),
        ("Frame Step", "frame_step"),
        ("Width", "render.resolution_x"),
        ("Height", "render.resolution_y"),
        ("Percent", "render.resolution_percentage"),
        ("Path", "render.filepath"),
        ("Format", "render.image_settings.file_format"),
        ("Transparent", "render.film_transparent"),
        ("Motion Blur", "render.use_motion_blur"),
        ("Motion Blur Shutter", "render.motion_blur_shutter"),
    )

    def init(self, context):
        super().init(context)
        for name, value in self.rsp_defaults.items():
            socket = self.inputs.get(name)
            if socket is None:
                continue
            try:
                socket.default_value = value
            except (TypeError, ValueError):
                pass

    def draw_buttons(self, context, layout):
        layout.label(text="Anchor: works alone. Chain to override.")
        layout.label(text="Path: {camera} {scene} {view_layer} {resolution} …")

    def rsp_compile(self, context, socket):
        if self.inputs["Job"].is_linked:
            job = context.input(self, "Job", required=True)
            if not isinstance(job, JobSpec):
                raise TypeError("Job input requires JobSpec")
        else:
            job = JobSpec(
                name=context.input(self, "Name") or "Render",
                source_scene=context.input(self, "Scene") or "",
            )

        values = {}
        camera = context.input(self, "Camera")
        if camera is not None:
            values["camera"] = camera
        world = context.input(self, "World")
        if world is not None:
            values["world"] = world
        for input_name, path in self.rsp_simple_overrides:
            values[path] = context.input(self, input_name)
        engine = context.input(self, "Engine")
        apply_engine_samples(values, engine, context.input(self, "Samples"))
        job = job.with_overrides(values)
        return _apply_view_layer(job, context.input(self, "View Layer") or "")


class RSP_JobListNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeJobList"
    bl_label = "Job List"
    rsp_inputs = (
        ("RenderSpineNodeSocketJob", "Job 1"),
        ("RenderSpineNodeSocketJob", "Job 2"),
        ("RenderSpineNodeSocketJob", "Job 3"),
        ("RenderSpineNodeSocketJob", "Job 4"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJobList", "Jobs"),)

    def rsp_compile(self, context, socket):
        jobs = []
        for input_socket in self.inputs:
            if input_socket.is_linked:
                value = context.input(self, input_socket.name)
                if not isinstance(value, JobSpec):
                    raise TypeError("{} requires JobSpec".format(input_socket.name))
                jobs.append(value)
        return JobList(tuple(jobs))


class RSP_JobIndexNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeJobIndex"
    bl_label = "Job Index"
    rsp_inputs = (
        ("RenderSpineNodeSocketJobList", "Jobs"),
        ("RenderSpineNodeSocketInt", "Index"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)

    def rsp_compile(self, context, socket):
        jobs = context.input(self, "Jobs", required=True)
        if not isinstance(jobs, JobList):
            raise TypeError("Jobs input requires JobList")
        return jobs.at(context.input(self, "Index"))


class RSP_JobOutputNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeJobOutput"
    bl_label = "Job Output"
    rsp_is_job_output = True
    rsp_inputs = (("RenderSpineNodeSocketJob", "Job"),)

    def rsp_compile(self, context, socket):
        return context.input(self, "Job", required=True)


class RSP_JobListOutputNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeJobListOutput"
    bl_label = "Job List Output"
    rsp_is_job_output = True
    rsp_inputs = (("RenderSpineNodeSocketJobList", "Jobs"),)

    def rsp_compile(self, context, socket):
        return context.input(self, "Jobs", required=True)


CLASSES = (
    RSP_JobSeedNode,
    RSP_RenderJobNode,
    RSP_JobListNode,
    RSP_JobIndexNode,
    RSP_JobOutputNode,
    RSP_JobListOutputNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)
