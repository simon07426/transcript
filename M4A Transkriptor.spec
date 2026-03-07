# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = []
hiddenimports = []
datas += collect_data_files('whisper')
datas += collect_data_files('pyannote.audio')
datas += collect_data_files('pyannote.core')
datas += collect_data_files('pyannote.database')
datas += collect_data_files('pyannote.pipeline')
hiddenimports += collect_submodules('whisper')
hiddenimports += collect_submodules('pyannote.audio')


a = Analysis(
    ['transcript.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['mlx', 'mlx_whisper', 'mlx.core', 'mlx.nn', 'mlx.optimizers'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='M4A Transkriptor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='M4A Transkriptor',
)
app = BUNDLE(
    coll,
    name='M4A Transkriptor.app',
    icon=None,
    bundle_identifier='com.simongodarsky.m4atranskriptor',
)
