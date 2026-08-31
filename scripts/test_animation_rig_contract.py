import json
from dataclasses import replace
from pathlib import Path

from orthovideo.animation.projection_job import write_projection_animation_job
from orthovideo.project_config import load_project_config
from orthovideo.projection.annotations import TechnicalAnnotation2D
from orthovideo.projection.result2d import Projection2D
from orthovideo.projection.view_system import build_six_views


ROOT = Path(__file__).resolve().parents[1]


def main():
    config = load_project_config(ROOT / "config" / "project.json", ROOT)
    config = replace(config, output=replace(config.output, mp4=False))
    views = build_six_views(config.main_view.normal, config.main_view.up)
    projections = {
        name: Projection2D(
            visible=[[(0.0, 0.0), (10.0, 10.0)]],
            hidden=[[(0.0, 10.0), (10.0, 0.0)]],
            tangent=[[(0.0, 5.0), (10.0, 5.0)]],
        )
        for name in views
    }
    output = ROOT / "output" / "tests" / "animation_rig_contract"
    job_file = write_projection_animation_job(
        config,
        model_mesh=ROOT / "models" / "test_mesh.obj",
        projections=projections,
        centerlines={},
        annotations={
            "front": [
                TechnicalAnnotation2D(
                    role="HATCH",
                    points=[(0.0, 2.0), (10.0, 2.0)],
                )
            ]
        },
        views=views,
        output_dir=output,
    )
    job = json.loads(job_file.read_text(encoding="utf-8"))

    rig = job["rig"]
    assert rig["type"] == "contiguous_first_angle_box"
    assert rig["physical_faces"] == {
        "front": "-Z",
        "rear": "+Z",
        "right": "-X",
        "left": "+X",
        "top": "-Y",
        "bottom": "+Y",
    }
    assert rig["parents"] == {
        "front": None,
        "right": "front",
        "left": "front",
        "top": "front",
        "bottom": "front",
        "rear": "left",
    }
    assert rig["unfold_degrees"] == {
        "right": -90.0,
        "left": 90.0,
        "top": 90.0,
        "bottom": -90.0,
        "rear": 90.0,
    }

    center_style = job["line_styles"]["center"]
    assert center_style["pattern_kind"] == "long_gap_dot_gap"
    assert center_style["pattern_ratios"] == [0.10, 0.025, 0.010, 0.025]
    assert center_style["continuous_phase"] is True
    assert job["views"]["front"]["tangent"] == [[[0.0, 5.0], [10.0, 5.0]]]
    assert job["views"]["front"]["annotations"] == [
        {"role": "HATCH", "points": [[0.0, 2.0], [10.0, 2.0]]}
    ]
    assert job["line_styles"]["section_cut"]["pattern"] == "solid"
    assert job["render"]["show_labels"] is False

    timing = job["timing"]
    assert timing["draw_end"] < timing["unfold_start"] < timing["unfold_end"]
    print("ANIMATION_RIG_CONTRACT_OK")


if __name__ == "__main__":
    main()
