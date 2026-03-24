"""
build_engine.py — Bundle VidScratch Python backend into a single executable.

Usage:
    cd python/
    pip install pyinstaller
    python build_engine.py

Output:
    dist/vidscratch_engine/vidscratch_engine.exe   (Windows)
    dist/vidscratch_engine/vidscratch_engine        (macOS/Linux)

Then copy the entire dist/vidscratch_engine/ folder into:
    tauri-app/src-tauri/engine/
"""

import PyInstaller.__main__
import sys
import os

def build():
    # Determine platform-specific options
    separator = ';' if sys.platform == 'win32' else ':'

    args = [
        'attack.py',                          # Entry point
        '--name', 'vidscratch_engine',        # Output name
        '--noconfirm',                        # Overwrite without asking
        '--clean',                            # Clean cache

        # ── Include all our Python modules ──
        '--hidden-import', 'vidscratch',
        '--hidden-import', 'model_wrapper',
        '--hidden-import', 'video_io',
        '--hidden-import', 'models',
        '--hidden-import', 'models.ssim',
        '--hidden-import', 'models.spatial_transformer',

        # ── Include PyTorch & dependencies ──
        '--hidden-import', 'torch',
        '--hidden-import', 'torchvision',
        '--hidden-import', 'pytorchvideo',
        '--hidden-import', 'pytorchvideo.models',
        '--hidden-import', 'cv2',
        '--hidden-import', 'scipy',
        '--hidden-import', 'scipy.stats',
        '--hidden-import', 'numpy',
        '--hidden-import', 'PIL',

        # ── Collect all torch data files (model weights etc) ──
        '--collect-all', 'torch',
        '--collect-all', 'torchvision',
        '--collect-all', 'pytorchvideo',

        # ── Add our models/ as data ──
        '--add-data', f'models{separator}models',

        # ── Add label map if exists ──
    ]

    # Optionally include label files
    for label_file in ['kinetics_400_labels.json', 'label_map.json']:
        if os.path.isfile(label_file):
            args.extend(['--add-data', f'{label_file}{separator}.'])

    # Use directory mode (not --onefile) for faster startup
    # onefile extracts to temp every launch which is slow for torch
    args.append('--distpath')
    args.append('dist')

    print("=" * 60)
    print("  Building VidScratch Engine with PyInstaller")
    print("=" * 60)
    print(f"  Platform: {sys.platform}")
    print(f"  Python:   {sys.version}")
    print()

    PyInstaller.__main__.run(args)

    print()
    print("=" * 60)
    print("  Build complete!")
    print("=" * 60)
    print()
    print("  Output: dist/vidscratch_engine/")
    print()
    print("  Next steps:")
    print("  1. Copy dist/vidscratch_engine/ → tauri-app/src-tauri/engine/")
    print("  2. Run: cd tauri-app && cargo tauri build")
    print()


if __name__ == '__main__':
    build()
