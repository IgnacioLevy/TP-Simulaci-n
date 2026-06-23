import random
import math


class Visitante:
    """
    Representa a cada persona que entra al Palacio Ferreyra.
    Guardamos en el objeto TODO su historial (sala actual, números
    aleatorios que se usaron para definir sus tiempos, etc.) para que
    el vector de estado pueda mostrar, fila por fila, el detalle
    completo de cada visitante presente en el sistema en ese instante,
    tal como pide la consigna del TP.
    """

    def __init__(self, id_visitante, reloj_llegada, puerta):
        self.id = id_visitante
        self.reloj_llegada = reloj_llegada
        self.puerta = puerta  # 'A', 'B' o 'C'

        # --- Edad (distribución exponencial, media 30 años) ---
        self.rnd_edad = random.random()
        edad_calc = -30 * math.log(1 - self.rnd_edad)
        self.edad = int(edad_calc)  # truncada, como pide el enunciado

        # --- Estado dinámico del visitante a lo largo de la simulación ---
        self.estado = "Llegando"          # texto legible para la tabla
        self.sala_actual = "Hall"         # Hall / Ventanilla / Pintura / ColaCerveza / Cerveza / Fotografia / Salio
        self.ventanilla = None            # 1 o 2, si corresponde
        self.fue_a_folletos = None        # True / False
        self.tomo_cerveza = None          # True / False / None (no fue elegido a degustar)
        self.fue_a_fotografia = None      # True / False

        # --- Tiempos / instantes clave (para depurar y para métricas) ---
        self.inicio_cola_informes = None
        self.fin_cola_informes = None
        self.inicio_pintura = None
        self.fin_pintura = None
        self.inicio_cola_cerveza = None
        self.inicio_cerveza = None
        self.fin_cerveza = None
        self.inicio_degustacion = None
        self.fin_degustacion = None
        self.inicio_fotografia = None
        self.fin_fotografia = None
        self.reloj_salida = None

        # --- Números aleatorios usados (para cumplir la consigna de
        #     "mostrar el número aleatorio que se usó para cada variable") ---
        self.rnd_decision_folletos = None
        self.rnd_ventanilla_elegida = None
        self.rnd_tiempo_folletos = None
        self.rnd_tiempo_pintura = None
        self.rnd_decision_fotografia = None
        self.rnd_decision_cerveza = None
        self.rnd_tiempo_cerveza = None

    def snapshot(self):
        """
        Devuelve un diccionario "plano" con el estado actual del visitante,
        listo para insertarse como columnas del vector de estado.
        """
        return {
            "ID": self.id,
            "Puerta": self.puerta,
            "Edad": self.edad,
            "RND_Edad": round(self.rnd_edad, 4),
            "Estado": self.estado,
            "Sala": self.sala_actual,
            "Llegada": round(self.reloj_llegada, 2),
        }
