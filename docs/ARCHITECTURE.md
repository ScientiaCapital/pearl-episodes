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

Added in Sprint 1 (`.claude/PLAN.md` section 6, items 12 and 13): the file frame rate for 59.94 and 29.97 Hz
sources, and guidance on the key frame interval for recordings used for training. No answer from Product is
recorded yet. An answer goes here with its written source; anything without one stays open.
