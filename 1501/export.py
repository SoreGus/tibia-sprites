import re
import shutil
import struct
from pathlib import Path

from PIL import Image

# ============================================================
# PATHS
# ============================================================


DAT_PATH = Path("Tibia.dat")
SPR_PATH = Path("Tibia.spr")

OUTPUT_PATH = Path("assets")


# ============================================================
# FORMAT
# ============================================================


SPRITE_SIZE = 32

FIRST_ITEM_ID = 100
FIRST_CREATURE_ID = 1
FIRST_EFFECT_ID = 1
FIRST_MISSILE_ID = 1

ATTRIBUTE_END = 0xFF

MAX_SPRITES_PER_GRAPHICS = 500000


# ============================================================
# ATTRIBUTE IDS
# ============================================================


ATTR_GROUND = 0
ATTR_GROUND_BORDER = 1
ATTR_ON_BOTTOM = 2
ATTR_ON_TOP = 3
ATTR_CONTAINER = 4
ATTR_STACKABLE = 5
ATTR_FORCE_USE = 6
ATTR_MULTI_USE = 7
ATTR_WRITABLE = 8
ATTR_WRITABLE_ONCE = 9
ATTR_FLUID_CONTAINER = 10
ATTR_SPLASH = 11
ATTR_NOT_WALKABLE = 12
ATTR_NOT_MOVEABLE = 13
ATTR_BLOCK_PROJECTILE = 14
ATTR_NOT_PATHABLE = 15
ATTR_PICKUPABLE = 16
ATTR_HANGABLE = 17
ATTR_HOOK_SOUTH = 18
ATTR_HOOK_EAST = 19
ATTR_ROTATEABLE = 20
ATTR_LIGHT = 21
ATTR_DONT_HIDE = 22
ATTR_TRANSLUCENT = 23
ATTR_DISPLACEMENT = 24
ATTR_ELEVATION = 25
ATTR_LYING_CORPSE = 26
ATTR_ANIMATE_ALWAYS = 27
ATTR_MINIMAP_COLOR = 28
ATTR_LENS_HELP = 29
ATTR_FULL_GROUND = 30
ATTR_LOOK = 31
ATTR_CLOTH = 32
ATTR_MARKET = 33
ATTR_USABLE = 34
ATTR_WRAPABLE = 35
ATTR_UNWRAPABLE = 36
ATTR_TOP_EFFECT = 37

ATTR_NO_MOVE_ANIMATION = 253


ATTRIBUTE_NAMES = {
    ATTR_GROUND: "ground",
    ATTR_GROUND_BORDER: "ground_border",
    ATTR_ON_BOTTOM: "on_bottom",
    ATTR_ON_TOP: "on_top",
    ATTR_CONTAINER: "container",
    ATTR_STACKABLE: "stackable",
    ATTR_FORCE_USE: "force_use",
    ATTR_MULTI_USE: "multi_use",
    ATTR_WRITABLE: "writable",
    ATTR_WRITABLE_ONCE: "writable_once",
    ATTR_FLUID_CONTAINER: "fluid_container",
    ATTR_SPLASH: "splash",
    ATTR_NOT_WALKABLE: "not_walkable",
    ATTR_NOT_MOVEABLE: "not_moveable",
    ATTR_BLOCK_PROJECTILE: "block_projectile",
    ATTR_NOT_PATHABLE: "not_pathable",
    ATTR_PICKUPABLE: "pickupable",
    ATTR_HANGABLE: "hangable",
    ATTR_HOOK_SOUTH: "hook_south",
    ATTR_HOOK_EAST: "hook_east",
    ATTR_ROTATEABLE: "rotateable",
    ATTR_LIGHT: "light",
    ATTR_DONT_HIDE: "dont_hide",
    ATTR_TRANSLUCENT: "translucent",
    ATTR_DISPLACEMENT: "displacement",
    ATTR_ELEVATION: "elevation",
    ATTR_LYING_CORPSE: "lying_corpse",
    ATTR_ANIMATE_ALWAYS: "animate_always",
    ATTR_MINIMAP_COLOR: "minimap_color",
    ATTR_LENS_HELP: "lens_help",
    ATTR_FULL_GROUND: "full_ground",
    ATTR_LOOK: "look",
    ATTR_CLOTH: "cloth",
    ATTR_MARKET: "market",
    ATTR_USABLE: "usable",
    ATTR_WRAPABLE: "wrapable",
    ATTR_UNWRAPABLE: "unwrapable",
    ATTR_TOP_EFFECT: "top_effect",
    ATTR_NO_MOVE_ANIMATION: "no_move_animation",
}


U16_ATTRIBUTES = {
    ATTR_GROUND,
    ATTR_WRITABLE,
    ATTR_WRITABLE_ONCE,
    ATTR_ELEVATION,
    ATTR_MINIMAP_COLOR,
    ATTR_LENS_HELP,
    ATTR_CLOTH,
    ATTR_USABLE,
}


# ============================================================
# ITEM CLASSIFICATION
# ============================================================


ITEM_CLASSIFICATION_PRIORITY = [
    "ground",
    "ground_border",
    "container",
    "stackable",
    "fluid_container",
    "splash",
    "writable",
    "writable_once",
    "pickupable",
    "usable",
]


def classify_item(
    attributes: dict,
) -> str:
    for name in ITEM_CLASSIFICATION_PRIORITY:
        if name in attributes:
            return name

    return "other"


# ============================================================
# GENERAL HELPERS
# ============================================================


def sanitize_name(
    value: str,
) -> str:
    value = value.strip().lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    value = value.strip(
        "_"
    )

    return (
        value
        or "unnamed"
    )


# ============================================================
# BINARY READER
# ============================================================


class Reader:
    def __init__(
        self,
        data: bytes,
        offset: int = 0,
    ):
        self.data = data
        self.cursor = offset

    def require(
        self,
        size: int,
    ):
        if (
            self.cursor + size
            > len(self.data)
        ):
            raise EOFError(
                f"Unexpected EOF at "
                f"0x{self.cursor:08X}"
            )

    def read_u8(
        self,
    ) -> int:
        self.require(
            1
        )

        value = self.data[
            self.cursor
        ]

        self.cursor += 1

        return value

    def read_u16(
        self,
    ) -> int:
        self.require(
            2
        )

        value = struct.unpack_from(
            "<H",
            self.data,
            self.cursor,
        )[0]

        self.cursor += 2

        return value

    def read_u32(
        self,
    ) -> int:
        self.require(
            4
        )

        value = struct.unpack_from(
            "<I",
            self.data,
            self.cursor,
        )[0]

        self.cursor += 4

        return value

    def read_i32(
        self,
    ) -> int:
        self.require(
            4
        )

        value = struct.unpack_from(
            "<i",
            self.data,
            self.cursor,
        )[0]

        self.cursor += 4

        return value

    def read_bytes(
        self,
        size: int,
    ) -> bytes:
        self.require(
            size
        )

        value = self.data[
            self.cursor:
            self.cursor + size
        ]

        self.cursor += size

        return value

    def read_string(
        self,
    ) -> str:
        length = (
            self.read_u16()
        )

        raw = (
            self.read_bytes(
                length
            )
        )

        return raw.decode(
            "utf-8",
            errors="replace",
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

        self.cache: dict[
            int,
            Sprite,
        ] = {}

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

            self.cache[
                0
            ] = sprite

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
        image = (
            self._empty_image()
        )

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

        pixels = (
            image.load()
        )

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
                        "Unexpected EOF "
                        "reading RGB."
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
    ):
        data = file.read(
            2
        )

        if len(
            data
        ) != 2:
            raise EOFError(
                "Unexpected EOF "
                "reading uint16."
            )

        return struct.unpack(
            "<H",
            data,
        )[0]

    @staticmethod
    def _read_u32(
        file,
    ):
        data = file.read(
            4
        )

        if len(
            data
        ) != 4:
            raise EOFError(
                "Unexpected EOF "
                "reading uint32."
            )

        return struct.unpack(
            "<I",
            data,
        )[0]


# ============================================================
# ATTRIBUTES
# ============================================================


def remap_attribute(
    raw_attribute: int,
) -> int:
    if raw_attribute == 0x10:
        return (
            ATTR_NO_MOVE_ANIMATION
        )

    if raw_attribute > 0x10:
        return (
            raw_attribute - 1
        )

    return raw_attribute


def read_market(
    reader: Reader,
):
    return {
        "category": (
            reader.read_u16()
        ),
        "trade_as": (
            reader.read_u16()
        ),
        "show_as": (
            reader.read_u16()
        ),
        "name": (
            reader.read_string()
        ),
        "restrict_vocation": (
            reader.read_u16()
        ),
        "required_level": (
            reader.read_u16()
        ),
    }


def read_attribute_payload(
    reader: Reader,
    attribute: int,
):
    if attribute in U16_ATTRIBUTES:
        return (
            reader.read_u16()
        )

    if attribute == ATTR_LIGHT:
        return {
            "intensity": (
                reader.read_u16()
            ),
            "color": (
                reader.read_u16()
            ),
        }

    if (
        attribute
        == ATTR_DISPLACEMENT
    ):
        return {
            "x": (
                reader.read_u16()
            ),
            "y": (
                reader.read_u16()
            ),
        }

    if attribute == ATTR_MARKET:
        return (
            read_market(
                reader
            )
        )

    return True


def read_attributes(
    reader: Reader,
    category: str,
    thing_id: int,
):
    attributes = {}

    while True:
        attribute_offset = (
            reader.cursor
        )

        raw_attribute = (
            reader.read_u8()
        )

        if (
            raw_attribute
            == ATTRIBUTE_END
        ):
            break

        attribute = (
            remap_attribute(
                raw_attribute
            )
        )

        if (
            attribute
            not in ATTRIBUTE_NAMES
        ):
            raise ValueError(
                f"Unknown attribute "
                f"0x{raw_attribute:02X} "
                f"for {category} "
                f"{thing_id} at "
                f"0x{attribute_offset:08X}"
            )

        name = (
            ATTRIBUTE_NAMES[
                attribute
            ]
        )

        value = (
            read_attribute_payload(
                reader=reader,
                attribute=attribute,
            )
        )

        attributes[
            name
        ] = value

    return attributes


# ============================================================
# ANIMATOR
# ============================================================


def read_animator(
    reader: Reader,
    frames: int,
):
    async_animation = (
        reader.read_u8()
    )

    loop_count = (
        reader.read_i32()
    )

    start_phase = (
        reader.read_u8()
    )

    if async_animation not in (
        0,
        1,
    ):
        raise ValueError(
            "Invalid animator "
            f"async value: "
            f"{async_animation}"
        )

    if start_phase >= frames:
        raise ValueError(
            "Invalid animator "
            f"start phase: "
            f"{start_phase}"
        )

    phases = []

    for phase in range(
        frames
    ):
        min_duration = (
            reader.read_u32()
        )

        max_duration = (
            reader.read_u32()
        )

        if (
            min_duration
            > max_duration
        ):
            raise ValueError(
                "Invalid animation "
                "duration range."
            )

        phases.append(
            {
                "phase": phase,
                "min_duration": (
                    min_duration
                ),
                "max_duration": (
                    max_duration
                ),
            }
        )

    return {
        "async": bool(
            async_animation
        ),
        "loop_count": (
            loop_count
        ),
        "start_phase": (
            start_phase
        ),
        "phases": (
            phases
        ),
    }


# ============================================================
# GRAPHICS
# ============================================================


def read_graphics(
    reader: Reader,
    sprite_count_limit: int,
):
    start_offset = (
        reader.cursor
    )

    width = (
        reader.read_u8()
    )

    height = (
        reader.read_u8()
    )

    if not (
        1 <= width <= 8
    ):
        raise ValueError(
            f"Invalid width "
            f"{width} at "
            f"0x{start_offset:08X}"
        )

    if not (
        1 <= height <= 8
    ):
        raise ValueError(
            f"Invalid height "
            f"{height} at "
            f"0x{start_offset:08X}"
        )

    real_size = (
        SPRITE_SIZE
    )

    if (
        width > 1
        or height > 1
    ):
        real_size = (
            reader.read_u8()
        )

    layers = (
        reader.read_u8()
    )

    pattern_x = (
        reader.read_u8()
    )

    pattern_y = (
        reader.read_u8()
    )

    pattern_z = (
        reader.read_u8()
    )

    frames = (
        reader.read_u8()
    )

    if not (
        1 <= layers <= 8
    ):
        raise ValueError(
            f"Invalid layers: "
            f"{layers}"
        )

    if not (
        1 <= pattern_x <= 32
    ):
        raise ValueError(
            "Invalid pattern_x: "
            f"{pattern_x}"
        )

    if not (
        1 <= pattern_y <= 32
    ):
        raise ValueError(
            "Invalid pattern_y: "
            f"{pattern_y}"
        )

    if not (
        1 <= pattern_z <= 32
    ):
        raise ValueError(
            "Invalid pattern_z: "
            f"{pattern_z}"
        )

    if not (
        1 <= frames <= 255
    ):
        raise ValueError(
            f"Invalid frames: "
            f"{frames}"
        )

    animator = None

    if frames > 1:
        animator = (
            read_animator(
                reader=reader,
                frames=frames,
            )
        )

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
        <= MAX_SPRITES_PER_GRAPHICS
    ):
        raise ValueError(
            "Invalid sprite count: "
            f"{sprite_count}"
        )

    sprite_ids = []

    for _ in range(
        sprite_count
    ):
        sprite_id = (
            reader.read_u32()
        )

        if (
            sprite_id != 0
            and sprite_id
            > sprite_count_limit
        ):
            raise ValueError(
                f"Invalid sprite ID: "
                f"{sprite_id}"
            )

        sprite_ids.append(
            sprite_id
        )

    return {
        "width": (
            width
        ),
        "height": (
            height
        ),
        "real_size": (
            real_size
        ),
        "layers": (
            layers
        ),
        "pattern_x": (
            pattern_x
        ),
        "pattern_y": (
            pattern_y
        ),
        "pattern_z": (
            pattern_z
        ),
        "frames": (
            frames
        ),
        "animator": (
            animator
        ),
        "sprite_count": (
            sprite_count
        ),
        "sprite_ids": (
            sprite_ids
        ),
    }


# ============================================================
# FRAME GROUPS
# ============================================================


def read_frame_groups(
    reader: Reader,
    sprite_count_limit: int,
):
    group_count = (
        reader.read_u8()
    )

    if not (
        1
        <= group_count
        <= 8
    ):
        raise ValueError(
            "Invalid frame group "
            f"count: {group_count}"
        )

    groups = []

    for index in range(
        group_count
    ):
        group_type = (
            reader.read_u8()
        )

        if group_type not in (
            0,
            1,
        ):
            raise ValueError(
                "Invalid frame group "
                f"type: {group_type}"
            )

        graphics = (
            read_graphics(
                reader=reader,
                sprite_count_limit=(
                    sprite_count_limit
                ),
            )
        )

        groups.append(
            {
                "index": index,
                "type": (
                    group_type
                ),
                "graphics": (
                    graphics
                ),
            }
        )

    return {
        "group_count": (
            group_count
        ),
        "groups": (
            groups
        ),
    }


# ============================================================
# DAT RECORDS
# ============================================================


def read_record(
    reader: Reader,
    category: str,
    thing_id: int,
    sprite_count_limit: int,
):
    attributes = (
        read_attributes(
            reader=reader,
            category=category,
            thing_id=thing_id,
        )
    )

    if category == "creatures":
        frame_groups = (
            read_frame_groups(
                reader=reader,
                sprite_count_limit=(
                    sprite_count_limit
                ),
            )
        )

        return {
            "id": thing_id,
            "category": (
                category
            ),
            "attributes": (
                attributes
            ),
            "type": (
                "frame_groups"
            ),
            "frame_groups": (
                frame_groups
            ),
        }

    graphics = (
        read_graphics(
            reader=reader,
            sprite_count_limit=(
                sprite_count_limit
            ),
        )
    )

    return {
        "id": (
            thing_id
        ),
        "category": (
            category
        ),
        "attributes": (
            attributes
        ),
        "type": (
            "single"
        ),
        "graphics": (
            graphics
        ),
    }


# ============================================================
# DAT PARSER
# ============================================================


def parse_dat(
    sprite_count_limit: int,
):
    data = (
        DAT_PATH.read_bytes()
    )

    reader = Reader(
        data=data,
    )

    signature = (
        reader.read_u32()
    )

    max_item_id = (
        reader.read_u16()
    )

    max_creature_id = (
        reader.read_u16()
    )

    max_effect_id = (
        reader.read_u16()
    )

    max_missile_id = (
        reader.read_u16()
    )

    print(
        f"DAT signature: "
        f"0x{signature:08X}"
    )

    print(
        f"Max item ID:     "
        f"{max_item_id}"
    )

    print(
        f"Max creature ID: "
        f"{max_creature_id}"
    )

    print(
        f"Max effect ID:   "
        f"{max_effect_id}"
    )

    print(
        f"Max missile ID:  "
        f"{max_missile_id}"
    )

    records = {
        "items": [],
        "creatures": [],
        "effects": [],
        "missiles": [],
    }

    sections = [
        (
            "items",
            FIRST_ITEM_ID,
            max_item_id,
        ),
        (
            "creatures",
            FIRST_CREATURE_ID,
            max_creature_id,
        ),
        (
            "effects",
            FIRST_EFFECT_ID,
            max_effect_id,
        ),
        (
            "missiles",
            FIRST_MISSILE_ID,
            max_missile_id,
        ),
    ]

    for (
        category,
        first_id,
        last_id,
    ) in sections:
        print()

        print(
            f"Parsing "
            f"{category}..."
        )

        total = (
            last_id
            - first_id
            + 1
        )

        for index, thing_id in enumerate(
            range(
                first_id,
                last_id + 1,
            ),
            start=1,
        ):
            record = (
                read_record(
                    reader=reader,
                    category=category,
                    thing_id=thing_id,
                    sprite_count_limit=(
                        sprite_count_limit
                    ),
                )
            )

            records[
                category
            ].append(
                record
            )

            step = (
                1000
                if category
                == "items"
                else 100
            )

            if (
                index % step
                == 0
                or index
                == total
            ):
                print(
                    f"  "
                    f"{index}/{total} "
                    f"| ID {thing_id} "
                    f"| offset "
                    f"0x{reader.cursor:08X}"
                )

    if (
        reader.cursor
        != len(data)
    ):
        raise ValueError(
            "DAT parser did not "
            "finish exactly at EOF. "
            f"Cursor=0x{reader.cursor:08X}, "
            f"EOF=0x{len(data):08X}"
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
# ASSET PATHS
# ============================================================


def get_record_name(
    record: dict,
):
    attributes = record[
        "attributes"
    ]

    market = attributes.get(
        "market"
    )

    if (
        isinstance(
            market,
            dict,
        )
        and market.get(
            "name"
        )
    ):
        return market[
            "name"
        ]

    return None


def build_asset_dir(
    record: dict,
):
    category = record[
        "category"
    ]

    thing_id = record[
        "id"
    ]

    name = get_record_name(
        record
    )

    if name:
        directory_name = (
            f"{thing_id}_"
            f"{sanitize_name(name)}"
        )

    else:
        directory_name = str(
            thing_id
        )

    if category == "items":
        item_type = classify_item(
            record[
                "attributes"
            ]
        )

        return (
            OUTPUT_PATH
            / "items"
            / item_type
            / directory_name
        )

    return (
        OUTPUT_PATH
        / category
        / directory_name
    )


# ============================================================
# GRAPHICS EXPORT
# ============================================================


def export_graphics(
    graphics: dict,
    output_dir: Path,
    spr_reader: SprReader,
):
    sprite_ids = graphics[
        "sprite_ids"
    ]

    if all(
        sprite_id == 0
        for sprite_id
        in sprite_ids
    ):
        return 0

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
                        group = (
                            sprite_ids[
                                index:
                                index
                                + tiles_per_image
                            ]
                        )

                        index += (
                            tiles_per_image
                        )

                        if all(
                            sprite_id == 0
                            for sprite_id
                            in group
                        ):
                            continue

                        image = (
                            compose_tiles(
                                spr_reader=(
                                    spr_reader
                                ),
                                sprite_ids=(
                                    group
                                ),
                                width=width,
                                height=height,
                            )
                        )

                        filename = (
                            f"frame_"
                            f"{frame:03d}_"
                            f"x_"
                            f"{pattern_x:02d}_"
                            f"y_"
                            f"{pattern_y:02d}_"
                            f"z_"
                            f"{pattern_z:02d}_"
                            f"layer_"
                            f"{layer:02d}.png"
                        )

                        image.save(
                            output_dir
                            / filename
                        )

                        exported += 1

    return exported


# ============================================================
# RECORD EXPORT
# ============================================================


def export_record(
    record: dict,
    spr_reader: SprReader,
):
    asset_dir = (
        build_asset_dir(
            record
        )
    )

    if (
        record[
            "type"
        ]
        == "single"
    ):
        return export_graphics(
            graphics=record[
                "graphics"
            ],
            output_dir=asset_dir,
            spr_reader=(
                spr_reader
            ),
        )

    exported = 0

    for group in record[
        "frame_groups"
    ][
        "groups"
    ]:
        group_dir = (
            asset_dir
            / (
                f"group_"
                f"{group['index']:02d}_"
                f"type_"
                f"{group['type']}"
            )
        )

        exported += (
            export_graphics(
                graphics=group[
                    "graphics"
                ],
                output_dir=(
                    group_dir
                ),
                spr_reader=(
                    spr_reader
                ),
            )
        )

    return exported


# ============================================================
# EXPORT ALL
# ============================================================


def export_all(
    records: dict,
    spr_reader: SprReader,
):
    total_assets = 0
    exported_assets = 0
    total_pngs = 0

    categories = [
        "items",
        "creatures",
        "effects",
        "missiles",
    ]

    for category in categories:
        category_records = (
            records[
                category
            ]
        )

        print()
        print(
            "=" * 72
        )

        print(
            category.upper()
        )

        print(
            "=" * 72
        )

        total = len(
            category_records
        )

        for index, record in enumerate(
            category_records,
            start=1,
        ):
            total_assets += 1

            exported_pngs = (
                export_record(
                    record=record,
                    spr_reader=(
                        spr_reader
                    ),
                )
            )

            if exported_pngs > 0:
                exported_assets += 1

                total_pngs += (
                    exported_pngs
                )

            step = (
                500
                if category
                == "items"
                else 50
            )

            if (
                index % step
                == 0
                or index
                == total
            ):
                print(
                    f"  "
                    f"{index}/{total} "
                    f"| ID "
                    f"{record['id']} "
                    f"| PNGs "
                    f"{exported_pngs}"
                )

    return (
        total_assets,
        exported_assets,
        total_pngs,
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
        f"DAT: "
        f"{DAT_PATH}"
    )

    print(
        f"SPR: "
        f"{SPR_PATH}"
    )

    print(
        f"Assets: "
        f"{OUTPUT_PATH.resolve()}"
    )

    print()

    print(
        "Reading SPR..."
    )

    spr_reader = (
        SprReader(
            SPR_PATH
        )
    )

    print(
        f"SPR signature: "
        f"0x"
        f"{spr_reader.signature:08X}"
    )

    print(
        f"SPR sprites: "
        f"{spr_reader.sprite_count}"
    )

    print()

    print(
        "Parsing DAT..."
    )

    records = parse_dat(
        sprite_count_limit=(
            spr_reader.sprite_count
        )
    )

    print()
    print(
        "DAT parsed successfully "
        "to EOF."
    )

    #
    # Always regenerate assets from scratch.
    #
    if OUTPUT_PATH.exists():
        print()
        print(
            "Removing previous assets..."
        )

        shutil.rmtree(
            OUTPUT_PATH
        )

    OUTPUT_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print(
        "Exporting assets..."
    )

    (
        total_assets,
        exported_assets,
        total_pngs,
    ) = export_all(
        records=records,
        spr_reader=(
            spr_reader
        ),
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
        f"Assets processed: "
        f"{total_assets}"
    )

    print(
        f"Assets exported:  "
        f"{exported_assets}"
    )

    print(
        f"PNGs exported:    "
        f"{total_pngs}"
    )

    print(
        f"Assets path:      "
        f"{OUTPUT_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()