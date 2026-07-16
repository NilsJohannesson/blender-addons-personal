# RenderSpine

Standalone Blender 5.2 extension for building and executing render jobs with
nodes.

## Design

Houdini-style *description vs execution*, adapted to Blender (no USD stage):

- **Render Job** is the anchor: defaults live on the node so a lone job works
  (scene/camera empty → active scene fallback at execute).
- Optional chains (**Render Settings**, small override nodes) retarget the job.
- **Job Output** + Preview / Apply / Render are the thin executor.
- Editing never mutates the scene; graphs compile to immutable job specs.
  Transactions restore after render, cancel, error, or unregister.

## Development install

From the repository root, run:

```powershell
.\install.ps1
```

The script links this package into Blender 5.2's default local extension
repository. Restart Blender or reload scripts after installation, then enable
**RenderSpine** under Get Extensions.

## First graph

1. Change an editor to **RenderSpine Graph**.
2. Add **Render Job** — fill fields; works alone with defaults.
3. Optionally chain **Render Settings** or small nodes to override.
4. Finish with **Job Output**, or **Job List** + **Job List Output**.
5. RenderSpine sidebar: **Preview** / **Apply** / **Render Selected** or **Render All**.

## Output path tokens

Output Path / Render Job **Path** supports `{token}` substitution at
Preview / Apply / Render time (safe replace only; no Python eval):

`//renders/{camera}_{scene}_{view_layer}_{resolution}_v001`

Common tokens: `name`, `job`, `scene`, `camera`, `world`, `view_layer`,
`engine`, `format`, `width`, `height`, `percent`, `resolution` (`WxH`),
`frame`, `frame_start`, `frame_end`, `frame_step`, `samples`,
`view_transform`, `look`, and other job override aliases.
Unknown tokens error with the available list.

## Version 1.0 nodes

- Values: boolean, integer, float, string, vector, object, material,
  collection, scene, world, and action.
- Jobs: seed, list, index, single output, and list output.
- Settings: camera, world, view layer, engine, Cycles/Eevee samples, current
  settings, frame range, resolution, output path/format, FFmpeg video (H.264
  MP4 proxy defaults), film, color management, simplify, Cycles denoising, and
  render passes (AOVs; default Combined only).
- Objects: visibility, transform, material, action, and collection visibility.
- Utility: job switch, safe boolean/math/string operations, optional To String,
  and reusable job groups. String / Path inputs also auto-coerce object,
  collection, numbers, etc. (jobs still cannot connect).

Unsafe arbitrary Python, property `eval`/`exec`, SMTP, runtime package
installation, removed `bgl` overlays, and legacy compositor generation are not
included.

## Validate and build

From the repository root:

```powershell
.\test-render-spine.ps1
```

It validates the manifest, runs registration/graph/transaction/queue/render
tests in Blender 5.2 with factory settings, and creates:

```text
dist/render_spine-1.0.0.zip
```

For manifest-only work:

```powershell
blender --factory-startup --command extension validate addons\render_spine
blender --factory-startup --command extension build --source-dir addons\render_spine
```

## Reference and license

Apache-2.0. Workflow concepts informed by RenderNode by Atticus. No upstream
runtime modules, `rigging_nodes`, `t3dn_bip`, icons, or binary presets are
packaged. See `NOTICE` and `THIRD_PARTY_NOTICES`.
