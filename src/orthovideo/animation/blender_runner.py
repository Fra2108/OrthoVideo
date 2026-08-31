from pathlib import Path
import subprocess


def check_blender(
    executable: str | Path,
) -> str:
    """
    Verifica che Blender possa essere avviato
    correttamente in modalità background.
    """

    executable = Path(executable)

    if not executable.exists():
        raise FileNotFoundError(
            f"Blender non trovato: {executable}"
        )

    command = [
        str(executable),
        "--background",
        "--python-expr",
        (
            "import bpy; "
            "print('ORTHOVIDEO_BLENDER_OK'); "
            "print('BLENDER_VERSION=' + bpy.app.version_string)"
        ),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    output = (
        result.stdout
        + "\n"
        + result.stderr
    )

    if (
        result.returncode != 0
        or "ORTHOVIDEO_BLENDER_OK" not in output
    ):
        raise RuntimeError(
            "Blender non ha superato il test.\n\n"
            + output
        )

    return output


def run_blender_script(
    executable: str | Path,
    script_file: str | Path,
    arguments: list[str] | None = None,
) -> str:
    """
    Esegue uno script Python all'interno di Blender
    in modalità background.
    """

    executable = Path(executable)
    script_file = Path(script_file)

    if not executable.exists():
        raise FileNotFoundError(
            f"Blender non trovato: {executable}"
        )

    if not script_file.exists():
        raise FileNotFoundError(
            f"Script Blender non trovato: {script_file}"
        )

    command = [
        str(executable),
        "--background",
        "--python",
        str(script_file),
    ]

    if arguments:
        command.append("--")
        command.extend(arguments)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    output = (
        result.stdout
        + "\n"
        + result.stderr
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Blender ha terminato con un errore.\n\n"
            + output
        )

    return output
