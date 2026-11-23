"""Relatório da extração IFC (somente leitura).

Combina:
  * o que o BIM SCHEDULE gravou no banco (``ifc_elements``), aberto em modo somente leitura;
  * uma leitura direta do arquivo IFC com IfcOpenShell para dados que o app ainda NÃO extrai
    (cabeçalho completo, unidades do projeto, classificações, pavimentos com cota).

Uso:
    .venv\\Scripts\\python.exe desktop\\scripts\\ifc_report.py --bench resultado.json --out relatorio.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.unit

NON_PHYSICAL = {"IfcOpeningElement", "IfcVirtualElement", "IfcOpeningStandardCase"}
ALT_QTY_NAMES = {"area", "volume", "length", "comprimento", "área", "netarea", "grossarea", "netvolume",
                 "grossvolume", "perimeter", "perímetro", "width", "height", "largura", "altura", "weight", "peso",
                 "massa", "mass"}


def is_physical(schema, ifc_type: str) -> bool:
    if ifc_type in NON_PHYSICAL:
        return False
    try:
        decl = schema.declaration_by_name(ifc_type)
    except Exception:
        return False
    while decl is not None:
        name = decl.name()
        if name in ("IfcFeatureElement", "IfcVirtualElement"):
            return False
        if name == "IfcElement":
            return True
        decl = decl.supertype()
    return False


def unit_label(f, kind):
    try:
        u = ifcopenshell.util.unit.get_project_unit(f, kind)
    except Exception:
        u = None
    if u is None:
        return None
    try:
        return ifcopenshell.util.unit.get_full_unit_name(u)
    except Exception:
        return str(u)


def direct_analysis(path: str) -> dict:
    t0 = time.perf_counter()
    f = ifcopenshell.open(path)
    out: dict = {"schema": f.schema}
    try:
        fn = f.header.file_name
        out["header"] = {
            "originating_system": fn.originating_system,
            "preprocessor_version": fn.preprocessor_version,
            "author": list(fn.author) if fn.author else [],
            "organization": list(fn.organization) if fn.organization else [],
            "time_stamp": fn.time_stamp,
            "description": list(f.header.file_description.description or []),
        }
    except Exception as exc:  # cabeçalho fora do padrão
        out["header"] = {"error": str(exc)}
    apps = []
    for app in f.by_type("IfcApplication"):
        apps.append(f"{app.ApplicationFullName} {app.Version}".strip())
    out["ifc_applications"] = sorted(set(apps))
    out["units"] = {k: unit_label(f, k) for k in ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT", "MASSUNIT", "PLANEANGLEUNIT")}
    storeys = []
    for s in f.by_type("IfcBuildingStorey"):
        storeys.append({"name": s.Name, "elevation": getattr(s, "Elevation", None)})
    out["storeys"] = sorted(storeys, key=lambda s: (s["elevation"] is None, s["elevation"] or 0))
    # Classificações
    systems = Counter()
    refs = Counter()
    classified = set()
    for rel in f.by_type("IfcRelAssociatesClassification"):
        ref = rel.RelatingClassification
        label = None
        if ref.is_a("IfcClassificationReference"):
            src = getattr(ref, "ReferencedSource", None)
            src_name = getattr(src, "Name", None) if src else None
            ident = getattr(ref, "Identification", None) if f.schema != "IFC2X3" else getattr(ref, "ItemReference", None)
            label = f"{ident or ''} {ref.Name or ''}".strip()
            systems[src_name or "(sem sistema)"] += len(rel.RelatedObjects)
        else:
            systems[getattr(ref, "Name", ref.is_a())] += len(rel.RelatedObjects)
        if label:
            refs[label] += len(rel.RelatedObjects)
        for o in rel.RelatedObjects:
            classified.add(o.id())
    out["classification_systems"] = dict(systems.most_common())
    out["classification_refs_top"] = dict(refs.most_common(15))
    out["classified_objects"] = len(classified)
    # Quantidades com unidade própria
    own_units = Counter()
    for q in f.by_type("IfcPhysicalSimpleQuantity"):
        if getattr(q, "Unit", None) is not None:
            own_units[q.is_a()] += 1
    out["quantities_with_own_unit"] = dict(own_units)
    out["direct_read_seconds"] = round(time.perf_counter() - t0, 2)
    return out


def db_analysis(conn: sqlite3.Connection, model_id: int, schema_name: str) -> dict:
    schema = None
    for candidate in (schema_name, "IFC4X3_ADD2", "IFC4X3_ADD1", "IFC4X3_TC1", "IFC4X3"):
        try:
            schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(candidate)
            break
        except Exception:
            continue
    by_type = Counter()
    by_storey = Counter()
    qto_sets = Counter()
    qto_names = defaultdict(Counter)
    physical_total = 0
    physical_with_qto = Counter()
    physical_without_qto = Counter()
    physical_without_qto_but_pset_dims = Counter()
    materials = Counter()
    elements_with_material = 0
    no_storey_physical = Counter()
    rows = conn.execute("SELECT ifc_type, storey_name, quantities_json, materials_json, properties_json "
                        "FROM ifc_elements WHERE model_id = ?", (model_id,))
    total = 0
    for ifc_type, storey, qjson, mjson, pjson in rows:
        total += 1
        by_type[ifc_type] += 1
        by_storey[storey or "(sem pavimento)"] += 1
        qtos = json.loads(qjson or "{}") or {}
        mats = json.loads(mjson or "[]") or []
        phys = is_physical(schema, ifc_type)
        for set_name, values in qtos.items():
            qto_sets[set_name] += 1
            for qn in values:
                if qn != "id":
                    qto_names[set_name][qn] += 1
        if mats:
            elements_with_material += 1
            for m in mats:
                materials[m] += 1
        if phys:
            physical_total += 1
            if not storey:
                no_storey_physical[ifc_type] += 1
            if qtos:
                physical_with_qto[ifc_type] += 1
            else:
                physical_without_qto[ifc_type] += 1
                psets = json.loads(pjson or "{}") or {}
                if any(k.lower() in ALT_QTY_NAMES for v in psets.values() if isinstance(v, dict) for k in v):
                    physical_without_qto_but_pset_dims[ifc_type] += 1
    return {
        "total_elements": total,
        "by_type": dict(by_type.most_common()),
        "by_storey": dict(by_storey.most_common()),
        "physical_elements": physical_total,
        "physical_with_qto": sum(physical_with_qto.values()),
        "physical_without_qto_by_type": dict(physical_without_qto.most_common()),
        "physical_without_qto_but_dimensions_in_psets": dict(physical_without_qto_but_pset_dims.most_common()),
        "physical_without_storey_by_type": dict(no_storey_physical.most_common()),
        "qto_sets": dict(qto_sets.most_common()),
        "qto_quantities": {k: dict(v.most_common(12)) for k, v in qto_names.items()},
        "elements_with_material": elements_with_material,
        "materials_top": dict(materials.most_common(20)),
        "distinct_materials": len(materials),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", default=os.path.join(os.environ.get("LOCALAPPDATA", ""), "BIM-SCHEDULE", "bim_schedule.db"))
    args = ap.parse_args()
    bench = json.loads(Path(args.bench).read_text(encoding="utf-8"))
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    report = []
    for rec in bench["results"]:
        entry = dict(rec)
        print("analisando", rec["filename"], flush=True)
        if rec.get("model_status") == "completed":
            entry["app_extraction"] = db_analysis(conn, rec["model_id"], rec["schema"])
        try:
            entry["direct"] = direct_analysis(rec["file"])
        except Exception as exc:
            entry["direct"] = {"error": str(exc)}
        report.append(entry)
        Path(args.out).write_text(json.dumps({"idle_service_rss_mb": bench.get("idle_service_rss_mb"), "models": report},
                                             ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
