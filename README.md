# Tibia Assets Exporter

Python scripts for extracting assets and metadata from Tibia `.dat` and `.spr` files.

## Supported Versions

- Tibia 7.41
- Tibia 15.01

Each version has its own parser due to differences between the DAT and SPR formats.

## Structure

```text
tibia-assets/
├── 741/
│   ├── Tibia.dat
│   ├── Tibia.spr
│   ├── export.py
│   ├── metadata.json
│   └── assets/
├── 1501/
│   ├── Tibia.dat
│   ├── Tibia.spr
│   ├── export.py
│   ├── metadata.json
│   └── assets/
├── README.md
└── requirements.txt
```

## Game Files

The original Tibia files are **not included in this repository**:

```text
Tibia.dat
Tibia.spr
```

You must obtain these files separately and place them inside the corresponding version directory.

The repository does not distribute copyrighted Tibia game data or assets.

## Requirements

- Python 3
- Pillow

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Tibia 7.41

```bash
cd 741
python export.py
```

Exports:

- Items
- Creatures
- Effects
- Missiles

### Tibia 15.01

```bash
cd 1501
python export.py
```

Exports:

- Items
- Creatures
- Metadata

## Output

Assets are exported to the `assets` directory and organized by category and DAT ID.

When a name is available, it is included in the directory name.

```text
assets/
├── items/
│   ├── 100/
│   ├── 101_some_item/
│   └── ...
└── creatures/
    ├── 1/
    ├── 2/
    └── ...
```

For supported versions, `metadata.json` contains information extracted from the DAT and links each entry to its exported assets.

The exporter supports:

- Multi-tile sprites
- Patterns
- Layers
- Animation frames
- Transparency
- Frame groups
- Metadata extraction
- Version-specific DAT and SPR structures