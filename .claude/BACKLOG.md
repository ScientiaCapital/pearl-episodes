# Backlog

Sprint 1 lives in GitHub issues #2 to #14 (milestone "Sprint 1", from 2026-10-15). After it, in priority order.
Effort: S under half a day, M about a day, L several days. Impact is for the Physical AI lab proof of concept.

## Sprint 2 candidates (need a real take first)
1. Operator session script over Edge MCP (effort M, impact H). The read-only preflight (`/preflight`) and the
   append-only session log (`preflight --session`) are built. Left: start and stop through `batch_recording`,
   polling status, the keep or discard verdict per take, and the hand-off to `pull` and `package`. Waits on a
   confirmed bench device.
2. Per-take labels captured from the operator at record start (effort S, impact M): a CLI prompt, later a tiny web
   form. Test whether `POST /channels/{cid}/bookmarks` (required `text` parameter) can carry the label; how a
   bookmark shows up in the file is undocumented.
3. RLDS export via tfds (effort L, impact M). Easier to get right once a real episode exists to compare.
4. Run an Open X-Embodiment model (RT-1-X) in Colab or on RunPod against Pearl frames of a desk scene (effort M,
   impact M).

## From the observers (2026-10-16)
- Preflight reads raw Edge tool results from files instead of a hand-built JSON (effort S, impact M).
- Preflight against the Pearl itself with `GET /system/storages`, so it also runs without Edge (effort S, impact L).
- Move the free-space floor into `Settings` when the session script needs it (effort S, impact L).
- Fill `--model` and `--firmware` in `package` from `device_info()` (effort S, impact L).
- Time the export frame sampler on a real 30-minute file (effort S, impact M).

## Open decisions (Tim)
- Decided 2026-10-16 (Tim): the repository stays in the ScientiaCapital GitHub org. The copyright and
  confidential notice stay Epiphan Systems Inc. Not an open question.
- Decided 2026-10-16: bold emphasis was removed from the README (#35), per the Epiphan style guide.
- A Dockerfile beside the Pearl (ffmpeg, uv, this package, pulling over REST): offered 2026-10-15, not accepted.
  Containers on the Pearl itself stay unsupported until Product confirms in writing.

## Stretch
- On-device manifest writer from Pearl's Apps page (needs Product's answer).
- EC20 PTZ preset recall for repeatable framing across takes (bench question; the EC20 has its own spec).
