from pathlib import Path
import json

from orthovideo.project_config import ProjectConfig
from orthovideo.projection.annotations import TechnicalAnnotation2D
from orthovideo.projection.centerlines import CenterLine2D
from orthovideo.projection.result2d import Projection2D
from orthovideo.projection.view_system import ViewDefinition


def _points(lines):
    return [
        [[float(point[0]), float(point[1])] for point in line]
        for line in lines
        if len(line) >= 2
    ]


def _annotations(items):
    return [
        {
            "role": item.role.upper(),
            "points": [
                [float(point[0]), float(point[1])]
                for point in item.points
            ],
        }
        for item in items
        if len(item.points) >= 2
    ]


def write_projection_animation_job(
    config: ProjectConfig,
    *,
    model_mesh: str | Path,
    projections: dict[str, Projection2D],
    centerlines: dict[str, list[CenterLine2D]],
    views: dict[str, ViewDefinition],
    output_dir: str | Path,
    annotations: dict[str, list[TechnicalAnnotation2D]] | None = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    annotations = annotations or {}

    frame_end = config.animation.frame_end
    draw_start = max(2, round(frame_end * 0.18))
    draw_end = max(draw_start + 6, round(frame_end * 0.50))
    unfold_start = max(draw_end + 4, round(frame_end * 0.58))
    unfold_end = max(unfold_start + 8, round(frame_end * 0.82))

    job = {
        "schema_version": 1,
        "model_mesh": str(Path(model_mesh).resolve()),
        "source_type": config.model.suffix.lower().lstrip("."),
        "main_normal": list(config.main_view.normal),
        "main_up": list(config.main_view.up),
        "projection_method": "first_angle",
        "rig": {
            "type": "contiguous_first_angle_box",
            "basis": {
                "x": "main_right",
                "y": "main_up",
                "z": "main_normal",
            },
            "physical_faces": {
                "front": "-Z",
                "rear": "+Z",
                "right": "-X",
                "left": "+X",
                "top": "-Y",
                "bottom": "+Y",
            },
            "parents": {
                "front": None,
                "right": "front",
                "left": "front",
                "top": "front",
                "bottom": "front",
                "rear": "left",
            },
            "unfold_degrees": {
                "right": -90.0,
                "left": 90.0,
                "top": 90.0,
                "bottom": -90.0,
                "rear": 90.0,
            },
            "box_clearance_ratio": 0.12,
        },
        "line_styles": {
            "visible": {
                "width_ratio": 0.0042,
                "pattern": "solid",
            },
            "hidden": {
                "width_ratio": 0.0026,
                "pattern_ratios": [0.065, 0.032],
                "continuous_phase": True,
            },
            "center": {
                "width_ratio": 0.0022,
                "pattern_ratios": [0.10, 0.025, 0.010, 0.025],
                "pattern_kind": "long_gap_dot_gap",
                "continuous_phase": True,
            },
            "tangent": {
                "width_ratio": 0.0018,
                "pattern": "solid",
            },
            "hatch": {
                "width_ratio": 0.0014,
                "pattern": "solid",
            },
            "section_cut": {
                "width_ratio": 0.0038,
                "pattern": "solid",
            },
        },
        "views": {
            name: {
                "normal": list(view.normal),
                "up": list(view.up),
                "visible": _points(projections[name].visible),
                "hidden": _points(projections[name].hidden),
                "tangent": _points(projections[name].tangent),
                "center": _points(
                    [[line.start, line.end] for line in centerlines.get(name, [])]
                ),
                "annotations": _annotations(annotations.get(name, [])),
            }
            for name, view in views.items()
        },
        "timing": {
            "frame_start": 1,
            "draw_start": draw_start,
            "draw_end": draw_end,
            "unfold_start": unfold_start,
            "unfold_end": unfold_end,
            "frame_end": frame_end,
        },
        "render": {
            "resolution_x": config.animation.resolution_x,
            "resolution_y": config.animation.resolution_y,
            "render_percentage": config.animation.render_percentage,
            "fps": config.animation.fps,
            "preview_file": str((output_dir / "orthovideo_preview.png").resolve()),
            "video_file": str((output_dir / "orthovideo_animation.mp4").resolve()),
            "blend_file": str((output_dir / "orthovideo_animation.blend").resolve()),
            "render_video": bool(config.output.mp4),
            "show_labels": False,
        },
    }

    job_file = output_dir / "orthovideo_animation_job.json"
    job_file.write_text(json.dumps(job, indent=2), encoding="utf-8")
    return job_file
