# Architecture

## Three layers

| Layer | Runs where | Talks to | Output |
|---|---|---|---|
| Operate | Claude Code session | Epiphan Edge via MCP (`get_devices_in_my_team`, `batch_recording`, `get_channel_image`, storage and recorder status) | Session log: which devices and channels recorded, when, with what warnings |
| Pull and package | `pearl_episodes` (this package) | Each Pearl's REST API; local disk; optional S3/SFTP where AFU already delivered the files | One episode directory per take: videos, `steps.parquet` or `.csv`, `manifest.json`, `hashes.txt` |
| Analyze | Notebook on the Mac (LeRobot) or Colab/RunPod (OXE models) | The episode directories | Plots, comparisons, model predictions |

## Episode manifest (the audit trail, in software)

Fields: `episode_id`, `device_serial`, `device_model`, `firmware`, `channel_id`, `channel_name`, `start_time` (device clock), `duration_s`, `file_name`, `file_size`, `sha256`, `task_label`, `operator`, `scene`, `clock_source` (ntp | ptp | unknown), `notes`. Everything the product does not carry today lives here.

## Pearl REST API facts to verify before use

From the product documentation (kb.epiphan.com, pearl-family/pearl-rest-api-*): recordings are listed per recorder with `id, name, extension, recording, downloaded, created, duration, size, recorder, uploading, event_id`; download is per file; the bulk start and stop endpoints are asynchronous and take an optional `ids` subset. The exact URL prefix and auth scheme must be confirmed on a real device before the client is trusted. File names carry a prefix plus date and time; the format is not documented, so the manifest records `created` from the API and never parses the name.

## Rules that shape the code

- No claim about multi-camera alignment anywhere in code, docs or output. Record `clock_source` and leave interpretation to Product.
- Recording actions target channels, not devices. A channel address for Edge batch tools is `<device_id>-<channel_id>`.
- Edge-controlled recordings are MP4 with a 500 MB cap; files roll every 30 minutes or 500 MB by default. The packager must stitch segments of one take.
- Recordings may contain people. They never leave the machine they were pulled to unless the lab says so.

## Open product questions this code should not guess at

USB camera ingest; a second simultaneous copy; simultaneous 1080p60 channel count; per-take labels by API; per-file hash at close; custom applications on the Apps page; the next Pearl.
