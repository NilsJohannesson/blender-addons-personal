# Agent Instructions

Blender addons / extensions (pure Python, `bpy` API). No package manager.

- `render_spine` (**RenderSpine**): standalone Blender 5.2+ extension with
  headless tests.

## Install / Reload

- Install: run `.\install.ps1` from repo root. It junctions
  `%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default\render_spine`
  to `addons/render_spine/`.
- Edits under `addons/render_spine/` are live through that junction; reload in
  Blender via **F3 > Reload Scripts** or toggle the extension off/on
  ("RenderSpine").
- Verify with `.\test-render-spine.ps1`. Requires Blender 5.2; validates, tests,
  then builds the extension (use `-SkipBuild` to skip the zip).

## Project Structure

```
addons/render_spine/
  blender_manifest.toml # Blender 5.2 extension metadata
  __init__.py           # Explicit registration entry point
  core/                 # Pure graph compilation and validation
  nodes/                # Render setup node definitions
  execution/            # Transactional preview and render queue
  operators.py          # Preview / Apply / Restore / Render
  ui.py                 # Node Editor header + RenderSpine sidebar
  state.py              # Scene.rsp_state PropertyGroup

docs/
  render-spine-plan.md       # Goals and architecture
  render-spine-port-map.md   # Upstream RenderNode port decisions
  render-spine-acceptance.md # 1.0 automated + manual gates

dev/                    # Local scratch blend + sample renders (LFS)
```

## Key Conventions

- Each submodule exposes `register()` / `unregister()`; `__init__.py` calls them
  in `_submodules` order. Add new modules to that list.
- Classes use `RSP_`, operators use `rsp.*`, node/socket IDs use
  `RenderSpineNode*`, tree is `RenderSpineNodeTree`.
- Scene-level state is `bpy.types.Scene.rsp_state` (`PropertyGroup`); attach in
  `register()`, `del` in `unregister()`.
- UI panels use `bl_category = "RenderSpine"` in the Node Editor.
- Graph compilation must not mutate Blender data. Mutations happen only in
  explicit transactional Preview / Apply / Render operations and must restore
  after render completion, cancellation, errors, and unregister.
- Never use `eval`, `exec`, runtime package installation, or dynamic
  filesystem-wide imports.
- Code style: 4-space indent, double-quoted strings, no type hints beyond
  Blender prop annotations.
- Design docs live under `docs/`; keep them updated when architecture changes.

## Dev scratch

- `dev/renderspine-dev-001.blend` and `dev/render/` are tracked (Git LFS for
  binary media).
- `dev/LilySurface/` is ignored (local scraper downloads).
- `*.blend1` / `*.blend2` are ignored.

## Commit Attribution

AI commits MUST include:

```
Co-Authored-By: (the agent's name and attribution byline)
```

Example: `Co-Authored-By: Cursor Grok 4.5 <noreply@cursor.com>`
