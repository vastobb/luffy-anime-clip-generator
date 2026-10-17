# 🏴‍☠️ Luffy Anime Clip Generator

Turn a text prompt into a short **Monkey D. Luffy–style anime clip** — generated
entirely in the cloud by **GitHub Actions**. No local installs, no model
downloads, no GPU required on your machine.

> Fan-made generative experiment. One Piece and Monkey D. Luffy are ©
> Eiichiro Oda / Shueisha. Not affiliated with or endorsed by the rights holders.

## Demo

![Luffy clip demo](https://github.com/vastobb/luffy-anime-clip-generator/releases/download/clip-3/luffy_clip_run3.gif)

`sunny_figurehead` scene — 4 s, 768×512, 8 fps, rendered on a plain GitHub
runner CPU with no secrets and no GPU → [release clip-3](https://github.com/vastobb/luffy-anime-clip-generator/releases/tag/clip-3)
(MP4 + GIF + manifest).

## How it works

```
workflow_dispatch  ->  GitHub runner  ->  generative text-to-video model  ->  mp4 + gif
                        (ubuntu-latest)      hosted API  or  local CPU diffusion
```

1. You pick a scene preset (or type your own prompt) and press **Run workflow**.
2. The runner generates the clip with one of two backends:
   * **Hosted (best quality)** — a state-of-the-art text-to-video model called
     through the [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers/tasks/text-to-video)
     router: **Wan 2.2** (`Wan-AI/Wan2.2-TI2V-5B`), **LTX-Video** or
     **HunyuanVideo** running on cloud GPUs. Needs an `HF_TOKEN` secret.
   * **Free CPU fallback (zero setup)** — **AnimateDiff-Lightning** (4-step
     distilled AnimateDiff) on top of an **anime SD1.5 checkpoint**, rendered on
     the Actions runner itself. No secrets, no cost, smaller clips.
3. The result (`mp4` + looping `gif` preview + `manifest.json` with prompt,
   seed, parameters and sha256) is uploaded as a build artifact and optionally
   attached to a **GitHub Release**, where the gif renders right in the browser.

The anime look comes from the prompt tail in [`luffy_clip/prompts.py`](luffy_clip/prompts.py)
(`2D anime style, cel-shaded animation, Eiichiro Oda inspired art style, ...`)
plus a matching negative prompt, so even general-purpose video models produce a
cel-shaded anime clip.

## Quick start — free, no secrets

**Actions → Generate Luffy Clip → Run workflow → Run workflow** (leave the
defaults: `provider: auto`, `scene: gear_second`, `segments: 2`).

Because no `HF_TOKEN` secret is configured, `auto` selects the free CPU
renderer: ~2 clips of 2 s each, upscaled to 768×512, 8 fps, plus a GIF preview.
Expect ~13 minutes on a standard runner (≈6 min per 2 s segment; model
downloads are cached between runs). When it finishes, open the **clip-N**
release — the GIF preview is embedded in the release notes, and the MP4 is
attached as an asset.

## Best quality — hosted models (optional)

1. Create a Hugging Face token with the *Make calls to Inference Providers*
   permission: [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained).
2. Add it to the repo: **Settings → Secrets and variables → Actions → New
   repository secret** → name `HF_TOKEN`.
3. Run the workflow again with `provider: auto` (or `hf`).

| model | notes |
| --- | --- |
| `Wan-AI/Wan2.2-TI2V-5B` *(default)* | fast, 720p-class, excellent prompt following; available on `fal-ai` and `replicate` |
| `Wan-AI/Wan2.1-T2V-1.3B` | cheapest/fastest hosted option (`fal-ai`) |
| `Lightricks/LTX-Video-0.9.8-13B-distilled` | very fast, cinematic motion |
| `tencent/HunyuanVideo` | highest fidelity of the set, slower / more credits |

Hosted inference is billed to your Hugging Face account (free accounts get a
small monthly credit; `fal-ai` and `replicate` also work with your own API keys
through the same router). Generated clips are 24 fps / a few seconds depending
on the provider.

## Scenes

`gear_second`, `gear_fourth`, `gum_gum_pistol`, `sunny_figurehead`,
`sunset_silhouette`, `meat_feast`, `laughing_sky`, `marine_chase`

Or pass your own action with the `prompt` input / `--prompt` flag; the anime
style tail is appended automatically.

## CLI (same code the workflow runs)

```bash
# free CPU backend
python -m luffy_clip.cli --provider cpu --scene marine_chase --segments 2 --steps 4

# hosted backend
export HF_TOKEN=hf_...
python -m luffy_clip.cli --provider hf --hf-provider fal-ai \
  --model Wan-AI/Wan2.2-TI2V-5B --scene gear_fourth --hf-steps 8

# custom prompt, 3 segments, no gif
python -m luffy_clip.cli --provider cpu \
  --prompt "Monkey D. Luffy fighting a giant sea king, dramatic waves" \
  --segments 3 --no-gif
```

(If you *do* run it locally, the CPU backend downloads ~4 GB of model weights
into `~/.cache/huggingface`; in Actions that happens on the runner, never on
your machine.) Local setup:

```bash
python -m pip install -r requirements/base.txt
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements/cpu.txt
```

## Repository layout

```
.github/workflows/generate-luffy-clip.yml   # the cloud generator (manual trigger)
.github/workflows/ci.yml                    # tests + config validation
luffy_clip/prompts.py                       # scene library, style + negative prompt
luffy_clip/providers.py                     # HF router backend + CPU diffusion backend
luffy_clip/postprocess.py                   # ffmpeg: frames->mp4, concat, gif, ffprobe
luffy_clip/cli.py                           # argparse entry point + manifest writer
scripts/make_release_notes.py               # renders the release page (inline gif)
tests/                                      # pure-python tests (no torch, no network)
```

## Outputs

Every run produces:

* `luffy_clip_run<N>.mp4` — H.264 / yuv420p / faststart, plays in any browser
* `luffy_clip_run<N>.gif` — small looping preview for READMEs and release notes
* `manifest.json` — prompt, backend, model(s), seed, fps, resolution, duration,
  sha256 — everything needed to reproduce the clip

## License

MIT (code). Generated media is fan art.
