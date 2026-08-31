from math import pi, tau
from pathlib import Path

from orthovideo.features.cylinders import extract_cylinders
from orthovideo.io.step_loader import load_step
from orthovideo.projection.centerlines import build_centerlines_for_view
from orthovideo.projection.view_system import build_six_views


ROOT = Path(__file__).resolve().parents[1]
TEST_PART = ROOT / "models" / "test_part.step"
VALVE = ROOT / "models" / "valvula_teflon_ensamblaje.step"

VIEWS = build_six_views(
    main_normal=(0.0, -1.0, 0.0),
    main_up=(0.0, 0.0, 1.0),
)


def centerline_counts(cylinders):
    return {
        name: len(
            build_centerlines_for_view(
                cylinders,
                view,
                extension=3.0,
            )
        )
        for name, view in VIEWS.items()
    }


def main():
    test_shape = load_step(TEST_PART)
    test_regions = extract_cylinders(test_shape, include_partial=True)
    test_cylinders = extract_cylinders(test_shape)

    assert len(test_regions) == 1
    assert sum(feature.source_face_count for feature in test_regions) == 1
    assert len(test_cylinders) == 1
    assert abs(test_cylinders[0].radius - 10.0) <= 1.0e-7
    assert test_cylinders[0].angular_coverage >= tau - pi / 180.0

    expected_test_counts = {
        "front": 2,
        "rear": 2,
        "top": 1,
        "bottom": 1,
        "right": 1,
        "left": 1,
    }
    actual_test_counts = centerline_counts(test_cylinders)
    assert actual_test_counts == expected_test_counts, actual_test_counts

    valve_shape = load_step(VALVE)
    valve_regions = extract_cylinders(valve_shape, include_partial=True)
    valve_cylinders = extract_cylinders(valve_shape)

    # The source contains 177 cylindrical B-Rep faces. SolidWorks splits every
    # useful full cylinder into half/quarter patches; consolidation must retain
    # those features while rejecting incomplete cylindrical fillets.
    assert sum(feature.source_face_count for feature in valve_regions) == 177
    assert len(valve_regions) == 117
    assert len(valve_cylinders) == 46
    assert sum(feature.source_face_count for feature in valve_cylinders) == 92
    assert any(feature.source_face_count > 1 for feature in valve_cylinders)
    assert all(
        feature.angular_coverage >= tau - pi / 180.0
        for feature in valve_cylinders
    )

    expected_valve_counts = {
        "front": 23,
        "rear": 23,
        "top": 16,
        "bottom": 16,
        "right": 36,
        "left": 36,
    }
    actual_valve_counts = centerline_counts(valve_cylinders)
    assert actual_valve_counts == expected_valve_counts, actual_valve_counts
    assert max(actual_valve_counts.values()) < 40

    print("CENTERLINE_CONSOLIDATION_OK")
    print("test_part:", len(test_cylinders), actual_test_counts)
    print(
        "valve:",
        "177 faces ->",
        len(valve_cylinders),
        "complete cylinders ->",
        actual_valve_counts,
    )


if __name__ == "__main__":
    main()
