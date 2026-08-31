from dataclasses import replace
from pathlib import Path

from orthovideo.drawing.sheet_layout import projection_bounds
from orthovideo.project_config import load_project_config
from orthovideo.projection.generator import generate_projections
from orthovideo.projection.mesh_projection import project_point_to_view
from orthovideo.projection.view_system import build_six_views


ROOT = Path(__file__).resolve().parents[1]


def dimensions(projection):
    xmin, ymin, xmax, ymax = projection_bounds(projection)
    return xmax - xmin, ymax - ymin


def main():
    views = build_six_views((0.0, -1.0, 0.0), (0.0, 0.0, 1.0))
    point = (1.0, 2.0, 3.0)
    assert project_point_to_view(point, views["front"]) == (1.0, 3.0)
    assert project_point_to_view(point, views["rear"]) == (-1.0, 3.0)
    assert project_point_to_view(point, views["top"]) == (1.0, 2.0)
    assert project_point_to_view(point, views["bottom"]) == (1.0, -2.0)
    assert project_point_to_view(point, views["right"]) == (2.0, 3.0)
    assert project_point_to_view(point, views["left"]) == (-2.0, 3.0)

    config = load_project_config(ROOT / "config" / "project.json", ROOT)
    common_projection = replace(config.projection, show_centerlines=False)
    step_config = replace(
        config,
        model=ROOT / "models" / "test_box.step",
        projection=common_projection,
    )
    obj_config = replace(
        config,
        model=ROOT / "models" / "test_mesh.obj",
        projection=common_projection,
    )
    step = generate_projections(step_config, centerline_extension=3.0)
    obj = generate_projections(obj_config, centerline_extension=3.0)

    expected_step = {
        "front": (100.0, 30.0),
        "rear": (100.0, 30.0),
        "top": (100.0, 60.0),
        "bottom": (100.0, 60.0),
        "right": (60.0, 30.0),
        "left": (60.0, 30.0),
    }
    expected_obj = {
        "front": (100.0, 50.0),
        "rear": (100.0, 50.0),
        "top": (100.0, 60.0),
        "bottom": (100.0, 60.0),
        "right": (60.0, 50.0),
        "left": (60.0, 50.0),
    }

    for name in views:
        for actual, expected in (
            (dimensions(step.projections[name]), expected_step[name]),
            (dimensions(obj.projections[name]), expected_obj[name]),
        ):
            assert all(abs(a - e) <= 1e-4 for a, e in zip(actual, expected)), (
                name,
                actual,
                expected,
            )

    print("STEP_OBJ_ORIENTATION_REGRESSION_OK")


if __name__ == "__main__":
    main()
