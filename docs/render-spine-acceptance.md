# RenderSpine 1.0 Acceptance

Use Blender 5.2 with factory preferences where practical.

## Automated gate

Run from repository root:

```powershell
.\test-render-spine.ps1
```

Required:

- extension manifest validates;
- registration and unregister tests pass repeatedly;
- every production node can be instantiated;
- representative graphs compile to deterministic jobs;
- invalid graphs return actionable diagnostics;
- scene, object, collection, material, and render settings restore exactly;
- render completion and cancellation restore state;
- tiny render queue writes expected output;
- extension archive builds under `dist/`.

## Manual UI gate

1. Run `install.ps1` and enable **RenderSpine**.
2. Open a Node Editor and select **RenderSpine Graph** tree type.
3. Create a tree with job, camera, frame range, resolution, output path, and
   render-list nodes.
4. Confirm editing nodes does not change scene settings.
5. Run validation and inspect resolved job summary.
6. Preview selected job, confirm expected changes, then Restore and verify all
   original values return.
7. Apply selected job, save and reopen the file, then restore before rendering.
8. Render Selected and confirm output path, frame range, camera, and format.
9. Add a second job and Render All; confirm order and status.
10. Cancel during a render and confirm all original scene values return.
11. Disable addon while preview state is active and confirm cleanup restores
    original values.
12. Save and reopen a node graph; confirm links, datablock references, and job
    settings persist.

Version 1.0 is accepted only when every item passes on Blender 5.2.
