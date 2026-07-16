# RenderNode to RenderSpine Port Map

RenderSpine is a Blender 5.2 extension. Upstream RenderNode is an Apache-2.0
behavioral reference only; it is not loaded, installed, or vendored in this
repository.

Upstream reference: `atticus-lv/RenderNode` `develop` at
`8a4797a2186b76fedebc5d634cff298e69089474` (2022-04-20)
https://github.com/atticus-lv/RenderNode

## Port policy

- **Reimplemented**: behavior retained with new Blender 5.2 code.
- **Redesigned**: user goal retained, architecture intentionally changed.
- **Deferred**: excluded from version 1.0.
- **Removed**: unsafe, broken, obsolete, or redundant behavior.

No upstream module is imported at runtime.

## Package and runtime

| Upstream module | Status | RenderSpine replacement |
|---|---|---|
| `__init__.py` | Redesigned | Extension manifest and explicit ordered registration |
| `preferences.py` | Redesigned | Node Editor sidebar and extension-safe package namespace |
| `utility.py` | Redesigned | Pure job compiler plus transactional execution |
| `nodes/BASE/_runtime.py` | Reimplemented | Deterministic graph compiler without live scene mutation |
| `nodes/BASE/node_base.py` | Reimplemented | Compile-only node base |
| `nodes/BASE/node_tree.py` | Reimplemented | `RenderSpineNodeTree` using Blender 5.2 APIs |
| `nodes/BASE/node_socket.py` | Reimplemented | Typed Blender 5.2 sockets and interfaces |
| `nodes/BASE/node_category.py` | Reimplemented | `NODE_MT_add` menus |
| `nodes/BASE/sockets/socket_*.py` | Reimplemented | Typed sockets in `sockets.py` |
| `nodes/BASE/sockets/Old_socket.py` | Removed | Obsolete pre-refactor sockets |
| `nodes/BASE/sockets/socket_TaskSettings.py` | Removed | Obsolete merge pipeline |
| `nodes/BASE/sockets/socket_RenderList.py` | Removed | Obsolete merge pipeline |

## Nodes

| Upstream area | Status | Version 1.0 scope |
|---|---|---|
| `nodes/Input/*.py` | Reimplemented | Safe scalar/vector/datablock values and job inputs |
| `nodes/List/*.py` | Reimplemented | Job list and active/list index |
| `nodes/Scene/GetScene*.py` | Redesigned | Explicit scene references and compile-time defaults |
| `nodes/Scene/SetScene*.py` | Reimplemented | Camera, world, view layer, engine, resolution, simplify, color management |
| `nodes/Output/*.py` | Reimplemented | Frame range, output path expressions (`$V/$res/$F4` + `{tokens}`), live Resolved preview, image format, film |
| `nodes/Object/*.py` | Reimplemented | Visibility, transform, material, action, and light settings overrides |
| *(new)* Variant Axis / Render Variants | Redesigned | TOPs-style cartesian job fan-out from typed value lists (not in upstream) |
| `nodes/Collection/*.py` | Reimplemented | Collection visibility overrides |
| `nodes/Eevee_cycles/SetCycles*.py` | Reimplemented | Current Cycles sampling and selected render settings |
| `nodes/Eevee_cycles/SetEevee*.py` | Redesigned | Current Eevee sampling only; removed Bloom/GTAO/legacy SSR controls |
| `nodes/Eevee_cycles/SetWorkBench*.py` | Deferred | Workbench tuning is outside production-core v1 |
| `nodes/Utility/Switch.py` | Reimplemented | Safe branch selection |
| `nodes/Utility/Math.py` | Reimplemented | Whitelisted operations without `eval` |
| `nodes/Utility/VectorMath.py` | Reimplemented | Safe vector operations |
| `nodes/Utility/StringOperate.py` | Reimplemented | Safe token/string operations |
| `nodes/Utility/BooleanMath.py` | Redesigned | Whitelisted boolean operations without `eval` |
| `nodes/Utility/Scripts.py` | Removed | Arbitrary `exec` is not permitted |
| `nodes/Convert/*.py` | Reimplemented | Safe conversions where sockets need them |
| `nodes/Group/node_Group.py` | Redesigned | Blender 5.2 node-tree interfaces |
| `nodes/Extra/GetTaskInfo.py` | Redesigned | Dry-run job inspector |
| `nodes/Extra/GetProperty.py` | Removed | Arbitrary `eval` is not permitted |
| `nodes/Extra/SetProperty.py` | Removed | Arbitrary `exec` is not permitted |
| `nodes/Extra/Property.py` | Removed | Legacy unsafe property pipeline |
| `nodes/Extra/Email.py` | Deferred | SMTP and stored credentials are outside v1 |
| `nodes/Extra/StoreValue.py` | Deferred | Redundant with deterministic compile values |
| `nodes/Extra/ssm_LightStudio.py` | Removed | Undeclared third-party addon dependency |
| `nodes/Comp/ImageSequence.py` | Deferred | Legacy compositor setup is outside v1 |

## Operators and UI

| Upstream area | Status | RenderSpine replacement |
|---|---|---|
| `operators/op_render_queue_v2.py` | Redesigned | Cancellation-safe transactional sequential queue |
| `operators/op_pop_up_window.py` | Redesigned | Sidebar status and job inspector |
| `operators/op_group_operate.py` | Redesigned | Native Blender 5.2 group interfaces |
| `operators/op_mute_nodes.py` | Deferred | Blender's built-in mute behavior |
| `operators/rsn_helper/*.py` | Deferred | Editor convenience tools after core stability |
| `operators/draw_nodes/*.py` | Removed | `bgl` overlays not ported; Viewer uses transactional Apply instead |
| `nodes/Task/ProcessorNode.py` | Reimplemented | `Processor` node shows live render-queue progress |
| `nodes/old_nodes/Viewer.py` | Redesigned | `Viewer` node applies a connected Job (no GPU outline draw) |
| `operators/op_create_comp_tree.py` | Deferred | Uses removed compositor API |
| `operators/op_save_task_to_file.py` | Removed | Broken upstream implementation |
| `operators/op_call_blend.py` | Removed | Hard-coded background repair workflow |
| `operators/script_call_blend.py` | Removed | Hard-coded node and tree names |
| `operators/op_send_email.py` | Deferred | Network behavior is outside v1 |
| `ui/ui_editor_header.py` | Reimplemented | Compile, preview, render, restore, and cancel controls |
| `ui/ui_helper_panel.py` | Redesigned | Validation and dry-run inspector |
| `ui/ui_properties_panel.py` | Redesigned | Node Editor sidebar; no global scene mutation |
| `ui/ui_pie_menu.py` | Deferred | Core controls remain visible without keymap setup |
| `ui/icon_utils.py` | Removed | Uses unnecessary third-party preview stack |
| `ui/t3dn_bip/*` | Removed | Runtime Pillow installation and vendored code are not used |
| `ui/icons/*` | Deferred | Native Blender icons used in v1 |

## Presets and resources

| Upstream resource | Status | Reason |
|---|---|---|
| `preset/node_groups/custom_path_exp.blend` | Deferred | Contains old node IDs and Blender-era data |
| `res/*` | Removed | Marketing assets are not runtime requirements |
| `.github/*`, `.gitignore`, `.gitee/*` | Removed | Upstream repository infrastructure |
| `README.md`, `LICENSE` | Retained as reference | Attribution via GitHub upstream + local `NOTICE` |

## Major behavioral change

Upstream RenderNode mutates the active scene whenever its graph evaluates.
RenderSpine first compiles a graph into validated job specifications.
Scene changes happen only through explicit Preview, Apply, or Render actions.
Every render operation captures touched values and restores them after completion,
cancellation, or failure.
