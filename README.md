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

`dev/` holds a local Blender scene (`renderspine-dev-001.blend`) and sample
outputs under `dev/render/`. Binary media (`.blend`, `.exr`, `.mp4`, `.png`)
is tracked with Git LFS. `dev/LilySurface/` (scraper downloads) and Blender
autosave sidecars (`*.blend1`, `*.blend2`) stay ignored.
