import argparse
import json
import re
import shutil
from pathlib import Path

from PIL import Image


# ============================================================
# PATHS
# ============================================================


BASE_PATH = Path(__file__).resolve().parent

ASSETS_PATH = (
    BASE_PATH
    / "assets"
)

OUTPUT_PATH = (
    BASE_PATH
    / "gifs"
)


# ============================================================
# CONFIGURATION
# ============================================================


DEFAULT_FRAME_DURATION = 120

GIF_LOOP = 0


# ============================================================
# HELPERS
# ============================================================


def load_json(
    path: Path,
):
    if not path.exists():
        return None

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


def natural_key(
    path: Path,
):
    parts = re.split(
        r"(\d+)",
        path.name,
    )

    result = []

    for part in parts:
        if part.isdigit():
            result.append(
                int(
                    part
                )
            )

        else:
            result.append(
                part.lower()
            )

    return result


def sanitize_name(
    value: str,
):
    value = value.strip().lower()

    value = re.sub(
        r"[^a-z0-9_-]+",
        "_",
        value,
    )

    value = re.sub(
        r"_+",
        "_",
        value,
    )

    return (
        value.strip("_")
        or "animation"
    )


# ============================================================
# FILE GROUPING
# ============================================================


def get_sequence_prefix(
    path: Path,
):
    stem = path.stem

    #
    # Creature animation:
    #
    # 001.png
    # 002.png
    #
    if stem.isdigit():
        return "animation"

    #
    # Generic exported asset:
    #
    # sea_001.png
    # sea_002.png
    #
    match = re.match(
        r"^(.*?)[_-](\d+)$",
        stem,
    )

    if match:
        return sanitize_name(
            match.group(
                1
            )
        )

    return sanitize_name(
        stem
    )


def group_pngs(
    directory: Path,
):
    groups = {}

    for path in sorted(
        directory.glob(
            "*.png"
        ),
        key=natural_key,
    ):
        prefix = (
            get_sequence_prefix(
                path
            )
        )

        groups.setdefault(
            prefix,
            [],
        ).append(
            path
        )

    return groups


# ============================================================
# ASSET.JSON ANIMATION DATA
# ============================================================


def get_animation_block(
    asset_json: dict | None,
    relative_directory: Path,
):
    if not asset_json:
        return None

    animations = (
        asset_json.get(
            "animations"
        )
        or {}
    )

    parts = list(
        relative_directory.parts
    )

    if not parts:
        return None

    #
    # Creature layout:
    #
    # walk/north/
    # walk/east/
    #
    animation_name = (
        parts[
            0
        ]
    )

    return animations.get(
        animation_name
    )


def get_frame_durations(
    asset_json: dict | None,
    relative_directory: Path,
    frame_count: int,
):
    animation_block = (
        get_animation_block(
            asset_json,
            relative_directory,
        )
    )

    if not animation_block:
        return [
            DEFAULT_FRAME_DURATION
        ] * frame_count

    animation = (
        animation_block.get(
            "animation"
        )
        or {}
    )

    durations = (
        animation.get(
            "frame_durations"
        )
    )

    if not isinstance(
        durations,
        list,
    ):
        return [
            DEFAULT_FRAME_DURATION
        ] * frame_count

    result = []

    for entry in durations:
        if isinstance(
            entry,
            dict,
        ):
            minimum = entry.get(
                "min"
            )

            maximum = entry.get(
                "max"
            )

            if (
                minimum is not None
                and maximum is not None
            ):
                #
                # For preview, use the middle of
                # the DAT duration range.
                #
                duration = int(
                    (
                        int(
                            minimum
                        )
                        + int(
                            maximum
                        )
                    )
                    / 2
                )

            elif minimum is not None:
                duration = int(
                    minimum
                )

            elif maximum is not None:
                duration = int(
                    maximum
                )

            else:
                duration = (
                    DEFAULT_FRAME_DURATION
                )

        elif isinstance(
            entry,
            int,
        ):
            duration = entry

        else:
            duration = (
                DEFAULT_FRAME_DURATION
            )

        result.append(
            duration
        )

    if not result:
        return [
            DEFAULT_FRAME_DURATION
        ] * frame_count

    if len(
        result
    ) == frame_count:
        return result

    #
    # Metadata does not correspond exactly
    # to this sequence. Use preview speed.
    #
    return [
        DEFAULT_FRAME_DURATION
    ] * frame_count


# ============================================================
# GIF
# ============================================================


def prepare_frame(
    path: Path,
):
    image = Image.open(
        path
    ).convert(
        "RGBA"
    )

    return image


def save_gif(
    files: list[Path],
    output: Path,
    durations: list[int],
):
    if len(
        files
    ) < 2:
        return False

    frames = [
        prepare_frame(
            path
        )
        for path in files
    ]

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frames[
        0
    ].save(
        output,
        save_all=True,
        append_images=(
            frames[
                1:
            ]
        ),
        duration=durations,
        loop=GIF_LOOP,
        disposal=2,
        optimize=False,
    )

    for frame in frames:
        frame.close()

    return True


# ============================================================
# DIRECTORY PROCESSING
# ============================================================


def get_output_name(
    relative_directory: Path,
    prefix: str,
    group_count: int,
):
    #
    # walk/north/001.png...
    #
    # becomes:
    #
    # walk/north.gif
    #
    if (
        prefix == "animation"
        and relative_directory.parts
    ):
        return (
            Path(
                *relative_directory.parts[
                    :-1
                ]
            )
            / (
                f"{relative_directory.name}"
                f".gif"
            )
        )

    #
    # Root sequence:
    #
    # sea_001.png...
    #
    if str(
        relative_directory
    ) == ".":
        return Path(
            f"{prefix}.gif"
        )

    #
    # borders/sea_n_001.png...
    #
    return (
        relative_directory
        / (
            f"{prefix}.gif"
        )
    )


def process_directory(
    asset_path: Path,
    directory: Path,
    asset_json: dict | None,
    output_root: Path,
):
    relative_directory = (
        directory.relative_to(
            asset_path
        )
    )

    groups = (
        group_pngs(
            directory
        )
    )

    generated = []

    for prefix, files in (
        groups.items()
    ):
        #
        # A single PNG is static,
        # therefore there is no GIF.
        #
        if len(
            files
        ) < 2:
            continue

        durations = (
            get_frame_durations(
                asset_json=asset_json,
                relative_directory=(
                    relative_directory
                ),
                frame_count=len(
                    files
                ),
            )
        )

        relative_output = (
            get_output_name(
                relative_directory=(
                    relative_directory
                ),
                prefix=prefix,
                group_count=len(
                    groups
                ),
            )
        )

        output = (
            output_root
            / relative_output
        )

        if save_gif(
            files=files,
            output=output,
            durations=durations,
        ):
            generated.append(
                (
                    output,
                    len(
                        files
                    ),
                    durations,
                )
            )

    return generated


# ============================================================
# GENERATION
# ============================================================


def generate(
    category: str,
    asset_name: str,
):
    asset_path = (
        ASSETS_PATH
        / category
        / asset_name
    )

    if not asset_path.exists():
        raise FileNotFoundError(
            "Asset not found: "
            f"{asset_path}"
        )

    if not asset_path.is_dir():
        raise ValueError(
            "Asset must be a directory: "
            f"{asset_path}"
        )

    asset_json_path = (
        asset_path
        / "asset.json"
    )

    asset_json = (
        load_json(
            asset_json_path
        )
    )

    output_root = (
        OUTPUT_PATH
        / category
        / asset_name
    )

    if output_root.exists():
        shutil.rmtree(
            output_root
        )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Asset:  "
        f"{asset_path}"
    )

    print(
        f"Output: "
        f"{output_root}"
    )

    print(
        f"JSON:   "
        f"{'yes' if asset_json else 'no'}"
    )

    print()
    print(
        "Searching PNG sequences..."
    )

    generated = []

    directories = [
        asset_path
    ]

    directories.extend(
        sorted(
            path
            for path in asset_path.rglob(
                "*"
            )
            if path.is_dir()
        )
    )

    for directory in directories:
        result = (
            process_directory(
                asset_path=asset_path,
                directory=directory,
                asset_json=asset_json,
                output_root=output_root,
            )
        )

        generated.extend(
            result
        )

    print()

    print(
        "=" * 72
    )

    print(
        "GIF PREVIEWS"
    )

    print(
        "=" * 72
    )

    if not generated:
        print(
            "No animation sequence "
            "with 2 or more PNGs was found."
        )

        return

    for (
        output,
        frame_count,
        durations,
    ) in generated:
        try:
            relative = (
                output.relative_to(
                    BASE_PATH
                )
            )

        except ValueError:
            relative = output

        unique_durations = sorted(
            set(
                durations
            )
        )

        if len(
            unique_durations
        ) == 1:
            duration_text = (
                f"{unique_durations[0]} ms"
            )

        else:
            duration_text = (
                f"{min(unique_durations)}"
                f".."
                f"{max(unique_durations)} ms"
            )

        print(
            f"{relative} "
            f"| frames={frame_count} "
            f"| duration={duration_text}"
        )

    print()
    print(
        f"Generated GIFs: "
        f"{len(generated)}"
    )


# ============================================================
# MAIN
# ============================================================


def main():
    parser = (
        argparse.ArgumentParser(
            description=(
                "Generate GIF previews "
                "from organized Tibia assets."
            )
        )
    )

    parser.add_argument(
        "category",
        help=(
            "Asset category, for example "
            "grounds or creatures."
        ),
    )

    parser.add_argument(
        "asset",
        help=(
            "Asset directory name, for example "
            "sea or angry_demon."
        ),
    )

    arguments = (
        parser.parse_args()
    )

    generate(
        category=(
            arguments.category
        ),
        asset_name=(
            arguments.asset
        ),
    )


if __name__ == "__main__":
    main()