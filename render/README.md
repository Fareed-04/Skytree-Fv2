# Sky Tree Tower: render kit

Pre-rendered experience pipeline: exterior orbits with clickable floors, fly-through clips, 8K interior/amenity panoramas, and capture sets for Gaussian splats. Everything is rendered once on the RTX 5070 PC (Blender Cycles); visitors only stream finished images and video.

## Steps

| # | What | How |
|---|------|-----|
| 1 | Downloads: system check, ffmpeg, splat-transform, ~3 GB of CC0 skies/textures/trees | double-click `1-setup-downloads.bat` |
| 2 | Export the client's full 3ds Max scene (geometry, cameras, materials, textures) | see `max/MAX_EXPORT.md` |
| 3 | Build the Blender render scene from the export and match the client's reference renders | (next) |
| 4 | Render orbits, ID passes, fly-throughs, panoramas | (next) |
| 5 | Render the splat capture set and train in Postshot | (later, separate chat) |

## Folders

- `assets/`: downloaded Poly Haven assets (not in git)
- `from-max/`: output of the 3ds Max export (not in git)
- `scripts/`: Python / PowerShell used by the .bat files
- `max/`: the 3ds Max export script

## Reference

Client reference renders: `E:\3d Rendering\Projects\3d-model-from-client\reference-renders-and-images\`. They are Corona renders: warm beige limestone, dark slate mansard roofs, champagne-gold signage, dusk/night façade uplighting, dense green landscaping with jacaranda and palms, Lahore street context.
