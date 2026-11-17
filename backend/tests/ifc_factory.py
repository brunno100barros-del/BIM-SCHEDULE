"""Gera arquivos IFC4 reais (via IfcOpenShell) para os testes de processamento."""
from pathlib import Path

import ifcopenshell
import ifcopenshell.api


def build_ifc(path: Path, walls: int = 5, slabs: int = 1) -> Path:
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Projeto de teste")
    ifcopenshell.api.run("unit.assign_unit", model)
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Terreno")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Edifício")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Térreo")
    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[building], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[storey], relating_object=building)
    products = []
    for i in range(walls):
        products.append(ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall", name=f"Parede {i + 1:03d}"))
    for i in range(slabs):
        products.append(ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSlab", name=f"Laje {i + 1:03d}"))
    ifcopenshell.api.run("spatial.assign_container", model, products=products, relating_structure=storey)
    model.write(str(path))
    return path
