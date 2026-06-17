# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static'), ('instructions.md', '.'), ('.agent_rules.md', '.'), ('version.json', '.')],
    hiddenimports=['greenlet', 'greenlet._greenlet'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'matplotlib', 'pandas', 'scipy', 'tkinter',
        'numpy', 'PIL', 'cv2', 'IPython', 'jupyter', 'notebook',
        'sqlalchemy', 'alembic', 'pytest',
        'curses', 'idlelib', 'lib2to3', 'turtle',
        'xmlrpc', 'pydoc', 'doctest', 'unittest',
        'multiprocessing', 'concurrent.futures.process',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Athena',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
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
    name='Athena',
)
