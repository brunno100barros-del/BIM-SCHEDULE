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


def build_building_ifc(path: Path, levels: int = 2) -> Path:
    """Edifício pequeno COM geometria (unidades em metros) para quantitativos e gerador.

    Por pavimento: 4 pilares 0,30×0,30×3,00 m, 2 vigas 0,20×0,50×5,00 m, 1 laje 5×5×0,20 m,
    2 paredes 5,00×3,00×0,20 m e 1 porta. No primeiro pavimento, 4 sapatas 1,00×1,00×0,50 m.
    Material "Concreto C30" na estrutura. Sem IfcElementQuantity (como nos modelos reais).
    """
    import numpy as np
    import ifcopenshell.util.unit  # noqa: F401

    run = ifcopenshell.api.run
    model = run("project.create_file", version="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="Edifício de teste")
    length = run("unit.add_si_unit", model, unit_type="LENGTHUNIT")
    area = run("unit.add_si_unit", model, unit_type="AREAUNIT")
    volume = run("unit.add_si_unit", model, unit_type="VOLUMEUNIT")
    run("unit.assign_unit", model, units=[length, area, volume])
    ctx = run("context.add_context", model, context_type="Model")
    body = run("context.add_context", model, context_type="Model", context_identifier="Body",
               target_view="MODEL_VIEW", parent=ctx)
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Terreno")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="Edifício")
    run("aggregate.assign_object", model, products=[site], relating_object=project)
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    concrete = run("material.add_material", model, name="Concreto C30")

    def place(product, x=0.0, y=0.0, z=0.0, rot_z=False):
        m = np.eye(4)
        if rot_z:
            m[:3, :3] = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
        m[:3, 3] = (x, y, z)
        run("geometry.edit_object_placement", model, product=product, matrix=m, is_si=True)

    def extruded(product, xdim, ydim, depth):
        profile = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=xdim, YDim=ydim)
        rep = run("geometry.add_profile_representation", model, context=body, profile=profile, depth=depth)
        run("geometry.assign_representation", model, product=product, representation=rep)

    for lv in range(levels):
        z = 3.0 * lv
        storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name=f"Pavimento {lv + 1}")
        storey.Elevation = z
        run("aggregate.assign_object", model, products=[storey], relating_object=building)
        products, structure = [], []
        if lv == 0:
            for i, (x, y) in enumerate([(0, 0), (5, 0), (0, 5), (5, 5)]):
                f = run("root.create_entity", model, ifc_class="IfcFooting", name=f"Sapata {i + 1}")
                extruded(f, 1.0, 1.0, 0.5)
                place(f, x, y, z - 0.5)
                products.append(f); structure.append(f)
        for i, (x, y) in enumerate([(0, 0), (5, 0), (0, 5), (5, 5)]):
            c = run("root.create_entity", model, ifc_class="IfcColumn", name=f"P{lv + 1}{i + 1}")
            extruded(c, 0.3, 0.3, 3.0)
            place(c, x, y, z)
            products.append(c); structure.append(c)
        for i in range(2):
            b = run("root.create_entity", model, ifc_class="IfcBeam", name=f"V{lv + 1}{i + 1}")
            extruded(b, 0.2, 0.5, 5.0)
            m = np.eye(4)
            m[:3, :3] = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])  # eixo de extrusão ao longo de X
            m[:3, 3] = (0.0, 5.0 * i, z + 2.75)
            run("geometry.edit_object_placement", model, product=b, matrix=m, is_si=True)
            products.append(b); structure.append(b)
        s = run("root.create_entity", model, ifc_class="IfcSlab", name=f"Laje {lv + 1}")
        extruded(s, 5.0, 5.0, 0.2)
        place(s, 2.5, 2.5, z + 3.0)
        products.append(s); structure.append(s)
        for i in range(2):
            w = run("root.create_entity", model, ifc_class="IfcWall", name=f"Parede {lv + 1}{i + 1}")
            extruded(w, 5.0, 0.2, 3.0)
            place(w, 2.5, 5.0 * i, z)
            products.append(w)
        d = run("root.create_entity", model, ifc_class="IfcDoor", name=f"Porta {lv + 1}")
        products.append(d)
        run("spatial.assign_container", model, products=products, relating_structure=storey)
        run("material.assign_material", model, products=structure, material=concrete)
    model.write(str(path))
    return path
