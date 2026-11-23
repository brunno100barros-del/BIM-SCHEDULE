# -*- mode: python ; coding: utf-8 -*-
# Empacota o serviço local (FastAPI + IfcOpenShell) em uma pasta com
# bim-schedule-service.exe. Usado pelo aplicativo desktop (Electron).
#
#   ..\..\.venv\Scripts\python.exe -m PyInstaller --noconfirm bim-schedule-service.spec
#
# alembic.ini e migrations/ são copiados para a raiz do pacote (_MEIPASS), que é o
# BACKEND_DIR calculado por app/core/config.py dentro do executável.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]
BACKEND = ROOT / "backend"

datas = [
    (str(BACKEND / "alembic.ini"), "."),
    (str(BACKEND / "migrations"), "migrations"),
]
binaries = []
# Os módulos de tarefa são importados dinamicamente (app/jobs/registry.py), então
# todos os módulos de app/ são listados a partir dos arquivos-fonte.
app_modules = sorted(
    ".".join(p.relative_to(BACKEND).with_suffix("").parts).removesuffix(".__init__")
    for p in (BACKEND / "app").rglob("*.py")
)
hiddenimports = app_modules + [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "multipart",
    "python_multipart",
]
for pkg in ("ifcopenshell", "alembic", "sqlalchemy", "shapely"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(BACKEND / "app" / "__main__.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "matplotlib", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bim-schedule-service",
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="bim-schedule-service")
