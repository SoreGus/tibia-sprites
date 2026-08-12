import json
import re
import struct
import unicodedata
from pathlib import Path

from PIL import Image


DAT_PATH = Path("Tibia.dat")
SPR_PATH = Path("Tibia.spr")

ASSETS_PATH = Path("assets")
METADATA_PATH = Path("metadata.json")

VERSION = "15.01"

SPRITE_SIZE = 32
SPRITE_COUNT = 555117

FIRST_ITEM_ID = 100
MAX_ITEM_ID = 51299

FIRST_CREATURE_ID = 1
MAX_CREATURE_ID = 1846

DAT_START_OFFSET = 12

MAX_PROPERTY_BYTES = 8192

RAW_MARKET_ATTRIBUTE = 0x22


# ============================================================
# BASIC READERS
# ============================================================


def u16(
    data: bytes,
    offset: int,
) -> int:
    return struct.unpack_from(
        "<H",
        data,
        offset,
    )[0]


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
# PATH / NAME
# ============================================================


def sanitize_name(
    name: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        name,
    )

    ascii_name = normalized.encode(
        "ascii",
        "ignore",
    ).decode(
        "ascii"
    )

    ascii_name = ascii_name.lower()

    ascii_name = re.sub(
        r"[^a-z0-9]+",
        "_",
        ascii_name,
    )

    ascii_name = ascii_name.strip(
        "_"
    )

    return ascii_name[:80]


def build_asset_directory_name(
    asset_id: int,
    name: str | None,
) -> str:
    if not name:
        return str(
            asset_id
        )

    safe_name = sanitize_name(
        name
    )

    if not safe_name:
        return str(
            asset_id
        )

    return (
        f"{asset_id}_"
        f"{safe_name}"
    )


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

    def _load_header(
        self,
    ):
        with self.path.open(
            "rb"
        ) as file:
            self.signature = (
                self._read_u32(
                    file
                )
            )

            self.sprite_count = (
                self._read_u32(
                    file
                )
            )

            self.offsets = [
                self._read_u32(
                    file
                )
                for _ in range(
                    self.sprite_count
                )
            ]

    def read_sprite(
        self,
        sprite_id: int,
    ) -> Sprite:
        if sprite_id in self.cache:
            return self.cache[
                sprite_id
            ]

        if sprite_id == 0:
            sprite = Sprite(
                sprite_id=0,
                image=self._empty_image(),
            )

            self.cache[0] = sprite

            return sprite

        if not (
            1
            <= sprite_id
            <= self.sprite_count
        ):
            raise ValueError(
                f"Invalid sprite ID: "
                f"{sprite_id}"
            )

        offset = self.offsets[
            sprite_id - 1
        ]

        with self.path.open(
            "rb"
        ) as file:
            image = (
                self._read_sprite_image(
                    file=file,
                    offset=offset,
                )
            )

        sprite = Sprite(
            sprite_id=sprite_id,
            image=image,
        )

        self.cache[
            sprite_id
        ] = sprite

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

        file.seek(
            offset
        )

        marker = file.read(
            3
        )

        if len(
            marker
        ) != 3:
            raise EOFError(
                "Unexpected EOF while "
                "reading sprite marker."
            )

        data_size = (
            self._read_u16(
                file
            )
        )

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
            file.tell()
            < data_end
            and pixel_index
            < max_pixels
        ):
            transparent_pixels = (
                self._read_u16(
                    file
                )
            )

            colored_pixels = (
                self._read_u16(
                    file
                )
            )

            pixel_index += (
                transparent_pixels
            )

            for _ in range(
                colored_pixels
            ):
                if (
                    pixel_index
                    >= max_pixels
                ):
                    break

                rgb = file.read(
                    3
                )

                if len(
                    rgb
                ) != 3:
                    raise EOFError(
                        "Unexpected EOF while "
                        "reading sprite RGB."
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

                pixels[
                    x,
                    y,
                ] = (
                    r,
                    g,
                    b,
                    255,
                )

                pixel_index += 1

        return image

    @staticmethod
    def _read_u16(
        file,
    ) -> int:
        data = file.read(
            2
        )

        if len(
            data
        ) != 2:
            raise EOFError(
                "Unexpected EOF reading "
                "uint16."
            )

        return struct.unpack(
            "<H",
            data,
        )[0]

    @staticmethod
    def _read_u32(
        file,
    ) -> int:
        data = file.read(
            4
        )

        if len(
            data
        ) != 4:
            raise EOFError(
                "Unexpected EOF reading "
                "uint32."
            )

        return struct.unpack(
            "<I",
            data,
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
        return (
            None,
            cursor,
        )

    if (
        cursor + 6
        > len(data)
    ):
        return (
            None,
            None,
        )

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
        return (
            None,
            None,
        )

    if (
        start_phase
        >= frames
    ):
        return (
            None,
            None,
        )

    phases = []

    for phase in range(
        frames
    ):
        if (
            cursor + 8
            > len(data)
        ):
            return (
                None,
                None,
            )

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

        if (
            min_duration
            > max_duration
        ):
            return (
                None,
                None,
            )

        if (
            max_duration
            > 600000
        ):
            return (
                None,
                None,
            )

        phases.append(
            {
                "phase": phase,
                "min_duration": min_duration,
                "max_duration": max_duration,
            }
        )

    return {
        "async": bool(
            async_animation
        ),
        "loop_count": loop_count,
        "start_phase": start_phase,
        "phases": phases,
    }, cursor


# ============================================================
# GRAPHICS
# ============================================================


def parse_graphics_block(
    data: bytes,
    offset: int,
):
    if (
        offset + 7
        > len(data)
    ):
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

    if not (
        1 <= width <= 8
    ):
        return None

    if not (
        1 <= height <= 8
    ):
        return None

    real_size = (
        SPRITE_SIZE
    )

    if (
        width > 1
        or height > 1
    ):
        if (
            cursor
            >= len(data)
        ):
            return None

        real_size = data[
            cursor
        ]

        cursor += 1

        if not (
            1
            <= real_size
            <= 255
        ):
            return None

    if (
        cursor + 5
        > len(data)
    ):
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

    if not (
        1 <= layers <= 8
    ):
        return None

    if not (
        1 <= pattern_x <= 32
    ):
        return None

    if not (
        1 <= pattern_y <= 32
    ):
        return None

    if not (
        1 <= pattern_z <= 32
    ):
        return None

    if not (
        1 <= frames <= 255
    ):
        return None

    animator = None

    if frames > 1:
        (
            animator,
            cursor,
        ) = read_animator(
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

    if not (
        1
        <= sprite_count
        <= 500000
    ):
        return None

    sprite_bytes = (
        sprite_count
        * 4
    )

    if (
        cursor
        + sprite_bytes
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
            and sprite_id
            > SPRITE_COUNT
        ):
            return None

        sprite_ids.append(
            sprite_id
        )

    return {
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
    if (
        offset
        >= len(data)
    ):
        return None

    group_count = data[
        offset
    ]

    if not (
        2
        <= group_count
        <= 8
    ):
        return None

    cursor = (
        offset + 1
    )

    groups = []

    for group_index in range(
        group_count
    ):
        if (
            cursor
            >= len(data)
        ):
            return None

        group_type = data[
            cursor
        ]

        cursor += 1

        if group_type not in (
            0,
            1,
        ):
            return None

        graphics = (
            parse_graphics_block(
                data=data,
                offset=cursor,
            )
        )

        if graphics is None:
            return None

        groups.append(
            {
                "index": group_index,
                "type": group_type,
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
# RECORD DETECTION
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
        if (
            data[
                ff_offset
            ]
            != 0xFF
        ):
            continue

        payload_offset = (
            ff_offset + 1
        )

        graphics = (
            parse_graphics_block(
                data=data,
                offset=payload_offset,
            )
        )

        if (
            graphics
            is not None
        ):
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

        frame_groups = (
            parse_frame_groups(
                data=data,
                offset=payload_offset,
            )
        )

        if (
            frame_groups
            is not None
        ):
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

    return sorted(
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
    )[0]


# ============================================================
# STRINGS / MARKET METADATA
# ============================================================


def decode_string(
    raw: bytes,
):
    try:
        text = raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError:
        return None

    if not text:
        return None

    if not all(
        character.isprintable()
        or character
        in "\t\r\n"
        for character in text
    ):
        return None

    return text


def try_parse_market(
    properties: bytes,
    offset: int,
):
    cursor = (
        offset + 1
    )

    if (
        cursor + 8
        > len(properties)
    ):
        return None

    category = u16(
        properties,
        cursor,
    )

    cursor += 2

    trade_as = u16(
        properties,
        cursor,
    )

    cursor += 2

    show_as = u16(
        properties,
        cursor,
    )

    cursor += 2

    name_length = u16(
        properties,
        cursor,
    )

    cursor += 2

    if not (
        1
        <= name_length
        <= 512
    ):
        return None

    if (
        cursor
        + name_length
        + 4
        > len(properties)
    ):
        return None

    raw_name = properties[
        cursor:
        cursor + name_length
    ]

    name = decode_string(
        raw_name
    )

    if name is None:
        return None

    cursor += (
        name_length
    )

    restrict_vocation = u16(
        properties,
        cursor,
    )

    cursor += 2

    required_level = u16(
        properties,
        cursor,
    )

    cursor += 2

    return {
        "name": name,
        "category": category,
        "trade_as": trade_as,
        "show_as": show_as,
        "restrict_vocation": restrict_vocation,
        "required_level": required_level,
    }


def find_market_metadata(
    properties: bytes,
):
    for offset, value in enumerate(
        properties
    ):
        if (
            value
            != RAW_MARKET_ATTRIBUTE
        ):
            continue

        market = try_parse_market(
            properties=properties,
            offset=offset,
        )

        if market is not None:
            return market

    return None


def find_length_prefixed_strings(
    properties: bytes,
):
    strings = []

    seen = set()

    for offset in range(
        max(
            0,
            len(properties) - 2,
        )
    ):
        length = u16(
            properties,
            offset,
        )

        if not (
            2
            <= length
            <= 256
        ):
            continue

        start = (
            offset + 2
        )

        end = (
            start + length
        )

        if (
            end
            > len(properties)
        ):
            continue

        text = decode_string(
            properties[
                start:end
            ]
        )

        if text is None:
            continue

        if not any(
            character.isalpha()
            for character in text
        ):
            continue

        if text in seen:
            continue

        seen.add(
            text
        )

        strings.append(
            text
        )

    return strings


# ============================================================
# PARSE RECORDS
# ============================================================


def build_record(
    data: bytes,
    thing_id: int,
    category: str,
    record_offset: int,
    candidate: dict,
):
    ff_offset = candidate[
        "ff_offset"
    ]

    properties = data[
        record_offset:
        ff_offset
    ]

    market = (
        find_market_metadata(
            properties
        )
    )

    strings = (
        find_length_prefixed_strings(
            properties
        )
    )

    name = (
        market[
            "name"
        ]
        if market
        else None
    )

    return {
        "id": thing_id,
        "category": category,
        "name": name,
        "market": market,
        "strings": strings,

        "offset": record_offset,

        "properties_end": ff_offset,

        "raw_properties": (
            properties.hex(
                " "
            )
        ),

        **candidate,
    }


def parse_section(
    data: bytes,
    category: str,
    first_id: int,
    last_id: int,
    offset: int,
):
    records = []

    for thing_id in range(
        first_id,
        last_id + 1,
    ):
        candidate = (
            choose_candidate(
                find_record_candidates(
                    data=data,
                    record_offset=offset,
                )
            )
        )

        if candidate is None:
            raise ValueError(
                f"Could not parse "
                f"{category} "
                f"{thing_id} at "
                f"0x{offset:08X}"
            )

        record = build_record(
            data=data,
            thing_id=thing_id,
            category=category,
            record_offset=offset,
            candidate=candidate,
        )

        records.append(
            record
        )

        offset = candidate[
            "end_offset"
        ]

    return (
        records,
        offset,
    )


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

    offset = (
        DAT_START_OFFSET
    )

    print(
        "Parsing items..."
    )

    (
        items,
        offset,
    ) = parse_section(
        data=data,
        category="items",
        first_id=FIRST_ITEM_ID,
        last_id=MAX_ITEM_ID,
        offset=offset,
    )

    print(
        f"Items parsed: "
        f"{len(items)}"
    )

    print(
        f"Creature section: "
        f"0x{offset:08X}"
    )

    print(
        "Parsing creatures..."
    )

    (
        creatures,
        offset,
    ) = parse_section(
        data=data,
        category="creatures",
        first_id=FIRST_CREATURE_ID,
        last_id=MAX_CREATURE_ID,
        offset=offset,
    )

    print(
        f"Creatures parsed: "
        f"{len(creatures)}"
    )

    print(
        f"Final DAT offset: "
        f"0x{offset:08X}"
    )

    print(
        f"DAT EOF:          "
        f"0x{len(data):08X}"
    )

    if (
        offset
        != len(data)
    ):
        raise ValueError(
            "DAT parser did not "
            "finish exactly at EOF."
        )

    return {
        "signature": signature,
        "items": items,
        "creatures": creatures,
    }


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
        sprite = (
            spr_reader.read_sprite(
                sprite_id
            )
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


def get_asset_directory(
    record: dict,
) -> Path:
    directory_name = (
        build_asset_directory_name(
            asset_id=record[
                "id"
            ],
            name=record[
                "name"
            ],
        )
    )

    return (
        ASSETS_PATH
        / record[
            "category"
        ]
        / directory_name
    )


def export_record(
    record: dict,
    spr_reader: SprReader,
):
    asset_dir = (
        get_asset_directory(
            record
        )
    )

    if (
        record[
            "type"
        ]
        == "single"
    ):
        graphics = record[
            "graphics"
        ]

        if all(
            sprite_id == 0
            for sprite_id in graphics[
                "sprite_ids"
            ]
        ):
            return (
                asset_dir,
                0,
            )

        exported = (
            export_graphics_block(
                graphics=graphics,
                output_dir=asset_dir,
                spr_reader=spr_reader,
            )
        )

        return (
            asset_dir,
            exported,
        )

    total_exported = 0

    frame_groups = record[
        "frame_groups"
    ]

    for group in frame_groups[
        "groups"
    ]:
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
                f"{group['index']:02d}_"
                f"type_{group['type']}"
            )
        )

        total_exported += (
            export_graphics_block(
                graphics=graphics,
                output_dir=group_dir,
                spr_reader=spr_reader,
            )
        )

    return (
        asset_dir,
        total_exported,
    )


# ============================================================
# METADATA
# ============================================================


def graphics_metadata(
    graphics: dict,
):
    return {
        "width": graphics[
            "width"
        ],
        "height": graphics[
            "height"
        ],
        "real_size": graphics[
            "real_size"
        ],

        "layers": graphics[
            "layers"
        ],

        "pattern_x": graphics[
            "pattern_x"
        ],
        "pattern_y": graphics[
            "pattern_y"
        ],
        "pattern_z": graphics[
            "pattern_z"
        ],

        "frames": graphics[
            "frames"
        ],

        "sprite_count": graphics[
            "sprite_count"
        ],

        "sprite_ids": graphics[
            "sprite_ids"
        ],

        "animator": graphics[
            "animator"
        ],
    }


def record_metadata(
    record: dict,
    asset_dir: Path,
    exported_pngs: int,
):
    metadata = {
        "id": record[
            "id"
        ],

        "category": record[
            "category"
        ],

        "name": record[
            "name"
        ],

        "asset_path": (
            asset_dir.as_posix()
        ),

        "exported_pngs": (
            exported_pngs
        ),

        "market": (
            record[
                "market"
            ]
        ),

        "strings": (
            record[
                "strings"
            ]
        ),

        "dat": {
            "offset": record[
                "offset"
            ],

            "properties_end": record[
                "properties_end"
            ],

            "end_offset": record[
                "end_offset"
            ],

            "record_type": record[
                "type"
            ],

            "raw_properties": record[
                "raw_properties"
            ],
        },
    }

    if (
        record[
            "type"
        ]
        == "single"
    ):
        metadata[
            "graphics"
        ] = graphics_metadata(
            record[
                "graphics"
            ]
        )

    else:
        metadata[
            "frame_groups"
        ] = [
            {
                "index": group[
                    "index"
                ],

                "type": group[
                    "type"
                ],

                "graphics": (
                    graphics_metadata(
                        group[
                            "graphics"
                        ]
                    )
                ),
            }
            for group in record[
                "frame_groups"
            ][
                "groups"
            ]
        ]

    return metadata


# ============================================================
# EXPORT ALL
# ============================================================


def export_all(
    parsed: dict,
    spr_reader: SprReader,
):
    metadata = {
        "version": VERSION,

        "dat_signature": (
            f"0x"
            f"{parsed['signature']:08X}"
        ),

        "spr_signature": (
            f"0x"
            f"{spr_reader.signature:08X}"
        ),

        "sprite_count": (
            spr_reader.sprite_count
        ),

        "items": [],

        "creatures": [],
    }

    total_assets = 0
    exported_assets = 0
    pngs_exported = 0

    for category in (
        "items",
        "creatures",
    ):
        print()
        print(
            "=" * 70
        )

        print(
            category.upper()
        )

        print(
            "=" * 70
        )

        records = parsed[
            category
        ]

        total = len(
            records
        )

        for index, record in enumerate(
            records,
            start=1,
        ):
            total_assets += 1

            (
                asset_dir,
                exported,
            ) = export_record(
                record=record,
                spr_reader=spr_reader,
            )

            if exported > 0:
                exported_assets += 1
                pngs_exported += exported

            metadata[
                category
            ].append(
                record_metadata(
                    record=record,
                    asset_dir=asset_dir,
                    exported_pngs=exported,
                )
            )

            display_name = (
                record[
                    "name"
                ]
                or "-"
            )

            print(
                f"[{index}/{total}] "
                f"{category} "
                f"{record['id']} "
                f"({display_name}): "
                f"{exported} PNG(s)"
            )

    return (
        metadata,
        total_assets,
        exported_assets,
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
        f"Assets: "
        f"{ASSETS_PATH.resolve()}"
    )

    print(
        f"Metadata: "
        f"{METADATA_PATH.resolve()}"
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

    parsed = parse_dat()

    print()
    print(
        "DAT parsed successfully."
    )

    print(
        f"Items: "
        f"{len(parsed['items'])}"
    )

    print(
        f"Creatures: "
        f"{len(parsed['creatures'])}"
    )

    ASSETS_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print(
        "Exporting assets "
        "and building metadata..."
    )

    (
        metadata,
        total_assets,
        exported_assets,
        pngs_exported,
    ) = export_all(
        parsed=parsed,
        spr_reader=spr_reader,
    )

    with METADATA_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        "=" * 70
    )

    print(
        "FINISHED"
    )

    print(
        "=" * 70
    )

    print(
        f"Assets processed: "
        f"{total_assets}"
    )

    print(
        f"Assets exported:  "
        f"{exported_assets}"
    )

    print(
        f"PNGs exported:    "
        f"{pngs_exported}"
    )

    print(
        f"Assets:           "
        f"{ASSETS_PATH.resolve()}"
    )

    print(
        f"Metadata:         "
        f"{METADATA_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()