from datetime import timedelta

from gestion_donaciones.modelos import TipoDonacion, Unidad

DIAS_CADUCIDAD = {
    TipoDonacion.SANGRE: 42,
    TipoDonacion.PLAQUETAS: 5,
}


def calcular_fecha_caducidad(tipo_donacion, fecha_extraccion):
    return fecha_extraccion + timedelta(days=DIAS_CADUCIDAD[tipo_donacion])


def generar_unidad(donacion, donante):
   
    fecha_extraccion = donacion.fecha_hora.date()
    return Unidad(
        id_donacion=donacion.id_donacion,      
        tipo_componente=donacion.tipo_donacion,
        tipo_sangre=donante.tipo_sangre(),
        fecha_extraccion=fecha_extraccion,
        fecha_caducidad=calcular_fecha_caducidad(donacion.tipo_donacion, fecha_extraccion),
    )