"""Cálculo de quantitativos por elemento a partir de um arquivo IFC.

Para cada medida (volume, área, comprimento, peso) usa a primeira fonte disponível, nesta ordem:

1. ``ifc_qto``: ``IfcElementQuantity`` (Qto_*/BaseQuantities) do próprio arquivo;
2. ``author_pset``: propriedade de Pset com **medida tipada** (IfcLengthMeasure, IfcAreaMeasure,
   IfcVolumeMeasure, IfcMassMeasure) e nome reconhecido; valores sem tipo de medida são ignorados,
   porque a unidade seria uma suposição;
3. ``geometry``: geometria calculada pelo IfcOpenShell (coordenadas locais do elemento):
   volume da malha; área = volume ÷ espessura nos elementos delgados (senão, metade da área
   superficial); comprimento = maior
   dimensão da caixa envolvente local; peso do aço = volume × 7850 kg/m³;
4. ``count``: 1 por elemento (sempre).

Todos os valores são gravados em SI (m, m², m³, kg), com o valor e a unidade de origem.

Elementos não quantificados (``excluded``): aberturas, elementos virtuais e de recorte, e
conjuntos (``IfcElementAssembly``, ``IfcCurtainWall``, ``IfcStair`` …) cujas peças são
quantificadas individualmente. As peças herdam o tipo do conjunto para as regras
(``mapping_type``), exceto em ``IfcElementAssembly`` (estrutura metálica), onde cada peça mantém o seu tipo.
"""
from __future__ import annotations

import math
import multiprocessing
import re
from typing import Callable, Optional

from app.modules.takeoff.catalog import (MAX_STEEL_SECTION_M2, STEEL_DENSITY_KG_M3, discipline_of, material_class,
                                         model_material_hint)

EXCLUDED_TYPES = {"IfcOpeningElement", "IfcOpeningStandardCase", "IfcVirtualElement", "IfcVoidingFeature",
                  "IfcProjectionElement", "IfcSurfaceFeature", "IfcEarthworksCut"}
KEEP_PART_TYPE_PARENTS = {"IfcElementAssembly"}

QTO_VOLUME = ("NetVolume", "GrossVolume", "Volume")
QTO_AREA = ("NetSideArea", "NetArea", "NetSurfaceArea", "NetFootprintArea", "GrossSideArea", "GrossArea",
            "GrossSurfaceArea", "GrossFootprintArea", "Area", "OuterSurfaceArea", "CrossSectionArea")
QTO_LENGTH = ("Length", "NetLength", "GrossLength", "Perimeter", "Height", "Depth")
QTO_WEIGHT = ("NetWeight", "GrossWeight", "Weight", "Mass")

PSET_NAMES = {
    "length": {"comprimento", "length", "comprimento total", "comprimento real", "lenght"},
    "area": {"area", "área", "area total", "área total", "superficie", "superfície"},
    "volume": {"volume", "volume total"},
    "weight": {"peso", "weight", "massa", "mass", "peso total"},
}
PSET_MEASURE = {
    "length": ("IfcLengthMeasure", "IfcPositiveLengthMeasure", "IfcNonNegativeLengthMeasure"),
    "area": ("IfcAreaMeasure",),
    "volume": ("IfcVolumeMeasure",),
    "weight": ("IfcMassMeasure",),
}
UNIT_TYPE = {"length": "LENGTHUNIT", "area": "AREAUNIT", "volume": "VOLUMEUNIT", "weight": "MASSUNIT"}
MEASURE_FIELD = {"volume": "volume_m3", "area": "area_m2", "length": "length_m", "weight": "weight_kg"}

ProgressCallback = Callable[[float, str], None]


def _norm_key(name: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).upper()


def _unit_scales(f) -> dict:
    import ifcopenshell.util.unit as uu

    scales = {}
    for kind, unit_type in UNIT_TYPE.items():
        try:
            scales[kind] = uu.calculate_unit_scale(f, unit_type)
        except Exception:
            scales[kind] = None
    # Massa sem unidade no projeto: o padrão IFC é o quilograma (fator 1 em relação ao kg).
    if not scales.get("weight"):
        scales["weight"] = 1.0
    return scales


def _unit_label(f, unit_type: str) -> str:
    import ifcopenshell.util.unit as uu

    try:
        unit = uu.get_project_unit(f, unit_type)
        return uu.get_full_unit_name(unit) if unit else "padrão SI"
    except Exception:
        return "desconhecida"


def _application(f) -> str:
    parts = []
    try:
        parts.append(str(f.header.file_name.originating_system or ""))
        parts.append(str(f.header.file_name.preprocessor_version or ""))
    except Exception:
        pass
    for app in f.by_type("IfcApplication"):
        parts.append(f"{app.ApplicationFullName or ''} {app.Version or ''}")
    return " | ".join(p for p in parts if p.strip())


def _parent_assembly(element):
    for rel in getattr(element, "Decomposes", None) or []:
        parent = rel.RelatingObject
        if parent.is_a("IfcElement"):
            return parent
    return None


def _container(element):
    import ifcopenshell.util.element as ue

    current = element
    for _ in range(10):
        container = ue.get_container(current)
        if container is not None:
            return container
        parent = ue.get_aggregate(current)
        if parent is None:
            return None
        current = parent
    return None


def _has_element_parts(element) -> bool:
    for rel in getattr(element, "IsDecomposedBy", None) or []:
        if any(o.is_a("IfcElement") for o in rel.RelatedObjects):
            return True
    return False


def _materials(element) -> list[str]:
    import ifcopenshell.util.element as ue

    try:
        return [getattr(m, "Name", None) or m.is_a() for m in ue.get_materials(element)]
    except Exception:
        return []


def _from_qto(element, scales) -> dict:
    found: dict = {}
    for rel in getattr(element, "IsDefinedBy", None) or []:
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        qset = rel.RelatingPropertyDefinition
        if not qset.is_a("IfcElementQuantity"):
            continue
        by_name = {q.Name: q for q in qset.Quantities or []}
        for kind, names, attr in (("volume", QTO_VOLUME, "VolumeValue"), ("area", QTO_AREA, "AreaValue"),
                                  ("length", QTO_LENGTH, "LengthValue"), ("weight", QTO_WEIGHT, "WeightValue")):
            if kind in found:
                continue
            for n in names:
                q = by_name.get(n)
                value = getattr(q, attr, None) if q is not None else None
                if value is None:
                    continue
                scale = scales.get(kind)
                unit = getattr(q, "Unit", None)
                if unit is not None:
                    try:
                        import ifcopenshell.util.unit as uu
                        scale = uu.get_unit_scale(unit) if hasattr(uu, "get_unit_scale") else scale
                    except Exception:
                        pass
                if scale is None:
                    continue
                found[kind] = (float(value) * scale, {"source": "ifc_qto", "method": f"{qset.Name}.{n}",
                                                       "original": float(value)})
                break
    return found


def _from_pset(element, scales) -> dict:
    found: dict = {}
    for rel in getattr(element, "IsDefinedBy", None) or []:
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pset = rel.RelatingPropertyDefinition
        if not pset.is_a("IfcPropertySet"):
            continue
        for prop in pset.HasProperties or []:
            if not prop.is_a("IfcPropertySingleValue") or prop.NominalValue is None:
                continue
            pname = (prop.Name or "").strip().lower()
            measure = prop.NominalValue.is_a()
            for kind, names in PSET_NAMES.items():
                if kind in found or pname not in names or measure not in PSET_MEASURE[kind]:
                    continue
                scale = scales.get(kind)
                if scale is None:
                    continue
                try:
                    value = float(prop.NominalValue.wrappedValue)
                except (TypeError, ValueError):
                    continue
                found[kind] = (value * scale, {"source": "author_pset", "method": f"{pset.Name}.{prop.Name} ({measure})",
                                               "original": value})
    return found


def compute_takeoff(path: str, *, on_progress: Optional[ProgressCallback] = None,
                    check_cancel: Optional[Callable[[], None]] = None, threads: Optional[int] = None) -> dict:
    """Lê o IFC e devolve ``{"rows": [...], "summary": {...}}`` (uma linha por elemento ``IfcElement``)."""
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.shape as us
    import numpy as np

    def report(p, m):
        if on_progress:
            on_progress(p, m)

    def cancel_point():
        if check_cancel:
            check_cancel()

    report(1, "Abrindo o arquivo IFC")
    f = ifcopenshell.open(path)
    cancel_point()
    scales = _unit_scales(f)
    application = _application(f)
    model_hint = model_material_hint(application)
    length_scale = scales.get("length") or 1.0

    storeys = {}
    for s in f.by_type("IfcBuildingStorey"):
        elev = getattr(s, "Elevation", None)
        storeys[s.id()] = (s.Name or "Sem nome", float(elev) * length_scale if elev is not None else None)

    elements = f.by_type("IfcElement")
    total = len(elements)
    rows: dict[int, dict] = {}
    to_geometry = []
    report(5, f"Classificando {total} elementos")
    for i, el in enumerate(elements, 1):
        if i % 500 == 0:
            cancel_point()
            report(5 + 15 * i / max(total, 1), f"Classificando {i} de {total} elementos")
        ifc_type = el.is_a()
        excluded_reason = None
        if ifc_type in EXCLUDED_TYPES or el.is_a("IfcFeatureElement") or el.is_a("IfcVirtualElement"):
            excluded_reason = "abertura/elemento virtual"
        elif _has_element_parts(el):
            excluded_reason = "conjunto (quantificado pelas peças)"
        parent = _parent_assembly(el)
        mapping_type = ifc_type
        if parent is not None and not parent.is_a("IfcElementAssembly"):
            mapping_type = parent.is_a()
        container = _container(el)
        storey_name, storey_elev = (None, None)
        if container is not None and container.id() in storeys:
            storey_name, storey_elev = storeys[container.id()]
        elif container is not None:
            storey_name = getattr(container, "Name", None)
        mats = _materials(el) or (_materials(parent) if parent is not None else [])
        row = {
            "global_id": el.GlobalId, "ifc_type": ifc_type, "mapping_type": mapping_type,
            "predefined_type": str(getattr(el, "PredefinedType", "") or "") or None,
            "name": (el.Name or None), "storey_name": storey_name, "storey_key": _norm_key(storey_name) or None,
            "storey_elevation_m": storey_elev, "z_min_m": None, "z_max_m": None,
            "discipline": discipline_of(mapping_type), "material": ", ".join(m for m in mats if m)[:255] or None,
            "material_class": material_class(mats, model_hint), "volume_m3": None, "area_m2": None, "length_m": None,
            "weight_kg": None, "count": 1.0, "geometry_ok": False, "excluded": excluded_reason is not None,
            "excluded_reason": excluded_reason, "sources": {"count": {"source": "count", "method": "1 por elemento"}},
        }
        if not row["excluded"]:
            for kind, (value, meta) in {**_from_pset(el, scales), **_from_qto(el, scales)}.items():
                row[MEASURE_FIELD[kind]] = value
                row["sources"][kind] = meta
            if getattr(el, "Representation", None) is not None:
                to_geometry.append(el)
        rows[el.id()] = row

    # Geometria (paralela, em threads do IfcOpenShell).
    done = 0
    geom_total = len(to_geometry)
    if geom_total:
        settings = ifcopenshell.geom.settings()
        it = ifcopenshell.geom.iterator(settings, f, threads or max(1, multiprocessing.cpu_count() - 1), include=to_geometry)
        report(20, f"Calculando geometria de {geom_total} elementos")
        if it.initialize():
            while True:
                shape = it.get()
                row = rows.get(shape.id)
                if row is not None:
                    try:
                        geometry = shape.geometry
                        verts = us.get_vertices(geometry)
                        if len(verts):
                            local_min, local_max = verts.min(axis=0), verts.max(axis=0)
                            dims = local_max - local_min
                            matrix = us.get_shape_matrix(shape)
                            world = np.c_[verts, np.ones(len(verts))] @ matrix.T
                            row["z_min_m"] = float(world[:, 2].min())
                            row["z_max_m"] = float(world[:, 2].max())
                            volume = abs(float(us.get_volume(geometry)))
                            sdims = sorted(float(d) for d in dims)
                            if volume > 0 and sdims[0] > 1e-6 and sdims[0] < 0.25 * sdims[1]:
                                area = volume / sdims[0]  # elemento delgado: volume ÷ espessura
                                area_method = "volume ÷ espessura (menor dimensão local)"
                            else:
                                area = float(us.get_area(geometry)) / 2.0
                                area_method = "metade da área superficial"
                            length = float(dims.max())
                            geo = {"volume": volume, "area": area, "length": length}
                            methods = {"volume": "volume da malha", "area": area_method,
                                       "length": "maior dimensão da caixa local"}
                            for kind, value in geo.items():
                                field = MEASURE_FIELD[kind]
                                if row[field] is None and math.isfinite(value) and value > 0:
                                    row[field] = value
                                    row["sources"][kind] = {"source": "geometry", "method": methods[kind]}
                            row["geometry_ok"] = True
                    except Exception:
                        pass
                done += 1
                if done % 200 == 0:
                    cancel_point()
                    report(20 + 75 * done / geom_total, f"Geometria: {done} de {geom_total} elementos")
                if not it.next():
                    break

    # Peso do aço a partir do volume, quando não veio de Qto/Pset.
    for row in rows.values():
        if row["weight_kg"] is None and row["material_class"] == "steel" and row["volume_m3"]:
            section = row["volume_m3"] / row["length_m"] if row["length_m"] else 0.0
            if section > MAX_STEEL_SECTION_M2:
                row["sources"]["weight"] = {"source": "none", "method": (
                    f"peso não estimado: seção maciça suspeita ({section:.3f} m² = volume ÷ comprimento)")}
                continue
            row["weight_kg"] = row["volume_m3"] * STEEL_DENSITY_KG_M3
            src = row["sources"].get("volume", {}).get("source", "?")
            row["sources"]["weight"] = {"source": src, "method": f"volume ({src}) × {STEEL_DENSITY_KG_M3:.0f} kg/m³"}

    out = list(rows.values())
    included = [r for r in out if not r["excluded"]]
    by_source: dict[str, dict[str, int]] = {}
    for r in included:
        for kind, meta in r["sources"].items():
            by_source.setdefault(kind, {}).setdefault(meta["source"], 0)
            by_source[kind][meta["source"]] += 1
    summary = {
        "application": application,
        "schema": f.schema,
        "units": {k: _unit_label(f, v) for k, v in UNIT_TYPE.items()},
        "unit_scales_to_si": scales,
        "elements": len(out),
        "included": len(included),
        "excluded": len(out) - len(included),
        "with_geometry": sum(1 for r in included if r["geometry_ok"]),
        "geometry_attempted": geom_total,
        "sources_by_measure": by_source,
        "material_hint": model_hint,
        "storeys": sorted({(r["storey_name"], r["storey_elevation_m"]) for r in out if r["storey_name"]},
                          key=lambda s: (s[1] is None, s[1] or 0)),
    }
    report(98, "Quantitativos calculados")
    return {"rows": out, "summary": summary}
