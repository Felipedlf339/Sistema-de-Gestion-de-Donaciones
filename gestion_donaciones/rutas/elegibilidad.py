from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from gestion_donaciones.modelos.enums import EstadoElegibilidad, GrupoSanguineo, FactorRh, CargoPersonal
from gestion_donaciones.modelos.donante import Donante
from gestion_donaciones.modelos.personalCentroDonacion import PersonalCentroDonacion
from gestion_donaciones.registro_donantes import RegistroDonantes

router = APIRouter()
templates = Jinja2Templates(directory="templates")

registro = RegistroDonantes()

# Mock de sesion
usuario_actual = PersonalCentroDonacion(
    run="77777777-7", 
    nombre="Gustavo", 
    id_personal="P-001", 
    cargo=CargoPersonal.ATENCION_DONANTE # Cambiar para probar validación
)

def obtener_o_crear_donante_prueba() -> Donante:
    run_prueba = "12345678-5"
    donante = registro.buscar_por_run(run_prueba)

    if donante is None:
        nuevo_donante = Donante(
            run=run_prueba,
            nombre="Francisca Hidalgo",
            grupo_sanguineo=GrupoSanguineo.O,
            factor_rh=FactorRh.POSITIVO,
            correo="fran.hidalgo@correo.cl",
            telefono="+56912345678",
        )
        nuevo_donante.estado_elegibilidad = EstadoElegibilidad.APTO
        errores = registro.registrar(nuevo_donante)
        if errores:
            raise HTTPException(status_code=500, detail=f"No se pudo crear el donante de prueba: {errores}")
        donante = registro.buscar_por_run(run_prueba)

    return donante


class EstadoRequest(BaseModel):
    nuevo_estado: EstadoElegibilidad
    motivo:str | None = None

@router.get("/elegibilidad")
def mostrar_pantalla(request: Request):
    donante_actual = obtener_o_crear_donante_prueba()
    return templates.TemplateResponse(
        request=request,
        name="elegibilidad.html",
        context={
            "donante": donante_actual,
            "usuario": usuario_actual,
        },
    )

@router.post("/api/elegibilidad")
def actualizar_estado(datos: EstadoRequest):
    if usuario_actual.cargo != CargoPersonal.ATENCION_DONANTE:
        raise HTTPException(status_code=403, detail="Acceso denegado. Solo el Personal de atención al donante puede modificar la elegibilidad.")

    motivo_final = (datos.motivo or "").strip()
    if not motivo_final:
        raise HTTPException(status_code=400, detail="Debes ingresar el motivo para cambiar el estado del donante.")

    # Persistencia en SQLite
    donante_actual = obtener_o_crear_donante_prueba()
    actualizado = registro.actualizar_elegibilidad(
        run=donante_actual.run,
        nuevo_estado=datos.nuevo_estado,
        motivo=motivo_final,
    )

    if not actualizado:
        raise HTTPException(
            status_code=404,
            detail="No se encontró el donante en la base de datos.",
        )

    return {
        "mensaje": "Estado actualizado correctamente.",
        "estado": datos.nuevo_estado.value,
        "motivo": motivo_final,
    }