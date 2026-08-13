import hashlib
import importlib.util
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path


# ============================================================
# PATHS
# ============================================================


BASE_PATH = Path(__file__).resolve().parent

CATALOG_PATH = (
    BASE_PATH
    / "catalog.json"
)

SOURCE_ASSETS_PATH = (
    BASE_PATH
    / "assets"
)

OUTPUT_PATH = (
    BASE_PATH
    / "organized_assets"
)

EXPORT_SCRIPT_PATH = (
    BASE_PATH
    / "export.py"
)

DAT_PATH = (
    BASE_PATH
    / "Tibia.dat"
)

SPR_PATH = (
    BASE_PATH
    / "Tibia.spr"
)


# ============================================================
# CONFIGURATION
# ============================================================


COPY_MODE = "copy"

SPRITE_SIZE = 32


DIRECTION_NAMES = {
    0: "north",
    1: "east",
    2: "south",
    3: "west",
}


FRAME_GROUP_NAMES = {
    0: "idle",
    1: "walk",
}


# ============================================================
# HELPERS
# ============================================================


def load_json(
    path: Path,
):
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


def slugify(
    value: str | None,
):
    if not value:
        return "unknown"

    value = value.strip().lower()

    value = re.sub(
        r"[^a-z0-9]+",
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
        or "unknown"
    )


def ensure_directory(
    path: Path,
):
    path.mkdir(
        parents=True,
        exist_ok=True,
    )


def relative_to_base(
    path: Path,
):
    try:
        return path.relative_to(
            BASE_PATH
        ).as_posix()

    except ValueError:
        return path.as_posix()


def get_item_name(
    item: dict,
):
    name = item.get(
        "name"
    )

    if name:
        return slugify(
            name
        )

    rme_item = (
        item.get(
            "rme_item"
        )
        or {}
    )

    name = rme_item.get(
        "name"
    )

    if name:
        return slugify(
            name
        )

    return None


def get_item_identifier(
    item: dict,
):
    name = get_item_name(
        item
    )

    if name:
        return name

    return str(
        item[
            "id"
        ]
    )


def get_source_pngs(
    source: Path,
):
    return sorted(
        source.rglob(
            "*.png"
        )
    )


# Files emitted by the DAT/SPR extractor encode the complete sprite tensor.
# Only ``frame`` is temporal.  The remaining coordinates select a static
# variation (or a compositing layer) and must never be appended to a frame
# sequence.
RAW_FRAME_FILENAME = re.compile(
    r"^frame_(?P<frame>\d+)_x_(?P<pattern_x>\d+)_"
    r"y_(?P<pattern_y>\d+)_z_(?P<pattern_z>\d+)_"
    r"layer_(?P<layer>\d+)\.png$",
    re.IGNORECASE,
)


def get_raw_frame_coordinates(
    source: Path,
    fallback_index: int,
):
    match = RAW_FRAME_FILENAME.match(
        source.name
    )

    if match:
        data = {
            name: int(value)
            for name, value in match.groupdict().items()
        }

        data["raw_frame_file"] = True
        return data

    # A legacy/unlabelled PNG has no reliable temporal coordinate.  Keep it
    # as an independent pattern instead of guessing that its position in a
    # directory means an animation frame.
    return {
        "frame": 0,
        "pattern_x": fallback_index,
        "pattern_y": 0,
        "pattern_z": 0,
        "layer": 0,
        "raw_frame_file": False,
    }


def frame_sort_key(
    source: Path,
):
    coordinates = get_raw_frame_coordinates(
        source,
        0,
    )

    return (
        coordinates["pattern_z"],
        coordinates["pattern_y"],
        coordinates["pattern_x"],
        coordinates["layer"],
        coordinates["frame"],
        source.as_posix(),
    )


# ============================================================
# JSON OUTPUT
# ============================================================


def write_json(
    path: Path,
    data: dict,
):
    ensure_directory(
        path.parent
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write(
            "\n"
        )


def write_asset_json(
    destination: Path,
    data: dict,
):
    write_json(
        destination
        / "asset.json",
        data,
    )


# ============================================================
# DAT GRAPHICS METADATA
# ============================================================


def build_animation_data(
    graphics: dict,
):
    animator = graphics.get(
        "animator"
    )

    if not animator:
        return None

    phases = (
        animator.get(
            "phases",
            [],
        )
    )

    durations = []

    for phase in phases:
        durations.append(
            {
                "min": (
                    phase[
                        "min_duration"
                    ]
                ),

                "max": (
                    phase[
                        "max_duration"
                    ]
                ),
            }
        )

    return {
        "async": (
            animator[
                "async"
            ]
        ),

        "loop_count": (
            animator[
                "loop_count"
            ]
        ),

        "start_phase": (
            animator[
                "start_phase"
            ]
        ),

        "frame_durations": (
            durations
        ),
    }


def build_graphics_data(
    graphics: dict,
):
    sprite_width = (
        graphics[
            "width"
        ]
    )

    sprite_height = (
        graphics[
            "height"
        ]
    )

    data = {
        "sprite_width": (
            sprite_width
        ),

        "sprite_height": (
            sprite_height
        ),

        "width": (
            sprite_width
            * SPRITE_SIZE
        ),

        "height": (
            sprite_height
            * SPRITE_SIZE
        ),

        "real_size": (
            graphics.get(
                "real_size"
            )
        ),

        "layers": (
            graphics[
                "layers"
            ]
        ),

        "pattern_x": (
            graphics[
                "pattern_x"
            ]
        ),

        "pattern_y": (
            graphics[
                "pattern_y"
            ]
        ),

        "pattern_z": (
            graphics[
                "pattern_z"
            ]
        ),

        "frames": (
            graphics[
                "frames"
            ]
        ),

        "frame_layout": {
            "temporal_axis": "frame",
            "variation_axes": [
                "pattern_x",
                "pattern_y",
                "pattern_z",
                "layer",
            ],
            "source_filename": (
                "frame_{frame:03d}_x_{pattern_x:02d}_"
                "y_{pattern_y:02d}_z_{pattern_z:02d}_"
                "layer_{layer:02d}.png"
            ),
        },
    }

    animation = (
        build_animation_data(
            graphics
        )
    )

    if animation:
        data[
            "animation"
        ] = animation

    return data


def build_single_record_data(
    asset_id: int,
    asset_name: str | None,
    asset_type: str,
    record: dict,
):
    data = {
        "id": (
            asset_id
        ),

        "name": (
            asset_name
        ),

        "type": (
            asset_type
        ),

        "sprite_size": (
            SPRITE_SIZE
        ),
    }

    graphics = (
        record.get(
            "graphics"
        )
    )

    if graphics:
        data.update(
            build_graphics_data(
                graphics
            )
        )

    return data


# ============================================================
# SOURCE ITEM ASSETS
# ============================================================


def get_source_asset_path(
    item: dict,
):
    asset_path = (
        item.get(
            "asset_path"
        )
    )

    if asset_path:
        candidate = (
            BASE_PATH
            / asset_path
        )

        if candidate.exists():
            return candidate

    item_id = (
        item[
            "id"
        ]
    )

    items_path = (
        SOURCE_ASSETS_PATH
        / "items"
    )

    direct = (
        items_path
        / str(
            item_id
        )
    )

    if direct.exists():
        return direct

    if not items_path.exists():
        return None

    for category_path in (
        items_path.iterdir()
    ):
        if not category_path.is_dir():
            continue

        direct = (
            category_path
            / str(
                item_id
            )
        )

        if direct.exists():
            return direct

        matches = sorted(
            category_path.glob(
                f"{item_id}_*"
            )
        )

        if matches:
            return matches[
                0
            ]

    return None


# ============================================================
# SOURCE RUNTIME ASSETS
# ============================================================


def get_runtime_pngs(
    source: Path,
):
    if source.is_file():
        if (
            source.suffix.lower()
            == ".png"
        ):
            return [
                source
            ]

        return []

    return get_source_pngs(
        source
    )


# ============================================================
# OUTPUT WRITER
# ============================================================


class AssetWriter:
    def __init__(
        self,
    ):
        self.counters = defaultdict(
            int
        )

        self.records = []

        self.files_written = 0

    def next_filename(
        self,
        directory: Path,
        prefix: str,
    ):
        key = (
            directory.as_posix(),
            prefix,
        )

        self.counters[
            key
        ] += 1

        index = (
            self.counters[
                key
            ]
        )

        return (
            f"{prefix}_"
            f"{index:03d}.png"
        )

    def write_file(
        self,
        source: Path,
        destination: Path,
    ):
        ensure_directory(
            destination.parent
        )

        if destination.exists():
            destination.unlink()

        if COPY_MODE == "symlink":
            destination.symlink_to(
                source.resolve()
            )

        else:
            shutil.copy2(
                source,
                destination,
            )

        self.files_written += 1

    def add_record(
        self,
        asset_id: int,
        asset_name: str | None,
        asset_type: str,
        category: str,
        source: Path,
        destination: Path,
        semantic: dict | None = None,
    ):
        self.records.append(
            {
                "item_id": (
                    asset_id
                ),

                "item_name": (
                    asset_name
                ),

                "asset_type": (
                    asset_type
                ),

                "category": (
                    category
                ),

                "semantic": (
                    semantic
                    or {}
                ),

                "source": (
                    relative_to_base(
                        source
                    )
                ),

                "destination": (
                    relative_to_base(
                        destination
                    )
                ),
            }
        )

    def export(
        self,
        item: dict,
        source_directory: Path,
        destination_directory: Path,
        prefix: str,
        category: str,
        semantic: dict | None = None,
    ):
        source_pngs = sorted(
            get_source_pngs(
                source_directory
            ),
            key=frame_sort_key,
        )

        if not source_pngs:
            return 0

        written = 0

        for index, source_png in enumerate(source_pngs):
            coordinates = get_raw_frame_coordinates(
                source_png,
                index,
            )

            # A sequence lives below one exact pattern/layer tuple.  Thus an
            # edge such as "east" with several patterns cannot accidentally
            # become one long e_001, e_002, ... animation.
            destination = (
                destination_directory
                / f"pattern_x_{coordinates['pattern_x']:02d}"
                / f"pattern_y_{coordinates['pattern_y']:02d}"
                / f"pattern_z_{coordinates['pattern_z']:02d}"
                / f"layer_{coordinates['layer']:02d}"
                / (
                    f"{prefix}_"
                    f"frame_{coordinates['frame']:03d}.png"
                )
            )

            self.write_file(
                source=source_png,
                destination=destination,
            )

            self.add_record(
                asset_id=(
                    item[
                        "id"
                    ]
                ),

                asset_name=(
                    item.get(
                        "name"
                    )
                ),

                asset_type=(
                    item.get(
                        "asset_type"
                    )
                    or "item"
                ),

                category=category,

                source=source_png,

                destination=destination,

                semantic={
                    **(semantic or {}),
                    "frame": coordinates["frame"],
                    "pattern_x": coordinates["pattern_x"],
                    "pattern_y": coordinates["pattern_y"],
                    "pattern_z": coordinates["pattern_z"],
                    "layer": coordinates["layer"],
                    "raw_frame_file": coordinates["raw_frame_file"],
                },
            )

            written += 1

        return written

    def export_runtime(
        self,
        asset_type: str,
        asset_id: int,
        asset_name: str | None,
        source: Path,
        destination_directory: Path,
        prefix: str,
        semantic: dict | None = None,
    ):
        source_pngs = (
            get_runtime_pngs(
                source
            )
        )

        if not source_pngs:
            return 0

        written = 0

        for source_png in source_pngs:
            filename = (
                self.next_filename(
                    directory=(
                        destination_directory
                    ),
                    prefix=prefix,
                )
            )

            destination = (
                destination_directory
                / filename
            )

            self.write_file(
                source=source_png,
                destination=destination,
            )

            self.add_record(
                asset_id=asset_id,
                asset_name=asset_name,
                asset_type=asset_type,
                category=asset_type,
                source=source_png,
                destination=destination,
                semantic=semantic,
            )

            written += 1

        return written


# ============================================================
# BRUSH DIRECTORIES
# ============================================================


BRUSH_DIRECTORIES = {
    "doodad": "doodads",
    "carpet": "carpets",
    "wall": "walls",
    "table": "tables",
    "wall decoration": (
        "wall_decorations"
    ),
}


def get_brush_directory(
    brush_type: str | None,
):
    if not brush_type:
        return "brushes"

    normalized = (
        brush_type.strip().lower()
    )

    return (
        BRUSH_DIRECTORIES.get(
            normalized,
            slugify(
                normalized
            ),
        )
    )


# ============================================================
# TILESET DIRECTORIES
# ============================================================


def get_tileset_path(
    tileset_name: str,
):
    name = (
        slugify(
            tileset_name
        )
    )

    equipment_prefix = (
        "equipments_"
    )

    if name.startswith(
        equipment_prefix
    ):
        subtype = name[
            len(
                equipment_prefix
            ):
        ]

        return (
            OUTPUT_PATH
            / "equipments"
            / subtype
        )

    weapon_prefix = (
        "weapons_"
    )

    if name.startswith(
        weapon_prefix
    ):
        subtype = name[
            len(
                weapon_prefix
            ):
        ]

        return (
            OUTPUT_PATH
            / "weapons"
            / subtype
        )

    return (
        OUTPUT_PATH
        / "tilesets"
        / name
    )


# ============================================================
# ITEM VARIANT PATHS
# ============================================================


def get_variant_directory(
    family_directory: Path,
    item_id: int,
):
    """
    A semantic family can contain several DAT objects.

    Those DAT objects MUST NOT share the same physical
    animation directory.

    Example:

        grounds/sea/
            variants/
                4608/
                4609/

    This prevents unrelated Sea graphics from being
    interpreted as frames of one animation.
    """

    return (
        family_directory
        / "variants"
        / str(
            item_id
        )
    )


# ============================================================
# GROUND
# ============================================================


def organize_ground(
    writer: AssetWriter,
    item: dict,
    source: Path,
    ground: dict,
):
    ground_name = (
        slugify(
            ground.get(
                "name"
            )
        )
    )

    family_destination = (
        OUTPUT_PATH
        / "grounds"
        / ground_name
    )

    destination = (
        get_variant_directory(
            family_directory=(
                family_destination
            ),
            item_id=(
                item[
                    "id"
                ]
            ),
        )
    )

    prefix = (
        f"{ground_name}_"
        f"{item['id']}"
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=prefix,
        category="ground",
        semantic={
            "ground_name": (
                ground.get(
                    "name"
                )
            ),

            "look_id": (
                ground.get(
                    "look_id"
                )
            ),

            "z_order": (
                ground.get(
                    "z_order"
                )
            ),

            "variant_id": (
                item[
                    "id"
                ]
            ),

            "family_directory": (
                relative_to_base(
                    family_destination
                )
            ),
        },
    )


# ============================================================
# BORDER
# ============================================================


def get_border_ground_names(
    border: dict,
):
    result = []

    seen = set()

    for ground in border.get(
        "grounds",
        [],
    ):
        name = (
            ground.get(
                "ground_name"
            )
        )

        if not name:
            continue

        if name in seen:
            continue

        seen.add(
            name
        )

        result.append(
            name
        )

    return result


def get_border_family_name(
    border: dict,
):
    border_name = (
        border.get(
            "border_name"
        )
    )

    if border_name:
        return slugify(
            border_name
        )

    border_id = (
        border.get(
            "border_id"
        )
    )

    return (
        f"border_{border_id}"
    )


def organize_border(
    writer: AssetWriter,
    item: dict,
    source: Path,
    border: dict,
):
    edge = (
        slugify(
            border.get(
                "edge"
            )
        )
    )

    ground_names = (
        get_border_ground_names(
            border
        )
    )

    total_written = 0

    if ground_names:
        for raw_ground_name in (
            ground_names
        ):
            ground_name = (
                slugify(
                    raw_ground_name
                )
            )

            family_destination = (
                OUTPUT_PATH
                / "grounds"
                / ground_name
                / "borders"
                / edge
            )

            destination = (
                get_variant_directory(
                    family_directory=(
                        family_destination
                    ),
                    item_id=(
                        item[
                            "id"
                        ]
                    ),
                )
            )

            prefix = (
                f"{ground_name}_"
                f"{edge}_"
                f"{item['id']}"
            )

            total_written += (
                writer.export(
                    item=item,
                    source_directory=source,
                    destination_directory=destination,
                    prefix=prefix,
                    category="ground_border",
                    semantic={
                        "ground_name": (
                            raw_ground_name
                        ),

                        "border_id": (
                            border.get(
                                "border_id"
                            )
                        ),

                        "border_name": (
                            border.get(
                                "border_name"
                            )
                        ),

                        "edge": (
                            border.get(
                                "edge"
                            )
                        ),

                        "variant_id": (
                            item[
                                "id"
                            ]
                        ),

                        "family_directory": (
                            relative_to_base(
                                family_destination
                            )
                        ),
                    },
                )
            )

        return total_written

    family_name = (
        get_border_family_name(
            border
        )
    )

    family_destination = (
        OUTPUT_PATH
        / "borders"
        / family_name
        / edge
    )

    destination = (
        get_variant_directory(
            family_directory=(
                family_destination
            ),
            item_id=(
                item[
                    "id"
                ]
            ),
        )
    )

    prefix = (
        f"{family_name}_"
        f"{edge}_"
        f"{item['id']}"
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=prefix,
        category="border",
        semantic={
            "border_id": (
                border.get(
                    "border_id"
                )
            ),

            "border_name": (
                border.get(
                    "border_name"
                )
            ),

            "edge": (
                border.get(
                    "edge"
                )
            ),

            "variant_id": (
                item[
                    "id"
                ]
            ),

            "family_directory": (
                relative_to_base(
                    family_destination
                )
            ),
        },
    )


# ============================================================
# GENERIC BRUSH
# ============================================================


def organize_brush(
    writer: AssetWriter,
    item: dict,
    source: Path,
    brush: dict,
):
    brush_type = (
        brush.get(
            "brush_type"
        )
    )

    raw_brush_name = (
        brush.get(
            "brush_name"
        )
    )

    brush_name = (
        slugify(
            raw_brush_name
        )
    )

    directory_name = (
        get_brush_directory(
            brush_type
        )
    )

    family_destination = (
        OUTPUT_PATH
        / directory_name
        / brush_name
    )

    destination = (
        get_variant_directory(
            family_directory=(
                family_destination
            ),
            item_id=(
                item[
                    "id"
                ]
            ),
        )
    )

    prefix = (
        get_item_name(
            item
        )
        or brush_name
    )

    prefix = (
        f"{prefix}_"
        f"{item['id']}"
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=prefix,
        category=directory_name,
        semantic={
            "brush_name": (
                raw_brush_name
            ),

            "brush_type": (
                brush_type
            ),

            "element": (
                brush.get(
                    "element"
                )
            ),

            "properties": (
                brush.get(
                    "properties"
                )
            ),

            "variant_id": (
                item[
                    "id"
                ]
            ),

            "family_directory": (
                relative_to_base(
                    family_destination
                )
            ),
        },
    )


# ============================================================
# TILESET
# ============================================================


def organize_tileset(
    writer: AssetWriter,
    item: dict,
    source: Path,
    tileset: dict,
):
    raw_tileset_name = (
        tileset.get(
            "tileset"
        )
        or "unknown"
    )

    destination_root = (
        get_tileset_path(
            raw_tileset_name
        )
    )

    item_identifier = (
        get_item_identifier(
            item
        )
    )

    family_destination = (
        destination_root
        / item_identifier
    )

    destination = (
        get_variant_directory(
            family_directory=(
                family_destination
            ),
            item_id=(
                item[
                    "id"
                ]
            ),
        )
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=(
            f"{item_identifier}_"
            f"{item['id']}"
        ),
        category="tileset",
        semantic={
            "tileset": (
                raw_tileset_name
            ),

            "variant_id": (
                item[
                    "id"
                ]
            ),

            "family_directory": (
                relative_to_base(
                    family_destination
                )
            ),
        },
    )


# ============================================================
# FALLBACK
# ============================================================


def organize_unclassified(
    writer: AssetWriter,
    item: dict,
    source: Path,
):
    asset_type = (
        slugify(
            item.get(
                "asset_type"
            )
        )
    )

    item_identifier = (
        get_item_identifier(
            item
        )
    )

    family_destination = (
        OUTPUT_PATH
        / "unclassified"
        / asset_type
        / item_identifier
    )

    destination = (
        get_variant_directory(
            family_directory=(
                family_destination
            ),
            item_id=(
                item[
                    "id"
                ]
            ),
        )
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=(
            f"{item_identifier}_"
            f"{item['id']}"
        ),
        category="unclassified",
        semantic={
            "original_asset_type": (
                item.get(
                    "asset_type"
                )
            ),

            "variant_id": (
                item[
                    "id"
                ]
            ),

            "family_directory": (
                relative_to_base(
                    family_destination
                )
            ),
        },
    )


# ============================================================
# ITEM ORGANIZATION
# ============================================================


def organize_item(
    writer: AssetWriter,
    item: dict,
    source: Path,
):
    rme = (
        item.get(
            "rme"
        )
        or {}
    )

    grounds = (
        rme.get(
            "grounds",
            [],
        )
    )

    borders = (
        rme.get(
            "borders",
            [],
        )
    )

    brushes = (
        rme.get(
            "brushes",
            [],
        )
    )

    tilesets = (
        rme.get(
            "tilesets",
            [],
        )
    )

    if grounds:
        total = 0
        seen = set()

        for ground in grounds:
            key = (
                ground.get(
                    "name"
                ),
                ground.get(
                    "look_id"
                ),
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            total += organize_ground(
                writer=writer,
                item=item,
                source=source,
                ground=ground,
            )

        return (
            "ground",
            total,
        )

    if borders:
        total = 0
        seen = set()

        for border in borders:
            key = (
                border.get(
                    "border_id"
                ),

                border.get(
                    "edge"
                ),

                tuple(
                    get_border_ground_names(
                        border
                    )
                ),
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            total += organize_border(
                writer=writer,
                item=item,
                source=source,
                border=border,
            )

        return (
            "border",
            total,
        )

    if brushes:
        total = 0
        seen = set()

        for brush in brushes:
            key = (
                brush.get(
                    "brush_type"
                ),

                brush.get(
                    "brush_name"
                ),
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            total += organize_brush(
                writer=writer,
                item=item,
                source=source,
                brush=brush,
            )

        return (
            "brush",
            total,
        )

    if tilesets:
        total = 0
        seen = set()

        for tileset in tilesets:
            tileset_name = (
                tileset.get(
                    "tileset"
                )
            )

            if tileset_name in seen:
                continue

            seen.add(
                tileset_name
            )

            total += organize_tileset(
                writer=writer,
                item=item,
                source=source,
                tileset=tileset,
            )

        return (
            "tileset",
            total,
        )

    total = (
        organize_unclassified(
            writer=writer,
            item=item,
            source=source,
        )
    )

    return (
        "unclassified",
        total,
    )


# ============================================================
# ITEM ASSET.JSON
# ============================================================


def get_item_metadata_name(
    record: dict,
):
    semantic = (
        record.get(
            "semantic"
        )
        or {}
    )

    for key in (
        "ground_name",
        "border_name",
        "brush_name",
        "tileset",
    ):
        value = (
            semantic.get(
                key
            )
        )

        if value:
            return str(
                value
            )

    value = (
        record.get(
            "item_name"
        )
    )

    if value:
        return str(
            value
        )

    return None


def get_family_directory_from_record(
    record: dict,
):
    semantic = (
        record.get(
            "semantic"
        )
        or {}
    )

    family = (
        semantic.get(
            "family_directory"
        )
    )

    if family:
        return (
            BASE_PATH
            / family
        )

    destination = (
        BASE_PATH
        / record[
            "destination"
        ]
    )

    return destination.parent


def build_variant_file_layout(
    records: list,
    item_id: int,
):
    """Describe the exported DAT tensor without flattening it into frames."""
    files = []

    for record in records:
        if int(record["item_id"]) != item_id:
            continue

        semantic = record.get("semantic") or {}

        if "frame" not in semantic:
            continue

        destination = Path(record["destination"])
        variant_marker = ("variants", str(item_id))
        path_parts = destination.parts

        try:
            marker_index = next(
                index
                for index in range(len(path_parts) - 1)
                if path_parts[index:index + 2] == variant_marker
            )
            relative_path = Path(
                *path_parts[marker_index + 2:]
            ).as_posix()
        except StopIteration:
            relative_path = destination.name

        files.append(
            {
                "frame": semantic["frame"],
                "pattern_x": semantic["pattern_x"],
                "pattern_y": semantic["pattern_y"],
                "pattern_z": semantic["pattern_z"],
                "layer": semantic["layer"],
                "path": relative_path,
            }
        )

    files.sort(
        key=lambda entry: (
            entry["pattern_z"],
            entry["pattern_y"],
            entry["pattern_x"],
            entry["layer"],
            entry["frame"],
        )
    )

    return {
        "temporal_axis": "frame",
        "variation_axes": [
            "pattern_x",
            "pattern_y",
            "pattern_z",
            "layer",
        ],
        "files": files,
    }


def write_item_asset_metadata(
    writer: AssetWriter,
    item_record_by_id: dict,
):
    """
    Write metadata at the semantic family level.

    Important:
        variants are separate DAT objects.

    Therefore:

        grounds/sea/asset.json

    describes all Sea variants, while each physical DAT object
    remains isolated under:

        grounds/sea/variants/<DAT ID>/
    """

    families = defaultdict(
        lambda: {
            "records": [],
            "item_ids": set(),
        }
    )

    for record in writer.records:
        if (
            record[
                "asset_type"
            ]
            in (
                "creatures",
                "effects",
                "missiles",
            )
        ):
            continue

        family_directory = (
            get_family_directory_from_record(
                record
            )
        )

        key = (
            family_directory.resolve()
        )

        families[
            key
        ][
            "records"
        ].append(
            record
        )

        families[
            key
        ][
            "item_ids"
        ].add(
            int(
                record[
                    "item_id"
                ]
            )
        )

    written = 0

    for family_directory, info in (
        families.items()
    ):
        records = (
            info[
                "records"
            ]
        )

        ids = sorted(
            info[
                "item_ids"
            ]
        )

        if not records:
            continue

        first_record = (
            records[
                0
            ]
        )

        category = (
            first_record[
                "category"
            ]
        )

        name = (
            get_item_metadata_name(
                first_record
            )
        )

        variants = []

        for item_id in ids:
            dat_record = (
                item_record_by_id.get(
                    item_id
                )
            )

            if not dat_record:
                continue

            graphics = (
                dat_record.get(
                    "graphics"
                )
            )

            if not graphics:
                continue

            matching_record = next(
                (
                    entry
                    for entry in records
                    if int(
                        entry[
                            "item_id"
                        ]
                    )
                    == item_id
                ),
                None,
            )

            variant_name = None

            if matching_record:
                variant_name = (
                    matching_record.get(
                        "item_name"
                    )
                )

            variant = {
                "id": (
                    item_id
                ),

                "name": (
                    variant_name
                ),

                "path": (
                    f"variants/"
                    f"{item_id}"
                ),
            }

            variant.update(
                build_graphics_data(
                    graphics
                )
            )

            variant["exported_files"] = build_variant_file_layout(
                records,
                item_id,
            )

            variants.append(
                variant
            )

            #
            # Each DAT variant also receives its own
            # asset.json so tools can inspect the variant
            # without needing to understand the parent.
            #
            variant_data = {
                "id": (
                    item_id
                ),

                "name": (
                    variant_name
                    or name
                ),

                "type": (
                    category
                ),

                "sprite_size": (
                    SPRITE_SIZE
                ),

                "family": (
                    name
                ),
            }

            variant_data.update(
                build_graphics_data(
                    graphics
                )
            )

            variant_data["exported_files"] = build_variant_file_layout(
                records,
                item_id,
            )

            write_asset_json(
                destination=(
                    family_directory
                    / "variants"
                    / str(
                        item_id
                    )
                ),
                data=variant_data,
            )

            written += 1

        if not variants:
            continue

        family_data = {
            "name": (
                name
            ),

            "type": (
                category
            ),

            "sprite_size": (
                SPRITE_SIZE
            ),

            "variants": (
                variants
            ),
        }

        write_asset_json(
            destination=family_directory,
            data=family_data,
        )

        written += 1

    return written


# ============================================================
# ORGANIZE ITEMS
# ============================================================


def organize_items(
    catalog: dict,
):
    items = (
        catalog.get(
            "items",
            [],
        )
    )

    writer = (
        AssetWriter()
    )

    statistics = {
        "items_processed": 0,
        "items_with_assets": 0,
        "missing_assets": 0,

        "named_items": 0,

        "ground_items": 0,
        "border_items": 0,
        "brush_items": 0,
        "tileset_items": 0,
        "unclassified_items": 0,

        "item_json_files": 0,

        "pngs_written": 0,

        "creatures_processed": 0,
        "creatures_named": 0,
        "creatures_missing": 0,
        "creatures_duplicates": 0,
        "creatures_animated": 0,
        "creature_pngs_written": 0,
        "creature_json_files": 0,

        "effects_processed": 0,
        "effects_named": 0,
        "effects_missing": 0,
        "effect_pngs_written": 0,
        "effect_json_files": 0,

        "missiles_processed": 0,
        "missiles_named": 0,
        "missiles_missing": 0,
        "missile_pngs_written": 0,
        "missile_json_files": 0,
    }

    total = (
        len(
            items
        )
    )

    for position, item in enumerate(
        items,
        start=1,
    ):
        statistics[
            "items_processed"
        ] += 1

        if get_item_name(
            item
        ):
            statistics[
                "named_items"
            ] += 1

        source = (
            get_source_asset_path(
                item
            )
        )

        if source is None:
            statistics[
                "missing_assets"
            ] += 1

            if (
                position % 5000 == 0
                or position == total
            ):
                print(
                    f"  "
                    f"{position}/{total}"
                )

            continue

        source_pngs = (
            get_source_pngs(
                source
            )
        )

        if not source_pngs:
            statistics[
                "missing_assets"
            ] += 1

            continue

        statistics[
            "items_with_assets"
        ] += 1

        category, written = (
            organize_item(
                writer=writer,
                item=item,
                source=source,
            )
        )

        if category == "ground":
            statistics[
                "ground_items"
            ] += 1

        elif category == "border":
            statistics[
                "border_items"
            ] += 1

        elif category == "brush":
            statistics[
                "brush_items"
            ] += 1

        elif category == "tileset":
            statistics[
                "tileset_items"
            ] += 1

        else:
            statistics[
                "unclassified_items"
            ] += 1

        statistics[
            "pngs_written"
        ] += written

        if (
            position % 5000 == 0
            or position == total
        ):
            print(
                f"  "
                f"{position}/{total}"
            )

    return (
        writer,
        statistics,
    )


# ============================================================
# RUNTIME NAME HELPERS
# ============================================================


def normalize_runtime_entries(
    data,
):
    result = {}

    if isinstance(
        data,
        dict,
    ):
        for key, value in (
            data.items()
        ):
            try:
                asset_id = (
                    int(
                        key
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if isinstance(
                value,
                str,
            ):
                result[
                    asset_id
                ] = {
                    "name": (
                        value
                    ),
                }

            elif isinstance(
                value,
                dict,
            ):
                result[
                    asset_id
                ] = value

        return result

    if isinstance(
        data,
        list,
    ):
        for entry in data:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            asset_id = (
                entry.get(
                    "id"
                )
                or entry.get(
                    "look_type"
                )
                or entry.get(
                    "lookType"
                )
            )

            try:
                asset_id = (
                    int(
                        asset_id
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            result[
                asset_id
            ] = entry

    return result


def get_runtime_names(
    catalog: dict,
    asset_type: str,
):
    runtime_names = (
        catalog.get(
            "runtime_names"
        )
        or {}
    )

    data = (
        runtime_names.get(
            asset_type
        )
    )

    if data is not None:
        return normalize_runtime_entries(
            data
        )

    data = (
        catalog.get(
            asset_type
        )
    )

    if data is not None:
        return normalize_runtime_entries(
            data
        )

    return {}


def get_runtime_entry_name(
    entry: dict | None,
):
    if not entry:
        return None

    for key in (
        "primary_name",
        "name",
        "monster_name",
        "creature_name",
        "effect_name",
        "missile_name",
        "constant",
    ):
        value = (
            entry.get(
                key
            )
        )

        if value:
            return str(
                value
            )

    names = (
        entry.get(
            "names"
        )
    )

    if isinstance(
        names,
        list,
    ):
        names = [
            str(
                name
            )
            for name in names
            if name
        ]

        if names:
            return names[
                0
            ]

    return None


# ============================================================
# DAT LOADING
# ============================================================


def load_export_module():
    specification = (
        importlib.util.spec_from_file_location(
            "tibia_1501_export",
            EXPORT_SCRIPT_PATH,
        )
    )

    if (
        specification is None
        or specification.loader is None
    ):
        raise RuntimeError(
            "Could not load export.py"
        )

    module = (
        importlib.util.module_from_spec(
            specification
        )
    )

    specification.loader.exec_module(
        module
    )

    return module


def load_dat_records():
    print()
    print(
        "Loading DAT metadata..."
    )

    export_module = (
        load_export_module()
    )

    export_module.DAT_PATH = (
        DAT_PATH
    )

    export_module.SPR_PATH = (
        SPR_PATH
    )

    spr_reader = (
        export_module.SprReader(
            SPR_PATH
        )
    )

    parsed = (
        export_module.parse_dat(
            sprite_count_limit=(
                spr_reader.sprite_count
            )
        )
    )

    return parsed


# ============================================================
# CREATURE SIGNATURES
# ============================================================


def get_creature_sprite_signature(
    record: dict,
):
    sprite_ids = []

    frame_groups = (
        record[
            "frame_groups"
        ][
            "groups"
        ]
    )

    for group in frame_groups:
        graphics = (
            group[
                "graphics"
            ]
        )

        sprite_ids.extend(
            int(
                sprite_id
            )
            for sprite_id
            in graphics[
                "sprite_ids"
            ]
            if sprite_id != 0
        )

    if not sprite_ids:
        return None

    payload = ",".join(
        str(
            sprite_id
        )
        for sprite_id
        in sprite_ids
    )

    return hashlib.sha256(
        payload.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# CREATURE RAW PNG LOOKUP
# ============================================================


def find_creature_group_directory(
    source: Path,
    group_index: int,
    group_type: int,
):
    expected = (
        source
        / (
            f"group_"
            f"{group_index:02d}_"
            f"type_"
            f"{group_type}"
        )
    )

    if expected.exists():
        return expected

    matches = sorted(
        source.glob(
            f"group_{group_index:02d}_*"
        )
    )

    if matches:
        return matches[
            0
        ]

    return None


def build_raw_graphic_filename(
    frame: int,
    pattern_x: int,
    pattern_y: int,
    pattern_z: int,
    layer: int,
):
    return (
        f"frame_{frame:03d}_"
        f"x_{pattern_x:02d}_"
        f"y_{pattern_y:02d}_"
        f"z_{pattern_z:02d}_"
        f"layer_{layer:02d}.png"
    )


# ============================================================
# CREATURE ANIMATION
# ============================================================


def get_direction_name(
    pattern_x: int,
    pattern_x_count: int,
):
    if pattern_x_count == 4:
        return (
            DIRECTION_NAMES.get(
                pattern_x,
                f"direction_{pattern_x:02d}",
            )
        )

    return (
        f"direction_{pattern_x:02d}"
    )


def get_group_name(
    group_type: int,
    group_index: int,
):
    return (
        FRAME_GROUP_NAMES.get(
            group_type,
            f"group_{group_index:02d}",
        )
    )


def build_creature_asset_data(
    asset_id: int,
    asset_name: str | None,
    record: dict,
):
    groups = (
        record[
            "frame_groups"
        ][
            "groups"
        ]
    )

    result = {
        "id": (
            asset_id
        ),

        "name": (
            asset_name
        ),

        "type": (
            "creature"
        ),

        "sprite_size": (
            SPRITE_SIZE
        ),

        "animations": {},
    }

    if not groups:
        return result

    root_graphics = (
        groups[
            0
        ][
            "graphics"
        ]
    )

    result[
        "sprite_width"
    ] = (
        root_graphics[
            "width"
        ]
    )

    result[
        "sprite_height"
    ] = (
        root_graphics[
            "height"
        ]
    )

    result[
        "width"
    ] = (
        root_graphics[
            "width"
        ]
        * SPRITE_SIZE
    )

    result[
        "height"
    ] = (
        root_graphics[
            "height"
        ]
        * SPRITE_SIZE
    )

    result[
        "real_size"
    ] = (
        root_graphics.get(
            "real_size"
        )
    )

    result[
        "layers"
    ] = (
        root_graphics[
            "layers"
        ]
    )

    for group in groups:
        graphics = (
            group[
                "graphics"
            ]
        )

        animation_name = (
            get_group_name(
                group_type=(
                    group[
                        "type"
                    ]
                ),
                group_index=(
                    group[
                        "index"
                    ]
                ),
            )
        )

        animation_data = {
            "frames": (
                graphics[
                    "frames"
                ]
            ),

            "directions": [
                get_direction_name(
                    direction,
                    graphics[
                        "pattern_x"
                    ],
                )
                for direction in range(
                    graphics[
                        "pattern_x"
                    ]
                )
            ],
        }

        if (
            graphics[
                "pattern_y"
            ]
            != 1
        ):
            animation_data[
                "pattern_y"
            ] = (
                graphics[
                    "pattern_y"
                ]
            )

        if (
            graphics[
                "pattern_z"
            ]
            != 1
        ):
            animation_data[
                "pattern_z"
            ] = (
                graphics[
                    "pattern_z"
                ]
            )

        if (
            graphics[
                "width"
            ]
            != root_graphics[
                "width"
            ]
            or graphics[
                "height"
            ]
            != root_graphics[
                "height"
            ]
            or graphics[
                "layers"
            ]
            != root_graphics[
                "layers"
            ]
        ):
            animation_data[
                "sprite_width"
            ] = (
                graphics[
                    "width"
                ]
            )

            animation_data[
                "sprite_height"
            ] = (
                graphics[
                    "height"
                ]
            )

            animation_data[
                "width"
            ] = (
                graphics[
                    "width"
                ]
                * SPRITE_SIZE
            )

            animation_data[
                "height"
            ] = (
                graphics[
                    "height"
                ]
                * SPRITE_SIZE
            )

            animation_data[
                "layers"
            ] = (
                graphics[
                    "layers"
                ]
            )

        animation = (
            build_animation_data(
                graphics
            )
        )

        if animation:
            animation_data[
                "animation"
            ] = animation

        result[
            "animations"
        ][
            animation_name
        ] = animation_data

    return result


def organize_creature_animation(
    writer: AssetWriter,
    asset_id: int,
    asset_name: str | None,
    source: Path,
    destination: Path,
    record: dict,
):
    total_written = 0

    groups = (
        record[
            "frame_groups"
        ][
            "groups"
        ]
    )

    for group in groups:
        group_index = (
            group[
                "index"
            ]
        )

        group_type = (
            group[
                "type"
            ]
        )

        graphics = (
            group[
                "graphics"
            ]
        )

        source_group = (
            find_creature_group_directory(
                source=source,
                group_index=group_index,
                group_type=group_type,
            )
        )

        if source_group is None:
            continue

        group_name = (
            get_group_name(
                group_type=group_type,
                group_index=group_index,
            )
        )

        frames = (
            graphics[
                "frames"
            ]
        )

        pattern_x_count = (
            graphics[
                "pattern_x"
            ]
        )

        pattern_y_count = (
            graphics[
                "pattern_y"
            ]
        )

        pattern_z_count = (
            graphics[
                "pattern_z"
            ]
        )

        layers = (
            graphics[
                "layers"
            ]
        )

        for frame in range(
            frames
        ):
            for pattern_z in range(
                pattern_z_count
            ):
                for pattern_y in range(
                    pattern_y_count
                ):
                    for pattern_x in range(
                        pattern_x_count
                    ):
                        direction_name = (
                            get_direction_name(
                                pattern_x,
                                pattern_x_count,
                            )
                        )

                        for layer in range(
                            layers
                        ):
                            raw_filename = (
                                build_raw_graphic_filename(
                                    frame=frame,
                                    pattern_x=pattern_x,
                                    pattern_y=pattern_y,
                                    pattern_z=pattern_z,
                                    layer=layer,
                                )
                            )

                            source_png = (
                                source_group
                                / raw_filename
                            )

                            if not source_png.exists():
                                continue

                            if (
                                pattern_y_count == 1
                                and pattern_z_count == 1
                                and layers == 1
                            ):
                                if frames == 1:
                                    destination_png = (
                                        destination
                                        / group_name
                                        / (
                                            f"{direction_name}.png"
                                        )
                                    )

                                else:
                                    destination_png = (
                                        destination
                                        / group_name
                                        / direction_name
                                        / (
                                            f"{frame + 1:03d}.png"
                                        )
                                    )

                            else:
                                destination_png = (
                                    destination
                                    / group_name
                                    / direction_name
                                    / (
                                        f"frame_"
                                        f"{frame + 1:03d}_"
                                        f"y_"
                                        f"{pattern_y:02d}_"
                                        f"z_"
                                        f"{pattern_z:02d}_"
                                        f"layer_"
                                        f"{layer:02d}.png"
                                    )
                                )

                            writer.write_file(
                                source=source_png,
                                destination=destination_png,
                            )

                            writer.add_record(
                                asset_id=asset_id,
                                asset_name=asset_name,
                                asset_type="creatures",
                                category="creature_animation",
                                source=source_png,
                                destination=destination_png,
                                semantic={
                                    "frame_group_index": (
                                        group_index
                                    ),

                                    "frame_group_type": (
                                        group_type
                                    ),

                                    "animation": (
                                        group_name
                                    ),

                                    "direction": (
                                        direction_name
                                    ),

                                    "direction_index": (
                                        pattern_x
                                    ),

                                    "frame": (
                                        frame
                                    ),

                                    "pattern_y": (
                                        pattern_y
                                    ),

                                    "pattern_z": (
                                        pattern_z
                                    ),

                                    "layer": (
                                        layer
                                    ),
                                },
                            )

                            total_written += 1

    if total_written > 0:
        asset_data = (
            build_creature_asset_data(
                asset_id=asset_id,
                asset_name=asset_name,
                record=record,
            )
        )

        write_asset_json(
            destination=destination,
            data=asset_data,
        )

    return total_written


# ============================================================
# CREATURE ORGANIZATION
# ============================================================


def choose_canonical_creature(
    ids: list[int],
    runtime_names: dict,
):
    named = []

    for asset_id in ids:
        entry = (
            runtime_names.get(
                asset_id
            )
        )

        if get_runtime_entry_name(
            entry
        ):
            named.append(
                asset_id
            )

    if named:
        return min(
            named
        )

    return min(
        ids
    )


def organize_creatures(
    catalog: dict,
    writer: AssetWriter,
    statistics: dict,
    dat_records: dict,
):
    source_root = (
        SOURCE_ASSETS_PATH
        / "creatures"
    )

    if not source_root.exists():
        print(
            "  creatures: "
            "source directory not found."
        )

        return

    runtime_names = (
        get_runtime_names(
            catalog,
            "creatures",
        )
    )

    creatures = (
        dat_records.get(
            "creatures",
            []
        )
    )

    record_by_id = {
        int(
            record[
                "id"
            ]
        ): record
        for record in creatures
    }

    source_by_id = {}

    for path in sorted(
        source_root.iterdir()
    ):
        raw_name = (
            path.stem
            if path.is_file()
            else path.name
        )

        match = re.match(
            r"^(\d+)",
            raw_name,
        )

        if not match:
            continue

        asset_id = (
            int(
                match.group(
                    1
                )
            )
        )

        if asset_id not in source_by_id:
            source_by_id[
                asset_id
            ] = path

    statistics[
        "creatures_processed"
    ] = (
        len(
            source_by_id
        )
    )

    signature_groups = defaultdict(
        list
    )

    no_signature = []

    for asset_id in sorted(
        source_by_id
    ):
        record = (
            record_by_id.get(
                asset_id
            )
        )

        if record is None:
            statistics[
                "creatures_missing"
            ] += 1

            continue

        runtime_entry = (
            runtime_names.get(
                asset_id
            )
        )

        if get_runtime_entry_name(
            runtime_entry
        ):
            statistics[
                "creatures_named"
            ] += 1

        signature = (
            get_creature_sprite_signature(
                record
            )
        )

        if signature:
            signature_groups[
                signature
            ].append(
                asset_id
            )

        else:
            no_signature.append(
                asset_id
            )

    groups = list(
        signature_groups.values()
    )

    for asset_id in no_signature:
        groups.append(
            [
                asset_id
            ]
        )

    used_destinations = {}

    for ids in groups:
        canonical_id = (
            choose_canonical_creature(
                ids=ids,
                runtime_names=runtime_names,
            )
        )

        statistics[
            "creatures_duplicates"
        ] += max(
            0,
            len(
                ids
            ) - 1,
        )

        record = (
            record_by_id.get(
                canonical_id
            )
        )

        source = (
            source_by_id.get(
                canonical_id
            )
        )

        if (
            record is None
            or source is None
        ):
            statistics[
                "creatures_missing"
            ] += 1

            continue

        runtime_entry = (
            runtime_names.get(
                canonical_id
            )
        )

        raw_name = (
            get_runtime_entry_name(
                runtime_entry
            )
        )

        if raw_name:
            identifier = (
                slugify(
                    raw_name
                )
            )

        else:
            identifier = (
                str(
                    canonical_id
                )
            )

        destination = (
            OUTPUT_PATH
            / "creatures"
            / identifier
        )

        destination_key = (
            destination.resolve()
        )

        signature = (
            get_creature_sprite_signature(
                record
            )
        )

        previous_signature = (
            used_destinations.get(
                destination_key
            )
        )

        if (
            previous_signature is not None
            and previous_signature != signature
        ):
            identifier = (
                f"{identifier}_"
                f"{canonical_id}"
            )

            destination = (
                OUTPUT_PATH
                / "creatures"
                / identifier
            )

            destination_key = (
                destination.resolve()
            )

        used_destinations[
            destination_key
        ] = signature

        written = (
            organize_creature_animation(
                writer=writer,
                asset_id=canonical_id,
                asset_name=raw_name,
                source=source,
                destination=destination,
                record=record,
            )
        )

        if written == 0:
            statistics[
                "creatures_missing"
            ] += 1

            continue

        statistics[
            "creatures_animated"
        ] += 1

        statistics[
            "creature_pngs_written"
        ] += written

        statistics[
            "creature_json_files"
        ] += 1

        statistics[
            "pngs_written"
        ] += written


# ============================================================
# EFFECTS / MISSILES
# ============================================================


def organize_runtime_category(
    catalog: dict,
    writer: AssetWriter,
    statistics: dict,
    asset_type: str,
    dat_records: dict,
):
    source_root = (
        SOURCE_ASSETS_PATH
        / asset_type
    )

    if not source_root.exists():
        print(
            f"  {asset_type}: "
            f"source directory not found."
        )

        return

    runtime_names = (
        get_runtime_names(
            catalog,
            asset_type,
        )
    )

    records = (
        dat_records.get(
            asset_type,
            []
        )
    )

    record_by_id = {
        int(
            record[
                "id"
            ]
        ): record
        for record in records
    }

    singular = {
        "effects": "effect",
        "missiles": "missile",
    }[
        asset_type
    ]

    processed_key = (
        f"{asset_type}_processed"
    )

    named_key = (
        f"{asset_type}_named"
    )

    missing_key = (
        f"{asset_type}_missing"
    )

    png_key = (
        f"{singular}_pngs_written"
    )

    json_key = (
        f"{singular}_json_files"
    )

    entries = []

    for path in sorted(
        source_root.iterdir()
    ):
        raw_name = (
            path.stem
            if path.is_file()
            else path.name
        )

        match = re.match(
            r"^(\d+)",
            raw_name,
        )

        if not match:
            continue

        asset_id = (
            int(
                match.group(
                    1
                )
            )
        )

        entries.append(
            (
                asset_id,
                path,
            )
        )

    seen_ids = set()

    for asset_id, source in entries:
        if asset_id in seen_ids:
            continue

        seen_ids.add(
            asset_id
        )

        statistics[
            processed_key
        ] += 1

        runtime_entry = (
            runtime_names.get(
                asset_id
            )
        )

        raw_name = (
            get_runtime_entry_name(
                runtime_entry
            )
        )

        if raw_name:
            statistics[
                named_key
            ] += 1

            identifier = (
                slugify(
                    raw_name
                )
            )

        else:
            identifier = (
                str(
                    asset_id
                )
            )

        source_pngs = (
            get_runtime_pngs(
                source
            )
        )

        if not source_pngs:
            statistics[
                missing_key
            ] += 1

            continue

        destination = (
            OUTPUT_PATH
            / asset_type
            / identifier
        )

        written = (
            writer.export_runtime(
                asset_type=asset_type,
                asset_id=asset_id,
                asset_name=raw_name,
                source=source,
                destination_directory=destination,
                prefix=identifier,
                semantic={
                    "runtime_id": (
                        asset_id
                    ),

                    "runtime_name": (
                        raw_name
                    ),

                    "runtime_data": (
                        runtime_entry
                        or {}
                    ),
                },
            )
        )

        statistics[
            png_key
        ] += written

        statistics[
            "pngs_written"
        ] += written

        dat_record = (
            record_by_id.get(
                asset_id
            )
        )

        if dat_record:
            asset_data = (
                build_single_record_data(
                    asset_id=asset_id,
                    asset_name=raw_name,
                    asset_type=singular,
                    record=dat_record,
                )
            )

            write_asset_json(
                destination=destination,
                data=asset_data,
            )

            statistics[
                json_key
            ] += 1


def organize_runtime_assets(
    catalog: dict,
    writer: AssetWriter,
    statistics: dict,
    dat_records: dict,
):
    print()
    print(
        "Organizing creatures..."
    )

    organize_creatures(
        catalog=catalog,
        writer=writer,
        statistics=statistics,
        dat_records=dat_records,
    )

    print()
    print(
        "Organizing effects..."
    )

    organize_runtime_category(
        catalog=catalog,
        writer=writer,
        statistics=statistics,
        asset_type="effects",
        dat_records=dat_records,
    )

    print()
    print(
        "Organizing missiles..."
    )

    organize_runtime_category(
        catalog=catalog,
        writer=writer,
        statistics=statistics,
        asset_type="missiles",
        dat_records=dat_records,
    )


# ============================================================
# MANIFEST
# ============================================================


def write_manifest(
    catalog: dict,
    writer: AssetWriter,
    statistics: dict,
):
    manifest = {
        "version": "15.01",

        "item_frame_schema": {
            "temporal_axis": "frame",
            "variation_axes": [
                "pattern_x",
                "pattern_y",
                "pattern_z",
                "layer",
            ],
            "rule": (
                "Only frame is an animation sequence. Patterns and layers "
                "are independent static variations."
            ),
        },

        "copy_mode": (
            COPY_MODE
        ),

        "sprite_size": (
            SPRITE_SIZE
        ),

        "sources": {
            "catalog": (
                relative_to_base(
                    CATALOG_PATH
                )
            ),

            "assets": (
                relative_to_base(
                    SOURCE_ASSETS_PATH
                )
            ),
        },

        "statistics": (
            statistics
        ),

        "catalog_validation": (
            catalog.get(
                "validation"
            )
        ),

        "files": (
            writer.records
        ),
    }

    path = (
        OUTPUT_PATH
        / "manifest.json"
    )

    write_json(
        path=path,
        data=manifest,
    )


# ============================================================
# VALIDATION
# ============================================================


def validate_known_border(
    writer: AssetWriter,
):
    expected = {
        1054: "cse",
        1055: "csw",
        1056: "cne",
        1057: "cnw",
        1058: "e",
        1059: "w",
        1060: "s",
        1061: "n",
        1062: "dse",
        1063: "dsw",
        1064: "dne",
        1065: "dnw",
    }

    print()
    print(
        "=" * 72
    )

    print(
        "KNOWN BORDER VALIDATION"
    )

    print(
        "=" * 72
    )

    passed = True

    for item_id, edge in (
        expected.items()
    ):
        matches = [
            record
            for record in writer.records
            if (
                record[
                    "item_id"
                ]
                == item_id
                and record[
                    "semantic"
                ].get(
                    "edge"
                )
                == edge
            )
        ]

        if matches:
            print(
                f"{item_id}: "
                f"{edge} OK -> "
                f"{matches[0]['destination']}"
            )

        else:
            print(
                f"{item_id}: "
                f"{edge} NOT FOUND"
            )

            passed = False

    print()

    if passed:
        print(
            "SUCCESS: known border family "
            "was organized correctly."
        )

    else:
        print(
            "WARNING: known border family "
            "did not fully validate."
        )

    return passed


def validate_item_variant_isolation(
    writer: AssetWriter,
):
    """
    Validate that no item animation directory contains
    PNGs from more than one DAT ID.
    """

    directories = defaultdict(
        set
    )

    for record in writer.records:
        if (
            record[
                "asset_type"
            ]
            in (
                "creatures",
                "effects",
                "missiles",
            )
        ):
            continue

        destination = (
            Path(
                record[
                    "destination"
                ]
            )
        )

        directories[
            destination.parent.as_posix()
        ].add(
            int(
                record[
                    "item_id"
                ]
            )
        )

    invalid = {
        directory: ids
        for directory, ids
        in directories.items()
        if len(
            ids
        ) > 1
    }

    print()
    print(
        "=" * 72
    )

    print(
        "ITEM VARIANT ISOLATION VALIDATION"
    )

    print(
        "=" * 72
    )

    if not invalid:
        print(
            "SUCCESS: every physical item directory "
            "contains exactly one DAT ID."
        )

        return True

    for directory, ids in sorted(
        invalid.items()
    ):
        print(
            f"INVALID: "
            f"{directory} -> "
            f"{sorted(ids)}"
        )

    print()
    print(
        "WARNING: some animation directories "
        "still contain multiple DAT IDs."
    )

    return False


def validate_item_frame_tensor(
    writer: AssetWriter,
    item_record_by_id: dict,
):
    """Verify that every exported item keeps frames within one variation."""
    groups = defaultdict(list)

    for record in writer.records:
        semantic = record.get("semantic") or {}

        required_coordinates = {
            "frame",
            "pattern_x",
            "pattern_y",
            "pattern_z",
            "layer",
        }

        # Creature/runtime records have their own direction/frame layout and
        # intentionally do not carry the item-pattern axes.
        if not required_coordinates.issubset(semantic):
            continue

        key = (
            int(record["item_id"]),
            semantic["pattern_x"],
            semantic["pattern_y"],
            semantic["pattern_z"],
            semantic["layer"],
        )
        groups[key].append(semantic["frame"])

    invalid = []

    for key, frames in groups.items():
        graphics = (item_record_by_id.get(key[0]) or {}).get("graphics") or {}
        expected_frames = graphics.get("frames")

        if expected_frames is None:
            continue

        actual = sorted(set(frames))
        expected = list(range(expected_frames))

        if actual != expected:
            invalid.append((key, actual, expected))

    print()
    print("=" * 72)
    print("ITEM FRAME TENSOR VALIDATION")
    print("=" * 72)

    if not invalid:
        print(
            "SUCCESS: frames are isolated by pattern_x, pattern_y, "
            "pattern_z and layer."
        )
        return True

    for key, actual, expected in invalid:
        print(
            f"INVALID: item {key[0]}, x={key[1]}, y={key[2]}, "
            f"z={key[3]}, layer={key[4]} -> frames {actual}; "
            f"expected {expected}"
        )

    return False


def validate_demon_output():
    runtime_path = (
        OUTPUT_PATH
        / "creatures"
        / "angry_demon"
    )

    print()
    print(
        "=" * 72
    )

    print(
        "CREATURE ANIMATION VALIDATION"
    )

    print(
        "=" * 72
    )

    if not runtime_path.exists():
        print(
            "angry_demon: not found"
        )

        return False

    idle_pngs = list(
        (
            runtime_path
            / "idle"
        ).rglob(
            "*.png"
        )
    )

    walk_pngs = list(
        (
            runtime_path
            / "walk"
        ).rglob(
            "*.png"
        )
    )

    asset_json = (
        runtime_path
        / "asset.json"
    )

    print(
        f"angry_demon idle: "
        f"{len(idle_pngs)}"
    )

    print(
        f"angry_demon walk: "
        f"{len(walk_pngs)}"
    )

    print(
        f"asset.json:       "
        f"{asset_json.exists()}"
    )

    expected = (
        len(
            idle_pngs
        )
        == 4
        and len(
            walk_pngs
        )
        == 32
        and asset_json.exists()
    )

    if expected:
        print()
        print(
            "SUCCESS: angry_demon "
            "animation was reconstructed."
        )

    else:
        print()
        print(
            "WARNING: angry_demon output "
            "does not match expected 4 + 32."
        )

    return expected


# ============================================================
# MAIN
# ============================================================


def main():
    required_paths = [
        CATALOG_PATH,
        SOURCE_ASSETS_PATH,
        EXPORT_SCRIPT_PATH,
        DAT_PATH,
        SPR_PATH,
    ]

    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing: "
                f"{path}"
            )

    if COPY_MODE not in (
        "copy",
        "symlink",
    ):
        raise ValueError(
            "COPY_MODE must be "
            "'copy' or 'symlink'."
        )

    print(
        f"Catalog: "
        f"{relative_to_base(CATALOG_PATH)}"
    )

    print(
        f"Assets:  "
        f"{relative_to_base(SOURCE_ASSETS_PATH)}"
    )

    print(
        f"Output:  "
        f"{relative_to_base(OUTPUT_PATH)}"
    )

    print(
        f"Mode:    "
        f"{COPY_MODE}"
    )

    print()
    print(
        "Loading catalog..."
    )

    catalog = (
        load_json(
            CATALOG_PATH
        )
    )

    if OUTPUT_PATH.exists():
        print(
            "Removing previous "
            "organized output..."
        )

        if OUTPUT_PATH.is_symlink():
            OUTPUT_PATH.unlink()

        else:
            shutil.rmtree(
                OUTPUT_PATH
            )

    ensure_directory(
        OUTPUT_PATH
    )

    dat_records = (
        load_dat_records()
    )

    item_record_by_id = {
        int(
            record[
                "id"
            ]
        ): record
        for record in dat_records.get(
            "items",
            []
        )
    }

    print()
    print(
        "Organizing items..."
    )

    (
        writer,
        statistics,
    ) = (
        organize_items(
            catalog
        )
    )

    print()
    print(
        "Writing item asset.json files..."
    )

    statistics[
        "item_json_files"
    ] = (
        write_item_asset_metadata(
            writer=writer,
            item_record_by_id=(
                item_record_by_id
            ),
        )
    )

    organize_runtime_assets(
        catalog=catalog,
        writer=writer,
        statistics=statistics,
        dat_records=dat_records,
    )

    validation_passed = (
        validate_known_border(
            writer
        )
    )

    statistics[
        "known_border_validation"
    ] = validation_passed

    variant_validation = (
        validate_item_variant_isolation(
            writer
        )
    )

    statistics[
        "item_variant_isolation_validation"
    ] = variant_validation

    frame_tensor_validation = (
        validate_item_frame_tensor(
            writer,
            item_record_by_id,
        )
    )

    statistics[
        "item_frame_tensor_validation"
    ] = frame_tensor_validation

    creature_validation = (
        validate_demon_output()
    )

    statistics[
        "creature_animation_validation"
    ] = creature_validation

    write_manifest(
        catalog=catalog,
        writer=writer,
        statistics=statistics,
    )

    print()
    print(
        "=" * 72
    )

    print(
        "FINISHED"
    )

    print(
        "=" * 72
    )

    print(
        f"Items processed:     "
        f"{statistics['items_processed']}"
    )

    print(
        f"Items with assets:   "
        f"{statistics['items_with_assets']}"
    )

    print(
        f"Named items:         "
        f"{statistics['named_items']}"
    )

    print(
        f"Missing assets:      "
        f"{statistics['missing_assets']}"
    )

    print(
        f"Ground items:        "
        f"{statistics['ground_items']}"
    )

    print(
        f"Border items:        "
        f"{statistics['border_items']}"
    )

    print(
        f"Brush items:         "
        f"{statistics['brush_items']}"
    )

    print(
        f"Tileset-only:        "
        f"{statistics['tileset_items']}"
    )

    print(
        f"Unclassified:        "
        f"{statistics['unclassified_items']}"
    )

    print(
        f"Item JSON files:     "
        f"{statistics['item_json_files']}"
    )

    print()

    print(
        f"Creatures:           "
        f"{statistics['creatures_processed']}"
    )

    print(
        f"Named creatures:     "
        f"{statistics['creatures_named']}"
    )

    print(
        f"Animated creatures:  "
        f"{statistics['creatures_animated']}"
    )

    print(
        f"Duplicate creatures: "
        f"{statistics['creatures_duplicates']}"
    )

    print(
        f"Creature PNGs:       "
        f"{statistics['creature_pngs_written']}"
    )

    print(
        f"Creature JSON files: "
        f"{statistics['creature_json_files']}"
    )

    print()

    print(
        f"Effects:             "
        f"{statistics['effects_processed']}"
    )

    print(
        f"Named effects:       "
        f"{statistics['effects_named']}"
    )

    print(
        f"Effect PNGs:         "
        f"{statistics['effect_pngs_written']}"
    )

    print(
        f"Effect JSON files:   "
        f"{statistics['effect_json_files']}"
    )

    print()

    print(
        f"Missiles:            "
        f"{statistics['missiles_processed']}"
    )

    print(
        f"Named missiles:      "
        f"{statistics['missiles_named']}"
    )

    print(
        f"Missile PNGs:        "
        f"{statistics['missile_pngs_written']}"
    )

    print(
        f"Missile JSON files:  "
        f"{statistics['missile_json_files']}"
    )

    print()

    print(
        f"Total PNGs:          "
        f"{statistics['pngs_written']}"
    )

    print(
        f"Output:              "
        f"{OUTPUT_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()
