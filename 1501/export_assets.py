import struct
from pathlib import Path

from PIL import Image


DAT_PATH = Path("Tibia.dat")
SPR_PATH = Path("Tibia.spr")

OUTPUT_PATH = Path("assets")

SPRITE_SIZE = 32

SPRITE_COUNT = 555117

FIRST_ITEM_ID = 100
MAX_ITEM_ID = 51299

FIRST_CREATURE_ID = 1
MAX_CREATURE_ID = 1846

DAT_START_OFFSET = 12

MAX_PROPERTY_BYTES = 8192


# ============================================================
# SPR
# ============================================================


class Sprite:
    def __init__(
        self,
        sprite_id: int,
        image: Image.Image,
    ):
        self.id = sprite_id
        self.image = image


class SprReader:
    def __init__(
        self,
        path: Path,
    ):
        self.path = path

        self.signature = 0
        self.sprite_count = 0
        self.offsets = []

        self.cache: dict[int, Sprite] = {}

        self._load_header()

    def _load_header(self):
        with self.path.open("rb") as file:
            self.signature = self._read_u32(file)

            # Tibia 15.01 uses uint32 for sprite count.
            self.sprite_count = self._read_u32(file)

            self.offsets = [
                self._read_u32(file)
                for _ in range(self.sprite_count)
            ]

    def read_sprite(
        self,
        sprite_id: int,
    ) -> Sprite:
        if sprite_id in self.cache:
            return self.cache[sprite_id]

        if sprite_id == 0:
            sprite = Sprite(
                sprite_id=0,
                image=self._empty_image(),
            )

            self.cache[0] = sprite

            return sprite

        if not 1 <= sprite_id <= self.sprite_count:
            raise ValueError(
                f"Invalid sprite ID: {sprite_id}"
            )

        offset = self.offsets[
            sprite_id - 1
        ]

        with self.path.open("rb") as file:
            image = self._read_sprite_image(
                file=file,
                offset=offset,
            )

        sprite = Sprite(
            sprite_id=sprite_id,
            image=image,
        )

        self.cache[sprite_id] = sprite

        return sprite

    @staticmethod
    def _empty_image():
        return Image.new(
            "RGBA",
            (
                SPRITE_SIZE,
                SPRITE_SIZE,
            ),
            (
                0,
                0,
                0,
                0,
            ),
        )

    def _read_sprite_image(
        self,
        file,
        offset: int,
    ) -> Image.Image:
        image = self._empty_image()

        if offset == 0:
            return image

        file.seek(offset)

        marker = file.read(3)

        if len(marker) != 3:
            raise EOFError(
                "Unexpected EOF while reading sprite marker."
            )

        data_size = self._read_u16(file)

        data_end = (
            file.tell()
            + data_size
        )

        pixels = image.load()

        pixel_index = 0

        max_pixels = (
            SPRITE_SIZE
            * SPRITE_SIZE
        )

        while (
            file.tell() < data_end
            and pixel_index < max_pixels
        ):
            transparent_pixels = (
                self._read_u16(file)
            )

            colored_pixels = (
                self._read_u16(file)
            )

            pixel_index += transparent_pixels

            for _ in range(
                colored_pixels
            ):
                if pixel_index >= max_pixels:
                    break

                rgb = file.read(3)

                if len(rgb) != 3:
                    raise EOFError(
                        "Unexpected EOF while reading RGB."
                    )

                r, g, b = rgb

                x = (
                    pixel_index
                    % SPRITE_SIZE
                )

                y = (
                    pixel_index
                    // SPRITE_SIZE
                )

                pixels[x, y] = (
                    r,
                    g,
                    b,
                    255,
                )

                pixel_index += 1

        return image

    @staticmethod
    def _read_u16(file):
        data = file.read(2)

        if len(data) != 2:
            raise EOFError(
                "Unexpected EOF reading uint16."
            )

        return struct.unpack(
            "<H",
            data,
        )[0]

    @staticmethod
    def _read_u32(file):
        data = file.read(4)

        if len(data) != 4:
            raise EOFError(
                "Unexpected EOF reading uint32."
            )

        return struct.unpack(
            "<I",
            data,
        )[0]


# ============================================================
# BASIC DAT READERS
# ============================================================


def u32(
    data: bytes,
    offset: int,
) -> int:
    return struct.unpack_from(
        "<I",
        data,
        offset,
    )[0]


def i32(
    data: bytes,
    offset: int,
) -> int:
    return struct.unpack_from(
        "<i",
        data,
        offset,
    )[0]


# ============================================================
# ANIMATOR
# ============================================================


def read_animator(
    data: bytes,
    cursor: int,
    frames: int,
):
    if frames <= 1:
        return None, cursor

    if cursor + 6 > len(data):
        return None, None

    async_animation = data[
        cursor
    ]

    cursor += 1

    loop_count = i32(
        data,
        cursor,
    )

    cursor += 4

    start_phase = data[
        cursor
    ]

    cursor += 1

    if async_animation not in (
        0,
        1,
    ):
        return None, None

    if start_phase >= frames:
        return None, None

    phases = []

    for phase in range(
        frames
    ):
        if cursor + 8 > len(data):
            return None, None

        min_duration = u32(
            data,
            cursor,
        )

        cursor += 4

        max_duration = u32(
            data,
            cursor,
        )

        cursor += 4

        if min_duration > max_duration:
            return None, None

        if max_duration > 600000:
            return None, None

        phases.append(
            {
                "phase": phase,
                "min_duration": min_duration,
                "max_duration": max_duration,
            }
        )

    return {
        "async": async_animation,
        "loop_count": loop_count,
        "start_phase": start_phase,
        "phases": phases,
    }, cursor


# ============================================================
# GRAPHICS BLOCK
# ============================================================


def parse_graphics_block(
    data: bytes,
    offset: int,
):
    if offset + 7 > len(data):
        return None

    cursor = offset

    width = data[
        cursor
    ]

    cursor += 1

    height = data[
        cursor
    ]

    cursor += 1

    if not 1 <= width <= 8:
        return None

    if not 1 <= height <= 8:
        return None

    real_size = SPRITE_SIZE

    if (
        width > 1
        or height > 1
    ):
        if cursor >= len(data):
            return None

        real_size = data[
            cursor
        ]

        cursor += 1

        if not 1 <= real_size <= 255:
            return None

    if cursor + 5 > len(data):
        return None

    layers = data[
        cursor
    ]

    cursor += 1

    pattern_x = data[
        cursor
    ]

    cursor += 1

    pattern_y = data[
        cursor
    ]

    cursor += 1

    pattern_z = data[
        cursor
    ]

    cursor += 1

    frames = data[
        cursor
    ]

    cursor += 1

    if not 1 <= layers <= 8:
        return None

    if not 1 <= pattern_x <= 32:
        return None

    if not 1 <= pattern_y <= 32:
        return None

    if not 1 <= pattern_z <= 32:
        return None

    if not 1 <= frames <= 255:
        return None

    animator = None

    if frames > 1:
        animator, cursor = read_animator(
            data=data,
            cursor=cursor,
            frames=frames,
        )

        if cursor is None:
            return None

    sprite_count = (
        width
        * height
        * layers
        * pattern_x
        * pattern_y
        * pattern_z
        * frames
    )

    if sprite_count <= 0:
        return None

    if sprite_count > 500000:
        return None

    sprite_bytes = (
        sprite_count
        * 4
    )

    if (
        cursor + sprite_bytes
        > len(data)
    ):
        return None

    sprite_ids = []

    for index in range(
        sprite_count
    ):
        sprite_id = u32(
            data,
            cursor
            + index * 4,
        )

        if (
            sprite_id != 0
            and sprite_id > SPRITE_COUNT
        ):
            return None

        sprite_ids.append(
            sprite_id
        )

    return {
        "offset": offset,

        "width": width,
        "height": height,
        "real_size": real_size,

        "layers": layers,

        "pattern_x": pattern_x,
        "pattern_y": pattern_y,
        "pattern_z": pattern_z,

        "frames": frames,

        "animator": animator,

        "sprite_count": sprite_count,
        "sprite_ids": sprite_ids,

        "sprites_offset": cursor,

        "end_offset": (
            cursor
            + sprite_bytes
        ),
    }


# ============================================================
# FRAME GROUPS
# ============================================================


def parse_frame_groups(
    data: bytes,
    offset: int,
):
    if offset >= len(data):
        return None

    group_count = data[
        offset
    ]

    if not 2 <= group_count <= 8:
        return None

    cursor = (
        offset + 1
    )

    groups = []

    for group_index in range(
        group_count
    ):
        if cursor >= len(data):
            return None

        frame_group_type = data[
            cursor
        ]

        cursor += 1

        if frame_group_type not in (
            0,
            1,
        ):
            return None

        graphics = parse_graphics_block(
            data=data,
            offset=cursor,
        )

        if graphics is None:
            return None

        groups.append(
            {
                "index": group_index,
                "type": frame_group_type,
                "graphics": graphics,
            }
        )

        cursor = graphics[
            "end_offset"
        ]

    return {
        "group_count": group_count,
        "groups": groups,
        "end_offset": cursor,
    }


# ============================================================
# DAT RECORD DETECTION
# ============================================================


def find_record_candidates(
    data: bytes,
    record_offset: int,
):
    search_end = min(
        len(data),
        record_offset
        + MAX_PROPERTY_BYTES,
    )

    candidates = []

    for ff_offset in range(
        record_offset,
        search_end,
    ):
        if data[
            ff_offset
        ] != 0xFF:
            continue

        payload_offset = (
            ff_offset + 1
        )

        graphics = parse_graphics_block(
            data=data,
            offset=payload_offset,
        )

        if graphics is not None:
            candidates.append(
                {
                    "type": "single",
                    "ff_offset": ff_offset,
                    "end_offset": graphics[
                        "end_offset"
                    ],
                    "graphics": graphics,
                }
            )

        frame_groups = parse_frame_groups(
            data=data,
            offset=payload_offset,
        )

        if frame_groups is not None:
            candidates.append(
                {
                    "type": "groups",
                    "ff_offset": ff_offset,
                    "end_offset": frame_groups[
                        "end_offset"
                    ],
                    "frame_groups": frame_groups,
                }
            )

    return candidates


def choose_candidate(
    candidates: list[dict],
):
    if not candidates:
        return None

    candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate[
                "ff_offset"
            ],
            0
            if candidate[
                "type"
            ] == "groups"
            else 1,
        ),
    )

    return candidates[
        0
    ]


# ============================================================
# DAT PARSER
# ============================================================


def parse_dat():
    data = DAT_PATH.read_bytes()

    signature = u32(
        data,
        0,
    )

    print(
        f"DAT signature: "
        f"0x{signature:08X}"
    )

    records = {
        "items": [],
        "creatures": [],
    }

    offset = (
        DAT_START_OFFSET
    )

    #
    # Items
    #
    for item_id in range(
        FIRST_ITEM_ID,
        MAX_ITEM_ID + 1,
    ):
        candidate = choose_candidate(
            find_record_candidates(
                data=data,
                record_offset=offset,
            )
        )

        if candidate is None:
            raise ValueError(
                f"Could not parse item "
                f"{item_id} at "
                f"0x{offset:08X}"
            )

        records[
            "items"
        ].append(
            {
                "id": item_id,
                "offset": offset,
                **candidate,
            }
        )

        offset = candidate[
            "end_offset"
        ]

    print(
        f"Items parsed: "
        f"{len(records['items'])}"
    )

    print(
        f"Creature section: "
        f"0x{offset:08X}"
    )

    #
    # Creatures
    #
    for creature_id in range(
        FIRST_CREATURE_ID,
        MAX_CREATURE_ID + 1,
    ):
        candidate = choose_candidate(
            find_record_candidates(
                data=data,
                record_offset=offset,
            )
        )

        if candidate is None:
            raise ValueError(
                f"Could not parse creature "
                f"{creature_id} at "
                f"0x{offset:08X}"
            )

        records[
            "creatures"
        ].append(
            {
                "id": creature_id,
                "offset": offset,
                **candidate,
            }
        )

        offset = candidate[
            "end_offset"
        ]

    print(
        f"Creatures parsed: "
        f"{len(records['creatures'])}"
    )

    print(
        f"Final DAT offset: "
        f"0x{offset:08X}"
    )

    print(
        f"DAT EOF:          "
        f"0x{len(data):08X}"
    )

    if offset != len(
        data
    ):
        raise ValueError(
            "DAT parser did not finish "
            "exactly at EOF."
        )

    return records


# ============================================================
# TILE COMPOSITION
# ============================================================


def compose_tiles(
    spr_reader: SprReader,
    sprite_ids: list[int],
    width: int,
    height: int,
) -> Image.Image:
    image = Image.new(
        "RGBA",
        (
            width
            * SPRITE_SIZE,
            height
            * SPRITE_SIZE,
        ),
        (
            0,
            0,
            0,
            0,
        ),
    )

    ordered_ids = list(
        reversed(
            sprite_ids
        )
    )

    for index, sprite_id in enumerate(
        ordered_ids
    ):
        sprite = spr_reader.read_sprite(
            sprite_id
        )

        x = (
            index
            % width
        ) * SPRITE_SIZE

        y = (
            index
            // width
        ) * SPRITE_SIZE

        image.alpha_composite(
            sprite.image,
            (
                x,
                y,
            ),
        )

    return image


# ============================================================
# GRAPHICS EXPORT
# ============================================================


def export_graphics_block(
    graphics: dict,
    output_dir: Path,
    spr_reader: SprReader,
):
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    width = graphics[
        "width"
    ]

    height = graphics[
        "height"
    ]

    layers = graphics[
        "layers"
    ]

    pattern_x_count = graphics[
        "pattern_x"
    ]

    pattern_y_count = graphics[
        "pattern_y"
    ]

    pattern_z_count = graphics[
        "pattern_z"
    ]

    frames = graphics[
        "frames"
    ]

    sprite_ids = graphics[
        "sprite_ids"
    ]

    tiles_per_image = (
        width
        * height
    )

    index = 0

    exported = 0

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
                    for layer in range(
                        layers
                    ):
                        group = sprite_ids[
                            index:
                            index
                            + tiles_per_image
                        ]

                        index += (
                            tiles_per_image
                        )

                        if all(
                            sprite_id == 0
                            for sprite_id in group
                        ):
                            continue

                        image = compose_tiles(
                            spr_reader=spr_reader,
                            sprite_ids=group,
                            width=width,
                            height=height,
                        )

                        filename = (
                            f"frame_{frame:03d}_"
                            f"x_{pattern_x:02d}_"
                            f"y_{pattern_y:02d}_"
                            f"z_{pattern_z:02d}_"
                            f"layer_{layer:02d}.png"
                        )

                        image.save(
                            output_dir
                            / filename
                        )

                        exported += 1

    return exported


# ============================================================
# ASSET EXPORT
# ============================================================


def export_record(
    category: str,
    record: dict,
    spr_reader: SprReader,
):
    asset_id = record[
        "id"
    ]

    asset_dir = (
        OUTPUT_PATH
        / category
        / str(asset_id)
    )

    if record[
        "type"
    ] == "single":
        graphics = record[
            "graphics"
        ]

        if all(
            sprite_id == 0
            for sprite_id in graphics[
                "sprite_ids"
            ]
        ):
            return 0

        return export_graphics_block(
            graphics=graphics,
            output_dir=asset_dir,
            spr_reader=spr_reader,
        )

    frame_groups = record[
        "frame_groups"
    ]

    total_exported = 0

    for group in frame_groups[
        "groups"
    ]:
        group_index = group[
            "index"
        ]

        group_type = group[
            "type"
        ]

        graphics = group[
            "graphics"
        ]

        if all(
            sprite_id == 0
            for sprite_id in graphics[
                "sprite_ids"
            ]
        ):
            continue

        group_dir = (
            asset_dir
            / (
                f"group_"
                f"{group_index:02d}_"
                f"type_{group_type}"
            )
        )

        exported = export_graphics_block(
            graphics=graphics,
            output_dir=group_dir,
            spr_reader=spr_reader,
        )

        total_exported += (
            exported
        )

    return total_exported


# ============================================================
# EXPORT ALL
# ============================================================


def export_all(
    records: dict,
    spr_reader: SprReader,
):
    categories = [
        "items",
        "creatures",
    ]

    assets_processed = 0
    assets_exported = 0
    pngs_exported = 0

    for category in categories:
        print()
        print("=" * 70)
        print(
            category.upper()
        )
        print("=" * 70)

        category_records = records[
            category
        ]

        total = len(
            category_records
        )

        for index, record in enumerate(
            category_records,
            start=1,
        ):
            assets_processed += 1

            exported = export_record(
                category=category,
                record=record,
                spr_reader=spr_reader,
            )

            if exported > 0:
                assets_exported += 1
                pngs_exported += exported

            print(
                f"[{index}/{total}] "
                f"{category} "
                f"{record['id']}: "
                f"{exported} PNG(s)"
            )

    return (
        assets_processed,
        assets_exported,
        pngs_exported,
    )


# ============================================================
# MAIN
# ============================================================


def main():
    if not DAT_PATH.exists():
        raise FileNotFoundError(
            f"DAT not found: "
            f"{DAT_PATH.resolve()}"
        )

    if not SPR_PATH.exists():
        raise FileNotFoundError(
            f"SPR not found: "
            f"{SPR_PATH.resolve()}"
        )

    print(
        f"DAT: {DAT_PATH}"
    )

    print(
        f"SPR: {SPR_PATH}"
    )

    print(
        f"Output: "
        f"{OUTPUT_PATH.resolve()}"
    )

    print()

    print(
        "Reading SPR..."
    )

    spr_reader = SprReader(
        SPR_PATH
    )

    print(
        f"SPR signature: "
        f"0x{spr_reader.signature:08X}"
    )

    print(
        f"SPR sprites: "
        f"{spr_reader.sprite_count}"
    )

    if (
        spr_reader.sprite_count
        != SPRITE_COUNT
    ):
        raise ValueError(
            "Unexpected SPR sprite count: "
            f"{spr_reader.sprite_count}. "
            f"Expected {SPRITE_COUNT}."
        )

    print()
    print(
        "Parsing DAT..."
    )

    records = parse_dat()

    print()
    print(
        "DAT parsed successfully."
    )

    print(
        f"Items: "
        f"{len(records['items'])}"
    )

    print(
        f"Creatures: "
        f"{len(records['creatures'])}"
    )

    OUTPUT_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print(
        "Exporting all assets..."
    )

    (
        assets_processed,
        assets_exported,
        pngs_exported,
    ) = export_all(
        records=records,
        spr_reader=spr_reader,
    )

    print()
    print("=" * 70)
    print("FINISHED")
    print("=" * 70)

    print(
        f"Assets processed: "
        f"{assets_processed}"
    )

    print(
        f"Assets exported:  "
        f"{assets_exported}"
    )

    print(
        f"PNGs exported:    "
        f"{pngs_exported}"
    )

    print(
        f"Output:           "
        f"{OUTPUT_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()