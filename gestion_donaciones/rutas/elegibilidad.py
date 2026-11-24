from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from gestion_donaciones.modelos.enums import EstadoElegibilidad, GrupoSanguineo, FactorRh, CargoPersonal
from gestion_donaciones.modelos.donante import Donante
from gestion_donaciones.registro_donantes import RegistroDonantes
from gestion_donaciones.rutas.permisos import obtener_usuario

router = APIRouter()
templates = Jinja2Templates(directory="templates")

registro = RegistroDonantes()


class EstadoRequest(BaseModel):
    run: str | None = None
    nuevo_estado: EstadoElegibilidad
    motivo: str | None = None

@router.get("/elegibilidad")
def mostrar_pantalla(request: Request, run: str | None = None, usuario=Depends(obtener_usuario)):
    # usuario es el de la sesión (T28); antes era un usuario fijo
    donante_actual = None
    if run:
        donante_actual = registro.buscar_por_run(run)
        if not donante_actual:
            raise HTTPException(status_code=404, detail="Donante no encontrado.")

    return templates.TemplateResponse(
        request=request,
        name="elegibilidad.html",
        context={
            "donante": donante_actual,
            "usuario": usuario,
        },
    )

@router.get("/api/elegibilidad/donante/{run}")
def obtener_datos_donante(run: str):
    donante = registro.buscar_por_run(run)
    if not donante:
        raise HTTPException(status_code=404, detail="Donante no encontrado.")
    return {
        "run": donante.run,
        "nombre": donante.nombre,
        "estado": donante.estado_elegibilidad.value if donante.estado_elegibilidad else None,
        "motivo": donante.motivo,
    }

@router.post("/api/elegibilidad")
def actualizar_estado(datos: EstadoRequest, usuario=Depends(obtener_usuario)):
    # main.py ya revisa el cargo; se vuelve a revisar aquí por si se llama la función directo
    if usuario is None or usuario.get("cargo") != CargoPersonal.ATENCION_DONANTE.name:
        raise HTTPException(status_code=403, detail="Acceso denegado. Solo el Personal de atención al donante puede modificar la elegibilidad.")

    run_objetivo = (datos.run or "").strip()
    if not run_objetivo:
        raise HTTPException(status_code=400, detail="Debes indicar el RUN del donante.")

    motivo_final = (datos.motivo or "").strip()
    if not motivo_final:
        raise HTTPException(status_code=400, detail="Debes ingresar el motivo para cambiar el estado del donante.")

    actualizado = registro.actualizar_elegibilidad(
        run=run_objetivo,
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
        "run": run_objetivo,
        "estado": datos.nuevo_estado.value,
        "motivo": motivo_final,
    }