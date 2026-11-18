"""Catálogo de tipos de tarefa.

As funções são referenciadas por caminho de importação (``modulo:funcao``) para
que o processo filho, iniciado com ``spawn`` (padrão no Windows), consiga
localizá-las sem depender de objetos herdados do processo principal.

Cada tipo pode declarar um ``abort_hook``, executado no processo principal quando
o processo da tarefa termina sem finalizar o próprio estado (encerramento
forçado ou falha inesperada), para manter os dados de domínio consistentes.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class JobKind:
    name: str
    target: str
    abort_hook: Optional[str] = None
    description: str = ""


JOB_KINDS: dict[str, JobKind] = {
    "ifc.parse": JobKind(
        name="ifc.parse",
        target="app.modules.ifc.jobs:parse_ifc_job",
        abort_hook="app.modules.ifc.jobs:on_parse_aborted",
        description="Leitura de um arquivo IFC e extração de elementos, propriedades e quantitativos.",
    ),
    "ifc.delete_revision": JobKind(
        name="ifc.delete_revision",
        target="app.modules.ifc.jobs:delete_revision_job",
        abort_hook="app.modules.ifc.jobs:on_delete_aborted",
        description="Remoção de uma revisão IFC: vínculos, elementos (em lotes) e arquivo.",
    ),
    "system.diagnostic": JobKind(
        name="system.diagnostic",
        target="app.jobs.diagnostic:diagnostic_job",
        abort_hook="app.jobs.diagnostic:on_diagnostic_aborted",
        description="Tarefa de diagnóstico usada nos testes do mecanismo de tarefas.",
    ),
}


def resolve(path: str) -> Callable:
    module_name, _, attr = path.partition(":")
    return getattr(importlib.import_module(module_name), attr)


def get_kind(name: str) -> JobKind:
    try:
        return JOB_KINDS[name]
    except KeyError as exc:
        raise ValueError(f"Tipo de tarefa desconhecido: {name}") from exc
