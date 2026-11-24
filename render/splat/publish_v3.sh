#!/bin/bash
# publish_v3.sh : join staged parts -> clean/tiers -> floors -> spz -> repo
set -e
S="/mnt/user-data/uploads/3d Rendering--Projects/sky-tree-tower/render/out/sp"; W=/home/claude/v3; mkdir -p $W; cd $W
cat "$S"/v3.part* > full.spz; ls -l full.spz
cd /home/claude/splattools && npx splat-transform -w $W/full.spz $W/full.ply >/dev/null 2>&1
cd $W && python3 /home/claude/v2b_fix/tools/tiers.py full.ply clean.ply m.ply 1300000 p.ply 300000
rm -rf floors && mkdir floors && python3 /home/claude/skytree-Fv2/render/splat/make_floors.py m.ply /home/claude/skytree-Fv2/public/skytree/media/levels.json floors | tail -2
cd /home/claude/splattools
mkdir -p $W/floors_spz
(for f in clean m p; do echo "$W/$f.ply $W/$f.spz"; done; for f in $W/floors/*.ply; do echo "$f $W/floors_spz/$(basename $f .ply).spz"; done) | xargs -P 2 -n 2 sh -c 'npx splat-transform -w "$0" "$1" >/dev/null 2>&1'
ls -la $W/*.spz; du -sh $W/floors_spz
