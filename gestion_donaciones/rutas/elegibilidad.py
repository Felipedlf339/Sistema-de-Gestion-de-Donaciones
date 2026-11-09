from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Donante falso temporal
donante_mock = {
    "run": "22267222-3",
    "nombre": "Pierluigi Cerulo",
    "estado": "Apto"
}

class EstadoRequest(BaseModel):
    nuevo_estado: str

@router.get("/elegibilidad")
def mostrar_pantalla(request: Request):
    return templates.TemplateResponse(request=request, name="elegibilidad.html", context={"request": request, "donante": donante_mock})

@router.post("/api/elegibilidad")
def actualizar_estado(datos: EstadoRequest):
    donante_mock["estado"] = datos.nuevo_estado
    print(f"BACKEND: El nuevo estado es {donante_mock['estado']}")
    return {"mensaje": "Estado guardado con éxito", "estado_actual": donante_mock["estado"]}
