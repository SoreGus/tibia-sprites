import shutil
import subprocess
import sys
from pathlib import Path


BASE_PATH = Path(__file__).resolve().parent

EXPORT_SCRIPT = (
    BASE_PATH
    / "export.py"
)

ORGANIZE_SCRIPT = (
    BASE_PATH
    / "organize_assets.py"
)

RAW_ASSETS_PATH = (
    BASE_PATH
    / "assets"
)

ORGANIZED_ASSETS_PATH = (
    BASE_PATH
    / "organized_assets"
)


PRESERVED_CATEGORIES = [
    "creatures",
    "effects",
    "missiles",
]


def run_script(
    script: Path,
):
    print()
    print("=" * 72)
    print(
        f"Running {script.name}"
    )
    print("=" * 72)

    subprocess.run(
        [
            sys.executable,
            str(script),
        ],
        cwd=BASE_PATH,
        check=True,
    )


def preserve_non_item_assets():
    print()
    print("=" * 72)
    print("Preserving non-item assets")
    print("=" * 72)

    for category in PRESERVED_CATEGORIES:
        source = (
            RAW_ASSETS_PATH
            / category
        )

        destination = (
            ORGANIZED_ASSETS_PATH
            / category
        )

        if not source.exists():
            print(
                f"{category}: not found"
            )

            continue

        if destination.exists():
            shutil.rmtree(
                destination
            )

        shutil.copytree(
            source,
            destination,
        )

        print(
            f"{category}: copied"
        )


def main():
    if not EXPORT_SCRIPT.exists():
        raise FileNotFoundError(
            f"Missing script: "
            f"{EXPORT_SCRIPT}"
        )

    if not ORGANIZE_SCRIPT.exists():
        raise FileNotFoundError(
            f"Missing script: "
            f"{ORGANIZE_SCRIPT}"
        )

    print(
        f"Base: "
        f"{BASE_PATH}"
    )

    #
    # 1. Export raw assets.
    #
    run_script(
        EXPORT_SCRIPT
    )

    if not RAW_ASSETS_PATH.exists():
        raise RuntimeError(
            "export.py finished, but "
            "assets/ was not created."
        )

    #
    # 2. Organize item assets.
    #
    run_script(
        ORGANIZE_SCRIPT
    )

    if not ORGANIZED_ASSETS_PATH.exists():
        raise RuntimeError(
            "organize_assets.py finished, "
            "but organized_assets/ "
            "was not created."
        )

    #
    # 3. Preserve creatures, effects
    # and missiles.
    #
    preserve_non_item_assets()

    #
    # 4. Remove raw assets.
    #
    print()
    print("=" * 72)
    print("Replacing raw assets")
    print("=" * 72)

    shutil.rmtree(
        RAW_ASSETS_PATH
    )

    #
    # 5. Rename organized_assets -> assets.
    #
    ORGANIZED_ASSETS_PATH.rename(
        RAW_ASSETS_PATH
    )

    print()
    print("=" * 72)
    print("FINISHED")
    print("=" * 72)

    print(
        f"Final assets: "
        f"{RAW_ASSETS_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()