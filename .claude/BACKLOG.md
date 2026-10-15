# Backlog

In build order (`.claude/PLAN.md` §9).

- Client: `GET /recorders/status`; check the `{"status": "ok"}` envelope; atomic, size-verified downloads; refuse
  files with `recording: true`; non-blocking disk I/O; CLI errors as one line and a non-zero exit
- `pearl-episodes pull`: new files for a recorder to `recordings/<host>/<recorder_id>/`, idempotent on file id
- Manifest v2: ordered segments per camera, derived files with hashes, session id, incidents, `clock_source`
  `manual`; frozen, validated models
- Packager: segment stitching by remux (no re-encode), then the LeRobot layout
- Notebook: one packaged Pearl episode beside a DROID episode (the demo for DROID campuses)
- Bench codec test on the Mini: H.264 at three bitrates, no re-encode vs LeRobot's AV1 default, size and quality
- Bench tests: ZED 2 (1344×376 UVC mode) and a RealSense colour stream on the Mini's USB input
- RLDS export via tfds
- Operator session script over Edge MCP with a session log; preflight from Fleetwatch's readiness check
- Run an Open X-Embodiment model (RT-1-X) in Colab or on RunPod against Pearl frames of a desk scene
- Per-take labels captured from the operator at record start (CLI prompt, later a tiny web form)
- Stretch: on-device manifest writer from Pearl's Apps page (needs Product's answer)
