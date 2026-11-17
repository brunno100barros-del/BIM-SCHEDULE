"""CPM com relações generalizadas (FS, SS, FF e SF).

As atividades são calculadas em unidades de tempo relativas ao início do projeto.
Todas as restrições são preservadas, inclusive relações múltiplas entre o mesmo par.
"""
from __future__ import annotations

import math
from typing import Any, Iterable
import networkx as nx

_EPS = 1e-8
_RELATIONS = {"FS", "SS", "FF", "SF"}


def _value(obj: Any, key: str, default: Any = None) -> Any:
    return getattr(obj, key, default) if not isinstance(obj, dict) else obj.get(key, default)


def analyze_cpm(
    activities: Iterable[Any],
    precedences: Iterable[Any],
    project_deadline: float | None = None,
    project_start: float = 0.0,
) -> dict[str, Any]:
    """Calcula datas cedo/tarde, folgas e viabilidade do prazo.

    Para cada relação i -> j, a restrição é ES_j >= ES_i + W_ij.
    O forward pass respeita ES >= project_start para todas as atividades.
    O prazo é um limite rígido; se impossível, os floats ficam negativos.
    """
    activity_list = list(activities)
    precedence_list = list(precedences)
    if not math.isfinite(float(project_start)):
        raise ValueError("O início do projeto precisa ser um número finito.")
    if project_deadline is not None and not math.isfinite(float(project_deadline)):
        raise ValueError("O prazo do projeto precisa ser um número finito.")

    durations: dict[Any, float] = {}
    for activity in activity_list:
        aid = _value(activity, "id")
        if aid is None:
            raise ValueError("Toda atividade precisa possuir um identificador.")
        if aid in durations:
            raise ValueError(f"Identificador de atividade duplicado: {aid}")
        duration = float(_value(activity, "duration", 0.0))
        if not math.isfinite(duration) or duration < 0:
            raise ValueError(f"Duração inválida para a atividade {aid}.")
        durations[aid] = duration

    graph = nx.DiGraph()
    graph.add_nodes_from(durations)
    constraints: list[dict[str, Any]] = []

    for index, relation in enumerate(precedence_list):
        pid = _value(relation, "predecessor_id")
        sid = _value(relation, "successor_id")
        rtype = str(_value(relation, "relation_type", "FS")).upper()
        lag = float(_value(relation, "lag", 0.0))
        if pid not in durations or sid not in durations:
            raise ValueError(f"Precedência {index + 1} referencia atividade inexistente.")
        if pid == sid:
            raise ValueError("Uma atividade não pode ser predecessora de si mesma.")
        if rtype not in _RELATIONS:
            raise ValueError(f"Tipo de relação inválido: {rtype}. Use FS, SS, FF ou SF.")
        if not math.isfinite(lag):
            raise ValueError("O lag precisa ser um número finito.")
        di, dj = durations[pid], durations[sid]
        weight = {
            "FS": di + lag,
            "SS": lag,
            "FF": di + lag - dj,
            "SF": lag - dj,
        }[rtype]
        constraints.append({
            "predecessor_id": pid,
            "successor_id": sid,
            "relation_type": rtype,
            "lag": lag,
            "weight": weight,
        })
        # Grafo simples é usado apenas para ordenação topológica.
        # Todas as restrições originais permanecem na lista constraints.
        graph.add_edge(pid, sid)

    try:
        order = list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible as exc:
        raise ValueError("Ciclo detectado na rede de precedências do CPM.") from exc

    incoming: dict[Any, list[dict[str, Any]]] = {aid: [] for aid in durations}
    outgoing: dict[Any, list[dict[str, Any]]] = {aid: [] for aid in durations}
    for constraint in constraints:
        incoming[constraint["successor_id"]].append(constraint)
        outgoing[constraint["predecessor_id"]].append(constraint)

    es: dict[Any, float] = {}
    ef: dict[Any, float] = {}
    for aid in order:
        lower_bounds = [float(project_start)]
        lower_bounds.extend(
            es[c["predecessor_id"]] + c["weight"] for c in incoming[aid]
        )
        es[aid] = max(lower_bounds)
        ef[aid] = es[aid] + durations[aid]

    project_finish = max(ef.values(), default=float(project_start))
    effective_deadline = float(project_deadline) if project_deadline is not None else project_finish

    ls: dict[Any, float] = {}
    lf: dict[Any, float] = {}
    for aid in reversed(order):
        upper_bounds = [effective_deadline - durations[aid]]
        upper_bounds.extend(
            ls[c["successor_id"]] - c["weight"] for c in outgoing[aid]
        )
        ls[aid] = min(upper_bounds)
        lf[aid] = ls[aid] + durations[aid]

    results: dict[Any, dict[str, Any]] = {}
    for aid in order:
        total_float = ls[aid] - es[aid]
        relation_floats: list[float] = []
        for c in outgoing[aid]:
            sid = c["successor_id"]
            relation_floats.append(es[sid] - (es[aid] + c["weight"]))
        free_float = min(relation_floats) if relation_floats else effective_deadline - ef[aid]
        results[aid] = {
            "id": aid,
            "es": es[aid], "ef": ef[aid],
            "ls": ls[aid], "lf": lf[aid],
            "tf": total_float, "ff": free_float,
            # Folga negativa também representa atividade crítica/impactada.
            "is_critical": int(total_float <= _EPS),
        }

    deadline_feasible = project_deadline is None or project_finish <= effective_deadline + _EPS
    return {
        "activities": results,
        "project_start": float(project_start),
        "project_finish": project_finish,
        "project_deadline": project_deadline,
        "deadline_feasible": deadline_feasible,
        "deadline_variance": (effective_deadline - project_finish) if project_deadline is not None else 0.0,
        "duration": project_finish - float(project_start),
        "constraints_count": len(constraints),
    }


def calculate_cpm(activities, precedences, project_deadline=None, project_start=0.0):
    """Compatibilidade com a API anterior: retorna somente o mapa de atividades."""
    return analyze_cpm(activities, precedences, project_deadline, project_start)["activities"]
