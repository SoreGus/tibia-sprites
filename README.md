# Tibia Assets Exporter

Python scripts for extracting assets from Tibia `.dat` and `.spr` files and exporting them as PNG images.

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
│   ├── export_assets.py
│   └── assets/
├── 1501/
│   ├── Tibia.dat
│   ├── Tibia.spr
│   ├── export_assets.py
│   └── assets/
├── README.md
└── requirements.txt
```

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
python export_assets.py
```

Exports:

- Items
- Creatures
- Effects
- Missiles

### Tibia 15.01

```bash
cd 1501
python export_assets.py
```

Exports:

- Items
- Creatures

## Output

Extracted assets are written to the `assets` directory and organized by category and DAT ID.

```text
assets/
├── items/
│   ├── 100/
│   ├── 101/
│   └── ...
└── creatures/
    ├── 1/
    ├── 2/
    └── ...
```

The exporter supports multi-tile sprites, patterns, layers, animation frames, transparency, and version-specific DAT structures.