from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from gestion_donaciones.database import obtener_conexion

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/stock", response_class=HTMLResponse)
def consultar_disponibilidad(
    request: Request,
    tipo: str = Query(None),
    grupo: str = Query(None),
    rh: str = Query(None),
    vence_antes_de: str = Query(None)
):
    # Abrimos conexión a la base de datos real
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # Consulta base: Buscar SOLO unidades con estado 'Disponible'
    query = "SELECT * FROM unidades WHERE estado = 'Disponible'"
    parametros = []

    # Agregamos los filtros dinámicos si el usuario los seleccionó
    if tipo:
        query += " AND tipo_componente = ?"
        parametros.append(tipo)
    
    if grupo and rh:
        query += " AND tipo_sangre = ?"
        parametros.append(f"{grupo}{rh}")
    elif grupo:
        query += " AND tipo_sangre LIKE ?"
        parametros.append(f"{grupo}%")
    elif rh:
        query += " AND tipo_sangre LIKE ?"
        parametros.append(f"%{rh}")

    if vence_antes_de:
        query += " AND fecha_caducidad <= ?"
        parametros.append(vence_antes_de)

    # Ejecutamos la búsqueda y cerramos la conexión
    cursor.execute(query, parametros)
    unidades_db = cursor.fetchall()
    conexion.close()

    # Enviamos los datos reales al HTML
    return templates.TemplateResponse(
        request=request,
        name="disponibilidad.html", 
        context={
            "request": request,
            "unidades": unidades_db
    })