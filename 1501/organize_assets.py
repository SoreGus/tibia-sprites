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


# ============================================================
# CONFIGURATION
# ============================================================


COPY_MODE = "copy"


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


# ============================================================
# SOURCE ITEM ASSETS
# ============================================================


def get_source_asset_path(
    item: dict,
):
    asset_path = item.get(
        "asset_path"
    )

    if asset_path:
        candidate = (
            BASE_PATH
            / asset_path
        )

        if candidate.exists():
            return candidate

    item_id = item[
        "id"
    ]

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


def get_runtime_source_path(
    asset_type: str,
    asset_id: int,
):
    root = (
        SOURCE_ASSETS_PATH
        / asset_type
    )

    if not root.exists():
        return None

    direct = (
        root
        / str(
            asset_id
        )
    )

    if direct.exists():
        return direct

    matches = sorted(
        root.glob(
            f"{asset_id}_*"
        )
    )

    if matches:
        return matches[
            0
        ]

    #
    # Some exporters may place the PNG directly
    # inside the category directory.
    #
    direct_png = (
        root
        / f"{asset_id}.png"
    )

    if direct_png.exists():
        return direct_png

    matches = sorted(
        root.glob(
            f"{asset_id}_*.png"
        )
    )

    if matches:
        return matches[
            0
        ]

    return None


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

        index = self.counters[
            key
        ]

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

    def export(
        self,
        item: dict,
        source_directory: Path,
        destination_directory: Path,
        prefix: str,
        category: str,
        semantic: dict | None = None,
    ):
        source_pngs = (
            get_source_pngs(
                source_directory
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

            self.records.append(
                {
                    "item_id": (
                        item[
                            "id"
                        ]
                    ),

                    "item_name": (
                        item.get(
                            "name"
                        )
                    ),

                    "asset_type": (
                        item.get(
                            "asset_type"
                        )
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
                            source_png
                        )
                    ),

                    "destination": (
                        relative_to_base(
                            destination
                        )
                    ),
                }
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
                        asset_type
                    ),

                    "semantic": (
                        semantic
                        or {}
                    ),

                    "source": (
                        relative_to_base(
                            source_png
                        )
                    ),

                    "destination": (
                        relative_to_base(
                            destination
                        )
                    ),
                }
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
    name = slugify(
        tileset_name
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
# GROUND
# ============================================================


def organize_ground(
    writer: AssetWriter,
    item: dict,
    source: Path,
    ground: dict,
):
    ground_name = slugify(
        ground.get(
            "name"
        )
    )

    destination = (
        OUTPUT_PATH
        / "grounds"
        / ground_name
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=ground_name,
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
        name = ground.get(
            "ground_name"
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
    border_name = border.get(
        "border_name"
    )

    if border_name:
        return slugify(
            border_name
        )

    border_id = border.get(
        "border_id"
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
    edge = slugify(
        border.get(
            "edge"
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
            ground_name = slugify(
                raw_ground_name
            )

            destination = (
                OUTPUT_PATH
                / "grounds"
                / ground_name
                / "borders"
            )

            prefix = (
                f"{ground_name}_"
                f"{edge}"
            )

            total_written += (
                writer.export(
                    item=item,
                    source_directory=source,
                    destination_directory=(
                        destination
                    ),
                    prefix=prefix,
                    category=(
                        "ground_border"
                    ),
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
                    },
                )
            )

        return total_written

    family_name = (
        get_border_family_name(
            border
        )
    )

    destination = (
        OUTPUT_PATH
        / "borders"
        / family_name
    )

    prefix = (
        f"{family_name}_"
        f"{edge}"
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
    brush_type = brush.get(
        "brush_type"
    )

    raw_brush_name = brush.get(
        "brush_name"
    )

    brush_name = slugify(
        raw_brush_name
    )

    directory_name = (
        get_brush_directory(
            brush_type
        )
    )

    destination = (
        OUTPUT_PATH
        / directory_name
        / brush_name
    )

    prefix = (
        get_item_name(
            item
        )
        or brush_name
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

    destination = (
        destination_root
        / item_identifier
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=item_identifier,
        category="tileset",
        semantic={
            "tileset": (
                raw_tileset_name
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
    asset_type = slugify(
        item.get(
            "asset_type"
        )
    )

    item_identifier = (
        get_item_identifier(
            item
        )
    )

    destination = (
        OUTPUT_PATH
        / "unclassified"
        / asset_type
        / item_identifier
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=item_identifier,
        category="unclassified",
        semantic={
            "original_asset_type": (
                item.get(
                    "asset_type"
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

    grounds = rme.get(
        "grounds",
        [],
    )

    borders = rme.get(
        "borders",
        [],
    )

    brushes = rme.get(
        "brushes",
        [],
    )

    tilesets = rme.get(
        "tilesets",
        [],
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

            total += (
                organize_ground(
                    writer=writer,
                    item=item,
                    source=source,
                    ground=ground,
                )
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

            total += (
                organize_border(
                    writer=writer,
                    item=item,
                    source=source,
                    border=border,
                )
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

            total += (
                organize_brush(
                    writer=writer,
                    item=item,
                    source=source,
                    brush=brush,
                )
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

            total += (
                organize_tileset(
                    writer=writer,
                    item=item,
                    source=source,
                    tileset=tileset,
                )
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
# ORGANIZE ITEMS
# ============================================================


def organize_items(
    catalog: dict,
):
    items = catalog.get(
        "items",
        [],
    )

    writer = AssetWriter()

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

        "pngs_written": 0,

        "creatures_processed": 0,
        "creatures_named": 0,
        "creatures_missing": 0,
        "creature_pngs_written": 0,

        "effects_processed": 0,
        "effects_named": 0,
        "effects_missing": 0,
        "effect_pngs_written": 0,

        "missiles_processed": 0,
        "missiles_named": 0,
        "missiles_missing": 0,
        "missile_pngs_written": 0,
    }

    total = len(
        items
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
                asset_id = int(
                    key
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
                    "name": value,
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
                asset_id = int(
                    asset_id
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

    data = runtime_names.get(
        asset_type
    )

    if data is not None:
        return normalize_runtime_entries(
            data
        )

    #
    # Compatibility with catalogs where the
    # enrichment was stored directly at root.
    #
    data = catalog.get(
        asset_type
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
        "name",
        "monster_name",
        "creature_name",
        "effect_name",
        "missile_name",
        "constant",
    ):
        value = entry.get(
            key
        )

        if value:
            return str(
                value
            )

    names = entry.get(
        "names"
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
# RUNTIME ASSET ORGANIZATION
# ============================================================


def organize_runtime_category(
    catalog: dict,
    writer: AssetWriter,
    statistics: dict,
    asset_type: str,
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

    singular = {
        "creatures": "creature",
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

    #
    # Runtime assets are driven by the raw
    # exported directories, not only by the
    # known-name table.
    #
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

        asset_id = int(
            match.group(
                1
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

            identifier = slugify(
                raw_name
            )

        else:
            identifier = str(
                asset_id
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
                destination_directory=(
                    destination
                ),
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


def organize_runtime_assets(
    catalog: dict,
    writer: AssetWriter,
    statistics: dict,
):
    print()
    print(
        "Organizing creatures..."
    )

    organize_runtime_category(
        catalog=catalog,
        writer=writer,
        statistics=statistics,
        asset_type="creatures",
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

        "copy_mode": (
            COPY_MODE
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

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            indent=2,
            ensure_ascii=False,
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
            for record
            in writer.records
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


# ============================================================
# MAIN
# ============================================================


def main():
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Catalog not found: "
            f"{CATALOG_PATH}"
        )

    if not SOURCE_ASSETS_PATH.exists():
        raise FileNotFoundError(
            f"Assets not found: "
            f"{SOURCE_ASSETS_PATH}"
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

    print()
    print(
        "Organizing items..."
    )

    (
        writer,
        statistics,
    ) = organize_items(
        catalog
    )

    #
    # Creatures, effects and missiles.
    #
    organize_runtime_assets(
        catalog=catalog,
        writer=writer,
        statistics=statistics,
    )

    validation_passed = (
        validate_known_border(
            writer
        )
    )

    statistics[
        "known_border_validation"
    ] = validation_passed

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
        f"Items processed:   "
        f"{statistics['items_processed']}"
    )

    print(
        f"Items with assets: "
        f"{statistics['items_with_assets']}"
    )

    print(
        f"Named items:       "
        f"{statistics['named_items']}"
    )

    print(
        f"Missing assets:    "
        f"{statistics['missing_assets']}"
    )

    print(
        f"Ground items:      "
        f"{statistics['ground_items']}"
    )

    print(
        f"Border items:      "
        f"{statistics['border_items']}"
    )

    print(
        f"Brush items:       "
        f"{statistics['brush_items']}"
    )

    print(
        f"Tileset-only:      "
        f"{statistics['tileset_items']}"
    )

    print(
        f"Unclassified:      "
        f"{statistics['unclassified_items']}"
    )

    print()

    print(
        f"Creatures:         "
        f"{statistics['creatures_processed']}"
    )

    print(
        f"Named creatures:   "
        f"{statistics['creatures_named']}"
    )

    print(
        f"Creature PNGs:     "
        f"{statistics['creature_pngs_written']}"
    )

    print()

    print(
        f"Effects:           "
        f"{statistics['effects_processed']}"
    )

    print(
        f"Named effects:     "
        f"{statistics['effects_named']}"
    )

    print(
        f"Effect PNGs:       "
        f"{statistics['effect_pngs_written']}"
    )

    print()

    print(
        f"Missiles:          "
        f"{statistics['missiles_processed']}"
    )

    print(
        f"Named missiles:    "
        f"{statistics['missiles_named']}"
    )

    print(
        f"Missile PNGs:      "
        f"{statistics['missile_pngs_written']}"
    )

    print()

    print(
        f"Total PNGs:        "
        f"{statistics['pngs_written']}"
    )

    print(
        f"Output:            "
        f"{OUTPUT_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()