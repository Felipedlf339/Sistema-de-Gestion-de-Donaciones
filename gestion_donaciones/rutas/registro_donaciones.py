from contextlib import closing

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from gestion_donaciones.database import obtener_conexion
from gestion_donaciones.modelos.donaciones import registrar_donacion, DonanteNoApto
from gestion_donaciones.modelos import TipoDonacion
from gestion_donaciones.rutas.elegibilidad import registro

router = APIRouter(prefix="/donaciones", tags=["Donaciones"])
templates = Jinja2Templates(directory="templates")


class DonacionCreate(BaseModel):
    id_donante: str      # aquí viaja el RUN
    tipo_donacion: str   # "SANGRE" o "PLAQUETAS"


@router.get("/registrar", response_class=HTMLResponse)
def ver_formulario_donacion(request: Request):
    return templates.TemplateResponse(request=request, name="registro_donaciones.html")


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
def procesar_registro_donacion(datos: DonacionCreate):
    donante = registro.buscar_por_run(datos.id_donante)
    if donante is None:
        raise HTTPException(status_code=404, detail="No hay un donante registrado con ese RUN.")

    try:
        tipo = TipoDonacion(datos.tipo_donacion)
    except ValueError:
        raise HTTPException(status_code=400, detail="La donación debe ser de sangre o plaquetas.")

    try:
        donacion, unidad = registrar_donacion(donante, tipo)
    except DonanteNoApto:
        estado = donante.estado_elegibilidad
        motivo = getattr(donante, "motivo", None)
        detalle = "El donante no está Apto"
        if estado:
            detalle += f" (estado: {estado.value})"
        if motivo:
            detalle += f". Motivo: {motivo}"
        raise HTTPException(status_code=400, detail=detalle + ". La donación no pudo ser registrada.")

    with closing(obtener_conexion()) as conexion:
        fila = conexion.execute("SELECT id_donante FROM donantes WHERE run = ?", (donante.run,)).fetchone()
        if fila is None:
            raise HTTPException(status_code=404, detail="No se encontró el donante en la base de datos.")
        cursor = conexion.execute(
            "INSERT INTO donaciones (id_donante, tipo_donacion, fecha_hora) VALUES (?, ?, ?)",
            (fila["id_donante"], tipo.value, donacion.fecha_hora.isoformat(timespec="seconds")),
        )
        id_donacion = cursor.lastrowid
        conexion.execute(
            """INSERT INTO unidades
               (id_donacion, tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad, estado)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                id_donacion,
                unidad.tipo_componente.value,
                unidad.tipo_sangre.value,
                unidad.fecha_extraccion.isoformat(),
                unidad.fecha_caducidad.isoformat(),
                unidad.estado.value,
            ),
        )
        conexion.commit()

    return {
        "mensaje": f"¡Donación de {tipo.value.lower()} registrada con éxito!",
        "id_donacion": id_donacion,
        "unidad": {
            "tipo_componente": unidad.tipo_componente.value,
            "tipo_sangre": unidad.tipo_sangre.value,
            "fecha_extraccion": unidad.fecha_extraccion.isoformat(),
            "fecha_caducidad": unidad.fecha_caducidad.isoformat(),
            "estado": unidad.estado.value,
        },
    }