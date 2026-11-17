"""Leitura IFC isolada do ciclo HTTP, com progresso persistido por lotes."""
import json


def parse_ifc_and_extract(filepath: str, model_id: int, db_session):
    try:
        import ifcopenshell
    except ImportError as exc:
        raise RuntimeError("IfcOpenShell não está instalado. Execute install.bat novamente.") from exc

    from app.models.ifc import IfcElementModel, IfcModelModel
    ifc_file = ifcopenshell.open(filepath)
    schema_name = getattr(ifc_file, "schema", None)
    elements = ifc_file.by_type("IfcProduct")
    total = len(elements)
    model = db_session.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
    if model:
        model.status = "processing"; model.progress = 0
        model.processing_message = "Modelo aberto; iniciando leitura dos elementos"
        model.schema_name = schema_name; db_session.commit()

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
    batch = []; processed = 0; batch_size = 500
    for index, element in enumerate(elements, start=1):
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
    if batch:
        db_session.bulk_save_objects(batch); processed += len(batch)
    model = db_session.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
    if model:
        model.schema_name = schema_name; model.element_count = processed
        model.progress = 100; model.status = "completed"
        model.processing_message = "Processamento concluído"; model.error_message = None
    db_session.commit()
    return {"schema": schema_name, "element_count": processed}
