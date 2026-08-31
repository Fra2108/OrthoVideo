from math import isclose, sqrt

from orthovideo.projection.centerlines import (
    CenterLine2D,
    clip_centerlines_to_projection,
    detect_four_hole_pattern,
)
from orthovideo.projection.cleanup import clean_projection
from orthovideo.projection.result2d import Projection2D
from orthovideo.projection.section import build_section_reference
from orthovideo.projection.view_system import build_six_views


def cross(center, half_length):
    x, y = center
    return [
        CenterLine2D((x - half_length, y), (x + half_length, y)),
        CenterLine2D((x, y - half_length), (x, y + half_length)),
    ]


def main():
    lines = cross((0.0, 0.0), 4.0)
    for center in ((-6.0, -6.0), (6.0, -6.0), (6.0, 6.0), (-6.0, 6.0)):
        lines.extend(cross(center, 1.5))

    pattern = detect_four_hole_pattern(lines)
    assert pattern is not None
    assert pattern.center == (0.0, 0.0)
    assert isclose(pattern.radius, 6.0 * sqrt(2.0), rel_tol=1.0e-9)
    assert len(pattern.holes) == 4

    envelope = Projection2D(
        visible=[
            [(-5.0, -3.0), (5.0, -3.0)],
            [(5.0, -3.0), (5.0, 3.0)],
            [(5.0, 3.0), (-5.0, 3.0)],
            [(-5.0, 3.0), (-5.0, -3.0)],
        ],
        hidden=[],
    )
    clipped = clip_centerlines_to_projection(
        [CenterLine2D((0.0, -10.0), (0.0, 10.0))],
        envelope,
    )
    assert clipped == [CenterLine2D((0.0, -3.0), (0.0, 3.0))]

    views = build_six_views((0.0, 0.0, -1.0), (0.0, 1.0, 0.0))
    annotations, labels = build_section_reference(
        (-5.0, -8.0, -4.0, 5.0, 8.0, 4.0),
        views["front"],
        views["left"],
        envelope,
    )
    assert annotations[0].role == "CENTER"
    assert sum(item.role == "SECTION_CUT" for item in annotations) == 6
    assert [label.text for label in labels] == ["A", "A"]
    label_y = sorted(label.position[1] for label in labels)
    end_y = sorted(point[1] for point in annotations[0].points)
    assert label_y[0] < end_y[0]
    assert label_y[1] > end_y[1]

    # Coincident CAD curves with different sampling must not darken a contour.
    coarse = [(0.0, 0.0), (5.0, 5.0), (10.0, 0.0)]
    dense = [(0.0, 0.0), (2.5, 2.5), (5.0, 5.0), (7.5, 2.5), (10.0, 0.0)]
    cleaned = clean_projection(Projection2D(visible=[coarse, dense], hidden=[]))
    assert len(cleaned.visible) == 1

    print("DRAWING_REFERENCE_CLEANUP_OK")


if __name__ == "__main__":
    main()
