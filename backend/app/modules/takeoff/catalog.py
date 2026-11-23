"""Catálogo padrão de serviços e regras de classificação de elementos IFC.

Regras explícitas e editáveis (copiadas para cada projeto na primeira utilização). As
produtividades começam **vazias**: o BIM SCHEDULE não inventa índices. Sem produtividade, a
duração usada é a padrão do serviço e a atividade fica marcada como **provisória**.
"""
from __future__ import annotations

import re

QUANTITY_BASES = {
    "volume_m3": "m³",
    "area_m2": "m²",
    "length_m": "m",
    "weight_kg": "kg",
    "count": "un",
}

STEEL_DENSITY_KG_M3 = 7850.0

# code, name, discipline, sequence, basis, ifc_types, quantity_ifc_types, material_class, preds, after_prev, include
DEFAULT_SERVICES: list[dict] = [
    dict(code="FUND", name="Fundações", discipline="estrutura", sequence=10, quantity_basis="volume_m3",
         ifc_types="IfcFooting,IfcPile,IfcDeepFoundation,IfcCaissonFoundation"),
    dict(code="PIL", name="Pilares de concreto", discipline="estrutura", sequence=20, quantity_basis="volume_m3",
         ifc_types="IfcColumn", material_class="not_steel", predecessors="FUND", after_previous_level="LAJ,VIG"),
    dict(code="VIG", name="Vigas de concreto", discipline="estrutura", sequence=30, quantity_basis="volume_m3",
         ifc_types="IfcBeam", material_class="not_steel", predecessors="PIL", after_previous_level="LAJ"),
    dict(code="LAJ", name="Lajes e pisos", discipline="estrutura", sequence=40, quantity_basis="area_m2",
         ifc_types="IfcSlab", predecessors="VIG,PIL"),
    dict(code="EMET", name="Estrutura metálica (perfis e chapas)", discipline="estrutura", sequence=25,
         quantity_basis="weight_kg", ifc_types="IfcBeam,IfcColumn,IfcMember,IfcPlate", material_class="steel",
         predecessors="FUND", after_previous_level="EMET"),
    dict(code="LIG", name="Ligações metálicas (parafusos e fixadores)", discipline="estrutura", sequence=27,
         quantity_basis="count", ifc_types="IfcMechanicalFastener,IfcFastener", predecessors="EMET"),
    dict(code="ESC", name="Escadas e rampas", discipline="estrutura", sequence=45, quantity_basis="volume_m3",
         ifc_types="IfcStair,IfcStairFlight,IfcRamp,IfcRampFlight", predecessors="LAJ"),
    dict(code="COB", name="Cobertura", discipline="arquitetura", sequence=48, quantity_basis="area_m2",
         ifc_types="IfcRoof", predecessors="LAJ,EMET"),
    dict(code="ALV", name="Alvenaria e vedações", discipline="arquitetura", sequence=50, quantity_basis="area_m2",
         ifc_types="IfcWall,IfcWallStandardCase,IfcWallElementedCase", predecessors="LAJ,EMET"),
    dict(code="FACH", name="Fachada e pele de vidro", discipline="arquitetura", sequence=55, quantity_basis="area_m2",
         ifc_types="IfcCurtainWall", predecessors="ALV,EMET"),
    dict(code="HID", name="Instalações hidrossanitárias", discipline="hidraulica", sequence=60, quantity_basis="length_m",
         ifc_types="IfcPipeSegment,IfcPipeFitting,IfcValve,IfcFlowSegment,IfcFlowFitting,IfcFlowController,IfcPump,"
                   "IfcTank,IfcFlowStorageDevice,IfcFlowMovingDevice,IfcDistributionFlowElement",
         quantity_ifc_types="IfcPipeSegment,IfcFlowSegment", predecessors="ALV"),
    dict(code="ELE", name="Instalações elétricas e iluminação", discipline="eletrica", sequence=62, quantity_basis="count",
         ifc_types="IfcLightFixture,IfcLamp,IfcCableSegment,IfcCableCarrierSegment,IfcCableFitting,IfcCableCarrierFitting,"
                   "IfcOutlet,IfcSwitchingDevice,IfcElectricDistributionBoard,IfcElectricAppliance,IfcJunctionBox,"
                   "IfcProtectiveDevice,IfcFlowTerminal",
         predecessors="ALV"),
    dict(code="ESQ", name="Esquadrias (portas e janelas)", discipline="arquitetura", sequence=65, quantity_basis="count",
         ifc_types="IfcDoor,IfcWindow", predecessors="ALV"),
    dict(code="REV", name="Revestimentos, pisos e forros", discipline="arquitetura", sequence=70, quantity_basis="area_m2",
         ifc_types="IfcCovering", predecessors="HID,ELE,ALV"),
    dict(code="LOU", name="Louças, metais e aparelhos", discipline="hidraulica", sequence=75, quantity_basis="count",
         ifc_types="IfcSanitaryTerminal,IfcWasteTerminal,IfcFireSuppressionTerminal", predecessors="REV,HID"),
    dict(code="GC", name="Guarda-corpos e corrimãos", discipline="arquitetura", sequence=78, quantity_basis="length_m",
         ifc_types="IfcRailing", predecessors="REV,ESC"),
    dict(code="MOB", name="Mobiliário e equipamentos", discipline="arquitetura", sequence=80, quantity_basis="count",
         ifc_types="IfcFurnishingElement,IfcFurniture,IfcSystemFurnitureElement", predecessors="REV"),
    dict(code="OUT", name="Outros elementos (a classificar)", discipline="outros", sequence=90, quantity_basis="count",
         ifc_types="*", predecessors="ALV,EMET", include_by_default=False),
]

STEEL_RE = re.compile(r"(\ba[- ]?36\b|\ba[- ]?572|\ba[- ]?992|\bs[- ]?235|\bs[- ]?275|\bs[- ]?355|\bq[- ]?235|astm|\ba[çc]o\b|steel|\bgr[- ]?50|\bcf-?\d|\bsae ?10\d\d|\bar[- ]?350)", re.I)
# Seção acima disso (≈ 470 kg/m) não é perfil usual: o sólido provavelmente não representa a peça de aço.
MAX_STEEL_SECTION_M2 = 0.06
CONCRETE_RE = re.compile(r"(concreto|concrete|\bc ?[1-9]\d\b|\bfck)", re.I)
STEEL_SOFTWARE_RE = re.compile(r"(advance steel|tekla|steelx|steel ?x|sds/2|pasb|plugin advance steel)", re.I)
CONCRETE_SOFTWARE_RE = re.compile(r"(eberick|tqs|cypecad)", re.I)

DISCIPLINE_BY_TYPE = {}
for _svc in DEFAULT_SERVICES:
    for _t in _svc["ifc_types"].split(","):
        if _t and _t != "*":
            DISCIPLINE_BY_TYPE.setdefault(_t.strip(), _svc["discipline"])


def split_codes(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def material_class(materials: list[str], model_hint: str | None) -> str | None:
    text = " | ".join(m for m in materials if m)
    if text and STEEL_RE.search(text):
        return "steel"
    if text and CONCRETE_RE.search(text):
        return "concrete"
    return model_hint


def model_material_hint(application: str) -> str | None:
    if STEEL_SOFTWARE_RE.search(application or ""):
        return "steel"
    if CONCRETE_SOFTWARE_RE.search(application or ""):
        return "concrete"
    return None


def discipline_of(ifc_type: str) -> str:
    return DISCIPLINE_BY_TYPE.get(ifc_type, "outros")


def service_matches(service: dict, mapping_type: str, mat_class: str | None) -> bool:
    types = split_codes(service.get("ifc_types"))
    if mapping_type not in types:
        return False
    wanted = service.get("material_class")
    if wanted == "steel":
        return mat_class == "steel"
    if wanted == "not_steel":
        return mat_class != "steel"
    return True


def match_service(services: list[dict], mapping_type: str, mat_class: str | None) -> dict | None:
    """Primeiro serviço ativo (por sequência) cuja regra aceita o elemento; ``*`` é o último recurso."""
    active = [s for s in services if s.get("is_active", True)]
    for s in sorted(active, key=lambda s: s["sequence"]):
        if service_matches(s, mapping_type, mat_class):
            return s
    for s in active:
        if "*" in split_codes(s.get("ifc_types")):
            return s
    return None
