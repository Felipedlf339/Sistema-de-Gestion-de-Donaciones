from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from gestion_donaciones.modelos import TipoDonacion
from gestion_donaciones.registro_donantes import RegistroDonantes
from gestion_donaciones.modelos.donaciones import registrar_donacion, DonanteNoApto

router = APIRouter(prefix="/donaciones", tags=["Donaciones"])
templates = Jinja2Templates(directory="templates")


registro = RegistroDonantes()


class DonacionCreate(BaseModel):
    id_donante: str     
    tipo_donacion: str   


@router.get("/registrar", response_class=HTMLResponse)
def ver_formulario_donacion(request: Request):
    return templates.TemplateResponse("registro_donaciones.html", {"request": request})


@router.get("/donante/{run}")
def buscar_donante(run: str):
    donante = registro.buscar_por_run(run)
    if donante is None:
        raise HTTPException(status_code=404, detail="No hay un donante registrado con ese RUN.")
    estado = donante.estado_elegibilidad
    return {
        "nombre": donante.nombre,
        "run": donante.run,
        "tipo_sangre": donante.tipo_sangre().value,
        "estado": estado.value if estado else None,
    }


@router.post("/registrar")
async def procesar_registro_donacion(datos: DonacionCreate):
    donante = registro.buscar_por_run(datos.id_donante)
    if donante is None:
        raise HTTPException(status_code=404, detail="No hay un donante registrado con ese RUN.")

    try:
        tipo = TipoDonacion(datos.tipo_donacion)
    except ValueError:
        raise HTTPException(status_code=400, detail="La donación debe ser de sangre o plaquetas.")

    try:
        donacion, unidad = registrar_donacion(donante, tipo)
    except DonanteNoApto as e:
        raise HTTPException(status_code=400, detail=str(e))

    datos_json = {
        "componente": unidad.tipo_componente.value,
        "grupo_sanguineo": unidad.tipo_sangre.value,
        "caducidad": unidad.fecha_caducidad.isoformat(),
        "estado": unidad.estado.value
    }
    from main import notificar_nuevo_stock
    await notificar_nuevo_stock(datos_json)

    return {
        "mensaje": f"¡Donación de {tipo.value.lower()} registrada con éxito!",
        "id_donacion": donacion.id_donacion,
        "unidad": {
            "tipo_componente": unidad.tipo_componente.value,
            "tipo_sangre": unidad.tipo_sangre.value,
            "fecha_extraccion": unidad.fecha_extraccion.isoformat(),
            "fecha_caducidad": unidad.fecha_caducidad.isoformat(),
            "estado": unidad.estado.value,
        },
    }