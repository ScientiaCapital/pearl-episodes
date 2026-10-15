# Bench hardware

Tim's own gear, so development never touches Epiphan's shared demo fleet. The **Pearl Mini with an EC20 is the
built PoC reference station**; a **Pearl Nano** is on the way as a second recorder. The intended production
station is the next Pearl; it is unannounced, so no spec of it appears here, and the code treats camera and
channel counts as data so moving to it is configuration. Facts below are quoted from
kb.epiphan.com (pages cited, read 2026-10-14); anything else is marked as a bench test.

| Device | Role | Documented facts to design around |
|---|---|---|
| Pearl Mini | PoC station recorder | Inputs: (1) 3G-SDI, (2) HDMI 1.4a, (2) rear USB 3.0 (UVC), but "Only one USB (UVC) video source can be connected at a time". Recommended "up to three 1080p30 channels and up to three 1080p video inputs"; HDMI and SDI to 60 fps; USB and IP 1080p30 recommended, higher "not guaranteed". Captures up to 1920×1200. H.264 4:2:0, 8-bit, 1 to 50 Mbps. Storage is user-supplied: SD card or SATA M.2 2280 SSD (SSD on units bought after 1 June 2024). Portable desktop, VESA-mountable, 1.7 kg. (`pearl-mini/pearl-mini-tech-specs`, `pearl-family/av-inputs`, `pearl-family/storage`) |
| EC20 | Station camera | Outputs HDMI 2.0, 3G-SDI, USB and network (NDI\|HX3, SRT, RTSP); "can simultaneously output up to three HD digital signals"; DC or PoE+ power. A camera, not a recorder. (`ec20/ec20-ptz-camera-overview`, `ec20/ec20-feature-list`) |
| Pearl Nano | Second recorder | One channel, no multi-track recorders. HDMI, SDI, RTSP and SRT inputs, one IP input at a time; no USB video input. H.264 and H.265, 4:2:0, 8-bit. PoE+ (802.3at) or DC. (`pearl-nano/what-is-pearl-nano`, `pearl-nano/pearl-nano-tech-specs`) |

## The PoC station for a DROID rig

A DROID station is a Franka arm, two ZED 2 exterior cameras, a wrist ZED Mini and a Quest 2 on a wheeled desk
that moves between scenes (droid-dataset.github.io). The Epiphan station rides on the same cart and records the
workspace independently:

- Pearl Mini, two EC20s on its two HDMI inputs, placed beside the two ZED 2s. One channel per camera.
- Local SSD; set the channel bitrate high (not auto) and leave the file type MP4 if Edge will control it.
- Edge for remote start, stop and status.

What it records: color video only, H.264 4:2:0 8-bit. Depth and robot state stay on the lab's own stack. It does
not record the lab's ZED feeds: a USB camera connects to one host, and a ZED 2's UVC stream is side-by-side stereo
(3840×1080, 2560×720 or 1344×376, per Stereolabs), so only its smallest mode fits the Mini's 1920×1200 limit.

## First bench session

1. Fit storage in the Mini, set a device name and an admin password, note its IP, copy `.env.example` to `.env`.
   A Mini with a self-signed certificate needs `PEARL_VERIFY_TLS=false`.
2. `uv run pearl-episodes doctor`, then `uv run pearl-episodes list <recorder_id>` (ids from `GET /recorders`).
3. EC20 into the Mini over HDMI. Record 60 seconds at three bitrates (for example 8, 20 and 40 Mbps).
4. Pull, hash and write the manifest. Open the file in a player with the manifest beside it.
5. Package one take with no re-encode and once at LeRobot's default (AV1, `yuv420p`, crf 30); compare size and
   image quality. This is the number Product asked for.
6. Bench tests, not claims: a ZED 2 (1344×376 mode) and a RealSense color stream on the Mini's USB input.
7. Add the Nano and run a take through bulk start and stop. Record `clock_source` for each device from its Date
   and Time page. Do not interpret it or claim anything about alignment.

## Edge

The REST API works directly against a device with its admin credentials. Putting the bench devices in an Edge
team adds the MCP (reads free, writes need Premium) and the dashboard. Keep them in a team separate from
Epiphan's demo fleet, or leave them out of Edge for the first sessions.

## Audio

Pearl-2, Pearl Mini and Pearl Nexus take Dante audio with firmware 4.24.6+ and the paid Dante audio feature add-on
(Mini: two channels, one stereo input). Useful only if a lab records audio at the station; ask before planning
for it. (`pearl-family/dante-audio-on-pearl-devices`)

## Containers on Pearl (Product's early view, 2026-10-14)

Product has said informally that containers on Pearl Nano look feasible, with kernel work. That is an
expectation, not a shipped capability or a commitment. Whether a custom application can be installed the way the
Echo360 integration is (from the Apps page) is an open question for Product. Treat an on-device manifest writer
as the stretch goal, and do not describe containers on Nano to anyone outside the company until Product confirms
it in writing. The Nano arriving on the bench is the natural test.
