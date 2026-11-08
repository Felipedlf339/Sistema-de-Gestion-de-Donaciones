from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Donante falso temporal
donante_mock = {
    "run": "22267222-3",
    "nombre": "Pierluigi Cerulo",
    "estado": "Apto",
    "motivo": None
}

class EstadoRequest(BaseModel):
    nuevo_estado: str
    motivo:str | None = None
@router.get("/elegibilidad")
def mostrar_pantalla(request: Request):
    return templates.TemplateResponse(request=request, name="elegibilidad.html", context={"request": request, "donante": donante_mock})

@router.post("/api/elegibilidad")
def actualizar_estado(datos: EstadoRequest):
    estado_actual_backend = donante_mock["estado"]
    if datos.nuevo_estado != estado_actual_backend and not datos.motivo:
        raise HTTPException(status_code=400, detail="Debes ingresar el motivo para cambiar el estado del donante.")
    
    donante_mock["estado"] = datos.nuevo_estado
    if datos.nuevo_estado != estado_actual_backend:
        donante_mock["motivo"] = datos.motivo
    print(f"BACKEND: Nuevo Estado: {donante_mock['estado']} | Motivo del cambio: {donante_mock['motivo']}")
    return {"mensaje": "Estado guardado con éxito", "estado_actual": donante_mock["estado"]}
