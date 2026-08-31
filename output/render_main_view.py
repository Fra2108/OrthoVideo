from pathlib import Path
import json

from orthovideo.project_config import (
    load_project_config,
)

from orthovideo.io.step_loader import (
    load_step,
)

from orthovideo.animation.mesh_prepare import (
    export_step_render_mesh,
)

from orthovideo.animation.blender_runner import (
    run_blender_script,
)


ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = (
    ROOT
    / "config"
    / "project.json"
)

BLENDER_SCRIPT = (
    ROOT
    / "blender"
    / "render_main_view.py"
)


def main():

    print()
    print("=" * 60)
    print("ORTHOVIDEO - MAIN VIEW RENDER")
    print("=" * 60)

    config = load_project_config(
        CONFIG_FILE,
        ROOT,
    )

    output_dir = (
        ROOT
        / "output"
        / "animation"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    suffix = (
        config.model.suffix.lower()
    )

    # =================================================
    # MODELLO PER BLENDER
    # =================================================

    if suffix in {
        ".step",
        ".stp",
    }:

        print()
        print("Preparazione mesh STEP...")

        shape = load_step(
            config.model
        )

        model_mesh = (
            output_dir
            / "model_render.stl"
        )

        export_step_render_mesh(
            shape,
            model_mesh,
            linear_deflection=0.10,
        )

    elif suffix == ".obj":

        model_mesh = (
            config.model
        )

    else:

        raise ValueError(
            "Formato modello non supportato."
        )

    # =================================================
    # JOB BLENDER
    # =================================================

    output_png = (
        output_dir
        / "main_view.png"
    )

    output_blend = (
        output_dir
        / "main_view.blend"
    )

    job_file = (
        output_dir
        / "render_job.json"
    )

    job = {
        "model_mesh": str(
            model_mesh.resolve()
        ),

        "main_normal": list(
            config.main_view.normal
        ),

        "main_up": list(
            config.main_view.up
        ),

        "resolution_x": 1200,
        "resolution_y": 900,

        "output_file": str(
            output_png.resolve()
        ),

        "blend_file": str(
            output_blend.resolve()
        ),
    }

    job_file.write_text(
        json.dumps(
            job,
            indent=2,
        ),
        encoding="utf-8",
    )

    # =================================================
    # BLENDER
    # =================================================

    print()
    print("Avvio Blender 5.1...")

    output = run_blender_script(
        config.blender.executable,
        BLENDER_SCRIPT,
        [
            str(job_file.resolve())
        ],
    )

    if "ORTHOVIDEO_RENDER_OK" not in output:

        raise RuntimeError(
            "Blender non ha confermato il render.\n\n"
            + output
        )

    print()
    print("RENDER COMPLETATO")

    print()
    print("PNG:")
    print(output_png)

    print()
    print("BLEND:")
    print(output_blend)

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()