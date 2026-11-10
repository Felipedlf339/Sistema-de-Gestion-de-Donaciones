from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from gestion_donaciones.modelos.enums import EstadoElegibilidad, GrupoSanguineo, FactorRh, CargoPersonal
from gestion_donaciones.modelos.donante import Donante
from gestion_donaciones.modelos.personalCentroDonacion import PersonalCentroDonacion

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Donante falso temporal
donante_mock = Donante(
    run="22267222-3",
    nombre="Pierluigi Cerulo",
    grupo_sanguineo=GrupoSanguineo.O,
    factor_rh=FactorRh.POSITIVO
)
donante_mock.estado_elegibilidad = EstadoElegibilidad.APTO
donante_mock.motivo = None

usuario_actual = PersonalCentroDonacion(
    run="77777777-7", 
    nombre="Gonzalito", 
    id_personal="P-001", 
    cargo=CargoPersonal.ATENCION_DONANTE # Cambiar para probar validación
)

class EstadoRequest(BaseModel):
    nuevo_estado: EstadoElegibilidad
    motivo:str | None = None

@router.get("/elegibilidad")
def mostrar_pantalla(request: Request):
    contexto = {
        "request": request, 
        "donante": {
            "run": donante_mock.run,
            "nombre": donante_mock.nombre,
            "estado": donante_mock.estado_elegibilidad.value
        },
        "usuario": usuario_actual
    }
    return templates.TemplateResponse(request=request, name="elegibilidad.html", context=contexto)

@router.post("/api/elegibilidad")
def actualizar_estado(datos: EstadoRequest):
    if usuario_actual.cargo != CargoPersonal.ATENCION_DONANTE:
        raise HTTPException(status_code=403, detail="Acceso denegado. Solo el Personal de atención al donante puede modificar la elegibilidad.")
    estado_actual_backend = donante_mock.estado_elegibilidad
    if datos.nuevo_estado != estado_actual_backend and not datos.motivo:
        raise HTTPException(status_code=400, detail="Debes ingresar el motivo para cambiar el estado del donante.")
    
    donante_mock.cambiar_elegibilidad(datos.nuevo_estado)
    if datos.nuevo_estado != estado_actual_backend:
        donante_mock.motivo = datos.motivo
    print(f"BACKEND: Nuevo Estado: {donante_mock.estado_elegibilidad.value} | Motivo: {donante_mock.motivo}")
    return {"mensaje": "Estado guardado con éxito", "estado_actual": donante_mock.estado_elegibilidad.value}
