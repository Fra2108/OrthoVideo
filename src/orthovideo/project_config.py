from dataclasses import dataclass
from pathlib import Path
import json


Vector3 = tuple[float, float, float]
Point2 = tuple[float, float]


@dataclass(frozen=True)
class MainViewConfig:
    normal: Vector3
    up: Vector3


@dataclass(frozen=True)
class ProjectionConfig:
    method: str
    show_hidden: bool
    hidden_views: tuple[str, ...]
    hidden_line_mode: str
    show_centerlines: bool
    center_mark_only_views: tuple[str, ...]
    tangent_edges: str
    section_view: str | None
    section_reference_view: str | None
    section_offset_mm: float
    hatch_angle_deg: float
    hatch_spacing_mm: float
    pitch_circle_views: tuple[str, ...]


@dataclass(frozen=True)
class SheetConfig:
    format: str
    orientation: str
    margin_mm: float
    gap_mm: float
    horizontal_gap_mm: float
    horizontal_gap_before_mm: float
    horizontal_gap_after_mm: float
    central_axis_offset_mm: float
    vertical_gap_mm: float
    vertical_gap_above_mm: float
    vertical_gap_below_mm: float
    automatic_scale: bool
    scale_mode: str
    layout: str
    show_view_labels: bool


@dataclass(frozen=True)
class OutputConfig:
    directory: Path
    svg: bool
    pdf: bool
    dxf: bool
    mp4: bool


@dataclass(frozen=True)
class BlenderConfig:
    executable: Path


@dataclass(frozen=True)
class AnimationConfig:
    resolution_x: int
    resolution_y: int
    fps: int
    frame_end: int
    render_percentage: int


@dataclass(frozen=True)
class ExplicitAnnotationConfig:
    view: str
    role: str
    points: tuple[Point2, ...] = ()
    center: Point2 | None = None
    radius: float | None = None


@dataclass(frozen=True)
class ProjectConfig:
    model: Path
    blender: BlenderConfig
    main_view: MainViewConfig
    projection: ProjectionConfig
    sheet: SheetConfig
    output: OutputConfig
    animation: AnimationConfig
    technical_annotations: tuple[ExplicitAnnotationConfig, ...]


def _vector3(value, name: str) -> Vector3:

    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(
            f"'{name}' deve contenere esattamente 3 numeri."
        )

    return (
        float(value[0]),
        float(value[1]),
        float(value[2]),
    )


def _point2(value, name: str) -> Point2:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"'{name}' deve contenere esattamente 2 numeri.")
    return float(value[0]), float(value[1])


def load_project_config(
    config_file: str | Path,
    project_root: str | Path,
) -> ProjectConfig:

    config_file = Path(config_file)
    project_root = Path(project_root)

    if not config_file.exists():
        raise FileNotFoundError(
            f"Configurazione non trovata: {config_file}"
        )

    data = json.loads(
        config_file.read_text(
            encoding="utf-8"
        )
    )

    model_value = Path(data["model"])
    model = (
        model_value
        if model_value.is_absolute()
        else project_root / model_value
    ).resolve()

    if not model.exists():
        raise FileNotFoundError(f"Modello non trovato: {model}")

    if model.suffix.lower() not in {".step", ".stp", ".obj"}:
        raise ValueError(
            "Formato non supportato. Sono ammessi: STEP, STP, OBJ."
        )

    blender_data = data["blender"]

    blender_executable = Path(
        blender_data["executable"]
    )

    if not blender_executable.exists():
        raise FileNotFoundError(
            f"Eseguibile Blender non trovato: "
            f"{blender_executable}"
        )

    blender = BlenderConfig(
        executable=blender_executable
    )

    main_view_data = data["main_view"]

    main_view = MainViewConfig(
        normal=_vector3(
            main_view_data["normal"],
            "main_view.normal",
        ),
        up=_vector3(
            main_view_data["up"],
            "main_view.up",
        ),
    )

    projection_data = data["projection"]

    valid_views = {"front", "rear", "top", "bottom", "right", "left"}

    def view_list(key: str) -> tuple[str, ...]:
        raw = projection_data.get(key, [])
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise ValueError(f"projection.{key} deve essere una lista di viste.")
        values = tuple(dict.fromkeys(str(value).lower() for value in raw))
        invalid = set(values) - valid_views
        if invalid:
            raise ValueError(
                f"projection.{key} contiene viste non valide: "
                + ", ".join(sorted(invalid))
            )
        return values

    projection = ProjectionConfig(
        method=projection_data.get(
            "method",
            "first_angle",
        ),
        show_hidden=bool(
            projection_data.get(
                "show_hidden",
                False,
            )
        ),
        hidden_line_mode=str(
            projection_data.get("hidden_line_mode", "all")
        ).lower(),
        show_centerlines=bool(
            projection_data.get(
                "show_centerlines",
                True,
            )
        ),
        hidden_views=view_list("hidden_views"),
        center_mark_only_views=view_list("center_mark_only_views"),
        tangent_edges=str(
            projection_data.get("tangent_edges", "omit")
        ).lower(),
        section_view=(
            str(projection_data["section_view"]).lower()
            if projection_data.get("section_view")
            else None
        ),
        section_reference_view=(
            str(projection_data["section_reference_view"]).lower()
            if projection_data.get("section_reference_view")
            else None
        ),
        section_offset_mm=float(
            projection_data.get("section_offset_mm", 0.0)
        ),
        hatch_angle_deg=float(
            projection_data.get("hatch_angle_deg", 45.0)
        ),
        hatch_spacing_mm=float(
            projection_data.get("hatch_spacing_mm", 4.0)
        ),
        pitch_circle_views=view_list("pitch_circle_views"),
    )
    if projection.tangent_edges not in {"omit", "thin", "full"}:
        raise ValueError("projection.tangent_edges deve essere omit, thin o full.")

    if projection.hidden_line_mode not in {"all", "essential"}:
        raise ValueError(
            "projection.hidden_line_mode deve essere all o essential."
        )

    if projection.section_view not in valid_views | {None}:
        raise ValueError("projection.section_view non è una delle sei viste.")

    if projection.section_reference_view not in valid_views | {None}:
        raise ValueError(
            "projection.section_reference_view non è una delle sei viste."
        )

    if (
        projection.section_view is not None
        and projection.section_reference_view == projection.section_view
    ):
        raise ValueError(
            "projection.section_reference_view deve essere diversa dalla sezione."
        )

    if projection.hatch_spacing_mm <= 0:
        raise ValueError("projection.hatch_spacing_mm deve essere positivo.")

    sheet_data = data["sheet"]

    sheet = SheetConfig(
        format=sheet_data.get(
            "format",
            "A3",
        ),
        orientation=sheet_data.get(
            "orientation",
            "landscape",
        ),
        margin_mm=float(
            sheet_data.get(
                "margin_mm",
                15.0,
            )
        ),
        gap_mm=float(
            sheet_data.get(
                "gap_mm",
                20.0,
            )
        ),
        horizontal_gap_mm=float(
            sheet_data.get(
                "horizontal_gap_mm",
                sheet_data.get("gap_mm", 20.0),
            )
        ),
        horizontal_gap_before_mm=float(
            sheet_data.get(
                "horizontal_gap_before_mm",
                sheet_data.get("horizontal_gap_mm", sheet_data.get("gap_mm", 20.0)),
            )
        ),
        horizontal_gap_after_mm=float(
            sheet_data.get(
                "horizontal_gap_after_mm",
                sheet_data.get("horizontal_gap_mm", sheet_data.get("gap_mm", 20.0)),
            )
        ),
        central_axis_offset_mm=float(sheet_data.get("central_axis_offset_mm", 0.0)),
        vertical_gap_mm=float(
            sheet_data.get(
                "vertical_gap_mm",
                sheet_data.get("gap_mm", 20.0),
            )
        ),
        vertical_gap_above_mm=float(
            sheet_data.get(
                "vertical_gap_above_mm",
                sheet_data.get("vertical_gap_mm", sheet_data.get("gap_mm", 20.0)),
            )
        ),
        vertical_gap_below_mm=float(
            sheet_data.get(
                "vertical_gap_below_mm",
                sheet_data.get("vertical_gap_mm", sheet_data.get("gap_mm", 20.0)),
            )
        ),
        automatic_scale=bool(
            sheet_data.get(
                "automatic_scale",
                True,
            )
        ),
        scale_mode=str(sheet_data.get("scale_mode", "iso")).lower(),
        layout=str(sheet_data.get("layout", "six_views")).lower(),
        show_view_labels=bool(sheet_data.get("show_view_labels", True)),
    )

    if sheet.layout not in {"six_views", "sectioned_first_angle"}:
        raise ValueError(
            "sheet.layout deve essere six_views o sectioned_first_angle."
        )

    if sheet.scale_mode not in {"iso", "fit"}:
        raise ValueError("sheet.scale_mode deve essere iso o fit.")

    if (
        sheet.horizontal_gap_mm <= 0
        or sheet.horizontal_gap_before_mm <= 0
        or sheet.horizontal_gap_after_mm <= 0
        or sheet.vertical_gap_mm <= 0
        or sheet.vertical_gap_above_mm <= 0
        or sheet.vertical_gap_below_mm <= 0
    ):
        raise ValueError("I gap orizzontale e verticale devono essere positivi.")

    output_data = data["output"]

    output_directory = (
        project_root
        / output_data.get(
            "directory",
            "output/project",
        )
    ).resolve()

    output = OutputConfig(
        directory=output_directory,
        svg=bool(
            output_data.get("svg", True)
        ),
        pdf=bool(
            output_data.get("pdf", False)
        ),
        dxf=bool(
            output_data.get("dxf", False)
        ),
        mp4=bool(
            output_data.get("mp4", False)
        ),
    )

    animation_data = data.get("animation", {})
    animation = AnimationConfig(
        resolution_x=int(animation_data.get("resolution_x", 1280)),
        resolution_y=int(animation_data.get("resolution_y", 720)),
        fps=int(animation_data.get("fps", 24)),
        frame_end=int(animation_data.get("frame_end", 216)),
        render_percentage=int(animation_data.get("render_percentage", 100)),
    )

    if animation.resolution_x <= 0 or animation.resolution_y <= 0:
        raise ValueError("La risoluzione Blender deve essere positiva.")

    if animation.fps <= 0 or animation.frame_end < 48:
        raise ValueError("fps non valido o frame_end Blender inferiore a 48.")

    if not 1 <= animation.render_percentage <= 100:
        raise ValueError("render_percentage deve essere compreso tra 1 e 100.")

    annotations: list[ExplicitAnnotationConfig] = []
    allowed_roles = {"CENTER", "SYMMETRY", "PITCH", "SECTION_CUT", "HATCH"}
    valid_views = {"front", "rear", "top", "bottom", "right", "left"}

    for index, item in enumerate(data.get("technical_annotations", [])):
        if not isinstance(item, dict):
            raise ValueError(f"technical_annotations[{index}] deve essere un oggetto.")

        view = str(item.get("view", "")).lower()
        role = str(item.get("role", "")).upper()

        if view not in valid_views:
            raise ValueError(f"Vista annotazione non valida: {view!r}.")

        if role not in allowed_roles:
            raise ValueError(f"Ruolo annotazione non valido: {role!r}.")

        raw_points = item.get("points")
        raw_center = item.get("center")
        raw_radius = item.get("radius")

        if raw_points is not None:
            points = tuple(
                _point2(point, f"technical_annotations[{index}].points")
                for point in raw_points
            )
            if len(points) < 2:
                raise ValueError("Una polilinea tecnica richiede almeno 2 punti.")
            annotations.append(
                ExplicitAnnotationConfig(view=view, role=role, points=points)
            )
            continue

        if raw_center is None or raw_radius is None:
            raise ValueError(
                "Un'annotazione richiede points oppure center e radius."
            )

        radius = float(raw_radius)
        if radius <= 0:
            raise ValueError("Il raggio dell'annotazione deve essere positivo.")
        annotations.append(
            ExplicitAnnotationConfig(
                view=view,
                role=role,
                center=_point2(
                    raw_center, f"technical_annotations[{index}].center"
                ),
                radius=radius,
            )
        )

    return ProjectConfig(
        model=model,
        blender=blender,
        main_view=main_view,
        projection=projection,
        sheet=sheet,
        output=output,
        animation=animation,
        technical_annotations=tuple(annotations),
    )
