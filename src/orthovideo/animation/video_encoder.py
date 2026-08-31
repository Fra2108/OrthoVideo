from pathlib import Path
import shutil
import subprocess


def encode_png_sequence(
    frames_dir: str | Path,
    output_file: str | Path,
    *,
    fps: int,
    start_number: int = 1,
    remove_frames: bool = True,
) -> Path:
    """Encode Blender PNG frames with an external FFmpeg executable.

    Blender 5.1 builds can be distributed without the FFMPEG output enum;
    keeping the encoder outside Blender makes the pipeline work with both
    full and reduced Blender builds.
    """
    frames_dir = Path(frames_dir)
    output_file = Path(output_file)
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg is None:
        raise FileNotFoundError(
            "FFmpeg non trovato nel PATH. Installarlo o aggiungerlo al PATH "
            "per creare l'MP4."
        )

    first_frame = frames_dir / f"frame_{start_number:04d}.png"

    if not first_frame.exists():
        raise FileNotFoundError(f"Primo frame Blender non trovato: {first_frame}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        str(start_number),
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_file),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0 or not output_file.exists():
        raise RuntimeError(
            "Codifica MP4 con FFmpeg fallita.\n\n"
            + (result.stdout or "")
            + "\n"
            + (result.stderr or "")
        )

    if output_file.stat().st_size < 1024:
        raise RuntimeError(f"MP4 creato ma non valido: {output_file}")

    if remove_frames:
        shutil.rmtree(frames_dir)

    return output_file
