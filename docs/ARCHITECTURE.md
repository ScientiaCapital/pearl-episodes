# Architecture

## Three layers

| Layer | Runs where | Talks to | Output |
|---|---|---|---|
| Operate | Claude Code session | Epiphan Edge via MCP (`get_devices_in_my_team`, `batch_recording`, `get_channel_image`, storage and recorder status) | Session log: which devices and channels recorded, when, with what warnings |
| Pull and package | `pearl_episodes` (this package) | Each Pearl's REST API; local disk; optional S3/SFTP where automatic file upload (AFU) already delivered the files | One episode directory per take: original files, `manifest.json`, `hashes.txt`, LeRobot and RLDS exports |
| Analyze | Notebook on the Mac (LeRobot) or Colab/RunPod (OXE models) | The episode directories | A Pearl episode beside a DROID episode, plots, model predictions |

`.claude/PLAN.md` has the full design for one episode, the segment-stitching rule and the operator session log.

## Episode manifest (provenance, in software)

`src/pearl_episodes/episodes/manifest.py`, `schema_version` 2. Models are frozen and reject unknown fields.

- Top level: `episode_id`, `device_serial` (from Edge; not in the REST API), `device_model`, `firmware`,
  `start_time` (raw `created` of the first segment, device clock, never parsed), `task_label`, `operator`,
  `scene`, `clock_source` (`ntp` | `ptp` | `manual` | `unknown`, recorded as read, never interpreted),
  `session_id`, `notes`.
- `cameras[]`: `channel_id`, `channel_name`, and at least one `segments[]` entry. Segments are numbered `seq`
  0..n-1 in order. Each has `file_id`, `path` (relative to the episode directory), `created` (raw device
  text), `duration`, `size`, `sha256` (64 lowercase hex), `recorder_id`, `event_id`.
- `derived[]`: `path`, `sha256`, `tool`, `version` for every file made from the originals.
- `incidents[]`: `ts`, `source`, `text`, copied verbatim from the tool that reported it.
- `hashes.txt` lists every segment and derived file as `<sha256>  <path>`; `shasum -a 256 -c hashes.txt` passes
  from the episode directory.
- `load_manifest` reads version 1 manifests (one file per camera) and upgrades them to one segment per camera.

## Pearl REST API (verified against the published OpenAPI spec, 2026-10-14)

Source: `epiphan-video/pearl_api_swagger_ui`, `api/v2.0/openapi.yml`, 64 paths, and the kb.epiphan.com REST
pages cited in `.claude/PLAN.md` §2. Base `/api/v2.0`, HTTP Basic auth, every response
`{"status": "ok", "result": ...}`. The client always uses `https://` and verifies TLS unless
`PEARL_VERIFY_TLS=false`; it assumes HTTPS is enabled on the device.

Used here: `GET /recorders`, `GET /recorders/status` (optional `ids`; items carry `id`, `name`, `status`) and
`GET /recorders/{rid}/status` (`state` is `disabled | starting | started | stopped | error`, plus `duration`,
`active`, `total` and, on error, `description`), `GET /recorders/{rid}/archive/files` (paged with `from` and
`limit`), `GET /recorders/{rid}/archive/files/{fid}` (raw media), `POST /recorders/control/start` and `/stop`
(optional `ids` query, asynchronous), `GET /system/ident`, `GET /system/firmware`.
Archive file fields: `id, name, extension, recording, downloaded, created, duration, size, recorder, uploading,
event_id`. File names carry a prefix plus date and time with no documented format, so the manifest records
`created` from the API and never parses the name.

## Rules that shape the code

- No claim about multi-camera alignment anywhere in code, docs or output. Record `clock_source` and leave
  interpretation to Product.
- Recording actions target channels, not devices. A channel address for Edge batch tools is
  `<device_id>-<channel_id>`.
- Pearl rolls a recording into a new file at 30 minutes or 500 MB by default, "without losing any content", so
  one take can be several files and the packager must stitch them (`pearl-family/about-recording`). Separately,
  a channel controlled by Edge must record MP4 with a 500 MB maximum file size
  (`pearl-family/configure-recording-settings-file-size-and-type`).
- Pearl records H.264 4:2:0 8-bit (Nano also H.265). Exports keep that stream as-is (remux, no re-encode) so the
  video loses no more quality. Depth is never recorded or claimed.
- Recordings may contain people. They never leave the machine they were pulled to unless the lab says so.

## Open product questions this code should not guess at

Which lab USB cameras work on Pearl-2 and Pearl Mini UVC input in practice (documented on both; Nano has none);
a second simultaneous copy; simultaneous 1080p60 channel count; per-take labels by API; per-file hash at close;
custom applications on the Apps page; a REST call for the Date and Time protocol; the next Pearl.
