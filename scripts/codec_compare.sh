#!/usr/bin/env bash
# Compare a Pearl recording as it is (lossless remux, no re-encode) with the same file encoded at LeRobot's
# default video settings. For the bench codec test (issue #11); the numbers belong in a results note in docs/.
#
#   bash scripts/codec_compare.sh <pearl-file.mp4> [output-dir]
#
# LeRobot defaults (huggingface.co/docs/lerobot/main/en/video_encoding_parameters, read 2026-10-15):
# vcodec libsvtav1, pix_fmt yuv420p, g 2, crf 30, preset 12. Only those five are passed here.
# SSIM and PSNR compare the encoded file against the Pearl file; they say nothing about timing.
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 <pearl-file.mp4> [output-dir]" >&2
  exit 2
fi
input=$1
out=${2:-codec-compare-out}
mkdir -p "$out"

encode() { # encode <name> <ffmpeg output args...>
  local name=$1
  shift
  echo "+ ffmpeg -y -i $input $* $out/$name.mp4"
  ffmpeg -hide_banner -nostats -benchmark -y -i "$input" "$@" "$out/$name.mp4" 2> "$out/$name.log"
  grep -o 'rtime=[0-9.]*s' "$out/$name.log" | tail -1 | cut -d= -f2 > "$out/$name.seconds" || true
}

encode remux -map 0:v:0 -c copy
encode lerobot_default -map 0:v:0 -c:v libsvtav1 -pix_fmt yuv420p -g 2 -crf 30 -preset 12

echo
echo "reference: $input (video stream)"
echo "+ ffmpeg -i $out/lerobot_default.mp4 -i $out/remux.mp4 -lavfi '[0:v][1:v]ssim;[0:v][1:v]psnr' -f null -"
ffmpeg -hide_banner -nostats -i "$out/lerobot_default.mp4" -i "$out/remux.mp4" \
  -lavfi '[0:v][1:v]ssim;[0:v][1:v]psnr' -f null - 2>&1 | grep -E 'SSIM|PSNR' || true

echo
printf '%-18s %12s %10s\n' file bytes encode_s
for name in remux lerobot_default; do
  printf '%-18s %12s %10s\n' "$name" "$(wc -c < "$out/$name.mp4" | tr -d ' ')" "$(cat "$out/$name.seconds" 2> /dev/null || echo n/a)"
done
