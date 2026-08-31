from dataclasses import replace
from pathlib import Path

from orthovideo.animation.blender_runner import run_blender_script
from orthovideo.animation.mesh_prepare import export_step_render_mesh
from orthovideo.animation.projection_job import write_projection_animation_job
from orthovideo.project_config import load_project_config
from orthovideo.projection.generator import generate_projections


ROOT = Path(__file__).resolve().parents[1]


def main():
    config = load_project_config(ROOT / "config" / "project.json", ROOT)
    config = replace(
        config,
        output=replace(config.output, mp4=False),
        animation=replace(
            config.animation,
            resolution_x=640,
            resolution_y=360,
            render_percentage=50,
            frame_end=96,
        ),
    )
    bundle = generate_projections(config, centerline_extension=3.0)
    output = ROOT / "output" / "tests" / "valve_animation_scene"
    mesh = export_step_render_mesh(
        bundle.source_geometry,
        output / "model.stl",
        linear_deflection=0.10,
    )
    job = write_projection_animation_job(
        config,
        model_mesh=mesh,
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
    assert "ORTHOVIDEO_FIRST_ANGLE_RIG_OK" in result
    assert "ORTHOVIDEO_ANIMATION_OK" in result
    assert (output / "orthovideo_preview.png").stat().st_size > 1000
    assert (output / "orthovideo_animation.blend").stat().st_size > 1000
    print("VALVE_ANIMATION_SCENE_OK")


if __name__ == "__main__":
    main()
