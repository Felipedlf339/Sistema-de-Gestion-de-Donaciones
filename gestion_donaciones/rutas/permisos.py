"""Permisos de cada cargo sobre las pantallas y rutas (HU-07, tarea T28)"""

from fastapi import Depends, Request

from gestion_donaciones.modelos.enums import CargoMedico, CargoPersonal
from gestion_donaciones.rutas.sesion import usuario_en_sesion

# en la sesión el cargo se guarda con su nombre (ej. "ATENCION_DONANTE")
ATENCION_DONANTE = CargoPersonal.ATENCION_DONANTE.name
ENCARGADO_INVENTARIO = CargoPersonal.ENCARGADO_INVENTARIO.name
CENTRO_MEDICO = [CargoMedico.RESPONSABLE_RECEPCION.name, CargoMedico.PERSONAL_CLINICO.name]

# ruta -> cargos que pueden usarla (también vale para las rutas que empiezan con ella)
# se revisan en orden, así que las rutas más específicas van primero
# al agregar una pantalla nueva (ej. despacho de HU-09) se suma aquí y en OPCIONES_MENU
PERMISOS = [
    ("/donantes", [ATENCION_DONANTE]),
    ("/elegibilidad", [ATENCION_DONANTE]),
    ("/api/elegibilidad", [ATENCION_DONANTE]),
    ("/donaciones", [ATENCION_DONANTE]),
    ("/stock/solicitar", CENTRO_MEDICO),
    ("/stock", [ENCARGADO_INVENTARIO] + CENTRO_MEDICO),
    ("/despachos", [ENCARGADO_INVENTARIO]),
]

# botones del panel principal: (ruta, texto)
OPCIONES_MENU = [
    ("/donantes/registrar", "Registrar donante"),
    ("/elegibilidad", "Elegibilidad"),
    ("/donaciones/registrar", "Registrar donación"),
    ("/stock", "Disponibilidad"),
    ("/despachos/pendientes", "Despachos"),
]

MENSAJE_SIN_SESION = "Debe iniciar sesión."
MENSAJE_ACCESO_DENEGADO = "Acceso denegado. Su cargo no tiene permiso para usar esta función."


class SinSesion(Exception):
    """Se lanza cuando se abre una ruta protegida sin haber iniciado sesión"""


class AccesoDenegado(Exception):
    """Se lanza cuando el cargo del usuario no puede usar la ruta"""


def cargos_permitidos(ruta):
    # devuelve la lista de cargos de la ruta, o None si basta con tener sesión
    for prefijo, cargos in PERMISOS:
        if ruta == prefijo or ruta.startswith(prefijo + "/"):
            return cargos
    return None


def puede_acceder(usuario, ruta):
    if usuario is None:
        return False
    cargos = cargos_permitidos(ruta)
    if cargos is None:
        return True
    return usuario.get("cargo") in cargos


def opciones_del_menu(usuario):
    # solo los botones que el cargo del usuario puede abrir
    opciones = []
    for ruta, texto in OPCIONES_MENU:
        if puede_acceder(usuario, ruta):
            opciones.append({"url": ruta, "texto": texto})
    return opciones


def quiere_html(request):
    # el navegador pide text/html al abrir una pantalla; fetch() pide */*
    return "text/html" in request.headers.get("accept", "")


def obtener_usuario(request: Request):
    # separado para que las pruebas puedan reemplazarlo (app.dependency_overrides)
    return usuario_en_sesion(request)


def verificar_acceso(request: Request, usuario=Depends(obtener_usuario)):
    # se agrega a cada router en main.py; los errores los responde main.py
    if usuario is None:
        raise SinSesion()
    if not puede_acceder(usuario, request.url.path):
        raise AccesoDenegado()
    return usuario
