from datetime import datetime


class Donacion:

    def __init__(self, id_donante, tipo_donacion, fecha_hora=None):
        self.id_donacion = None                         
        self.id_donante = id_donante                   
        self.tipo_donacion = tipo_donacion             
        self.fecha_hora = fecha_hora or datetime.now()
        self.id_unidad = None                        