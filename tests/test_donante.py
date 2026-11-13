"""Pruebas del modelo Donante (HU-01, tarea 1.4)."""

import unittest

from gestion_donaciones.modelos import (
    Donante,
    EstadoElegibilidad,
    FactorRh,
    GrupoSanguineo,
    TipoSangre,
)


class PruebasDonante(unittest.TestCase):

    def test_tipo_sangre_combina_grupo_y_factor(self):
        donante = Donante("12345678-5", "Ana", GrupoSanguineo.AB, FactorRh.NEGATIVO)
        self.assertEqual(donante.tipo_sangre(), TipoSangre.AB_NEG)

        donante = Donante("12345678-5", "Ana", GrupoSanguineo.O, FactorRh.POSITIVO)
        self.assertEqual(donante.tipo_sangre(), TipoSangre.O_POS)

    def test_datos_que_empiezan_vacios(self):
        donante = Donante("12345678-5", "Ana", GrupoSanguineo.A, FactorRh.POSITIVO)

        self.assertIsNone(donante.id_donante)
        self.assertIsNone(donante.estado_elegibilidad)
        self.assertIsNone(donante.correo)
        self.assertIsNone(donante.telefono)

    def test_es_apto_solo_con_estado_apto(self):
        donante = Donante("12345678-5", "Ana", GrupoSanguineo.A, FactorRh.POSITIVO)
        self.assertFalse(donante.es_apto())

        donante.cambiar_elegibilidad(EstadoElegibilidad.DIFERIDO_TEMPORAL)
        self.assertFalse(donante.es_apto())

        donante.cambiar_elegibilidad(EstadoElegibilidad.APTO)
        self.assertTrue(donante.es_apto())


if __name__ == "__main__":
    unittest.main()
