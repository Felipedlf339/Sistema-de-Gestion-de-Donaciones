from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from gestion_donaciones.modelos.enums import TipoSangre

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Datos simulados 
stock_falso = [
    {"id_unidad": "U-100", "tipo_componente": "Glóbulos Rojos", "tipo_sangre": TipoSangre.O_POS.value, "caducidad": "2026-11-20", "estado": "Disponible"},
    {"id_unidad": "U-101", "tipo_componente": "Plaquetas", "tipo_sangre": TipoSangre.A_NEG.value, "caducidad": "2026-11-13", "estado": "Disponible"},
    {"id_unidad": "U-102", "tipo_componente": "Plasma", "tipo_sangre": TipoSangre.O_POS.value, "caducidad": "2026-10-01", "estado": "Usado"}
]

@router.get("/stock")
def consultar_stock(request: Request, tipo: str = None, grupo: str = None, caducidad: str = None):
    """
    Muestra la tabla del stock disponible y aplica filtros combinados (HU-04, T13 y T14).
    """
    # Filtro base : Mostramos solo unidades Disponibles
    resultados = [unidad for unidad in stock_falso if unidad.get("estado") == "Disponible"]
    
    # Filtro dinámico : Por tipo de componente
    if tipo and tipo != "":
        resultados = [unidad for unidad in resultados if unidad["tipo_componente"] == tipo]
        
    # Filtro dinámico : Por grupo sanguíneo
    if grupo and grupo != "":
        resultados = [unidad for unidad in resultados if unidad["tipo_sangre"] == grupo]
        
    # Filtro dinámico : Por fecha de caducidad
    if caducidad and caducidad != "":
        resultados = [unidad for unidad in resultados if unidad["caducidad"] == caducidad]
        
    contexto = {
        "request": request,
        "unidades": resultados
    }
    
    return templates.TemplateResponse(request=request, name="disponibilidad.html", context=contexto)