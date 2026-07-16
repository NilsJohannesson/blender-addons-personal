"""Task creation, collection, indexing, and output nodes."""

from dataclasses import replace

import bpy

from ..core.model import Override, TaskList, TaskSpec
from ..core.node import RSP_NodeBase, apply_engine_samples
from ..core.variants import OVERRIDE_BUNDLE_PATH


def _retarget_layer_collection_path(path, layer_name):
    marker = '"].layer_collection'
    if path.startswith('view_layers["') and marker in path:
        suffix = path.split(marker, 1)[1]
        return 'view_layers["{}"].layer_collection{}'.format(
            layer_name, suffix
        )
    return path


def _retarget_override(override, layer_name):
    path = _retarget_layer_collection_path(override.path, layer_name)
    if path == override.path:
        return override
    return Override(
        path,
        override.value,
        override.target_type,
        override.target_name,
    )


def _retarget_axis_value(value, layer_name):
    if isinstance(value, tuple) and value:
        if all(isinstance(item, Override) for item in value):
            return tuple(_retarget_override(item, layer_name) for item in value)
    return value


def _retarget_layer_collection_overrides(job, layer_name):
    """Move LayerCollection overrides (and pending bundles) to selected VL."""
    result = replace(job, overrides=(), axes=())
    for override in job.overrides:
        item = _retarget_override(override, layer_name)
        result = result.with_override(
            item.path,
            item.value,
            target_type=item.target_type,
            target_name=item.target_name,
        )
    for axis in job.axes or ():
        if axis.path == OVERRIDE_BUNDLE_PATH:
            values = tuple(
                _retarget_axis_value(value, layer_name) for value in axis.values
            )
            result = result.with_axis(replace(axis, values=values))
        else:
            result = result.with_axis(axis)
    return result

def _resolve_view_layer_name(job, layer_name):
    """Pick an explicit layer, else the scene's active view layer."""
    source = job.source_scene
    scene = source if isinstance(source, bpy.types.Scene) else bpy.data.scenes.get(source)
    scene = scene or bpy.context.scene
    if layer_name:
        if '"' in layer_name or "\\" in layer_name:
            raise ValueError("View layer name cannot contain quotes or backslashes")
        if scene.view_layers.get(layer_name) is None:
            raise ValueError("View layer not found: {}".format(layer_name))
        return scene, layer_name
    active = getattr(scene.view_layers, "active", None)
    if active is None and bpy.context.scene == scene:
        active = getattr(bpy.context, "view_layer", None)
    if active is not None:
        return scene, active.name
    if scene.view_layers:
        return scene, scene.view_layers[0].name
    raise ValueError("No view layer available")


def _apply_view_layer(job, layer_name=""):
    """Enable one view layer and disable the others for this task.

    Empty ``layer_name`` pins the scene's active view layer. Leaving every
    ``view_layer.use`` flag alone lets Blender render all enabled layers
    before writing a single still — slow and looks like a remembered list.
    """
    scene, layer_name = _resolve_view_layer_name(job, layer_name or "")
    result = _retarget_layer_collection_overrides(job, layer_name)
    result = result.with_metadata("view_layer", layer_name)
    result = result.with_override("scene.view_layer", layer_name)
    for layer in sorted(scene.view_layers, key=lambda item: item.name):
        result = result.with_override(
            'view_layers["{}"].use'.format(layer.name),
            layer.name == layer_name,
        )
    return result

class RSP_TaskSeedNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeTaskSeed"
    bl_label = "Task Seed"
    rsp_inputs = (
        ("RenderSpineNodeSocketString", "Name"),
        ("RenderSpineNodeSocketScene", "Scene"),
    )
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)

    def init(self, context):
        super().init(context)
        self.inputs["Name"].default_value = "Render"

    def rsp_compile(self, context, socket):
        return TaskSpec(
            name=context.input(self, "Name") or "Render",
            source_scene=context.input(self, "Scene") or "",
        )


class RSP_RenderTaskNode(RSP_NodeBase, bpy.types.Node):
    """Anchor job: defaults on the node, optional chain in/out.

    Works standalone (Blender-like). Optional Job input and downstream
    Render Settings / small nodes override. Task Output + Render ops execute.
    """

    bl_idname = "RenderSpineNodeRenderTask"
    bl_label = "Render Task"
    bl_width_default = 240
    rsp_inputs = (
        ("RenderSpineNodeSocketTask", "Task"),
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
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)
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

    def rsp_compile(self, context, socket):
        if self.inputs["Task"].is_linked:
            job = context.input(self, "Task", required=True)
            if not isinstance(job, TaskSpec):
                raise TypeError("Task input requires TaskSpec")
        else:
            job = TaskSpec(
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
            value = context.input(self, input_name)
            # Empty Path must not wipe a template from upstream Output Path.
            if path == "render.filepath" and not str(value or "").strip():
                continue
            values[path] = value
        engine = context.input(self, "Engine")
        apply_engine_samples(values, engine, context.input(self, "Samples"))
        job = job.with_overrides(values)
        return _apply_view_layer(job, context.input(self, "View Layer") or "")


class RSP_TaskListNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeTaskList"
    bl_label = "Task List"
    rsp_inputs = (
        ("RenderSpineNodeSocketTask", "Task 1"),
        ("RenderSpineNodeSocketTask", "Task 2"),
        ("RenderSpineNodeSocketTask", "Task 3"),
        ("RenderSpineNodeSocketTask", "Task 4"),
    )
    rsp_outputs = (("RenderSpineNodeSocketTaskList", "Tasks"),)

    def rsp_compile(self, context, socket):
        jobs = []
        for input_socket in self.inputs:
            if input_socket.is_linked:
                value = context.input(self, input_socket.name)
                if not isinstance(value, TaskSpec):
                    raise TypeError("{} requires TaskSpec".format(input_socket.name))
                jobs.append(value)
        return TaskList(tuple(jobs))


class RSP_TaskIndexNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeTaskIndex"
    bl_label = "Task Index"
    rsp_inputs = (
        ("RenderSpineNodeSocketTaskList", "Tasks"),
        ("RenderSpineNodeSocketInt", "Index"),
    )
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)

    def rsp_compile(self, context, socket):
        jobs = context.input(self, "Tasks", required=True)
        if not isinstance(jobs, TaskList):
            raise TypeError("Tasks input requires TaskList")
        return jobs.at(context.input(self, "Index"))


class RSP_TaskOutputNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeTaskOutput"
    bl_label = "Task Output"
    rsp_is_task_output = True
    rsp_inputs = (("RenderSpineNodeSocketTask", "Task"),)

    def rsp_compile(self, context, socket):
        return context.input(self, "Task", required=True)


class RSP_TaskListOutputNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeTaskListOutput"
    bl_label = "Task List Output"
    rsp_is_task_output = True
    rsp_inputs = (("RenderSpineNodeSocketTaskList", "Tasks"),)

    def rsp_compile(self, context, socket):
        return context.input(self, "Tasks", required=True)


CLASSES = (
    RSP_TaskSeedNode,
    RSP_RenderTaskNode,
    RSP_TaskListNode,
    RSP_TaskIndexNode,
    RSP_TaskOutputNode,
    RSP_TaskListOutputNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)
