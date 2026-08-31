from dataclasses import replace
from math import dist
from pathlib import Path

from orthovideo.project_config import load_project_config
from orthovideo.projection.cleanup import clean_projection
from orthovideo.projection.generator import generate_projections
from orthovideo.projection.result2d import Projection2D


ROOT = Path(__file__).resolve().parents[1]


def main():
    line = [(0.0, 0.0), (10.0, 0.0)]
    circle = [
        (1.0, 0.0),
        (0.0, 1.0),
        (-1.0, 0.0),
        (0.0, -1.0),
        (1.0, 0.0),
    ]
    shifted_circle = circle[2:-1] + circle[:3]
    cleaned = clean_projection(
        Projection2D(
            visible=[line, list(reversed(line)), circle, shifted_circle],
            hidden=[line, list(reversed(circle))],
        )
    )
    assert len(cleaned.visible) == 2
    assert cleaned.hidden == []

    config = load_project_config(ROOT / "config" / "project.json", ROOT)
    config = replace(
        config,
        model=ROOT / "models" / "componente_valvola.step",
        projection=replace(
            config.projection,
            show_hidden=False,
            hidden_views=(),
            tangent_edges="omit",
            section_view="front",
            section_reference_view="left",
            pitch_circle_views=("top",),
        ),
    )
    bundle = generate_projections(config, centerline_extension=3.0)

    # The simple and complex axial faces must stay measurably different.
    assert len(bundle.projections["top"].visible) < len(
        bundle.projections["bottom"].visible
    )
    assert all(not projection.hidden for projection in bundle.projections.values())

    # A-A is an independent cutaway view, never a hatch painted onto FRONT.
    assert bundle.section_name == "front"
    assert bundle.section_projection is not None
    assert bundle.section_projection.hidden == []
    assert any(item.role == "HATCH" for item in bundle.section_annotations)
    assert not any(
        item.role == "SECTION_CUT" for item in bundle.section_annotations
    )
    assert not any(
        item.role == "HATCH"
        for items in bundle.annotations.values()
        for item in items
    )
    assert not bundle.section_reference_annotations["top"]
    assert bundle.section_reference_annotations["left"][0].role == "CENTER"
    assert [label.text for label in bundle.section_reference_labels["left"]] == [
        "A",
        "A",
    ]

    pitch_items = [
        item for item in bundle.annotations["top"] if item.role == "PITCH"
    ]
    pattern_center_items = [
        item for item in bundle.annotations["top"] if item.role == "CENTER"
    ]
    assert len(pitch_items) == 1
    # Two complete diagonal diameters locate opposite holes; four short
    # tangential ticks form the local X marks without redundant H/V crosses.
    assert len(pattern_center_items) == 6
    pattern_lengths = sorted(
        dist(item.points[0], item.points[-1]) for item in pattern_center_items
    )
    assert pattern_lengths[3] < pattern_lengths[4]

    # The pitch-circle face moves its four hole centres to structured radial /
    # tangential annotations. The opposite face retains four local pluses and
    # the principal-bore plus (five marks, two segments each).
    assert len(bundle.centerlines["top"]) == 2
    assert len(bundle.centerlines["bottom"]) == 10

    for view_name in ("top", "bottom"):
        lines = bundle.centerlines[view_name]
        for horizontal, vertical in zip(lines[0::2], lines[1::2]):
            h_center = (
                (horizontal.start[0] + horizontal.end[0]) / 2.0,
                (horizontal.start[1] + horizontal.end[1]) / 2.0,
            )
            v_center = (
                (vertical.start[0] + vertical.end[0]) / 2.0,
                (vertical.start[1] + vertical.end[1]) / 2.0,
            )
            assert dist(h_center, v_center) <= 1.0e-6
            assert abs(horizontal.start[1] - horizontal.end[1]) <= 1.0e-6
            assert abs(vertical.start[0] - vertical.end[0]) <= 1.0e-6
            assert abs(
                dist(horizontal.start, horizontal.end)
                - dist(vertical.start, vertical.end)
            ) <= 1.0e-6

    print("PROJECTION_CLEANUP_AND_SECTION_SEPARATION_OK")


if __name__ == "__main__":
    main()
