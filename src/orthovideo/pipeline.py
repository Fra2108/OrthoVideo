from dataclasses import dataclass
from pathlib import Path
import json

from orthovideo.animation.blender_runner import run_blender_script
from orthovideo.animation.mesh_prepare import export_step_render_mesh
from orthovideo.animation.projection_job import write_projection_animation_job
from orthovideo.animation.video_encoder import encode_png_sequence
from orthovideo.drawing.dxf_exporter import export_layout_dxf
from orthovideo.drawing.paper import get_paper_size
from orthovideo.drawing.pdf_exporter import export_layouts_pdf
from orthovideo.drawing.sheet_layout import (
    build_first_angle_layout,
    build_sectioned_first_angle_layout,
    build_single_view_layout,
)
from orthovideo.drawing.svg_exporter import export_layout_svg
from orthovideo.drawing.technical_styles import (
    DEFAULT_TECHNICAL_STYLE_PRESET,
    ORTHOGRAPHIC_LIGHT_STYLE_PRESET,
)
from orthovideo.drawing.technical_sheet import (
    choose_iso_scale,
    choose_sectioned_fit_scale,
    choose_sectioned_iso_scale,
    choose_single_view_iso_scale,
    scale_to_text,
)
from orthovideo.project_config import ProjectConfig
from orthovideo.projection.generator import generate_projections


@dataclass(frozen=True)
class GenerationResult:
    source_type: str
    drawing_scale: float
    outputs: dict[str, Path]


def generate_project(
    config: ProjectConfig,
    *,
    write_manifest: bool = True,
) -> GenerationResult:
    page_width, page_height = get_paper_size(
        config.sheet.format,
        config.sheet.orientation,
    )

    # The definitive scale needs Projection2D, while centerline extension uses
    # that scale. First calculate the views, then rebuild only STEP centerlines.
    bundle = generate_projections(config, centerline_extension=3.0)
    sectioned_layout = config.sheet.layout == "sectioned_first_angle"
    if sectioned_layout and (
        bundle.section_name is None or bundle.section_projection is None
    ):
        raise RuntimeError(
            "Il layout sectioned_first_angle richiede projection.section_view."
        )
    if sectioned_layout and bundle.section_name != "front":
        raise RuntimeError(
            "Il layout sectioned_first_angle integrato richiede section_view=front."
        )

    if config.sheet.automatic_scale:
        if sectioned_layout:
            scale_selector = (
                choose_sectioned_fit_scale
                if config.sheet.scale_mode == "fit"
                else choose_sectioned_iso_scale
            )
            scale = scale_selector(
                bundle.projections,
                bundle.section_projection,
                page_width=page_width,
                page_height=page_height,
                margin=config.sheet.margin_mm,
                horizontal_gap=config.sheet.horizontal_gap_mm,
                horizontal_gap_before=config.sheet.horizontal_gap_before_mm,
                horizontal_gap_after=config.sheet.horizontal_gap_after_mm,
                vertical_gap=config.sheet.vertical_gap_mm,
                vertical_gap_above=config.sheet.vertical_gap_above_mm,
                vertical_gap_below=config.sheet.vertical_gap_below_mm,
            )
        else:
            scale = choose_iso_scale(
                bundle.projections,
                page_width=page_width,
                page_height=page_height,
                margin=config.sheet.margin_mm,
                gap=config.sheet.gap_mm,
            )
    else:
        scale = 1.0

    if (
        bundle.source_type == "STEP"
        and config.projection.show_centerlines
        and abs(scale - 1.0) > 1e-9
    ):
        bundle = generate_projections(config, centerline_extension=3.0 / scale)

    output_dir = config.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    sheet_annotations = {
        name: (
            list(bundle.annotations.get(name, []))
            + list(bundle.section_reference_annotations.get(name, []))
        )
        for name in bundle.projections
    }

    section_layout = None
    section_scale = None

    if sectioned_layout:
        layout = build_sectioned_first_angle_layout(
            bundle.projections,
            bundle.section_projection,
            centerlines=bundle.centerlines,
            annotations=sheet_annotations,
            view_labels=bundle.section_reference_labels,
            section_centerlines=bundle.section_centerlines,
            section_annotations=bundle.section_annotations,
            page_width=page_width,
            page_height=page_height,
            margin=config.sheet.margin_mm,
            horizontal_gap=config.sheet.horizontal_gap_mm,
            horizontal_gap_before=config.sheet.horizontal_gap_before_mm,
            horizontal_gap_after=config.sheet.horizontal_gap_after_mm,
            central_axis_offset=config.sheet.central_axis_offset_mm,
            vertical_gap=config.sheet.vertical_gap_mm,
            vertical_gap_above=config.sheet.vertical_gap_above_mm,
            vertical_gap_below=config.sheet.vertical_gap_below_mm,
            drawing_scale=scale,
        )
        section_scale = scale
    else:
        layout = build_first_angle_layout(
            bundle.projections,
            centerlines=bundle.centerlines,
            annotations=sheet_annotations,
            view_labels=bundle.section_reference_labels,
            page_width=page_width,
            page_height=page_height,
            margin=config.sheet.margin_mm,
            gap=config.sheet.gap_mm,
            drawing_scale=scale,
            show_labels=config.sheet.show_view_labels,
        )

    if (
        not sectioned_layout
        and bundle.section_name
        and bundle.section_projection
    ):
        section_scale = choose_single_view_iso_scale(
            bundle.section_projection,
            page_width=page_width,
            page_height=page_height,
            margin=config.sheet.margin_mm,
        )
        section_layout = build_single_view_layout(
            "section_A-A",
            bundle.section_projection,
            centerlines=bundle.section_centerlines,
            annotations=bundle.section_annotations,
            label=f"SEZIONE A-A   SCALA {scale_to_text(section_scale)}",
            page_width=page_width,
            page_height=page_height,
            margin=config.sheet.margin_mm,
            drawing_scale=section_scale,
        )

    if config.output.svg:
        svg_file = output_dir / "orthographic_sheet.svg"
        outputs["svg"] = export_layout_svg(
            layout,
            svg_file,
            style_preset=ORTHOGRAPHIC_LIGHT_STYLE_PRESET,
        )

        if section_layout:
            outputs["section_svg"] = export_layout_svg(
                section_layout,
                output_dir / "section_A-A.svg",
                style_preset=DEFAULT_TECHNICAL_STYLE_PRESET,
            )

    if config.output.pdf:
        pdf_layouts = [layout]
        if section_layout:
            pdf_layouts.append(section_layout)
        outputs["pdf"] = export_layouts_pdf(
            pdf_layouts,
            output_dir / "orthographic_sheet.pdf",
            style_presets=(
                [
                    ORTHOGRAPHIC_LIGHT_STYLE_PRESET,
                    DEFAULT_TECHNICAL_STYLE_PRESET,
                ]
                if section_layout
                else [ORTHOGRAPHIC_LIGHT_STYLE_PRESET]
            ),
        )

    if config.output.dxf:
        outputs["dxf"] = export_layout_dxf(
            layout,
            output_dir / "orthographic_sheet.dxf",
            style_preset=ORTHOGRAPHIC_LIGHT_STYLE_PRESET,
        )
        if section_layout:
            outputs["section_dxf"] = export_layout_dxf(
                section_layout,
                output_dir / "section_A-A.dxf",
                style_preset=DEFAULT_TECHNICAL_STYLE_PRESET,
            )

    if config.output.mp4:
        animation_dir = output_dir / "animation"
        animation_dir.mkdir(parents=True, exist_ok=True)

        if bundle.source_type == "STEP":
            model_mesh = export_step_render_mesh(
                bundle.source_geometry,
                animation_dir / "model_render.stl",
                linear_deflection=0.10,
            )
        else:
            model_mesh = config.model

        job_file = write_projection_animation_job(
            config,
            model_mesh=model_mesh,
            projections=bundle.projections,
            centerlines=bundle.centerlines,
            annotations=bundle.annotations,
            views=bundle.views,
            output_dir=animation_dir,
        )
        blender_script = Path(__file__).resolve().parents[2] / "blender" / "render_projection_animation.py"
        blender_output = run_blender_script(
            config.blender.executable,
            blender_script,
            [str(job_file.resolve())],
        )

        if "ORTHOVIDEO_ANIMATION_OK" not in blender_output:
            raise RuntimeError("Blender non ha completato l'animazione.\n\n" + blender_output)

        video_file = encode_png_sequence(
            animation_dir / "frames",
            animation_dir / "orthovideo_animation.mp4",
            fps=config.animation.fps,
            start_number=1,
            remove_frames=True,
        )

        outputs.update(
            {
                "preview": animation_dir / "orthovideo_preview.png",
                "blend": animation_dir / "orthovideo_animation.blend",
                "mp4": video_file,
            }
        )

    if write_manifest:
        manifest_file = output_dir / "manifest.json"
        manifest_file.write_text(
            json.dumps(
                {
                "source": bundle.source_type,
                "model": str(config.model),
                "projection_method": "first_angle",
                "sheet_layout": config.sheet.layout,
                "displayed_views": (
                    ["right", "section_A-A", "left", "bottom", "top"]
                    if sectioned_layout
                    else ["right", "front", "left", "rear", "bottom", "top"]
                ),
                "main_view": {
                    "normal": list(config.main_view.normal),
                    "up": list(config.main_view.up),
                },
                "drawing_scale": scale_to_text(scale),
                "views": {
                    name: {
                        "visible": len(projection.visible),
                        "hidden": len(projection.hidden),
                        "tangent": len(projection.tangent),
                        "center": len(bundle.centerlines.get(name, [])),
                        "annotations": {
                            role: sum(
                                item.role == role
                                for item in bundle.annotations.get(name, [])
                            )
                            for role in (
                                "SYMMETRY",
                                "PITCH",
                                "SECTION_CUT",
                                "HATCH",
                            )
                        },
                    }
                    for name, projection in bundle.projections.items()
                },
                "section": (
                    {
                        "name": "A-A",
                        "source_view": bundle.section_name,
                        "drawing_scale": scale_to_text(section_scale),
                        "integrated": sectioned_layout,
                        "visible": len(bundle.section_projection.visible),
                        "hidden": len(bundle.section_projection.hidden),
                        "center": len(bundle.section_centerlines),
                        "contours": sum(
                            item.role == "SECTION_CUT"
                            for item in bundle.section_annotations
                        ),
                        "hatches": sum(
                            item.role == "HATCH"
                            for item in bundle.section_annotations
                        ),
                    }
                    if bundle.section_projection
                    else None
                ),
                "outputs": {name: str(path.resolve()) for name, path in outputs.items()},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        outputs["manifest"] = manifest_file

    return GenerationResult(
        source_type=bundle.source_type,
        drawing_scale=scale,
        outputs=outputs,
    )
