import struct
from pathlib import Path

from PIL import Image


DAT_PATH = Path("Tibia.dat")
SPR_PATH = Path("Tibia.spr")

OUTPUT_PATH = Path("assets")

SPRITE_SIZE = 32


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
            self.sprite_count = self._read_u16(file)

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
                f"Invalid SPR sprite ID: {sprite_id}"
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
        max_pixels = SPRITE_SIZE * SPRITE_SIZE

        while (
            file.tell() < data_end
            and pixel_index < max_pixels
        ):
            transparent_pixels = self._read_u16(file)
            colored_pixels = self._read_u16(file)

            pixel_index += transparent_pixels

            for _ in range(colored_pixels):
                if pixel_index >= max_pixels:
                    break

                rgb = file.read(3)

                if len(rgb) != 3:
                    raise EOFError(
                        "Unexpected EOF while reading sprite RGB."
                    )

                r, g, b = rgb

                x = pixel_index % SPRITE_SIZE
                y = pixel_index // SPRITE_SIZE

                pixels[x, y] = (
                    r,
                    g,
                    b,
                    255,
                )

                pixel_index += 1

        return image

    @staticmethod
    def _read_u16(file) -> int:
        data = file.read(2)

        if len(data) != 2:
            raise EOFError(
                "Unexpected EOF while reading uint16."
            )

        return struct.unpack(
            "<H",
            data,
        )[0]

    @staticmethod
    def _read_u32(file) -> int:
        data = file.read(4)

        if len(data) != 4:
            raise EOFError(
                "Unexpected EOF while reading uint32."
            )

        return struct.unpack(
            "<I",
            data,
        )[0]


# ============================================================
# DAT
# ============================================================


class DatReader:
    def __init__(
        self,
        path: Path,
    ):
        self.path = path
        self.data = path.read_bytes()

        self.cursor = 0

        self.signature = 0

        self.max_item_id = 0
        self.max_creature_id = 0
        self.max_effect_id = 0
        self.max_missile_id = 0

    def read_u8(self) -> int:
        self._require(1)

        value = self.data[
            self.cursor
        ]

        self.cursor += 1

        return value

    def read_u16(self) -> int:
        self._require(2)

        value = struct.unpack_from(
            "<H",
            self.data,
            self.cursor,
        )[0]

        self.cursor += 2

        return value

    def read_u32(self) -> int:
        self._require(4)

        value = struct.unpack_from(
            "<I",
            self.data,
            self.cursor,
        )[0]

        self.cursor += 4

        return value

    def _require(
        self,
        count: int,
    ):
        if (
            self.cursor + count
            > len(self.data)
        ):
            raise EOFError(
                f"Unexpected EOF at "
                f"0x{self.cursor:08X}"
            )

    def read_header(self):
        self.signature = self.read_u32()

        self.max_item_id = self.read_u16()
        self.max_creature_id = self.read_u16()
        self.max_effect_id = self.read_u16()
        self.max_missile_id = self.read_u16()

    def read_flags(
        self,
    ) -> list[dict]:
        flags = []

        while True:
            offset = self.cursor
            flag = self.read_u8()

            if flag == 0xFF:
                break

            flags.append(
                self.read_flag(
                    flag=flag,
                    offset=offset,
                )
            )

        return flags

    def read_flag(
        self,
        flag: int,
        offset: int,
    ) -> dict:
        if flag == 0x00:
            return {
                "id": flag,
                "name": "ground",
                "speed": self.read_u16(),
            }

        if flag == 0x01:
            return {
                "id": flag,
                "name": "on_bottom",
            }

        if flag == 0x02:
            return {
                "id": flag,
                "name": "on_top",
            }

        if flag == 0x03:
            return {
                "id": flag,
                "name": "container",
            }

        if flag == 0x04:
            return {
                "id": flag,
                "name": "stackable",
            }

        if flag == 0x05:
            return {
                "id": flag,
                "name": "multi_use",
            }

        if flag == 0x06:
            return {
                "id": flag,
                "name": "force_use",
            }

        if flag == 0x07:
            return {
                "id": flag,
                "name": "writable",
                "length": self.read_u16(),
            }

        if flag == 0x08:
            return {
                "id": flag,
                "name": "writable_once",
                "length": self.read_u16(),
            }

        if flag == 0x09:
            return {
                "id": flag,
                "name": "fluid_container",
            }

        if flag == 0x0A:
            return {
                "id": flag,
                "name": "fluid",
            }

        if flag == 0x0B:
            return {
                "id": flag,
                "name": "unpassable",
            }

        if flag == 0x0C:
            return {
                "id": flag,
                "name": "unmovable",
            }

        if flag == 0x0D:
            return {
                "id": flag,
                "name": "block_missile",
            }

        if flag == 0x0E:
            return {
                "id": flag,
                "name": "block_pathfinder",
            }

        if flag == 0x0F:
            return {
                "id": flag,
                "name": "pickupable",
            }

        if flag == 0x10:
            return {
                "id": flag,
                "name": "light_info",
                "level": self.read_u16(),
                "color": self.read_u16(),
            }

        if flag == 0x11:
            return {
                "id": flag,
                "name": "floor_change",
            }

        if flag == 0x12:
            return {
                "id": flag,
                "name": "full_ground",
            }

        if flag == 0x13:
            return {
                "id": flag,
                "name": "has_elevation",
                "height": self.read_u16(),
            }

        if flag == 0x14:
            return {
                "id": flag,
                "name": "has_offset",
            }

        if flag == 0x15:
            return {
                "id": flag,
                "name": "unknown",
            }

        if flag == 0x16:
            return {
                "id": flag,
                "name": "minimap",
                "color": self.read_u16(),
            }

        if flag == 0x17:
            return {
                "id": flag,
                "name": "rotatable",
            }

        if flag == 0x18:
            return {
                "id": flag,
                "name": "lying_object",
            }

        if flag == 0x19:
            return {
                "id": flag,
                "name": "hangable",
            }

        if flag == 0x1A:
            return {
                "id": flag,
                "name": "vertical",
            }

        if flag == 0x1B:
            return {
                "id": flag,
                "name": "horizontal",
            }

        if flag == 0x1C:
            return {
                "id": flag,
                "name": "always_animate",
            }

        if flag == 0x1D:
            return {
                "id": flag,
                "name": "lens_help",
                "value": self.read_u16(),
            }

        raise ValueError(
            f"Unknown DAT flag "
            f"0x{flag:02X} "
            f"at 0x{offset:08X}"
        )

    def read_graphics(
        self,
    ) -> dict:
        offset = self.cursor

        width = self.read_u8()
        height = self.read_u8()

        real_size = SPRITE_SIZE

        if (
            width > 1
            or height > 1
        ):
            real_size = self.read_u8()

        exact_size = min(
            real_size,
            max(
                width * SPRITE_SIZE,
                height * SPRITE_SIZE,
            ),
        )

        layers = self.read_u8()

        pattern_x = self.read_u8()
        pattern_y = self.read_u8()

        pattern_z = 1

        frames = self.read_u8()

        sprite_count = (
            width
            * height
            * layers
            * pattern_x
            * pattern_y
            * pattern_z
            * frames
        )

        sprite_ids = [
            self.read_u16()
            for _ in range(
                sprite_count
            )
        ]

        return {
            "offset": offset,
            "width": width,
            "height": height,
            "real_size": real_size,
            "exact_size": exact_size,
            "layers": layers,
            "pattern_x": pattern_x,
            "pattern_y": pattern_y,
            "pattern_z": pattern_z,
            "frames": frames,
            "sprite_ids": sprite_ids,
        }

    def read_thing(
        self,
        thing_id: int,
        category: str,
    ) -> dict:
        offset = self.cursor

        flags = self.read_flags()
        graphics = self.read_graphics()

        return {
            "id": thing_id,
            "category": category,
            "offset": offset,
            "end_offset": self.cursor,
            "flags": flags,
            "graphics": graphics,
        }

    def read_range(
        self,
        category: str,
        first_id: int,
        last_id: int,
    ) -> list[dict]:
        return [
            self.read_thing(
                thing_id=thing_id,
                category=category,
            )
            for thing_id in range(
                first_id,
                last_id + 1,
            )
        ]

    def parse(
        self,
    ) -> dict:
        self.read_header()

        items = self.read_range(
            category="items",
            first_id=100,
            last_id=self.max_item_id,
        )

        creatures = self.read_range(
            category="creatures",
            first_id=1,
            last_id=self.max_creature_id,
        )

        effects = self.read_range(
            category="effects",
            first_id=1,
            last_id=self.max_effect_id,
        )

        missiles = self.read_range(
            category="missiles",
            first_id=1,
            last_id=self.max_missile_id,
        )

        if self.cursor != len(
            self.data
        ):
            raise ValueError(
                "DAT parser did not finish exactly at EOF. "
                f"Cursor=0x{self.cursor:08X} "
                f"EOF=0x{len(self.data):08X}"
            )

        return {
            "items": items,
            "creatures": creatures,
            "effects": effects,
            "missiles": missiles,
        }


# ============================================================
# COMPOSITION
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
            width * SPRITE_SIZE,
            height * SPRITE_SIZE,
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
            index % width
        ) * SPRITE_SIZE

        y = (
            index // width
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
# EXPORT
# ============================================================


def export_thing(
    thing: dict,
    spr_reader: SprReader,
):
    category = thing[
        "category"
    ]

    thing_id = thing[
        "id"
    ]

    graphics = thing[
        "graphics"
    ]

    sprite_ids = graphics[
        "sprite_ids"
    ]

    if all(
        sprite_id == 0
        for sprite_id in sprite_ids
    ):
        return 0

    output_dir = (
        OUTPUT_PATH
        / category
        / str(thing_id)
    )

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

    frames = graphics[
        "frames"
    ]

    tiles_per_image = (
        width
        * height
    )

    index = 0
    exported_images = 0

    for frame in range(
        frames
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
                        f"frame_{frame:02d}_"
                        f"x_{pattern_x:02d}_"
                        f"y_{pattern_y:02d}_"
                        f"layer_{layer:02d}.png"
                    )

                    image.save(
                        output_dir
                        / filename
                    )

                    exported_images += 1

    return exported_images


# ============================================================
# EXPORT ALL
# ============================================================


def export_all(
    parsed: dict,
    spr_reader: SprReader,
):
    categories = [
        "items",
        "creatures",
        "effects",
        "missiles",
    ]

    total_assets = 0
    exported_assets = 0
    empty_assets = 0
    pngs_exported = 0

    for category in categories:
        print()
        print("=" * 60)
        print(
            category.upper()
        )
        print("=" * 60)

        things = parsed[
            category
        ]

        total = len(
            things
        )

        for index, thing in enumerate(
            things,
            start=1,
        ):
            total_assets += 1

            exported_images = export_thing(
                thing=thing,
                spr_reader=spr_reader,
            )

            if exported_images > 0:
                exported_assets += 1
                pngs_exported += exported_images
            else:
                empty_assets += 1

            print(
                f"[{index}/{total}] "
                f"{category} "
                f"{thing['id']}: "
                f"{exported_images} PNG(s)"
            )

    return (
        total_assets,
        exported_assets,
        empty_assets,
        pngs_exported,
    )


# ============================================================
# MAIN
# ============================================================


def main():
    if not DAT_PATH.exists():
        raise FileNotFoundError(
            f"DAT file not found: "
            f"{DAT_PATH.resolve()}"
        )

    if not SPR_PATH.exists():
        raise FileNotFoundError(
            f"SPR file not found: "
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

    print()

    print(
        "Parsing DAT..."
    )

    dat_reader = DatReader(
        DAT_PATH
    )

    parsed = dat_reader.parse()

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

    print(
        f"Effects: "
        f"{len(parsed['effects'])}"
    )

    print(
        f"Missiles: "
        f"{len(parsed['missiles'])}"
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
        total_assets,
        exported_assets,
        empty_assets,
        pngs_exported,
    ) = export_all(
        parsed=parsed,
        spr_reader=spr_reader,
    )

    print()
    print("=" * 60)
    print("FINISHED")
    print("=" * 60)

    print(
        f"Assets processed: "
        f"{total_assets}"
    )

    print(
        f"Assets exported:  "
        f"{exported_assets}"
    )

    print(
        f"Empty assets:     "
        f"{empty_assets}"
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