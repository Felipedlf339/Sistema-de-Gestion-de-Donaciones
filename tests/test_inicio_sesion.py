"""Pruebas HTTP del inicio de sesión y de la restricción por cargo (HU-07, tarea T29)

A diferencia de test_permisos.py, aquí no se reemplaza el usuario de la sesión:
se inicia sesión de verdad con POST /login, sobre una base de datos temporal.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd
from gestion_donaciones.modelos import (
    CargoMedico,
    CargoPersonal,
    CentroMedico,
    Donante,
    FactorRh,
    GrupoSanguineo,
    PersonalCentroDonacion,
    PersonalCentroMedico,
)
from gestion_donaciones.registro_donantes import RegistroDonantes
from gestion_donaciones.registro_personal import RegistroPersonal
from gestion_donaciones.rutas import permisos
from gestion_donaciones.rutas.sesion import MENSAJE_INCORRECTO
from main import app

# usuarios de prueba: (RUN, contraseña)
ATENCION = ("15.555.555-6", "donacion123")
INVENTARIO = ("16.666.666-K", "inventario123")
RECEPCION = ("18.888.888-7", "hospital123")
CLINICO = ("11.111.111-1", "clinico123")

# encabezados de un navegador que abre una pantalla y de un fetch() de JavaScript
PANTALLA = {"accept": "text/html,application/xhtml+xml"}
FETCH = {"accept": "*/*"}

# pantallas protegidas y el cargo que puede abrir cada una
PANTALLAS = {
    "/donantes/registrar": [ATENCION],
    "/elegibilidad": [ATENCION],
    "/donaciones/registrar": [ATENCION],
    "/stock": [INVENTARIO, RECEPCION, CLINICO],
    "/despachos/pendientes": [INVENTARIO],
}

RUN_DONANTE = "12.345.678-5"


class PruebaConSesion(unittest.TestCase):
    """Base temporal con un usuario por cargo; cada prueba usa clientes nuevos"""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(database, "DB_PATH", Path(carpeta.name) / "prueba.db")
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()
        # por si otra prueba dejó un usuario fijo
        app.dependency_overrides.clear()

        registro = RegistroPersonal()
        centro = CentroMedico("Hospital Regional de Concepción")
        registro.registrar_centro_medico(centro)
        registro.registrar(
            PersonalCentroDonacion(ATENCION[0], "Ana Pérez", None, CargoPersonal.ATENCION_DONANTE),
            ATENCION[1],
        )
        registro.registrar(
            PersonalCentroDonacion(INVENTARIO[0], "Luis Soto", None, CargoPersonal.ENCARGADO_INVENTARIO),
            INVENTARIO[1],
        )
        registro.registrar(
            PersonalCentroMedico(RECEPCION[0], "Camila Rojas", CargoMedico.RESPONSABLE_RECEPCION, centro),
            RECEPCION[1],
        )
        registro.registrar(
            PersonalCentroMedico(CLINICO[0], "Pedro Muñoz", CargoMedico.PERSONAL_CLINICO, centro),
            CLINICO[1],
        )

    def cliente_nuevo(self):
        # sin seguir redirecciones, para revisar el 303 y su destino
        return TestClient(app, follow_redirects=False)

    def iniciar_sesion(self, usuario):
        cliente = self.cliente_nuevo()
        respuesta = cliente.post("/login", json={"run": usuario[0], "contrasena": usuario[1]})
        self.assertEqual(respuesta.status_code, 200)
        return cliente

    def comprobar_va_al_login(self, respuesta):
        self.assertEqual(respuesta.status_code, 303)
        self.assertEqual(respuesta.headers["location"], "/login")

    def comprobar_acceso_denegado(self, respuesta):
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn(permisos.MENSAJE_ACCESO_DENEGADO, respuesta.text)


class TestIngreso(PruebaConSesion):
    """Test 1: credenciales válidas, contraseña incorrecta, RUN inexistente y cierre de sesión"""

    def test_credenciales_validas_inician_sesion(self):
        cliente = self.cliente_nuevo()

        respuesta = cliente.post("/login", json={"run": ATENCION[0], "contrasena": ATENCION[1]})

        self.assertEqual(respuesta.status_code, 200)
        usuario = respuesta.json()["usuario"]
        self.assertEqual(usuario["run"], "15555555-6")
        self.assertEqual(usuario["cargo"], "ATENCION_DONANTE")
        # con la cookie de sesión ya se puede abrir el panel principal
        panel = cliente.get("/", headers=PANTALLA)
        self.assertEqual(panel.status_code, 200)
        self.assertIn("Ana Pérez", panel.text)

    def test_run_sin_puntos_tambien_entra(self):
        cliente = self.cliente_nuevo()

        respuesta = cliente.post("/login", json={"run": "16666666-k", "contrasena": INVENTARIO[1]})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["usuario"]["cargo"], "ENCARGADO_INVENTARIO")

    def test_personal_medico_queda_con_su_centro(self):
        cliente = self.cliente_nuevo()

        respuesta = cliente.post("/login", json={"run": RECEPCION[0], "contrasena": RECEPCION[1]})

        self.assertEqual(respuesta.json()["usuario"]["centro_medico"], "Hospital Regional de Concepción")
        self.assertIn("Hospital Regional de Concepción", cliente.get("/", headers=PANTALLA).text)

    def test_contrasena_incorrecta_no_inicia_sesion(self):
        cliente = self.cliente_nuevo()

        respuesta = cliente.post("/login", json={"run": ATENCION[0], "contrasena": "otra"})

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()["detail"], MENSAJE_INCORRECTO)
        self.comprobar_va_al_login(cliente.get("/", headers=PANTALLA))

    def test_run_inexistente_da_el_mismo_mensaje(self):
        cliente = self.cliente_nuevo()

        respuesta = cliente.post("/login", json={"run": "22.222.222-2", "contrasena": ATENCION[1]})

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()["detail"], MENSAJE_INCORRECTO)

    def test_campos_vacios_piden_completar(self):
        cliente = self.cliente_nuevo()

        for datos in ({"run": "", "contrasena": "x"}, {"run": ATENCION[0], "contrasena": "  "}, {}):
            with self.subTest(datos=datos):
                respuesta = cliente.post("/login", json=datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()["detail"], "Ingrese su RUN y su contraseña.")

    def test_pantalla_de_login_sin_y_con_sesion(self):
        self.assertEqual(self.cliente_nuevo().get("/login").status_code, 200)

        cliente = self.iniciar_sesion(ATENCION)
        respuesta = cliente.get("/login")

        self.assertEqual(respuesta.status_code, 303)
        self.assertEqual(respuesta.headers["location"], "/")

    def test_cerrar_sesion_corta_el_acceso(self):
        cliente = self.iniciar_sesion(ATENCION)
        self.assertEqual(cliente.get("/elegibilidad", headers=PANTALLA).status_code, 200)

        respuesta = cliente.post("/logout")

        self.comprobar_va_al_login(respuesta)
        self.comprobar_va_al_login(cliente.get("/", headers=PANTALLA))
        self.comprobar_va_al_login(cliente.get("/elegibilidad", headers=PANTALLA))

    def test_otro_inicio_de_sesion_reemplaza_al_anterior(self):
        cliente = self.iniciar_sesion(ATENCION)

        cliente.post("/login", json={"run": INVENTARIO[0], "contrasena": INVENTARIO[1]})

        self.assertEqual(cliente.get("/stock", headers=PANTALLA).status_code, 200)
        self.comprobar_acceso_denegado(cliente.get("/elegibilidad", headers=PANTALLA))


class TestSinSesion(PruebaConSesion):
    """Test 2 (a): sin sesión no se abre ninguna pantalla protegida"""

    def test_pantallas_redirigen_al_login(self):
        cliente = self.cliente_nuevo()
        for ruta in list(PANTALLAS) + ["/"]:
            with self.subTest(ruta=ruta):
                self.comprobar_va_al_login(cliente.get(ruta, headers=PANTALLA))

    def test_fetch_recibe_401(self):
        cliente = self.cliente_nuevo()

        respuesta = cliente.post(
            "/api/elegibilidad",
            json={"run": RUN_DONANTE, "nuevo_estado": "APTO", "motivo": "x"},
            headers=FETCH,
        )

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()["detail"], permisos.MENSAJE_SIN_SESION)

    def test_cookie_falsa_no_sirve(self):
        cliente = self.cliente_nuevo()
        cliente.cookies.set("session", "inventada")

        self.comprobar_va_al_login(cliente.get("/stock", headers=PANTALLA))


class TestRestriccionPorCargo(PruebaConSesion):
    """Test 2 (b y c): cargo autorizado y cargo no autorizado"""

    def test_cada_cargo_abre_solo_sus_pantallas(self):
        for usuario in (ATENCION, INVENTARIO, RECEPCION, CLINICO):
            cliente = self.iniciar_sesion(usuario)
            for ruta, autorizados in PANTALLAS.items():
                with self.subTest(usuario=usuario[0], ruta=ruta):
                    respuesta = cliente.get(ruta, headers=PANTALLA)
                    if usuario in autorizados:
                        self.assertEqual(respuesta.status_code, 200)
                    else:
                        self.comprobar_acceso_denegado(respuesta)

    def test_fetch_no_autorizado_recibe_403_en_json(self):
        cliente = self.iniciar_sesion(INVENTARIO)

        respuesta = cliente.post(
            "/stock/solicitar",
            data={"tipo_hemoderivado": "SANGRE", "grupo_sanguineo": "O+", "cantidad": "1"},
            headers=FETCH,
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], permisos.MENSAJE_ACCESO_DENEGADO)

    def test_solo_atencion_al_donante_modifica_la_elegibilidad(self):
        donante = Donante(RUN_DONANTE, "Marta Díaz", GrupoSanguineo.O, FactorRh.POSITIVO, correo="marta@correo.cl")
        self.assertEqual(RegistroDonantes().registrar(donante), [])
        datos = {"run": RUN_DONANTE, "nuevo_estado": "APTO", "motivo": "Cumple requisitos"}

        medico = self.iniciar_sesion(RECEPCION).post("/api/elegibilidad", json=datos, headers=FETCH)
        self.assertEqual(medico.status_code, 403)
        self.assertIsNone(RegistroDonantes().buscar_por_run(RUN_DONANTE).estado_elegibilidad)

        atencion = self.iniciar_sesion(ATENCION).post("/api/elegibilidad", json=datos, headers=FETCH)
        self.assertEqual(atencion.status_code, 200)
        self.assertEqual(RegistroDonantes().buscar_por_run(RUN_DONANTE).estado_elegibilidad.value, "APTO")


class TestPanelSegunCargo(PruebaConSesion):
    """El panel principal muestra solo los botones del cargo"""

    def botones(self, usuario):
        html = self.iniciar_sesion(usuario).get("/", headers=PANTALLA).text
        return [ruta for ruta in PANTALLAS if f'data-url="{ruta}"' in html]

    def test_botones_de_cada_cargo(self):
        self.assertEqual(self.botones(ATENCION), ["/donantes/registrar", "/elegibilidad", "/donaciones/registrar"])
        self.assertEqual(self.botones(INVENTARIO), ["/stock", "/despachos/pendientes"])
        self.assertEqual(self.botones(RECEPCION), ["/stock"])
        self.assertEqual(self.botones(CLINICO), ["/stock"])


if __name__ == "__main__":
    unittest.main()
