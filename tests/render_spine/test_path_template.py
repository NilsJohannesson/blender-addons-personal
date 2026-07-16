"""Expand output-path {tokens} from job overrides."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

from render_spine.core.model import JobSpec
from render_spine.core.path_template import (
    PathTemplateError,
    expand_path_template,
)
from render_spine.execution.path_expand import (
    expand_job_filepath,
    resolved_job_overrides,
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
    JobSpec(name="Beauty")
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

expanded = expand_job_filepath(
    job.get_override("render.filepath"), job, scene
)
assert_equal(
    expanded,
    "//renders/HeroCam_{}_{}_1280x720_CYCLES_v001".format(
        scene.name, "ViewLayer"
    ),
)

resolved = resolved_job_overrides(job, scene)
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

bpy.data.objects.remove(camera)
bpy.data.cameras.remove(camera_data)
extension.unregister()
finish("path_template")
