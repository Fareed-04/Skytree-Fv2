#!/bin/bash
# enc.sh <frames_dir> <name_fwd> <name_rev> <outdir>
set -e; D="$1"; OUT="$4"; mkdir -p "$OUT" /tmp/rev_$$
n=$(ls "$D"/f_*.jpg | wc -l); i=1
for f in $(ls "$D"/f_*.jpg | sort -r); do cp "$f" /tmp/rev_$$/f_$(printf %03d $i).jpg; i=$((i+1)); done
for pair in "$D:$2" "/tmp/rev_$$:$3"; do src=${pair%%:*}; nm=${pair##*:}
  ffmpeg -y -loglevel error -framerate 30 -i "$src/f_%03d.jpg" -vf "scale=1600:900:flags=lanczos,format=yuv420p" -c:v libx264 -preset slow -crf 20 -movflags +faststart -an "$OUT/$nm.mp4"
  ffmpeg -y -loglevel error -framerate 30 -i "$src/f_%03d.jpg" -vf "scale=960:540:flags=lanczos,format=yuv420p" -c:v libx264 -preset slow -crf 23 -movflags +faststart -an "$OUT/${nm}_s.mp4"
done
rm -rf /tmp/rev_$$; ls -la "$OUT"
