"""Leitura IFC isolada do ciclo HTTP, com progresso persistido por lotes.

Executada dentro do processo de tarefa (``app.modules.ifc.jobs``). Os parâmetros
opcionais permitem informar progresso e verificar cancelamento cooperativo; sem
eles, o comportamento é o mesmo da versão anterior.
"""
import json
from typing import Callable, Optional

ProgressCallback = Callable[[float, str], None]
CancelCheck = Callable[[], None]

CANCEL_CHECK_EVERY = 25  # elementos entre verificações de cancelamento


def read_identity(ifc_file) -> tuple:
    """GlobalId do IfcProject e cabeçalho STEP (software de autoria, data, autor) do arquivo."""
    project_global_id = None
    try:
        projects = ifc_file.by_type("IfcProject")
        project_global_id = getattr(projects[0], "GlobalId", None) if projects else None
    except Exception:
        project_global_id = None
    header = {}
    try:
        file_name = ifc_file.header.file_name
        for key in ("name", "time_stamp", "author", "organization", "preprocessor_version",
                    "originating_system", "authorization"):
            value = getattr(file_name, key, None)
            if value not in (None, "", (), []):
                header[key] = list(value) if isinstance(value, (list, tuple)) else value
        description = getattr(ifc_file.header.file_description, "description", None)
        if description:
            header["description"] = list(description) if isinstance(description, (list, tuple)) else description
    except Exception:
        pass
    return project_global_id, json.dumps(header, ensure_ascii=False, default=str) if header else None


def parse_ifc_and_extract(filepath: str, model_id: int, db_session, *,
                          on_progress: Optional[ProgressCallback] = None,
                          check_cancel: Optional[CancelCheck] = None):
    def report(percent: float, message: str) -> None:
        if on_progress:
            on_progress(percent, message)

    def cancel_point() -> None:
        if check_cancel:
            check_cancel()

    try:
        import ifcopenshell
    except ImportError as exc:
        raise RuntimeError("IfcOpenShell não está instalado. Execute install.bat novamente.") from exc

    from app.models.ifc import IfcElementModel, IfcModelModel
    cancel_point()
    report(1, "Abrindo o arquivo IFC")
    ifc_file = ifcopenshell.open(filepath)
    cancel_point()
    schema_name = getattr(ifc_file, "schema", None)
    elements = ifc_file.by_type("IfcProduct")
    total = len(elements)
    model = db_session.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
    if model:
        model.status = "processing"; model.progress = 0
        model.processing_message = "Modelo aberto; iniciando leitura dos elementos"
        model.schema_name = schema_name
        model.ifc_project_global_id, model.header_json = read_identity(ifc_file)
        db_session.commit()

    try:
        from ifcopenshell.util.element import get_psets
    except Exception:
        get_psets = None
    try:
        from ifcopenshell.util.element import get_container
    except Exception:
        get_container = None
    try:
        from ifcopenshell.util.element import get_materials
    except Exception:
        get_materials = None

    db_session.query(IfcElementModel).filter(IfcElementModel.model_id == model_id).delete()
    # Confirma já a remoção: o progresso é gravado por outra conexão (JobContext) e o SQLite
    # admite um único escritor; manter esta transação aberta bloquearia essas gravações
    # ("database is locked"). Em falha ou cancelamento, os elementos do modelo são removidos
    # pela rotina de consistência, como nos lotes já confirmados.
    db_session.commit()
    batch = []; processed = 0; batch_size = 500
    report(5, f"Modelo aberto: {total} produtos IFC")
    for index, element in enumerate(elements, start=1):
        if index % CANCEL_CHECK_EVERY == 0:
            cancel_point()
            report(5 + index / max(total, 1) * 90, f"Lendo {index} de {total} produtos IFC")
        global_id = getattr(element, "GlobalId", None)
        if global_id:
            psets, qtos, materials, storey_name = {}, {}, [], None
            if get_psets:
                try: psets = get_psets(element, psets_only=True)
                except Exception: psets = {}
                try: qtos = get_psets(element, qtos_only=True)
                except Exception: qtos = {}
            if get_container:
                try:
                    container = get_container(element)
                    storey_name = getattr(container, "Name", None) if container else None
                except Exception: pass
            if get_materials:
                try:
                    materials = [getattr(material, "Name", None) or material.is_a() for material in get_materials(element)]
                except Exception: materials = []
            batch.append(IfcElementModel(
                model_id=model_id, global_id=global_id,
                name=getattr(element, "Name", None) or "Sem Nome",
                ifc_type=element.is_a(), description=getattr(element, "Description", None),
                object_type=getattr(element, "ObjectType", None),
                predefined_type=str(getattr(element, "PredefinedType", "") or "") or None,
                properties_json=json.dumps(psets, ensure_ascii=False, default=str),
                quantities_json=json.dumps(qtos, ensure_ascii=False, default=str),
                materials_json=json.dumps(materials, ensure_ascii=False, default=str),
                storey_name=storey_name,
            ))
        if len(batch) >= batch_size:
            db_session.bulk_save_objects(batch); processed += len(batch); batch.clear()
            model = db_session.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
            if model:
                model.element_count = processed
                model.progress = min(95, int(index / max(total, 1) * 95))
                model.processing_message = f"Lidos {index} de {total} produtos IFC"
            db_session.commit()
            report(5 + index / max(total, 1) * 90, f"Lidos {index} de {total} produtos IFC")
    cancel_point()
    if batch:
        db_session.bulk_save_objects(batch); processed += len(batch)
    model = db_session.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
    if model:
        model.schema_name = schema_name; model.element_count = processed
        model.progress = 100; model.status = "completed"
        model.processing_message = "Processamento concluído"; model.error_message = None
    db_session.commit()
    return {"schema": schema_name, "element_count": processed}
