"""Gerador de cronograma por regras (sem IA).

EAP = nível (pavimento ou faixa de cota) × serviço. Para cada par com elementos:
quantidade = soma da medida-base do serviço; duração = ⌈quantidade ÷ produtividade⌉ dias
quando há produtividade cadastrada; caso contrário, a duração padrão do serviço, marcada como
**provisória**. Precedências padrão (término-início, sem defasagem):

* ``predecessors``: serviço predecessor no **mesmo nível**; se não existir nesse nível, o do nível
  anterior mais próximo; se não existir em nenhum nível anterior, o de qualquer nível (o mais baixo);
* ``after_previous_level``: serviço no **nível imediatamente anterior** (p.ex. pilares do nível N+1
  após a laje do nível N).

Relações que criariam ciclo são descartadas e informadas em ``warnings``.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Iterable

from app.modules.takeoff.catalog import QUANTITY_BASES, match_service, split_codes

NO_LEVEL = "__SEM_NIVEL__"


def _levels(rows: list[dict], mode: str, band_height: float) -> tuple[dict, list[dict], str]:
    """Atribui um nível a cada linha. Devolve (nível por índice da linha, níveis ordenados, modo efetivo)."""
    storey_keys = {r["storey_key"] for r in rows if r.get("storey_key")}
    effective = mode
    if mode == "auto":
        effective = "storey" if len(storey_keys) >= 2 else "elevation"
    assignment: dict[int, str] = {}
    info: dict[str, dict] = {}
    if effective == "storey":
        names: dict[str, dict] = defaultdict(lambda: defaultdict(int))
        for i, r in enumerate(rows):
            key = r.get("storey_key") or NO_LEVEL
            assignment[i] = key
            names[key][r.get("storey_name") or "Sem pavimento"] += 1
            lv = info.setdefault(key, {"key": key, "zs": [], "elevations": []})
            if r.get("z_min_m") is not None:
                lv["zs"].append(r["z_min_m"])
            if r.get("storey_elevation_m") is not None:
                lv["elevations"].append(r["storey_elevation_m"])
        for key, lv in info.items():
            lv["name"] = "Sem pavimento" if key == NO_LEVEL else max(names[key].items(), key=lambda kv: kv[1])[0]
            lv["elevation_m"] = min(lv["elevations"]) if lv["elevations"] else None
            lv["sort"] = (key == NO_LEVEL, statistics.median(lv["zs"]) if lv["zs"] else (lv["elevation_m"] or 0.0))
    else:
        h = max(0.5, float(band_height or 3.0))
        zs = [r["z_min_m"] for r in rows if r.get("z_min_m") is not None]
        z0 = min(zs) if zs else 0.0
        for i, r in enumerate(rows):
            z = r.get("z_min_m")
            if z is None:
                key = NO_LEVEL
                info.setdefault(key, {"key": key, "name": "Sem cota", "elevation_m": None, "sort": (True, 0.0)})
            else:
                idx = int(math.floor((z - z0) / h + 1e-9))
                key = f"FAIXA-{idx:03d}"
                lo, hi = z0 + idx * h, z0 + (idx + 1) * h
                info.setdefault(key, {"key": key, "name": f"Faixa {idx + 1} (cota {lo:+.2f} a {hi:+.2f} m)",
                                      "elevation_m": lo, "sort": (False, lo)})
            assignment[i] = key
    ordered = sorted(info.values(), key=lambda lv: lv["sort"])
    levels = []
    for order, lv in enumerate(ordered, 1):
        levels.append({"key": lv["key"], "name": lv["name"], "order": order, "elevation_m": lv.get("elevation_m"),
                       "element_count": sum(1 for k in assignment.values() if k == lv["key"])})
    return assignment, levels, effective


def build_proposal(rows: Iterable[dict], services: list[dict], *, level_mode: str = "auto",
                   band_height_m: float = 3.0) -> dict:
    rows = [r for r in rows if not r.get("excluded")]
    warnings: list[str] = []
    if not rows:
        return {"levels": [], "activities": [], "precedences": [], "unmapped": {}, "level_mode": level_mode,
                "warnings": ["Nenhum elemento quantificado. Calcule os quantitativos dos modelos primeiro."]}
    services = sorted([dict(s) for s in services if s.get("is_active", True)], key=lambda s: s["sequence"])
    by_code = {s["code"]: s for s in services}
    assignment, levels, effective = _levels(rows, level_mode, band_height_m)
    level_by_key = {lv["key"]: lv for lv in levels}

    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    unmapped: dict[str, int] = defaultdict(int)
    for i, r in enumerate(rows):
        svc = match_service(services, r["mapping_type"], r.get("material_class"))
        if svc is None:
            unmapped[r["mapping_type"]] += 1
            continue
        groups[(assignment[i], svc["code"])].append(i)

    activities = []
    for (level_key, code), idxs in groups.items():
        svc = by_code[code]
        lv = level_by_key[level_key]
        basis = svc["quantity_basis"]
        qtypes = set(split_codes(svc.get("quantity_ifc_types")))
        contributing = [rows[i] for i in idxs if not qtypes or rows[i]["mapping_type"] in qtypes or rows[i]["ifc_type"] in qtypes]
        if basis == "count":
            quantity = float(len(idxs))
            with_value = len(idxs)
            contributing_n = len(idxs)
        else:
            values = [r.get(basis) for r in contributing]
            quantity = float(sum(v for v in values if v))
            with_value = sum(1 for v in values if v)
            contributing_n = len(contributing)
        coverage = (with_value / contributing_n) if contributing_n else 0.0
        productivity = svc.get("productivity_per_day")
        provisional_reason = None
        if productivity and quantity > 0:
            duration = max(1.0, float(math.ceil(quantity / productivity)))
        else:
            duration = float(svc.get("default_duration_days") or 5.0)
            provisional_reason = "sem produtividade cadastrada" if not productivity else "sem quantidade calculada"
        if coverage < 0.999 and basis != "count" and provisional_reason is None:
            provisional_reason = f"quantidade parcial ({coverage:.0%} dos elementos com medida)"
        activities.append({
            "key": f"{level_key}|{code}", "level_key": level_key, "level_name": lv["name"], "level_order": lv["order"],
            "service_code": code, "service_name": svc["name"], "sequence": svc["sequence"],
            "code": f"{lv['order']:02d}-{code}", "name": f"{svc['name']} — {lv['name']}",
            "quantity": round(quantity, 3), "unit": QUANTITY_BASES.get(basis, basis), "quantity_basis": basis,
            "coverage": round(coverage, 4), "productivity": productivity, "duration": duration,
            "provisional": provisional_reason is not None, "provisional_reason": provisional_reason,
            "element_count": len(idxs), "include": bool(svc.get("include_by_default", True)),
            "element_global_ids": [rows[i]["global_id"] for i in idxs],
            "element_ids": [rows[i]["element_id"] for i in idxs if rows[i].get("element_id")],
        })
    activities.sort(key=lambda a: (a["level_order"], a["sequence"]))

    present = {(a["level_order"], a["service_code"]): a for a in activities}
    orders = sorted({lv["order"] for lv in levels})
    precedences: list[dict] = []
    edges: dict[str, set[str]] = defaultdict(set)  # pred -> succs

    def reachable(src: str, dst: str) -> bool:
        stack, seen = [src], set()
        while stack:
            n = stack.pop()
            if n == dst:
                return True
            if n in seen:
                continue
            seen.add(n)
            stack.extend(edges.get(n, ()))
        return False

    def add(pred: dict, succ: dict, rule: str) -> None:
        if pred["key"] == succ["key"] or succ["key"] in edges[pred["key"]]:
            return
        if reachable(succ["key"], pred["key"]):
            warnings.append(f"Relação {pred['code']} → {succ['code']} descartada (criaria ciclo).")
            return
        edges[pred["key"]].add(succ["key"])
        precedences.append({"pred_key": pred["key"], "succ_key": succ["key"], "relation_type": "FS", "lag": 0.0,
                            "rule": rule})

    def find_pred(order: int, code: str):
        if (order, code) in present:
            return present[(order, code)], "mesmo nível"
        for o in reversed([o for o in orders if o < order]):
            if (o, code) in present:
                return present[(o, code)], "nível anterior"
        for o in orders:
            if (o, code) in present:
                return present[(o, code)], "outro nível"
        return None, None

    for act in activities:
        svc = by_code[act["service_code"]]
        linked = False
        for code in split_codes(svc.get("predecessors")):
            pred, where = find_pred(act["level_order"], code)
            if pred is not None:
                add(pred, act, f"{code} → {act['service_code']} ({where})")
                linked = True
        prev_orders = [o for o in orders if o < act["level_order"]]
        if prev_orders:
            prev = prev_orders[-1]
            for code in split_codes(svc.get("after_previous_level")):
                if (prev, code) in present:
                    add(present[(prev, code)], act, f"{code} do nível anterior → {act['service_code']}")
                    linked = True
        act["has_predecessor"] = linked

    totals = defaultdict(float)
    for a in activities:
        totals[a["unit"]] += a["quantity"] if a["include"] else 0
    return {
        "level_mode": effective,
        "levels": levels,
        "activities": activities,
        "precedences": precedences,
        "unmapped": dict(unmapped),
        "warnings": warnings,
        "stats": {"elements": len(rows), "activities": len(activities),
                  "provisional": sum(1 for a in activities if a["provisional"]), "precedences": len(precedences)},
    }
