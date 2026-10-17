# Architecture

## Three layers

| Layer | Runs where | Talks to | Output |
|---|---|---|---|
| Operate | Claude Code session | Epiphan Edge via MCP (`get_devices_in_my_team`, `batch_recording`, `get_channel_image`, storage and recorder status) | Session log: which devices and channels recorded, when, with what warnings |
| Pull and package | `pearl_episodes` (this package) | Each Pearl's REST API; local disk; optional S3/SFTP where automatic file upload (AFU) already delivered the files | One episode directory per take: original files, `manifest.json`, `hashes.txt`, LeRobot and RLDS exports |
| Analyze | Notebook on the Mac (LeRobot) or Colab/RunPod (OXE models) | The episode directories | A Pearl episode beside a DROID episode, plots, model predictions |

`.claude/PLAN.md` has the full design for one episode, the segment-stitching rule and the operator session log.

**Preflight (read only).** Python cannot call MCP tools, so the work is split. `/preflight` has a Claude session
read `get_devices_in_my_team`, `get_storage_status_for_devices` and `get_channel_settings`, save the results as
JSON outside the repo, and run `pearl-episodes preflight <json> --channel <device_id>-<channel_id>`
(`src/pearl_episodes/operate/preflight.py`, pure functions, no network). Per channel it checks: device online,
storage `ready` with free space above a floor (our policy, default 10 GB; a full drive overwrites the oldest
files), recorder stopped, no no-signal warning, file type, and file size limit. The kb says a channel controlled
by Edge must record MP4 with a 500 MB maximum file size, so a larger limit or another type fails. A Pearl reports
`recorder.file_format` values such as `MP4 Fragmented`, and the kb does not say whether Edge accepts that, so it
is shown as `UNVERIFIED` and does not fail the run. Device and channel warnings are copied verbatim.

**Session log.** `src/pearl_episodes/operate/session_log.py` appends one JSON line per action to
`sessions/<session_id>.jsonl` (gitignored, because it names devices and operators). Each line has `machine_ts`
(this computer's clock, UTC, with no meaning for any device's clock), `tool`, `args`, `result_summary`,
`warnings` (verbatim), an optional take `verdict` (`keep` or `discard`) and a `note`. Lines are only ever
appended. A line that holds a credentialed URL is refused, and a session id must be a plain file name.
`pearl-episodes preflight --session <id>` writes the first entry type; start, stop and the take verdict come
with the session script. The manifest's `session_id` points at this file.

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

## DROID, the target dataset (read 2026-10-15)

Sources: https://droid-dataset.github.io/droid/the-droid-dataset.html and `lerobot/droid_1.0.1` on the Hugging
Face Hub (`meta/info.json`). The DROID site describes 76k trajectories, about 350 hours; the LeRobot copy's
`info.json` reports 95,658 episodes and 27,630,375 frames at 15 fps. Neither page explains the difference, so
this repo cites each number with its source and does not reconcile them.

- **RLDS** (`gs://gresearch/robotics/droid`, 1.7 TB; `droid_100`, 2 GB, is the debugging subset).
  `episode_metadata`: `recording_folderpath`, `file_path`. Each step: `is_first`, `is_last`, `is_terminal`,
  `language_instruction`, `language_instruction_2`, `language_instruction_3`, `observation` (`gripper_position`,
  `cartesian_position`, `joint_position`, `wrist_image_left`, `exterior_image_1_left`,
  `exterior_image_2_left`, images `180 x 320 x 3` uint8), `action_dict`, `action`, `discount`, `reward`.
- **Raw** (`gs://gresearch/robotics/droid_raw`, 8.7 TB): per episode `metadata_*.json`, `trajectory.h5`,
  `recordings/MP4/*.mp4`, `*-stereo.mp4` and `recordings/SVO/*.svo`.
- **LeRobot copy** (codebase `v3.0`): cameras `observation.images.wrist_left`, `exterior_1_left`,
  `exterior_2_left`, each AV1, `yuv420p`, 320 x 180, 15 fps; plus state, action, language, `building`,
  `collector_id`, `date` and camera extrinsics columns. One episode's files are about 1.7 GB (three video shards
  of about 500 MB and about 170 MB of parquet), because v3 packs many episodes per file.
- What a Pearl episode can fill: camera images, `is_first` / `is_last` / `is_terminal`, `language_instruction`
  and episode metadata. It cannot fill state or action.

## LeRobot v3.0 export

`pearl-episodes export <episode_dir>` writes `<episode_dir>/lerobot` from a packaged episode
(`src/pearl_episodes/export/lerobot_v3.py`). The layout follows `lerobot` 0.6.1 (checked 2026-10-15 against its
`lerobot/datasets/utils.py` and `dataset_metadata.py`): `meta/info.json` (`codebase_version "v3.0"`),
`meta/stats.json`, `meta/tasks.parquet`, `meta/episodes/chunk-000/file-000.parquet`,
`data/chunk-000/file-000.parquet`, `videos/observation.images.<channel_name>/chunk-000/file-000.mp4`.

- Pearl's H.264 is copied as it is. The `video.*` values (`codec`, `pix_fmt`, `height`, `width`, `fps`) come
  from ffprobe on the joined file. Encoder settings LeRobot would add when it encodes (`video.g`, `video.crf`,
  `video.preset`) are absent, because Pearl was the encoder.
- No `action` and no `observation.state`: Pearl records video only. A lab joins its own step table.
- The step table has one row per frame of the shortest camera, `timestamp = frame_index / fps`. The format
  indexes cameras by frame number; this code claims nothing about timing between cameras. When frame counts
  differ, the manifest gets an incident and each video is kept in full.
- Refused with a clear error: cameras with different frame rates, a non-integer frame rate (LeRobot stores
  `fps` as an integer), two camera names that make the same key.
- LeRobot's `merge_datasets` needs `video.codec`, `video.pix_fmt`, `video.height`, `video.width` and
  `video.fps` to match across sources, so a Pearl episode sits beside a DROID episode, not inside it, unless
  it is re-encoded (bench issue #11 measures that).
- Verified: `tests/test_lerobot_loader.py` opens an export with `LeRobotDataset` (lerobot 0.6.1, `pyav`
  backend) and decodes the first and last frame. `torchcodec`, LeRobot's default decoder, supports FFmpeg 4
  to 8; with FFmpeg 9 installed it cannot load and LeRobot falls back to `pyav` by itself.

## Pearl REST API (verified against the published OpenAPI spec, 2026-10-14; re-checked 2026-10-16)

Source: `epiphan-video/pearl_api_swagger_ui`, `api/v2.0/openapi.yml`, 64 paths (the repo's last update is
2026-06-09, and the 2026-10-16 re-check found the same 64 paths), and the kb.epiphan.com REST pages cited in
`.claude/PLAN.md` §2. Base `/api/v2.0`, HTTP Basic auth, every response
`{"status": "ok", "result": ...}`. The client always uses `https://` and verifies TLS unless
`PEARL_VERIFY_TLS=false`; it assumes HTTPS is enabled on the device. The kb says `http://` is the default and
`https://` applies "if HTTPS is configured on the device", so a device that has not enabled HTTPS needs that
changed before the first run. Epiphan's "Automate your Pearl with the REST API" guide (September 2026, firmware
4.24.1 and later) agrees with the spec on every call it covers.

kb page for each call the client makes (all `pearl-family/`, applies to Pearl-2, Pearl Mini, Pearl Nexus and
Pearl Nano):

| Call | kb page |
|---|---|
| `GET /recorders`, `POST /recorders/control/start` and `/stop` | `pearl-rest-api-start-and-stop-recording` |
| `GET /recorders/status`, `GET /recorders/{rid}/status`, `GET /recorders/{rid}/archive/files`, `GET /recorders/{rid}/archive/files/{fid}` | `pearl-rest-api-check-recorder-status-and-download-recordings` |
| `GET /system/ident`, `GET /system/firmware` | `pearl-rest-api-check-firmware-version-and-device-identity` |
| base path, Basic auth, `http` or `https` | `pearl-rest-api-base-url-authentication-and-versioning` |

Two kb details the code relies on. Start and stop are asynchronous: `{"status": "ok"}` "confirms the command was
processed, not that recording has begun", so poll status. Without `ids`, `POST /recorders/control/start` starts
all recorders on the device, so `PearlClient.start_all` and `stop_all` need `ids` or an explicit
`all_recorders=True` and refuse an empty call. On Pearl Nano the kb says there is one channel and no multitrack recorders.
`/system/ident` returns name, location and description only, so the device serial number comes from Edge.

Used here: `GET /recorders`, `GET /recorders/status` (optional `ids`; items carry `id`, `name`, `status`) and
`GET /recorders/{rid}/status` (`state` is `disabled | starting | started | stopped | error`, plus `duration`,
`active`, `total` and, on error, `description`), `GET /recorders/{rid}/archive/files` (paged with `from` and
`limit`), `GET /recorders/{rid}/archive/files/{fid}` (raw media), `POST /recorders/control/start` and `/stop`
(optional `ids` query, asynchronous), `GET /system/ident`, `GET /system/firmware`.
Archive file fields: `id, name, extension, recording, downloaded, created, duration, size, recorder, uploading,
event_id`. File names carry a prefix plus date and time with no documented format, so the manifest records
`created` from the API and never parses the name. The spec types `created` as `date-time` and does not say
whether it carries a timezone, so it stays raw text until a bench device shows what it returns.

**In the spec, not used yet** (nothing here is relied on until it has run on a bench device):

- `POST /channels/{cid}/bookmarks` adds a bookmark to an archive file while the channel records, MP4 or MOV
  only. The spec's one required query parameter is `text` ("Bookmark name"). How a bookmark shows up in the file
  or in the archive listing is not documented, so whether it can carry a per-take label is a bench test.
- `GET /system/storages` and `/system/storages/{stid}/status`: a device-side storage check, so a preflight could
  also run against the Pearl itself and not only through Edge.
- `GET /system/singletouchcontrol/{stcid}/state` (combined state of recorders and publishers),
  `GET /afu/status`, `GET /system/status`, and `/schedule/events` for events on the device.
- Writes that would need the same approval as an Edge write: `/system/presets/{pid}/control/apply`,
  `/system/control/reboot`, `/system/control/factoryreset`.
- Not in the spec: any call that returns the Date and Time protocol (NTP, PTP or manual). `clock_source` still
  comes from the operator reading the Admin page.

**EC20.** The same repo publishes a separate EC20 spec (`api/ec20/v1/openapi.yml`, 44 paths, base
`http://{camera-ip}/api/v1`): PTZ movement, presets, focus, image and streaming settings, and `/misc/record`
(get and set recording state on the camera). It is not used. Where the camera records to is not in the spec.
Whether PTZ preset recall gives repeatable framing across takes is a bench question.

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

Added in Sprint 1 (`.claude/PLAN.md` section 6, items 12 and 13): the file frame rate for 59.94 and 29.97 Hz
sources, and guidance on the key frame interval for recordings used for training. No answer from Product is
recorded yet. An answer goes here with its written source; anything without one stays open.
