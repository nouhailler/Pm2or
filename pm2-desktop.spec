from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "src" / "pm2" / "__main__.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[
        (str(root / "04_PM2_METHODOLOGY.yaml"), "pm2/resources"),
        (str(root / "templates"), "pm2/templates"),
    ],
    hiddenimports=["sqlalchemy.dialects.sqlite", "jinja2.ext"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pm2-desktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="pm2-desktop",
)
