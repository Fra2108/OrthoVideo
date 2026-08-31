from argparse import ArgumentParser
from dataclasses import replace
from pathlib import Path
import sys

from orthovideo.pipeline import generate_project
from orthovideo.project_config import load_project_config


def _vector(values):
    return tuple(float(value) for value in values)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="orthovideo",
        description="Genera tavola first-angle e animazione da STEP/STP o OBJ.",
    )
    parser.add_argument("model", nargs="?", help="Modello STEP/STP/OBJ; sostituisce quello del config.")
    parser.add_argument("--config", type=Path, help="File JSON di progetto.")
    parser.add_argument("--normal", nargs=3, metavar=("X", "Y", "Z"), type=float)
    parser.add_argument("--up", nargs=3, metavar=("X", "Y", "Z"), type=float)
    parser.add_argument("--output", type=Path, help="Directory di output.")
    parser.add_argument(
        "--tangent-edges",
        choices=("omit", "thin", "full"),
        help="Politica per le linee di tangenza STEP.",
    )
    hidden = parser.add_mutually_exclusive_group()
    hidden.add_argument(
        "--hidden",
        action="store_true",
        help="Mostra tutte le linee nascoste tratteggiate.",
    )
    hidden.add_argument(
        "--no-hidden",
        action="store_true",
        help="Genera viste HLR pulite; consigliato quando è presente una sezione.",
    )
    parser.add_argument(
        "--hidden-view",
        action="append",
        choices=("front", "rear", "top", "bottom", "right", "left"),
        help="Mostra le nascoste solo nella vista indicata; opzione ripetibile.",
    )
    sections = parser.add_mutually_exclusive_group()
    sections.add_argument(
        "--section-view",
        choices=("front", "rear", "top", "bottom", "right", "left"),
        help="Aggiunge una sezione esatta/campionata nella vista scelta.",
    )
    sections.add_argument(
        "--no-section",
        action="store_true",
        help="Disattiva la sezione definita nel config.",
    )
    parser.add_argument(
        "--section-reference-view",
        choices=("front", "rear", "top", "bottom", "right", "left"),
        help="Vista sulla quale collocare la traccia A-A.",
    )
    parser.add_argument(
        "--section-offset",
        type=float,
        help="Offset del piano di sezione dal centro del modello, in mm.",
    )
    parser.add_argument(
        "--hatch-spacing",
        type=float,
        help="Passo della campitura a 45 gradi, in mm.",
    )
    parser.add_argument(
        "--pitch-circle-view",
        action="append",
        choices=("front", "rear", "top", "bottom", "right", "left"),
        help="Aggiunge automaticamente cerchio primitivo e radiali; ripetibile.",
    )
    video = parser.add_mutually_exclusive_group()
    video.add_argument("--video", action="store_true", help="Forza il rendering MP4.")
    video.add_argument("--no-video", action="store_true", help="Salta Blender/MP4.")
    video.add_argument(
        "--pdf-only",
        action="store_true",
        help="Genera soltanto orthographic_sheet.pdf, senza manifest o altri output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    package_root = Path(__file__).resolve().parents[2]
    config_file = (args.config or package_root / "config" / "project.json").resolve()
    project_root = config_file.parent.parent

    try:
        config = load_project_config(config_file, project_root)

        if args.model:
            model = Path(args.model).expanduser().resolve()
            if not model.exists():
                raise FileNotFoundError(f"Modello non trovato: {model}")
            if model.suffix.lower() not in {".step", ".stp", ".obj"}:
                raise ValueError("Il modello deve essere STEP, STP o OBJ.")
            config = replace(config, model=model)

        if args.normal or args.up:
            config = replace(
                config,
                main_view=replace(
                    config.main_view,
                    normal=_vector(args.normal) if args.normal else config.main_view.normal,
                    up=_vector(args.up) if args.up else config.main_view.up,
                ),
            )

        if args.output:
            config = replace(
                config,
                output=replace(config.output, directory=args.output.resolve()),
            )

        if (
            args.tangent_edges
            or args.hidden
            or args.no_hidden
            or args.hidden_view
            or args.section_view
            or args.no_section
            or args.section_reference_view
            or args.section_offset is not None
            or args.hatch_spacing is not None
            or args.pitch_circle_view
        ):
            if args.hatch_spacing is not None and args.hatch_spacing <= 0:
                raise ValueError("--hatch-spacing deve essere positivo.")

            config = replace(
                config,
                projection=replace(
                    config.projection,
                    tangent_edges=(
                        args.tangent_edges or config.projection.tangent_edges
                    ),
                    show_hidden=(
                        args.hidden
                        if args.hidden or args.no_hidden
                        else config.projection.show_hidden
                    ),
                    hidden_views=(
                        ()
                        if args.no_hidden
                        else tuple(args.hidden_view)
                        if args.hidden_view
                        else config.projection.hidden_views
                    ),
                    section_view=(
                        None
                        if args.no_section
                        else args.section_view or config.projection.section_view
                    ),
                    section_reference_view=(
                        args.section_reference_view
                        or config.projection.section_reference_view
                    ),
                    section_offset_mm=(
                        args.section_offset
                        if args.section_offset is not None
                        else config.projection.section_offset_mm
                    ),
                    hatch_spacing_mm=(
                        args.hatch_spacing
                        if args.hatch_spacing is not None
                        else config.projection.hatch_spacing_mm
                    ),
                    pitch_circle_views=(
                        tuple(args.pitch_circle_view)
                        if args.pitch_circle_view
                        else config.projection.pitch_circle_views
                    ),
                ),
            )

        if args.pdf_only:
            config = replace(
                config,
                output=replace(
                    config.output,
                    svg=False,
                    pdf=True,
                    dxf=False,
                    mp4=False,
                ),
            )
        elif args.video or args.no_video:
            config = replace(
                config,
                output=replace(config.output, mp4=args.video and not args.no_video),
            )

        print("OrthoVideo: generazione in corso...")
        print(f"Modello: {config.model}")
        result = generate_project(config, write_manifest=not args.pdf_only)
        print(f"Completato [{result.source_type}] - scala {result.drawing_scale:g}:1")

        for name, path in result.outputs.items():
            print(f"{name.upper()}: {path}")

        return 0
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
