# PyInstaller spec pour CABReplay
# Build : pyinstaller --noconfirm CABReplay.spec
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules

block_cipher = None

# customtkinter : embarque ses thèmes JSON, assets, etc.
ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")

# cyndilib : embarque les DLLs NDI bundlées + tous les sous-modules Cython
cyndi_binaries = collect_dynamic_libs("cyndilib")
cyndi_hidden = collect_submodules("cyndilib")

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=ctk_binaries + cyndi_binaries,
    datas=ctk_datas + [("assets/icon.ico", "assets")],
    hiddenimports=ctk_hidden + cyndi_hidden + ["darkdetect"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CABReplay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # pas de fenêtre console ; les erreurs vont dans crash.log a cote de l'exe
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CABReplay",
)
