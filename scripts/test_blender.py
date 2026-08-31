from pathlib import Path

from orthovideo.project_config import load_project_config
from orthovideo.animation.blender_runner import check_blender


ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = (
    ROOT
    / "config"
    / "project.json"
)


def main():

    print()
    print("=" * 60)
    print("ORTHOVIDEO - BLENDER TEST")
    print("=" * 60)

    config = load_project_config(
        CONFIG_FILE,
        ROOT,
    )

    print()
    print("Blender:")
    print(config.blender.executable)

    print()
    print("Avvio Blender in background...")

    output = check_blender(
        config.blender.executable
    )

    print()
    print("BLENDER COLLEGATO CORRETTAMENTE")

    for line in output.splitlines():

        if (
            "ORTHOVIDEO_BLENDER_OK" in line
            or "BLENDER_VERSION=" in line
        ):
            print(line)

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()