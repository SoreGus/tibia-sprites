# Tibia Assets Exporter

Python scripts for extracting and organizing assets from Tibia `.dat` and `.spr` files.

## Supported Versions

- Tibia 7.41
- Tibia 15.01

Each version has its own parser due to differences between DAT and SPR formats.

## Structure

```text
tibia-assets/
├── 741/
│   ├── export.py
│   └── metadata.json
├── 1501/
│   ├── export.py
│   ├── organize_assets.py
│   ├── generate.py
│   └── catalog.json
├── README.md
└── requirements.txt
```

## Game Files

The original Tibia files are **not included**:

```text
Tibia.dat
Tibia.spr
```

Place them inside the corresponding version directory before running the exporter.

Generated assets are also not included in the repository.

## Requirements

- Python 3
- Pillow

```bash
pip install -r requirements.txt
```

## Tibia 7.41

```bash
cd 741
python export.py
```

Exports items, creatures, effects, missiles and metadata to `assets/` and `metadata.json`.

## Tibia 15.01

Tibia 15.01 includes semantic organization based on `catalog.json`.

Place:

```text
1501/
├── Tibia.dat
├── Tibia.spr
├── export.py
├── organize_assets.py
├── generate.py
└── catalog.json
```

Then run:

```bash
cd 1501
python generate.py
```

The pipeline is:

```text
Tibia.dat + Tibia.spr
        ↓
export.py
        ↓
raw assets/
        ↓
organize_assets.py + catalog.json
        ↓
assets/
```

`generate.py` runs the complete process automatically and removes the temporary raw assets.

The final assets are semantically organized into categories such as grounds, borders, brushes and tilesets.

Example:

```text
assets/
└── grounds/
    └── acid/
        ├── acid_001.png
        ├── acid_002.png
        └── borders/
            ├── acid_cne_001.png
            ├── acid_cnw_001.png
            ├── acid_n_001.png
            └── ...
```

Assets that cannot be reliably mapped are preserved as unclassified assets.

## Graphics Support

The exporters support:

- Multi-tile sprites
- Patterns
- Layers
- Animation frames
- Transparency
- Frame groups
- Sprite composition
- Version-specific DAT/SPR formats

## Repository Policy

The repository contains extraction scripts and supporting metadata, but does **not** distribute:

```text
Tibia.dat
Tibia.spr
assets/
```

These files must be obtained or generated separately.