"""Generation backends.

Two ways to turn a prompt into a video:

* ``generate_with_hf_router`` - hosted text-to-video through the Hugging Face
  Inference Providers router (fal-ai / replicate / wavespeed). This is the
  "best model" path: Wan 2.2, LTX-Video, HunyuanVideo, ... run on beefy GPUs in
  the cloud. Requires an ``HF_TOKEN`` secret with inference-provider access.
* ``generate_with_cpu`` - free fallback that runs entirely on the GitHub
  Actions runner CPU: AnimateDiff-Lightning (4-step distilled AnimateDiff)
  on top of an anime SD1.5 checkpoint. Slower, smaller, but needs no secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_HF_MODEL = "Wan-AI/Wan2.2-TI2V-5B"
DEFAULT_HF_PROVIDER = "fal-ai"
DEFAULT_CPU_BASE_MODEL = "dreamlike-art/dreamlike-anime-1.0"
DEFAULT_MOTION_ADAPTER = "ByteDance/AnimateDiff-Lightning"
CPU_STEPS_CHOICES = (1, 2, 4, 8)


def _looks_like_mp4(header: bytes) -> bool:
    return len(header) >= 12 and b"ftyp" in header[:16]


def _write_video_bytes(data: bytes, out_path: Path) -> int:
    """Persist provider output, refusing anything that is not an MP4."""
    if len(data) < 4096:
        raise RuntimeError(
            "provider returned only {} bytes (expected an MP4)".format(len(data))
        )
    header = data[:32]
    if not _looks_like_mp4(header):
        raise RuntimeError(
            "provider response does not look like an MP4 "
            "(first bytes: {!r})".format(header)
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".part")
    tmp_path.write_bytes(data)
    tmp_path.replace(out_path)
    return len(data)


def _force_float32(pipe: Any, torch_module: Any) -> None:
    """CPU inference needs fp32.

    Several SD1.5 checkpoints (e.g. dreamlike-anime) are stored in fp16 and
    diffusers infers that dtype from the repo config; PyTorch then refuses to
    run ("Input type (c10::Half) and bias type (float) should be the same").
    Casting every torch component explicitly afterwards is version-agnostic.
    """
    seen = set()
    for name in (
        "motion_adapter",
        "unet",
        "vae",
        "text_encoder",
        "text_encoder_2",
        "image_encoder",
        "transformer",
    ):
        module = getattr(pipe, name, None)
        if isinstance(module, torch_module.nn.Module) and id(module) not in seen:
            module.to(torch_module.float32)
            seen.add(id(module))


def generate_with_hf_router(
    prompt: str,
    out_path: Path,
    *,
    model: str = DEFAULT_HF_MODEL,
    provider: str = DEFAULT_HF_PROVIDER,
    token: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    num_frames: Optional[float] = None,
    num_inference_steps: Optional[int] = None,
    guidance_scale: Optional[float] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Text-to-video through the Hugging Face Inference Providers router."""
    try:
        from huggingface_hub import InferenceClient
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "huggingface_hub is required for the hosted provider "
            "(pip install -r requirements/base.txt)"
        ) from exc

    token = token or os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError(
            "HF_TOKEN is not set - add it as a repository secret "
            "(Settings -> Secrets and variables -> Actions) or run with --provider cpu"
        )

    try:
        client = InferenceClient(provider=provider, api_key=token, timeout=3600)
    except TypeError:  # older huggingface_hub without `timeout`
        client = InferenceClient(provider=provider, api_key=token)

    kwargs: Dict[str, Any] = {}
    if negative_prompt:
        kwargs["negative_prompt"] = (
            [negative_prompt] if isinstance(negative_prompt, str) else list(negative_prompt)
        )
    if seed is not None:
        kwargs["seed"] = int(seed)
    if num_frames is not None:
        kwargs["num_frames"] = float(num_frames)
    if num_inference_steps is not None:
        kwargs["num_inference_steps"] = int(num_inference_steps)
    if guidance_scale is not None:
        kwargs["guidance_scale"] = float(guidance_scale)

    print(
        "generating with {}/{} (this can take a few minutes)...".format(provider, model),
        flush=True,
    )
    try:
        result = client.text_to_video(prompt, model=model, **kwargs)
    except Exception as exc:
        raise RuntimeError(
            "{} via the HF router failed for model {}: {}".format(provider, model, exc)
            + "\nHint: the token needs the 'Make calls to Inference Providers' permission "
            "and the Hugging Face account needs available inference credits."
        ) from exc

    if isinstance(result, (bytes, bytearray)):
        data = bytes(result)
    elif isinstance(result, str) and result.startswith("http"):
        import requests

        response = requests.get(result, timeout=900)
        response.raise_for_status()
        data = response.content
    else:
        raise RuntimeError(
            "unexpected response type from the inference provider: {!r}".format(
                type(result).__name__
            )
        )

    size = _write_video_bytes(data, out_path)
    return {
        "backend": "hf-router",
        "provider": provider,
        "model": model,
        "bytes": size,
        "parameters": {key: str(value) for key, value in kwargs.items()},
    }


def generate_with_cpu(
    prompt: str,
    frames_dir: Path,
    *,
    base_model: str = DEFAULT_CPU_BASE_MODEL,
    motion_adapter_repo: str = DEFAULT_MOTION_ADAPTER,
    steps: int = 4,
    num_frames: int = 16,
    width: int = 384,
    height: int = 256,
    guidance_scale: float = 1.2,
    seed: int = 42,
    negative_prompt: Optional[str] = None,
    frame_offset: int = 0,
) -> Dict[str, Any]:
    """Render frames on the local CPU with AnimateDiff-Lightning + SD1.5 anime."""
    if int(steps) not in CPU_STEPS_CHOICES:
        raise ValueError(
            "steps must be one of {} for AnimateDiff-Lightning, got {}".format(
                list(CPU_STEPS_CHOICES), steps
            )
        )

    try:
        import torch
        from diffusers import AnimateDiffPipeline, EulerDiscreteScheduler, MotionAdapter
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "torch + diffusers are required for the local CPU backend "
            "(see requirements/cpu.txt)"
        ) from exc

    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file

    torch.set_num_threads(os.cpu_count() or 2)
    device = "cpu"

    checkpoint = "animatediff_lightning_{}step_diffusers.safetensors".format(steps)
    print(
        "loading motion adapter {}/{}".format(motion_adapter_repo, checkpoint),
        flush=True,
    )
    adapter = MotionAdapter().to(device, torch.float32)
    adapter.load_state_dict(
        load_file(hf_hub_download(motion_adapter_repo, checkpoint), device=device)
    )

    print("loading anime base model {}".format(base_model), flush=True)
    # NOTE: no dtype kwarg on purpose (its name changed across diffusers
    # releases); we hard-cast every component to float32 afterwards instead.
    pipe = AnimateDiffPipeline.from_pretrained(base_model, motion_adapter=adapter)
    pipe = pipe.to(device)
    _force_float32(pipe, torch)
    pipe.scheduler = EulerDiscreteScheduler.from_config(
        pipe.scheduler.config, timestep_spacing="trailing", beta_schedule="linear"
    )
    vae = getattr(pipe, "vae", None)
    if vae is not None and hasattr(vae, "enable_slicing"):
        vae.enable_slicing()
    elif hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    generator = torch.Generator(device).manual_seed(int(seed))
    output = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt or None,
        num_frames=int(num_frames),
        guidance_scale=float(guidance_scale),
        num_inference_steps=int(steps),
        width=int(width),
        height=int(height),
        generator=generator,
    )

    frames_dir.mkdir(parents=True, exist_ok=True)
    frames = output.frames[0]
    written = 0
    for index, frame in enumerate(frames):
        path = frames_dir / "frame_{:04d}.png".format(frame_offset + index)
        if hasattr(frame, "save"):
            frame.save(path)
        else:  # numpy array fallback (output_type="np")
            import numpy as np
            from PIL import Image

            Image.fromarray(np.asarray(frame)).save(path)
        written += 1

    return {
        "backend": "cpu-diffusion",
        "base_model": base_model,
        "motion_adapter": "{}/{}".format(motion_adapter_repo, checkpoint),
        "steps": int(steps),
        "guidance_scale": float(guidance_scale),
        "width": int(width),
        "height": int(height),
        "frames": written,
    }
