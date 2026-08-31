from math import hypot
from pathlib import Path

from orthovideo.io.step_loader import load_step
from orthovideo.io.obj_loader import load_obj
from orthovideo.projection.annotations import circle_annotation
from orthovideo.projection.section import (
    build_mesh_section_annotations,
    build_step_section_annotations,
)
from orthovideo.projection.view_system import build_six_views


ROOT = Path(__file__).resolve().parents[1]


def main():
    shape = load_step(ROOT / "models" / "test_part.step")
    front = build_six_views((0.0, -1.0, 0.0), (0.0, 0.0, 1.0))["front"]
    annotations = build_step_section_annotations(
        shape,
        front,
        hatch_angle_deg=45.0,
        hatch_spacing_mm=4.0,
    )
    contours = [item for item in annotations if item.role == "SECTION_CUT"]
    hatches = [item for item in annotations if item.role == "HATCH"]
    assert contours
    assert hatches

    # test_part has a through bore centred at (30, 28), radius 10, in FRONT.
    # No hatch midpoint may lie in the removed material.
    for hatch in hatches:
        start, end = hatch.points
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        assert hypot(midpoint[0] - 30.0, midpoint[1] - 28.0) >= 9.9

    pitch = circle_annotation(role="PITCH", center=(12.0, 7.0), radius=5.0)
    assert pitch.role == "PITCH"
    assert pitch.points[0] == pitch.points[-1]
    assert len(pitch.points) == 97

    mesh_annotations = build_mesh_section_annotations(
        load_obj(ROOT / "models" / "test_mesh.obj"),
        front,
        hatch_angle_deg=45.0,
        hatch_spacing_mm=4.0,
    )
    assert any(item.role == "SECTION_CUT" for item in mesh_annotations)
    assert any(item.role == "HATCH" for item in mesh_annotations)
    print("TECHNICAL_SECTIONS_OK")


if __name__ == "__main__":
    main()
