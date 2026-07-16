# blender-addons-personal

Personal Blender addons / extensions.

## RenderSpine

Blender 5.2+ node graph for building and executing render jobs
(`addons/render_spine`).

```powershell
.\install.ps1
.\test-render-spine.ps1
```

See [addons/render_spine/README.md](addons/render_spine/README.md).

## Dev scratch

`dev/` holds a local Blender scene (`renderspine-dev-001.blend`), sample
outputs under `dev/render/`, and LilySurface assets. Binary media
(`.blend`, `.exr`, `.mp4`, `.png`) is tracked with Git LFS. Blender
autosave sidecars (`*.blend1`, `*.blend2`) stay ignored.
