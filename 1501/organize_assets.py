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

#
# Supported:
#
# "copy"
#     Copies PNG files.
#
# "symlink"
#     Creates symbolic links to PNG files.
#


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


# ============================================================
# SOURCE ASSETS
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

    #
    # Old/raw layout fallback.
    #
    direct = (
        SOURCE_ASSETS_PATH
        / "items"
        / str(
            item_id
        )
    )

    if direct.exists():
        return direct

    #
    # Current categorized layout fallback:
    #
    # assets/items/ground/123
    # assets/items/ground_border/123
    # assets/items/other/123
    # ...
    #
    items_path = (
        SOURCE_ASSETS_PATH
        / "items"
    )

    if items_path.exists():
        matches = list(
            items_path.glob(
                f"*/{item_id}"
            )
        )

        if matches:
            return matches[
                0
            ]

    return None


def get_source_pngs(
    source: Path,
):
    return sorted(
        source.rglob(
            "*.png"
        )
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
                    directory=destination_directory,
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
                    "item_id": item[
                        "id"
                    ],

                    "item_name": item.get(
                        "name"
                    ),

                    "asset_type": item.get(
                        "asset_type"
                    ),

                    "category": category,

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
# BRUSH DIRECTORY NAMES
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
            "ground_name": ground.get(
                "name"
            ),

            "look_id": ground.get(
                "look_id"
            ),

            "z_order": ground.get(
                "z_order"
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

    #
    # Preferred structure:
    #
    # grounds/acid/
    # grounds/acid/borders/
    #
    if ground_names:
        for raw_ground_name in ground_names:
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
                    },
                )
            )

        return total_written

    #
    # Border exists in RME but is not connected
    # to a ground brush.
    #
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
            "border_id": border.get(
                "border_id"
            ),

            "border_name": border.get(
                "border_name"
            ),

            "edge": border.get(
                "edge"
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

    brush_name = slugify(
        brush.get(
            "brush_name"
        )
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

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=brush_name,
        category=directory_name,
        semantic={
            "brush_name": (
                brush.get(
                    "brush_name"
                )
            ),

            "brush_type": (
                brush_type
            ),

            "element": brush.get(
                "element"
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
    tileset_name = slugify(
        tileset.get(
            "tileset"
        )
    )

    destination = (
        OUTPUT_PATH
        / "tilesets"
        / tileset_name
    )

    item_id = item[
        "id"
    ]

    prefix = (
        f"{tileset_name}_"
        f"{item_id}"
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=prefix,
        category="tileset",
        semantic={
            "tileset": tileset.get(
                "tileset"
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
    item_id = item[
        "id"
    ]

    asset_type = slugify(
        item.get(
            "asset_type"
        )
    )

    destination = (
        OUTPUT_PATH
        / "unclassified"
        / asset_type
        / str(
            item_id
        )
    )

    #
    # We do not invent a name here.
    #
    # Instead of:
    #
    # frame_000_x_00_y_00_z_00_layer_00.png
    #
    # we simply use:
    #
    # 43430_001.png
    #
    prefix = str(
        item_id
    )

    return writer.export(
        item=item,
        source_directory=source,
        destination_directory=destination,
        prefix=prefix,
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

    #
    # Priority:
    #
    # 1. Ground
    # 2. Border
    # 3. Generic RME brush
    # 4. Tileset-only relation
    # 5. Unclassified
    #
    # This avoids creating several unnecessary copies
    # for the same item merely because it also appears
    # in a tileset.
    #

    if grounds:
        total = 0

        seen = set()

        for ground in grounds:
            name = ground.get(
                "name"
            )

            key = (
                name,
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
# ORGANIZE ALL
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

        "ground_items": 0,
        "border_items": 0,
        "brush_items": 0,
        "tileset_items": 0,
        "unclassified_items": 0,

        "pngs_written": 0,
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

    #
    # Always rebuild the final output.
    #
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
        "Organizing assets..."
    )

    (
        writer,
        statistics,
    ) = organize_items(
        catalog
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

    print(
        f"PNGs written:      "
        f"{statistics['pngs_written']}"
    )

    print(
        f"Output:            "
        f"{OUTPUT_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()