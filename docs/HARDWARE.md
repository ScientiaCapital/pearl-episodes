# Bench hardware

Tim's own gear, so development never touches Epiphan's shared demo fleet: a **Pearl Mini** and an **EC20** at
home, and a **Pearl Nano** on the way.

| Device | Role on the bench | Facts from product documentation to design around |
|---|---|---|
| Pearl Mini | Recorder, up to three 1080p30 channels | No factory SSD: recording needs a customer-fitted SATA SSD or SD card. Without storage the Admin panel warns "Storage is not ready" and nothing records. |
| EC20 | The camera | HDMI 2.0, 3G-SDI, USB, NDI\|HX3, SRT and RTSP outputs; one high-quality network stream plus one preview, up to 60 fps. It is a camera, not a recorder: Edge shows it for monitoring and firmware only. |
| Pearl Nano | Second recorder, one channel | Single input, PoE+ capable. A second device makes batch start and stop across devices testable. |

## First bench session

1. Put storage in the Mini, set a device name and an admin password, note its IP, copy `.env.example` to `.env`.
2. `uv run pearl-episodes doctor`, then `uv run pearl-episodes list <recorder_id>` (recorder ids come from
   `GET /recorders`).
3. EC20 into the Mini over HDMI or SDI (60 fps capable) or over NDI|HX3, SRT or RTSP. Record 60 seconds.
4. Pull it, hash it, write the manifest. Open the file in a player and the manifest beside it.
5. Add the Nano as a second device and run the same take through bulk start and stop. Record `clock_source`
   for each device from its settings page. Do not interpret or claim anything about alignment.

## Edge

The REST API works directly against a device with its admin credentials. Putting the home devices in an Edge
team adds the MCP (reads free, writes need Premium) and the dashboard. Keep them in a team separate from
Epiphan's demo fleet, or leave them out of Edge for the first sessions.
