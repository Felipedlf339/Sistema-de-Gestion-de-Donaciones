"""Pruebas de los permisos por cargo (HU-07, tarea T28)"""

import unittest

from gestion_donaciones.modelos.enums import CargoMedico, CargoPersonal
from gestion_donaciones.rutas import permisos


def usuario(cargo):
    return {"id_personal": 1, "run": "15555555-6", "nombre": "Prueba",
            "cargo": cargo.name, "nombre_cargo": cargo.value, "centro_medico": None}


ATENCION = usuario(CargoPersonal.ATENCION_DONANTE)
INVENTARIO = usuario(CargoPersonal.ENCARGADO_INVENTARIO)
RECEPCION = usuario(CargoMedico.RESPONSABLE_RECEPCION)
CLINICO = usuario(CargoMedico.PERSONAL_CLINICO)


class TestCargosPermitidos(unittest.TestCase):
    def test_ruta_exacta_y_subrutas(self):
        self.assertEqual(permisos.cargos_permitidos("/donantes"), [permisos.ATENCION_DONANTE])
        self.assertEqual(permisos.cargos_permitidos("/donantes/registrar"), [permisos.ATENCION_DONANTE])

    def test_ruta_que_solo_empieza_igual_no_hereda_el_permiso(self):
        self.assertIsNone(permisos.cargos_permitidos("/donantesX"))

    def test_la_ruta_mas_especifica_gana(self):
        self.assertEqual(permisos.cargos_permitidos("/stock/solicitar"), permisos.CENTRO_MEDICO)
        self.assertIn(permisos.ENCARGADO_INVENTARIO, permisos.cargos_permitidos("/stock"))

    def test_api_de_elegibilidad_solo_atencion_al_donante(self):
        self.assertEqual(
            permisos.cargos_permitidos("/api/elegibilidad/donante/12345678-5"),
            [permisos.ATENCION_DONANTE],
        )

    def test_los_cargos_de_la_tabla_existen(self):
        nombres = [c.name for c in CargoPersonal] + [c.name for c in CargoMedico]
        for ruta, cargos in permisos.PERMISOS:
            for cargo in cargos:
                with self.subTest(ruta=ruta, cargo=cargo):
                    self.assertIn(cargo, nombres)


class TestPuedeAcceder(unittest.TestCase):
    def test_sin_usuario_no_entra(self):
        self.assertFalse(permisos.puede_acceder(None, "/stock"))

    def test_atencion_al_donante(self):
        for ruta in ("/donantes/registrar", "/elegibilidad", "/api/elegibilidad", "/donaciones/registrar"):
            with self.subTest(ruta=ruta):
                self.assertTrue(permisos.puede_acceder(ATENCION, ruta))
        self.assertFalse(permisos.puede_acceder(ATENCION, "/stock"))

    def test_encargado_de_inventario(self):
        self.assertTrue(permisos.puede_acceder(INVENTARIO, "/stock"))
        self.assertFalse(permisos.puede_acceder(INVENTARIO, "/stock/solicitar"))
        self.assertFalse(permisos.puede_acceder(INVENTARIO, "/api/elegibilidad"))

    def test_despachos_solo_encargado_de_inventario(self):
        self.assertTrue(permisos.puede_acceder(INVENTARIO, "/despachos/pendientes"))
        for otro in (ATENCION, RECEPCION, CLINICO):
            with self.subTest(cargo=otro["cargo"]):
                self.assertFalse(permisos.puede_acceder(otro, "/despachos/pendientes"))

    def test_personal_de_centro_medico(self):
        for medico in (RECEPCION, CLINICO):
            with self.subTest(cargo=medico["cargo"]):
                self.assertTrue(permisos.puede_acceder(medico, "/stock"))
                self.assertTrue(permisos.puede_acceder(medico, "/stock/solicitar"))
                self.assertFalse(permisos.puede_acceder(medico, "/elegibilidad"))
                self.assertFalse(permisos.puede_acceder(medico, "/api/elegibilidad"))
                self.assertFalse(permisos.puede_acceder(medico, "/donantes/registrar"))


class TestOpcionesDelMenu(unittest.TestCase):
    def rutas(self, usuario):
        return [opcion["url"] for opcion in permisos.opciones_del_menu(usuario)]

    def test_cada_cargo_ve_solo_sus_opciones(self):
        self.assertEqual(
            self.rutas(ATENCION),
            ["/donantes/registrar", "/elegibilidad", "/donaciones/registrar"],
        )
        self.assertEqual(self.rutas(INVENTARIO), ["/stock", "/despachos/pendientes"])
        self.assertEqual(self.rutas(RECEPCION), ["/stock"])
        self.assertEqual(self.rutas(CLINICO), ["/stock"])

    def test_todos_los_cargos_tienen_al_menos_una_opcion(self):
        for cargo in list(CargoPersonal) + list(CargoMedico):
            with self.subTest(cargo=cargo.name):
                self.assertNotEqual(self.rutas(usuario(cargo)), [])


class Peticion:
    """Imita lo mínimo de un Request: la ruta y los encabezados"""

    def __init__(self, ruta, accept="*/*"):
        self.url = self
        self.path = ruta
        self.headers = {"accept": accept}


class TestVerificarAcceso(unittest.TestCase):
    def test_sin_sesion_lanza_sin_sesion(self):
        with self.assertRaises(permisos.SinSesion):
            permisos.verificar_acceso(Peticion("/elegibilidad"), usuario=None)

    def test_cargo_no_autorizado_lanza_acceso_denegado(self):
        with self.assertRaises(permisos.AccesoDenegado):
            permisos.verificar_acceso(Peticion("/api/elegibilidad"), usuario=RECEPCION)

    def test_cargo_autorizado_devuelve_el_usuario(self):
        self.assertIs(permisos.verificar_acceso(Peticion("/elegibilidad"), usuario=ATENCION), ATENCION)

    def test_distingue_pantalla_de_fetch(self):
        self.assertTrue(permisos.quiere_html(Peticion("/stock", "text/html,application/xhtml+xml")))
        self.assertFalse(permisos.quiere_html(Peticion("/stock", "*/*")))


if __name__ == "__main__":
    unittest.main()
