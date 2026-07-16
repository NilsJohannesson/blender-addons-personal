"""Expand output-path {tokens} from job overrides."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

from render_spine.core.model import TaskSpec
from render_spine.core.path_template import (
    PathTemplateError,
    expand_path_expression,
    expand_path_template,
    format_color_token,
)
from render_spine.execution.path_expand import (
    expand_task_filepath,
    resolved_task_overrides,
    validate_output_filepath,
)


assert_equal(
    expand_path_template(
        "//renders/{camera}_{scene}_{resolution}_v001",
        {
            "camera": "Cam.A",
            "scene": "Shot01",
            "resolution": "1280x720",
        },
    ),
    "//renders/Cam.A_Shot01_1280x720_v001",
)

try:
    expand_path_template("//x/{missing}", {"camera": "A"})
except PathTemplateError:
    pass
else:
    raise AssertionError("Unknown token should fail")

scene = bpy.context.scene
camera_data = bpy.data.cameras.new("NRN Path Cam")
camera = bpy.data.objects.new("HeroCam", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera

job = (
    TaskSpec(name="Beauty")
    .with_override("camera", camera)
    .with_override("render.resolution_x", 1280)
    .with_override("render.resolution_y", 720)
    .with_override("render.engine", "CYCLES")
    .with_override(
        "render.filepath",
        "//renders/{camera}_{scene}_{view_layer}_{resolution}_{engine}_v001",
    )
    .with_metadata("view_layer", "ViewLayer")
)

expanded = expand_task_filepath(
    job.get_override("render.filepath"), job, scene
)
assert_equal(
    expanded,
    "//renders/HeroCam_{}_{}_1280x720_CYCLES_v001".format(
        scene.name, "ViewLayer"
    ),
)

resolved = resolved_task_overrides(job, scene)
filepath = None
for override in resolved:
    if override.path == "render.filepath":
        filepath = override.value
        break
assert_equal(filepath, expanded)

try:
    validate_output_filepath(
        "\\\\renders/{view_layer}_{camera}_{resolution}.png"
    )
except PathTemplateError:
    pass
else:
    raise AssertionError("UNC-looking blend-relative typo should fail")

try:
    validate_output_filepath("\\\\renders/area_cam02_1920x1080.png")
except PathTemplateError:
    pass
else:
    raise AssertionError("Expanded UNC typo should fail")

# Real UNC share path should still be allowed.
assert_equal(
    validate_output_filepath("\\\\fileserver\\share\\shot\\beauty.png"),
    "\\\\fileserver\\share\\shot\\beauty.png",
)

import math

variant_job = (
    TaskSpec(name="Sweep")
    .with_override("data.energy", 10.0)
    .with_override("data.color", (1.0, 0.0, 0.0))
    .with_override("data.spread", math.radians(80.0))
    .with_override(
        "render.filepath",
        "//renders/{name}_{variant_index}_{intensity}_{color}_{spread}.png",
    )
    .with_metadata("variant_index", 3)
    .with_metadata("variant", "intensity=10_color=1x0x0")
)
variant_path = expand_task_filepath(
    variant_job.get_override("render.filepath"), variant_job, scene
)
assert_equal(
    variant_path,
    "//renders/Sweep_3_10_red_80.png",
)

collection_job = (
    TaskSpec(name="Preview")
    .with_override(
        "hide_viewport",
        False,
        target_type="collections",
        target_name="spot",
    )
    .with_override(
        "hide_render",
        True,
        target_type="collections",
        target_name="spot",
    )
    .with_override(
        "render.filepath",
        "//renders/{name}_{camera}_{resolution}_{collection}.png",
    )
)
collection_path = expand_task_filepath(
    collection_job.get_override("render.filepath"), collection_job, scene
)
assert_equal(
    collection_path,
    "//renders/Preview_HeroCam_1920x1080_spot.png",
)

assert_equal(format_color_token((1.0, 0.0, 0.0)), "red")
assert_equal(format_color_token((0.0, 1.0, 0.0)), "green")
assert_equal(format_color_token((0.0, 0.0, 1.0)), "blue")
assert_equal(format_color_token((1.0, 1.0, 0.0)), "yellow")
assert_equal(format_color_token((1.0, 0.5, 0.0)), "red-yellow")
assert_equal(format_color_token((0.5, 1.0, 0.0)), "green-yellow")
assert_equal(format_color_token((0.0, 1.0, 0.5)), "green-cyan")
assert_equal(format_color_token((0.0, 0.5, 1.0)), "blue-cyan")
assert_equal(format_color_token((0.5, 0.0, 1.0)), "blue-red")
assert_equal(format_color_token((1.0, 0.0, 0.5)), "red-magenta")
assert_equal(format_color_token((0.076, 1.0, 0.175)), "green")

# Upstream-style $token path expressions.
scene.frame_current = 77
scene.render.resolution_x = 1203
scene.render.resolution_y = 1080
dollar_job = (
    TaskSpec(name="Task")
    .with_override("camera", camera)
    .with_override("render.resolution_x", 1203)
    .with_override("render.resolution_y", 1080)
    .with_override(
        "render.filepath",
        "//RENDER/$V/$res$camera/$F4",
    )
    .with_metadata("version", 1)
)
dollar_path = expand_task_filepath(
    dollar_job.get_override("render.filepath"), dollar_job, scene
)
assert_equal(dollar_path, "//RENDER/001/1203x1080HeroCam/0077")

assert_equal(
    expand_path_expression(
        "renders/$label/$V/$T{%m}",
        {
            "name": "Beauty",
            "label": "Beauty",
            "version": "2",
            "frame": "1",
        },
    ).split("/")[-2],
    "002",
)

bpy.data.objects.remove(camera)
bpy.data.cameras.remove(camera_data)
extension.unregister()
finish("path_template")
