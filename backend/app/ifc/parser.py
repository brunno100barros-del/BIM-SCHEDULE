import ifcopenshell
import os

def parse_ifc_and_extract(filepath: str, model_id: int, db_session):
    from app.models.ifc import IfcElementModel
    try:
        ifc_file = ifcopenshell.open(filepath)
        elements = ifc_file.by_type("IfcBuildingElement")
        
        records = []
        for el in elements:
            global_id = el.GlobalId
            name = el.Name if el.Name else "Sem Nome"
            ifc_type = el.is_a()
            
            records.append(IfcElementModel(
                model_id=model_id,
                global_id=global_id,
                name=name,
                ifc_type=ifc_type,
                description=getattr(el, "Description", None)
            ))
        
        db_session.bulk_save_objects(records)
        db_session.commit()
        return True
    except Exception as e:
        print(f"Erro ao processar IFC: {e}")
        db_session.rollback()
        return False
