from dataclasses import replace
from pathlib import Path

from orthovideo.animation.blender_runner import run_blender_script
from orthovideo.animation.projection_job import write_projection_animation_job
from orthovideo.project_config import load_project_config
from orthovideo.projection.generator import generate_projections


ROOT = Path(__file__).resolve().parents[1]


def main():
    config = load_project_config(ROOT / "config" / "project.json", ROOT)
    config = replace(
        config,
        model=ROOT / "models" / "test_mesh.obj",
        output=replace(config.output, mp4=False),
        animation=replace(
            config.animation,
            resolution_x=640,
            resolution_y=360,
            render_percentage=50,
            frame_end=72,
        ),
    )
    bundle = generate_projections(config, centerline_extension=3.0)
    output = ROOT / "output" / "tests" / "animation_obj_scene"
    job = write_projection_animation_job(
        config,
        model_mesh=config.model,
        projections=bundle.projections,
        centerlines=bundle.centerlines,
        annotations=bundle.annotations,
        views=bundle.views,
        output_dir=output,
    )
    result = run_blender_script(
        config.blender.executable,
        ROOT / "blender" / "render_projection_animation.py",
        [str(job.resolve())],
    )
    assert "ORTHOVIDEO_ANIMATION_OK" in result
    assert (output / "orthovideo_preview.png").stat().st_size > 1000
    assert (output / "orthovideo_animation.blend").stat().st_size > 1000
    print("ANIMATION_OBJ_SCENE_OK")


if __name__ == "__main__":
    main()
