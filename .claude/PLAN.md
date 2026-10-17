# Plan: one Pearl take to one packaged episode

Written 2026-10-14 from `docs/PROMPT.md`. No code until Tim has read this.
Sources: kb.epiphan.com pages cited inline (fetched 2026-10-14, page dates 2026-10-07 to 10-13), the Open
X-Embodiment README and paper (arXiv 2310.08864), and `docs/ARCHITECTURE.md`. The internal context documents
are not quoted here.

## 0. What the sources say that shapes the design

- **RLDS is the OXE storage format.** README: "each episode is represented using the RLDS episode format",
  loaded with `tfds.load`. Paper §III-A: RLDS as "serialized tfrecord files", and it accommodates "differing
  numbers of RGB cameras, depth cameras and point clouds". The paper counts 60 datasets from 34 labs; the
  dataset sheet now has 72 rows. Cite both numbers with their dates.
- **OXE models use one camera.** Paper §IV-A: RT-X uses "one canonical camera view" from each dataset,
  resized to a common resolution. A Pearl episode is useful to a model with a single camera, and extra cameras are optional.
- **The paper makes no statement about timing or alignment during collection.** Neither does this plan (rule 1).
- **Pearl rolls files.** "The default recording limits are set to 30 minutes or 500 MB, whichever comes first.
  When the time or file size limit is reached, the current recording is saved and a new recording file starts
  automatically without losing any content." (`pearl-family/about-recording`). Under Edge control: "must be set
  to MP4 and the maximum file size supported is 500 MB" (`pearl-family/configure-recording-settings-file-size-and-type`).
- **Other documented behaviour the packager has to handle** (`pearl-family/about-recording`): unplugging a source does not stop
  recording ("A No Signal image is inserted"); "When the local drive is full, newer recordings overwrite oldest
  recordings"; an auto channel starts a new file when its source switches; a multi-track recorder starts a new
  file when a source is added mid-recording.

## 1. One episode on disk

The source of truth is the original Pearl files, hashed and never modified. Each export layout is derived from them.

```
episodes/<episode_id>/                    # gitignored
  manifest.json                           # section 4
  hashes.txt                              # sha256 of every original and every derived file
  source/<channel_id>/<file_id>.<ext>     # Pearl originals, untouched, one or more segments per camera
  lerobot/                                # derived
  rlds/                                   # derived
```

**LeRobot v3.0, built (lerobot 0.6.1; the Hub copy of DROID is also v3.0, so v2.1 is not used):**
```
lerobot/meta/info.json                    # codebase_version v3.0, fps, features; video.* probed from the file
lerobot/meta/stats.json
lerobot/meta/tasks.parquet                # task = manifest task_label
lerobot/meta/episodes/chunk-000/file-000.parquet
lerobot/data/chunk-000/file-000.parquet
lerobot/videos/observation.images.<channel_name>/chunk-000/file-000.mp4
```
The step table holds one row per frame of the shortest camera: `timestamp = frame_index / fps` (fps probed from
the file, one integer for all cameras), `frame_index`, `episode_index`, `index` and `task_index`. **There is no
robot state or action:** Pearl records video only. Those columns stay absent until a lab's own step table is
joined, and that join is the lab's. The format indexes cameras by frame number; this project claims nothing about
timing between cameras. Details and the checked 0.6.1 sources are in `docs/ARCHITECTURE.md`.

**RLDS:** one tfds episode with `steps`, where each step has `observation/<channel_name>` (image),
`is_first`, `is_last`, `is_terminal` and `language_instruction` (= task_label). `action` and `reward` are
absent, as above. Episode metadata carries `episode_id` and the manifest path. It is built with a tfds builder
under the optional `datasets` extra (unpinned until the first verified install).

## 2. Pearl REST calls and the page that documents each

Base `/api/v2.0`, HTTP Basic auth, `https://` when configured
(`pearl-family/pearl-rest-api-base-url-authentication-and-versioning`).

| Step | Call | Documented on | In `client.py` |
|---|---|---|---|
| Identify device | `GET /system/firmware`, `GET /system/ident` | `pearl-family/pearl-rest-api-check-firmware-version-and-device-identity` | yes |
| Find recorders | `GET /recorders` (`id`, `name`, `multisource`) | `pearl-family/pearl-rest-api-start-and-stop-recording` | yes |
| Start / stop (bench only; Edge in sessions) | `POST /recorders/control/start\|stop?ids=` | same page. "These calls are asynchronous" | yes |
| Confirm state | `GET /recorders/status?ids=`, `GET /recorders/{rid}/status` (`disabled, starting, started, stopped, error`) | `pearl-family/pearl-rest-api-check-recorder-status-and-download-recordings` | yes (`recorder_status`, `recorder_status_one`) |
| List files | `GET /recorders/{rid}/archive/files?from=&limit=` | same page | yes |
| Download | `GET /recorders/{rid}/archive/files/{fid}` (octet-stream; 404 if missing) | same page | yes |

The device serial is not in the REST API, so it comes from Edge (`get_devices_in_my_team`). The device name defaults to
the serial but is editable (`pearl-2/configure-system-settings`), so it is never used as the serial.

Fixes to `client.py` before `pull`: add recorder status; move the blocking `open`/`write` in `download` and
`manifest.write` off the event loop (`anyio.to_thread` or `aiofiles`), as rule 3 requires.

## 3. Stitching a take that rolled over

1. A **take** is the span between one start and one stop on a recorder. Membership is decided from the session
   log (section 5) when there is one. Otherwise: files on the same recorder whose `created` falls within the take
   window, ordered by `created` and then by `id`. **File names are never parsed** (their format is undocumented).
2. Skip any file with `recording: true`. It is still being written, so `pull` retries it later.
3. Keep every segment as a separate original in `source/` and list it in the manifest in order, with
   `created`, `duration`, `size` and `sha256`.
4. **Decision: keep the segments and derive one joined video per camera for the export layouts only**, by
   lossless remux (ffmpeg concat with `-c copy`, no re-encode). The joined file gets its own hash. Reason: lab
   tools expect one video per camera per episode, and the originals stay provable byte-for-byte. The manifest
   records the segment boundaries and makes no statement about continuity across them beyond quoting the kb
   sentence. If the remux fails (codec change mid-take, for example after a source switch on an auto channel),
   the episode is exported as several sub-episodes and the reason is noted.
5. Pearl-2 multi-track recorder: one file holds several channels (`pearl-2/multi-track-recorders`). The
   packager splits the tracks into per-camera videos by remux. Whether a multi-track file means anything for
   cross-channel timing is a Product question (section 6), not an assumption.

## 4. What the manifest carries that the product does not

Already in `episodes/manifest.py`: `episode_id`, `device_serial` (from Edge), `device_model`, `firmware`,
`start_time` (device clock, from `created`), per-camera `channel_id`, `channel_name`, `file_name`,
`file_size`, `sha256`, `duration_s`, plus `task_label`, `operator`, `scene`, `clock_source`, `notes` and
`schema_version`.

Proposed additions (schema_version 2):
- `segments[]` per camera: `file_id`, `created`, `duration`, `size`, `sha256`, `recorder_id`, `event_id`.
- `derived[]`: path, sha256, tool and version (ffmpeg, lerobot, tfds).
- `session_id`: link to the operator log in section 5.
- `incidents[]`: warnings seen during the take (low storage, recorder `error` with its `description`,
  "No Signal" reported by the operator), copied verbatim from tool output.
- `clock_source`: `ntp | ptp | manual | unknown`, recorded as read and never interpreted. **Adding `manual`**: the
  Date and Time page lets time be set by hand (`pearl-2/configure-system-settings`).

The product carries none of these per take. Its four static channel metadata fields are per channel, not per
recording.

## 5. An operator session over Epiphan Edge MCP

The log goes to `sessions/<session_id>.jsonl` (`sessions/` is gitignored: it names devices and operators). The
writer is built (`operate/session_log.py`, 2026-10-16) and `preflight --session` uses it; the script that adds
start, stop and the take verdict is not.
There is one line per action: `ts` (machine clock, labelled as such), `tool`, `args` (with secrets masked by the
existing hook), `result_summary` and `warnings`.

1. **Preflight, read only (built 2026-10-16, `/preflight`):** `get_devices_in_my_team` → `get_device_info`; `get_storage_status_for_devices`
   (refuse to start below a free-space floor set in Settings, because a full drive overwrites the oldest
   files); `get_system_status_for_devices`; `get_recorder_status_for_devices`.
2. **Ask:** print the device, the channels (`<device_id>-<channel_id>`) and the expected effect, then wait for Tim's
   yes. This happens every time and is never batched.
3. **Start:** `batch_recording` start, then poll `get_recorder_status_for_devices` until each channel is
   recording or a limit is reached, and log what the tool reports.
4. **During the take:** `get_channel_image` is optional for a visual check. Log only that a frame was checked;
   never save it, and describe people by role only.
5. **Stop:** ask again, then `batch_recording` stop and poll until stopped.
6. **Pull and package:** `pearl-episodes pull` (REST, idempotent on file id), then `pearl-episodes package`
   with the take window from steps 3 and 5 and the operator's labels.

Sessions run on Tim's bench devices. The shared demo fleet is used only when Tim says so in that session.

## 6. Open questions for Product (answer before relying on any of them)

Recorded so far: Pearl records H.264 4:2:0 8-bit (Nano also H.265), which matches how LeRobot stores color
streams; depth (12-bit lossless in LeRobot) cannot ride on it and stays on the lab's stack.

1. Is there a documented REST call that returns the Date and Time protocol (NTP / PTP v1 / manual)? Until there is,
   `clock_source` comes from the operator reading the Admin page.
2. Do segment boundaries at the 30 min / 500 MB rollover remux cleanly with `-c copy`? Test this on the bench and do
   not assume it.
3. Does a multi-track file (several channels in one file) carry anything Product will state about the
   relationship between its tracks? If not, it is treated exactly like separate channel files.
4. USB (UVC) input is documented on Pearl-2 and Pearl Mini (Mini: one UVC source at a time, 1920×1200 max) and
   absent on Nano. Which lab cameras work in practice (ZED 2 side-by-side modes, RealSense color) is a bench test.
5. A second simultaneous copy of a recording, and the loss window on power loss.
6. Simultaneous 1080p60 channel count on Pearl-2, by input type.
7. Per-take labels by API or sidecar; a per-file hash at close; what the AFU log records and whether it can be exported.
8. Custom containers on the Apps page, which would let a manifest writer run on the device at record stop.
9. Whether Edge MCP `batch_recording` on a recorder already running is a no-op or an error (spec silent;
   verify on the bench).
10. Whether `created` in the archive listing is the file-open time or the take start time, and in which time zone.

11. Is there any Pearl path to a bit depth above 8 bits, or is "color video only, no depth" the wording?
12. What frame rate does a recording file carry when the source is 59.94 or 29.97 Hz and "Limit frame rate" is
    not set: the source rate (for example 60000/1001) or an integer? The LeRobot export needs one integer fps and
    refuses a non-integer rate with a clear error. Bench test first (#10), then Product.
13. Pearl's Key frame interval is a channel setting in seconds, with "a good rule of thumb ... between 2 to 3
    seconds" (`pearl-mini/configure-video-encoding`, page dated 2026-10-06). LeRobot's default encoder uses a
    keyframe every 2 frames (`g=2`) for fast random access in training loaders. The decode and seek cost of a
    longer interval is a bench measurement (#11). Does Product have guidance for recordings meant for training?

## 7. DROID is the target (decided 2026-10-14)

DROID is one rig replicated 18 times across 13 institutions (droid-dataset.github.io, arXiv 2403.12945), and most
of those campuses already run Pearl. So the first demo, the first export and the first lab conversation are all
DROID-shaped:

- **Station:** the Pearl Mini reference station with two EC20s on HDMI, on the DROID cart (`docs/HARDWARE.md`).
  The Mini is the PoC; the intended production station is the next Pearl (unannounced; nothing here depends on
  its specs until Product publishes them). So camera count, channels and recorders are data, never constants:
  the manifest's `cameras[]`, per-recorder pulls and the export's camera keys all come from the device listing.
- **Format bar:** LeRobot's DROID copy (codebase v3.0, 95,658 episodes) stores each camera as AV1, `yuv420p`, 320×180,
  15 fps (`lerobot/droid_1.0.1`, `meta/info.json`, read 2026-10-15). Pearl's H.264 4:2:0 is the same class of stream, so the LeRobot export
  keeps the H.264 as-is (LeRobot records `video.codec` per feature) instead of re-encoding.
- **Camera names:** DROID's RLDS exterior keys are `exterior_image_1_left` and `exterior_image_2_left`; the
  LeRobot copy names them `observation.images.exterior_1_left`, `observation.images.exterior_2_left` and
  `observation.images.wrist_left` (`lerobot/droid_1.0.1`, `meta/info.json`, read 2026-10-15). Our exports use
  `observation.images.<channel_name>`, and the notebook shows them side by side; we don't rename Pearl channels
  to pretend they are ZED views.
- **Demo:** one Pearl take, packaged, opened in the same notebook as a DROID episode.

## 8. Reuse, not rebuild: the Edge Claude Kit and Fleetwatch

- **Now:** the Kit's write guard and redaction hooks are used unchanged, with its tests and the redaction cases
  shared with Fleetwatch (`tests/hook-test.sh`, NOTICE).
- **Session script (§5):** take Fleetwatch's readiness check (picture present, unit online) plus a storage floor
  as the preflight, and its replay fixtures to test the script offline.
- **Unattended writes, later:** Fleetwatch v0.2's executor (single-use approval, fresh re-read, refuse while
  recording, sandbox fence) is the pattern, as a pinned dependency once Fleetwatch tags a release.
- **Direction:** this private repo depends on those public ones, never the reverse. Nothing about labs, the PoC
  or robotics goes into their issues, PRs or commits.

## 9. Build order once approved

`client.py` fixes (status call, envelope check, verified atomic downloads) → `pull` → `package` (manifest v2,
segments, hashes) → LeRobot export → **notebook beside a DROID episode** → bench codec test → RLDS export →
session script. Each step comes with tests against a mocked `httpx` transport and no network.

**Sprint 1 progress (2026-10-15):** built and merged: client envelope check, atomic downloads, recorder status,
`recorders`, CLI exit codes, manifest v2, `pull`, `package` (remux), LeRobot v3.0 export, the notebook beside a
DROID episode, and the test-gap sweep. Still open: the bench issues (#10 first session, #11 codec test, #12 USB
cameras) and Product's answers (#14). RLDS export and the session script follow the sprint.
