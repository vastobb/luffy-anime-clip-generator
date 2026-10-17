# 🏴‍☠️ Luffy Anime Clip Generator — procedural cel animation

Anime-style clips of a straw-hat pirate boy, **drawn by math — not by an AI model**.
Every frame is generated from vector geometry and rasterised into animation cels
on a GitHub Actions runner, then encoded with ffmpeg. No models, no weights, no
downloads, no GPU.

```
math (bezier / capsules / FK rig)  ->  cel masks (PIL + numpy)  ->  ffmpeg  ->  mp4 + gif
```

> Fan-made animation experiment. One Piece and Monkey D. Luffy are ©
> Eiichiro Oda / Shueisha. Not affiliated with or endorsed by the rights holders.

## How a frame is made (the same way a cel is painted)

1. **Rig** — the character is a parametric skeleton: pelvis → spine → head plus
   two-bone arms and legs, solved with forward kinematics
   ([`luffy_clip/rig.py`](luffy_clip/rig.py)). Proportions, palette, open red
   vest, yellow sash with a fluttering tail, denim shorts, sandals, and the
   straw hat (dome + red band + brim, including the shadow the brim casts across
   the forehead).
2. **Cel masks** — each part is rasterised at `--supersample`× resolution and
   downscaled with Lanczos, so silhouettes are anti-aliased
   ([`luffy_clip/cel.py`](luffy_clip/cel.py)).
3. **Second tone + ink line** — the shadow is a *crescent* (the mask minus a
   shifted copy of itself, restricted to the shape) and the outline is a *band*
   (the mask minus its eroded copy). That is literally how a cel is painted:
   flat colour, second tone, inked line — which is why limbs keep clean outlines
   where they join.
4. **Animation** — poses are keyframed and blended with anime timing
   (ease-out bursts, elastic snap-backs, holds), cycles are sine-driven, the
   rubber arm is a bezier ribbon with **motion-smear ghost copies**, and every
   effect is procedural: radial speed lines, impact stars, shockwaves, dust,
   steam, cannonball splashes, spinning god-rays, sparkles, and even
   impact-frame white flashes ([`luffy_clip/scenes.py`](luffy_clip/scenes.py),
   [`luffy_clip/bg.py`](luffy_clip/bg.py)).
5. **Shot on twos** — drawings are rendered at `draw_rate` 12/s and the mp4 is
   encoded at 24 fps, so each drawing is held for two frames, exactly like
   hand-drawn TV anime.
6. **Encode** — ffmpeg (a static binary bundled by `imageio-ffmpeg`, since
   GitHub runners no longer ship one) produces H.264/yuv420p/faststart MP4s and
   small looping GIF previews.

Everything is deterministic: the same `--seed` reproduces the same clip
(`manifest.json` records sizes, durations and sha256 of every output).

## Scenes

| scene | length | what happens |
| --- | --- | --- |
| `gear_second` | 4.0 s, one-shot | crouch wind-up → white activation flash → red aura, steam, radial speed lines, gear sprint |
| `gum_gum_pistol` | 4.5 s, one-shot | rubber arm stretches at the camera with smear ghosts → impact star + shockwave rings + recoil snap |
| `marine_chase` | 4.0 s, loops | run cycle on a scrolling deck, cannonball splashes, dust puffs, camera shake |
| `sunny_figurehead` | 5.0 s, loops | calm establishing shot: clouds, god-rays, seagulls, sea sparkles, slow zoom-in |
| `sunset_silhouette` | 5.0 s, loops | ending-shot look: silhouette with a warm rim light against a sunset, reflection column, birds |

## Run it in the cloud

**Actions → Generate Luffy Clip → Run workflow.** Inputs:

| input | default | notes |
| --- | --- | --- |
| `scene` | `all` | any single scene, or `all` to stitch every scene into one **reel** |
| `resolution` | `1280x720` | `1920x1080` and `960x540` also offered |
| `supersample` | `2` | `3` gives crisper ink lines, ~1.6× slower |
| `draw_rate` / `fps` | `12` / `24` | the "on twos" pair; `24`/`24` renders on ones |
| `seconds` | `0` | `0` = use each scene's own timing |
| `seed` | `42` | FX jitter / sparkles / dust |
| `publish_release` | `true` | attach everything to a GitHub Release |

Outputs per run: every scene as `mp4` + `gif`, a stitched `luffy_reel.mp4` +
`luffy_reel.gif`, and `manifest.json`. All of it is uploaded as a build artifact
and (optionally) published as a release whose page previews the GIF inline.

Typical cost on a standard 4-vCPU runner: the full 22.5 s reel at 720p /
supersample 2 is ~270 drawings ≈ 10–15 minutes; a single 4 s scene is ~2–3
minutes. Nothing is installed or downloaded on your machine.

## CLI (same code the workflow runs)

```bash
python -m pip install -r requirements/base.txt

# whole reel, 720p
python -m luffy_clip.cli --scene all --out out

# one scene at 1080p with crisper lines
python -m luffy_clip.cli --scene gum_gum_pistol --width 1920 --height 1080 \
    --supersample 3 --out out

# on ones (24 drawings/second) and a different seed
python -m luffy_clip.cli --scene marine_chase --draw-rate 24 --fps 24 --seed 7
```

## Repository layout

```
luffy_clip/vec.py         vector math: beziers, splines, capsules, easing, FK
luffy_clip/cel.py         cel canvas: masks, second tone, ink outlines, textures
luffy_clip/rig.py         the character: proportions, palette, poses, faces
luffy_clip/bg.py          skies, sea, deck, speed lines, impact stars, steam
luffy_clip/scenes.py      five scene timelines (pose keys + FX choreography)
luffy_clip/render.py      frame loop -> mp4/gif (draw rate vs playback rate)
luffy_clip/postprocess.py ffmpeg helpers + dependency-free MP4 probing
luffy_clip/cli.py         command line entry point
scripts/make_release_notes.py  renders the release page (inline GIF + tables)
.github/workflows/        generate-luffy-clip.yml (render) + ci.yml (tests)
tests/                    math, cel, scene and renderer tests
```

## Tests

`python -m pytest -q` runs the math layer, cel-mask/outline behaviour, scene
smoke tests (non-blank frames, real motion between frames), GIF-loop
seamlessness, and renderer plumbing. CI also renders a 3-frame smoke clip with
the real ffmpeg pipeline.

## License

MIT (code). Generated media is fan art.
