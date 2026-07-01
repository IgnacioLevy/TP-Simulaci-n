import random
import math

from .visitante import Visitante
from .runge_kutta import calcular_tiempo_degustacion


class Simulador:
    """
    Motor de simulación por eventos discretos del Palacio Ferreyra.

    Cada jornada va de 9:00 a 22:00 hs (13 horas = 46800 segundos).
    Si se pide simular "varios días", se encadenan jornadas: al llegar
    a las 22 hs se reinician colas, salas y horarios de llegada, pero
    se acumulan las métricas y se sigue numerando iteraciones y
    visitantes en forma continua, para que el usuario vea el sistema
    funcionando día tras día.
    """

    SEGUNDOS_JORNADA = 13 * 3600  # 9 a 22 hs

    def __init__(self, parametros):
        self.parametros = parametros

        self.reloj = 0.0          # reloj global (acumula todos los días simulados)
        self.reloj_dia = 0.0      # reloj relativo al día actual (0 a 46800)
        self.dia_actual = 1

        self.dias_a_simular = parametros.get('dias', 1)
        self.tiempo_x = parametros.get('tiempo_x', 0.0)
        self.paso_h = parametros.get('rk_h', 0.05)
        self.dist_salas = parametros.get('dist_salas', 'Normal')

        # Probabilidades del recorrido, todas parametrizables por el usuario
        self.prob_folletos = parametros.get('prob_folletos', 0.60)
        self.prob_fotografia = parametros.get('prob_fotografia', 0.40)
        self.prob_cerveza = parametros.get('prob_cerveza', 0.50)

        self.iteracion = 0
        self.visitantes_totales = 0
        self.vector_estado = []   # acá se guarda la "foto" de cada iteración pedida

        # --- Servidores y colas ---
        self.servidores_cerveza = 2
        self.cola_cerveza = []

        self.ventanillas = {
            1: {'libres': 2, 'cola': []},
            2: {'libres': 2, 'cola': []},
        }

        # Empleados como objetos (Req. 2)
        self.ventanillas_empleados = {
            1: [
                {'id': 1, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None},
                {'id': 2, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None}
            ],
            2: [
                {'id': 1, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None},
                {'id': 2, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None}
            ]
        }
        self.cerveza_servidores = [
            {'id': 1, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None},
            {'id': 2, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None}
        ]

        # Visitantes activos en el sistema (no salieron todavía)
        self.visitantes_activos = {}
        # Guardamos a todos para poder graficar / depurar si hace falta
        self.visitantes_historicos = {}

        # --- Conteos en sala (para el control cada 15 min) ---
        self.personas_en_pintura = 0
        self.personas_en_fotografia = 0

        # --- MÉTRICAS OBLIGATORIAS ---
        self.acumulador_espera_v1 = 0.0
        self.visitantes_esperaron_v1 = 0
        self.acumulador_espera_v2 = 0.0
        self.visitantes_esperaron_v2 = 0
        self.acumulador_tiempo_permanencia = 0.0
        self.visitantes_finalizados = 0
        self.metricas_15_min = []

        # --- 5 MÉTRICAS EXTRA (todas distintas entre sí) ---
        self.metrica_total_folletos = 0                # 1) visitantes que pidieron folletos
        self.metrica_total_cervezas = 0                 # 2) cervezas servidas
        self.metrica_suma_edades_cerveza = 0.0           #    (auxiliar para promedio de edad)
        self.metrica_total_fotografia = 0                # 3) visitantes que entraron a fotografía
        self.metrica_abandonos_post_pintura = 0          # 4) personas que se van tras pintura (no van a foto)
        self.max_cola_cerveza = 0                      # 5) máxima longitud alcanzada por la cola de cerveza
        self.contador_directo_muestra = 0              # Contador adicional para la planilla Excel

        # Almacenamiento de RNDs de próximas llegadas
        self.prox_llegadas_rnd = {'A': "", 'B': "", 'C': ""}

        # Tablas de Runge-Kutta generadas, para mostrarlas en la interfaz
        self.tablas_rk_generadas = {}

        # Lista de eventos futuros: clave -> tiempo (en reloj GLOBAL, segundos)
        self.eventos = {}

        # Inicializar variables de paso temporales
        self._clear_step_variables()

        self._programar_llegadas_iniciales()
        self.eventos['Control_15min'] = self.reloj + (15 * 60)
        self.eventos['Fin_Jornada'] = self.reloj + self.SEGUNDOS_JORNADA

    def _clear_step_variables(self):
        self.step_rnd1_lleg_a = ""
        self.step_rnd2_lleg_a = ""
        self.step_dur_lleg_a = ""
        
        self.step_rnd1_lleg_b = ""
        self.step_rnd2_lleg_b = ""
        self.step_dur_lleg_b = ""
        
        self.step_rnd1_lleg_c = ""
        self.step_rnd2_lleg_c = ""
        self.step_dur_lleg_c = ""
        
        self.step_rnd_foll = ""
        self.step_res_foll = ""
        self.step_rnd_vent = ""
        self.step_res_vent = ""
        self.step_rnd_t_foll = ""
        self.step_dur_t_foll = ""
        
        self.step_rnd_t_pint = ""
        self.step_dur_t_pint = ""
        self.step_fin_t_pint = ""
        
        self.step_rnd_foto_dec = ""
        self.step_res_foto_dec = ""
        
        self.step_rnd_edad = ""
        self.step_edad_trunc = ""
        self.step_es_mayor = ""
        
        self.step_rnd_cerv_dec = ""
        self.step_res_cerv_dec = ""
        
        self.step_tpo_tomar_rk = ""
        self.step_rnd_tpo_servir = ""
        self.step_tpo_serv = ""
        
        self.step_rnd_tiempo_foto = ""
        self.step_dur_tiempo_foto = ""
        self.step_fin_tiempo_foto = ""

    def _iniciar_servicio_ventanilla(self, v_id, visitante, t_servicio):
        self.ventanillas[v_id]['libres'] -= 1
        for emp in self.ventanillas_empleados[v_id]:
            if emp['estado'] == 'Libre':
                emp['estado'] = 'Ocupado'
                emp['fin_atencion'] = self.reloj + t_servicio
                emp['vis_id'] = visitante.id
                break

    def _finalizar_servicio_ventanilla(self, v_id, vis_id):
        self.ventanillas[v_id]['libres'] += 1
        for emp in self.ventanillas_empleados[v_id]:
            if emp['vis_id'] == vis_id:
                emp['estado'] = 'Libre'
                emp['fin_atencion'] = None
                emp['vis_id'] = None
                break

    def _iniciar_servicio_cerveza(self, visitante, t_servicio):
        self.servidores_cerveza -= 1
        for serv in self.cerveza_servidores:
            if serv['estado'] == 'Libre':
                serv['estado'] = 'Ocupado'
                serv['fin_atencion'] = self.reloj + t_servicio
                serv['vis_id'] = visitante.id
                break

    def _finalizar_servicio_cerveza(self, vis_id):
        self.servidores_cerveza += 1
        for serv in self.cerveza_servidores:
            if serv['vis_id'] == vis_id:
                serv['estado'] = 'Libre'
                serv['fin_atencion'] = None
                serv['vis_id'] = None
                break

    def _empleado_ventanilla_libre(self, v_id):
        return any(emp['estado'] == 'Libre' for emp in self.ventanillas_empleados[v_id])

    def _servidor_cerveza_libre(self):
        return any(serv['estado'] == 'Libre' for serv in self.cerveza_servidores)

    # ------------------------------------------------------------------
    # Utilidades de números aleatorios (siempre devuelven también el rnd)
    # ------------------------------------------------------------------
    def generar_normal(self, media, desv):
        """Genera un valor con distribución Normal (Box-Muller) y devuelve
        también los dos números aleatorios [0,1) usados, truncando a un
        mínimo de 0.1 para asegurar tiempos siempre mayores que cero."""
        rnd1, rnd2 = random.random(), random.random()
        z = math.sqrt(-2 * math.log(rnd1)) * math.cos(2 * math.pi * rnd2)
        valor = max(0.1, media + desv * z)
        return valor, rnd1, rnd2

    def generar_uniforme(self, minimo, maximo):
        rnd = random.random()
        valor = minimo + rnd * (maximo - minimo)
        return valor, rnd

    # ------------------------------------------------------------------
    # Inicialización
    # ------------------------------------------------------------------
    def _programar_llegadas_iniciales(self):
        media_a, desv_a = self.parametros['puerta_a']
        media_b, desv_b = self.parametros['puerta_b']
        media_c, desv_c = self.parametros['puerta_c']

        t_a, rnd1_a, rnd2_a = self.generar_normal(media_a, desv_a)
        t_b, rnd1_b, rnd2_b = self.generar_normal(media_b, desv_b)
        t_c, rnd1_c, rnd2_c = self.generar_normal(media_c, desv_c)

        self.prox_llegadas_rnd['A'] = f"{rnd1_a:.4f}, {rnd2_a:.4f}"
        self.prox_llegadas_rnd['B'] = f"{rnd1_b:.4f}, {rnd2_b:.4f}"
        self.prox_llegadas_rnd['C'] = f"{rnd1_c:.4f}, {rnd2_c:.4f}"

        self.eventos['Llegada_A'] = self.reloj + t_a
        # Puerta B arranca 2 hs después de abierto el palacio (11 hs)
        self.eventos['Llegada_B'] = self.reloj + 2 * 3600 + t_b
        # Puerta C arranca 3 hs después de la B (14 hs)
        self.eventos['Llegada_C'] = self.reloj + 5 * 3600 + t_c

    def _reiniciar_para_nuevo_dia(self):
        """Al llegar a las 22 hs, si quedan días por simular, arrancamos
        un nuevo día: se vacían colas y salas (el palacio cierra y al otro
        día vuelve a recibir gente desde cero), pero las métricas
        acumuladas NO se resetean."""
        self.dia_actual += 1
        self.reloj_dia = 0.0

        # Cerramos cualquier visitante que haya quedado "colgado" en el
        # sistema al cierre (no se cuenta su permanencia porque no llegó
        # a completar su recorrido en el horario de atención).
        self.visitantes_activos = {}
        self.personas_en_pintura = 0
        self.personas_en_fotografia = 0
        self.servidores_cerveza = 2
        self.cola_cerveza = []
        self.ventanillas = {
            1: {'libres': 2, 'cola': []},
            2: {'libres': 2, 'cola': []},
        }
        self.ventanillas_empleados = {
            1: [
                {'id': 1, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None},
                {'id': 2, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None}
            ],
            2: [
                {'id': 1, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None},
                {'id': 2, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None}
            ]
        }
        self.cerveza_servidores = [
            {'id': 1, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None},
            {'id': 2, 'estado': 'Libre', 'fin_atencion': None, 'vis_id': None}
        ]

        # Limpiamos eventos pendientes del día anterior y reprogramamos
        # las llegadas del nuevo día
        self.eventos = {}
        self._programar_llegadas_iniciales()
        self.eventos['Control_15min'] = self.reloj + (15 * 60)
        self.eventos['Fin_Jornada'] = self.reloj + self.SEGUNDOS_JORNADA

    # ------------------------------------------------------------------
    # Tiempos de sala según la tabla del enunciado (dependen de la hora)
    # ------------------------------------------------------------------
    def determinar_tiempo_sala(self, sala):
        hora_actual = 9 + (self.reloj_dia / 3600)
        
        # Mapeo de medias y desvíos/tolerancias según la hora (desde los parámetros)
        tiempos = self.parametros['salas'][sala]
        if 9 <= hora_actual < 12: media, desv = tiempos['9_12']
        elif 12 <= hora_actual < 14: media, desv = tiempos['12_14']
        elif 14 <= hora_actual < 18: media, desv = tiempos['14_18']
        else: media, desv = tiempos['18_22']

        if self.dist_salas == "Uniforme":

            tiempo, rnd = self.generar_uniforme(media - desv, media + desv)
            return tiempo, rnd, None
        else:
           
            return self.generar_normal(media, desv)

    # ------------------------------------------------------------------
    # Snapshot de TODO el sistema en el instante actual
    # ------------------------------------------------------------------
    def _snapshot_sistema(self, evento_actual):
        """
        Construye la fila del vector de estado con las 63 columnas base
        alineadas con la estructura de la planilla Excel de cátedra (TP SIM.xlsx),
        más los visitantes activos.
        """
        visitantes_snapshot = []
        for vis in self.visitantes_activos.values():
            visitantes_snapshot.append(vis.snapshot(self))

        v1_e1_est = self.ventanillas_empleados[1][0]['estado']
        v1_e1_fin = self.ventanillas_empleados[1][0]['fin_atencion']
        v1_e2_est = self.ventanillas_empleados[1][1]['estado']
        v1_e2_fin = self.ventanillas_empleados[1][1]['fin_atencion']
        
        v2_e1_est = self.ventanillas_empleados[2][0]['estado']
        v2_e1_fin = self.ventanillas_empleados[2][0]['fin_atencion']
        v2_e2_est = self.ventanillas_empleados[2][1]['estado']
        v2_e2_fin = self.ventanillas_empleados[2][1]['fin_atencion']

        s1_est = self.cerveza_servidores[0]['estado']
        s1_fin = self.cerveza_servidores[0]['fin_atencion']
        s2_est = self.cerveza_servidores[1]['estado']
        s2_fin = self.cerveza_servidores[1]['fin_atencion']

        def fmt_time(t):
            if t is None or t == "":
                return ""
            return round(t, 2)

        return {
            'Iteracion': self.iteracion,
            'Evento': evento_actual,
            'Reloj': round(self.reloj, 2),
            'Reloj_Global': round(self.reloj, 2),
            'Dia': self.dia_actual,
            'Hora_Aprox': self._formatear_hora(),

            # Llegadas A
            'RND1_Lleg_A': self.step_rnd1_lleg_a,
            'RND2_Lleg_A': self.step_rnd2_lleg_a,
            'Dur_Lleg_A': self.step_dur_lleg_a,
            'Prox_Lleg_A': fmt_time(self.eventos.get('Llegada_A')),

            # Llegadas B
            'RND1_Lleg_B': self.step_rnd1_lleg_b,
            'RND2_Lleg_B': self.step_rnd2_lleg_b,
            'Dur_Lleg_B': self.step_dur_lleg_b,
            'Prox_Lleg_B': fmt_time(self.eventos.get('Llegada_B')),

            # Llegadas C
            'RND1_Lleg_C': self.step_rnd1_lleg_c,
            'RND2_Lleg_C': self.step_rnd2_lleg_c,
            'Dur_Lleg_C': self.step_dur_lleg_c,
            'Prox_Lleg_C': fmt_time(self.eventos.get('Llegada_C')),

            # Brochures decisions
            'RND_Foll': self.step_rnd_foll,
            'Res_Foll': self.step_res_foll,
            'RND_Vent': self.step_rnd_vent,
            'Res_Vent': self.step_res_vent,
            'RND_T_Foll': self.step_rnd_t_foll,
            'Dur_T_Foll': self.step_dur_t_foll,

            # Ventanilla employees (Req. 2)
            'V1_E1_Est': v1_e1_est,
            'V1_E1_Fin': fmt_time(v1_e1_fin),
            'V1_E2_Est': v1_e2_est,
            'V1_E2_Fin': fmt_time(v1_e2_fin),
            'V2_E1_Est': v2_e1_est,
            'V2_E1_Fin': fmt_time(v2_e1_fin),
            'V2_E2_Est': v2_e2_est,
            'V2_E2_Fin': fmt_time(v2_e2_fin),

            'Cola_V1': len(self.ventanillas[1]['cola']),
            'Cola_V2': len(self.ventanillas[2]['cola']),

            # Painting
            'Personas_Pintura': self.personas_en_pintura,
            'RND_Tiempo_Pint': self.step_rnd_t_pint,
            'Dur_Tiempo_Pint': self.step_dur_t_pint,
            'Fin_Tiempo_Pint': fmt_time(self.step_fin_t_pint),

            # Photography decision & age
            'RND_Foto_Dec': self.step_rnd_foto_dec,
            'Res_Foto_Dec': self.step_res_foto_dec,
            'RND_Edad': self.step_rnd_edad,
            'Edad_Trunc': self.step_edad_trunc,
            'Es_Mayor': self.step_es_mayor,

            # Beer decision & service
            'RND_Cerv_Dec': self.step_rnd_cerv_dec,
            'Res_Cerv_Dec': self.step_res_cerv_dec,
            'Tpo_Tomar_RK': self.step_tpo_tomar_rk,
            'RND_Tpo_Servir': self.step_rnd_tpo_servir,
            'Tpo_Serv': self.step_tpo_serv,
            'Cola_Stand': len(self.cola_cerveza),

            # Beer servers (Req. 2)
            'S1_Est': s1_est,
            'S1_Fin': fmt_time(s1_fin),
            'S2_Est': s2_est,
            'S2_Fin': fmt_time(s2_fin),

            # Photography
            'Personas_Fotografia': self.personas_en_fotografia,
            'RND_Tiempo_Foto': self.step_rnd_tiempo_foto,
            'Dur_Tiempo_Foto': self.step_dur_tiempo_foto,
            'Fin_Tiempo_Foto': fmt_time(self.step_fin_tiempo_foto),

            # Metric accumulators
            'AC_Tpo_Espera_V1': round(self.acumulador_espera_v1, 2),
            'Cont_Clientes_V1': self.visitantes_esperaron_v1,
            'AC_Tpo_Espera_V2': round(self.acumulador_espera_v2, 2),
            'Cont_Clientes_V2': self.visitantes_esperaron_v2,
            'AC_Tpo_Perm_Sistema': round(self.acumulador_tiempo_permanencia, 2),
            'Cont_Visit_Salen': self.visitantes_finalizados,
            'Cont_Birras': self.metrica_total_cervezas,
            'AC_Edades': round(self.metrica_suma_edades_cerveza, 2),
            'Cont_Directo_Muestra': self.contador_directo_muestra,

            'Visitantes_Activos_Detalle': visitantes_snapshot,
            'Cantidad_Visitantes_Activos': len(visitantes_snapshot),
        }

    def _formatear_hora(self):
        total_seg = self.reloj_dia
        horas = int(9 + total_seg // 3600)
        minutos = int((total_seg % 3600) // 60)
        segundos = int(total_seg % 60)
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"

    def formatear_hora_reloj(self, T):
        if T is None:
            return ""
        relative_seg = T - self.reloj + self.reloj_dia
        horas = int(9 + relative_seg // 3600)
        minutos = int((relative_seg % 3600) // 60)
        segundos = int(relative_seg % 60)
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    def simular(self, iteraciones_max, desde_j, cantidad_i):
        while self.iteracion < iteraciones_max:

            evento_actual, tiempo_evento = min(self.eventos.items(), key=lambda x: x[1])
            # --- CORTE POR TIEMPO X ---
            if self.tiempo_x > 0 and tiempo_evento > self.tiempo_x:
                self._clear_step_variables()
                fila_final = self._snapshot_sistema("Fin por Instante X")
                fila_final['Visitantes_Activos_Detalle'] = []  # Sin temporales
                self.vector_estado.append(fila_final)
                break
            avance = tiempo_evento - self.reloj
            self.reloj = tiempo_evento
            self.reloj_dia += avance

            # --- FIN DE JORNADA (22 hs) ---
            if evento_actual == 'Fin_Jornada':
                self._clear_step_variables()
                # Guardamos la fila final del día (sin objetos temporales,
                # tal como pide la consigna para la fila del instante X)
                fila_final = self._snapshot_sistema(evento_actual)
                fila_final['Visitantes_Activos_Detalle'] = []  # sin temporales
                self.vector_estado.append(fila_final)

                if self.dia_actual >= self.dias_a_simular:
                    ultima_fila_guardada = True
                    break
                else:
                    self._reiniciar_para_nuevo_dia()
                    self.iteracion += 1
                    continue

            # Limpiar RNDs y duraciones para la iteración actual
            self._clear_step_variables()

            # --- LLEGADAS (PUERTAS A, B, C) ---
            if evento_actual in ('Llegada_A', 'Llegada_B', 'Llegada_C'):
                puerta = evento_actual[-1]
                clave_param = {'A': 'puerta_a', 'B': 'puerta_b', 'C': 'puerta_c'}[puerta]
                media, desv = self.parametros[clave_param]
                t_next, rnd1, rnd2 = self.generar_normal(media, desv)
                
                if puerta == 'A':
                    self.step_rnd1_lleg_a = round(rnd1, 4)
                    self.step_rnd2_lleg_a = round(rnd2, 4)
                    self.step_dur_lleg_a = round(t_next, 2)
                elif puerta == 'B':
                    self.step_rnd1_lleg_b = round(rnd1, 4)
                    self.step_rnd2_lleg_b = round(rnd2, 4)
                    self.step_dur_lleg_b = round(t_next, 2)
                elif puerta == 'C':
                    self.step_rnd1_lleg_c = round(rnd1, 4)
                    self.step_rnd2_lleg_c = round(rnd2, 4)
                    self.step_dur_lleg_c = round(t_next, 2)
                    
                self.prox_llegadas_rnd[puerta] = f"{rnd1:.4f}, {rnd2:.4f}"
                self.eventos[evento_actual] = self.reloj + t_next

                self.visitantes_totales += 1
                media_edad = self.parametros.get('edad_media', 30)
                nuevo = Visitante(self.visitantes_totales, self.reloj, puerta, media_edad)
                self.visitantes_activos[nuevo.id] = nuevo
                self.visitantes_historicos[nuevo.id] = nuevo

                rnd_decision = random.random()
                self.step_rnd_foll = round(rnd_decision, 4)

                if rnd_decision <= self.prob_folletos:
                    nuevo.fue_a_folletos = True
                    self.step_res_foll = "SI"
                    
                    rnd_vent = random.random()
                    self.step_rnd_vent = round(rnd_vent, 4)
                    v_elegida = 1 if rnd_vent < 0.5 else 2
                    nuevo.ventanilla = v_elegida
                    self.step_res_vent = v_elegida

                    if self._empleado_ventanilla_libre(v_elegida):
                        media_f, desv_f = self.parametros['folletos']
                        t_folletos, rnd_f = self.generar_uniforme(media_f - desv_f, media_f + desv_f)
                        self.step_rnd_t_foll = round(rnd_f, 4)
                        self.step_dur_t_foll = round(t_folletos, 2)
                        
                        nuevo.rnd_tiempo_folletos = rnd_f
                        nuevo.duracion_folletos = t_folletos
                        nuevo.fin_folletos_reloj = self.reloj + t_folletos
                        nuevo.estado = "En ventanilla"
                        nuevo.sala_actual = f"Ventanilla {v_elegida}"
                        nuevo.destino = "Pintura"
                        
                        self._iniciar_servicio_ventanilla(v_elegida, nuevo, t_folletos)
                        self.eventos[f'Fin_Folletos_{v_elegida}_{nuevo.id}'] = self.reloj + t_folletos
                        self.metrica_total_folletos += 1
                    else:
                        nuevo.inicio_cola_informes = self.reloj
                        nuevo.estado = "En cola de informes"
                        nuevo.sala_actual = f"Cola Ventanilla {v_elegida}"
                        nuevo.destino = f"Ventanilla {v_elegida}"
                        self.ventanillas[v_elegida]['cola'].append(nuevo)
                else:
                    nuevo.fue_a_folletos = False
                    self.step_res_foll = "NO"
                    self.contador_directo_muestra += 1
                    
                    nuevo.estado = "En Pintura"
                    nuevo.sala_actual = "Pintura"
                    nuevo.destino = "Por decidir"
                    nuevo.inicio_pintura = self.reloj
                    t_pintura, rnd_p1, rnd_p2 = self.determinar_tiempo_sala("Pintura")
                    
                    self.step_rnd_t_pint = f"{rnd_p1:.4f}, {rnd_p2:.4f}" if rnd_p2 is not None else f"{rnd_p1:.4f}"
                    self.step_dur_t_pint = round(t_pintura, 2)
                    self.step_fin_t_pint = round(self.reloj + t_pintura, 2)
                    
                    nuevo.rnd_tiempo_pintura = (rnd_p1, rnd_p2)
                    nuevo.duracion_pintura = t_pintura
                    nuevo.fin_pintura_reloj = self.reloj + t_pintura
                    self.eventos[f'Fin_Pintura_{nuevo.id}'] = self.reloj + t_pintura
                    self.personas_en_pintura += 1

            # --- SALIDA DE FOLLETOS ---
            elif evento_actual.startswith('Fin_Folletos_'):
                partes = evento_actual.split('_')
                v_id = int(partes[2])
                id_vis = int(partes[-1])
                visitante = self.visitantes_activos[id_vis]

                visitante.fin_cola_informes = self.reloj
                self._finalizar_servicio_ventanilla(v_id, id_vis)

                # Pasamos el visitante a pintura
                visitante.estado = "En Pintura"
                visitante.sala_actual = "Pintura"
                visitante.destino = "Por decidir"
                visitante.inicio_pintura = self.reloj
                t_pintura, rnd_p1, rnd_p2 = self.determinar_tiempo_sala("Pintura")
                
                self.step_rnd_t_pint = f"{rnd_p1:.4f}, {rnd_p2:.4f}" if rnd_p2 is not None else f"{rnd_p1:.4f}"
                self.step_dur_t_pint = round(t_pintura, 2)
                self.step_fin_t_pint = round(self.reloj + t_pintura, 2)
                
                visitante.rnd_tiempo_pintura = (rnd_p1, rnd_p2)
                visitante.duracion_pintura = t_pintura
                visitante.fin_pintura_reloj = self.reloj + t_pintura
                self.eventos[f'Fin_Pintura_{visitante.id}'] = self.reloj + t_pintura
                self.personas_en_pintura += 1

                # Atender al siguiente en cola si hay
                if len(self.ventanillas[v_id]['cola']) > 0:
                    siguiente = self.ventanillas[v_id]['cola'].pop(0)

                    tiempo_esperado = self.reloj - siguiente.inicio_cola_informes
                    if v_id == 1:
                        self.acumulador_espera_v1 += tiempo_esperado
                        self.visitantes_esperaron_v1 += 1
                    else:
                        self.acumulador_espera_v2 += tiempo_esperado
                        self.visitantes_esperaron_v2 += 1

                    siguiente.estado = "En ventanilla"
                    siguiente.sala_actual = f"Ventanilla {v_id}"
                    siguiente.destino = "Pintura"
                    
                    media_f, desv_f = self.parametros['folletos']
                    t_folletos, rnd_f = self.generar_uniforme(media_f - desv_f, media_f + desv_f)
                    
                    self.step_rnd_t_foll = round(rnd_f, 4)
                    self.step_dur_t_foll = round(t_folletos, 2)
                    
                    siguiente.rnd_tiempo_folletos = rnd_f
                    siguiente.duracion_folletos = t_folletos
                    siguiente.fin_folletos_reloj = self.reloj + t_folletos
                    
                    self._iniciar_servicio_ventanilla(v_id, siguiente, t_folletos)
                    self.eventos[f'Fin_Folletos_{v_id}_{siguiente.id}'] = self.reloj + t_folletos
                    self.metrica_total_folletos += 1

            # --- SALIDA DE PINTURA ---
            elif evento_actual.startswith('Fin_Pintura_'):
                id_vis = int(evento_actual.split('_')[-1])
                visitante = self.visitantes_activos[id_vis]
                visitante.fin_pintura = self.reloj
                self.personas_en_pintura -= 1

                rnd_foto = random.random()
                self.step_rnd_foto_dec = round(rnd_foto, 4)

                if rnd_foto <= self.prob_fotografia:
                    visitante.fue_a_fotografia = True
                    self.step_res_foto_dec = "SI"
                    self.metrica_total_fotografia += 1
                    self.personas_en_fotografia += 1
                    
                    # Edad
                    self.step_rnd_edad = round(visitante.rnd_edad, 4)
                    self.step_edad_trunc = visitante.edad
                    self.step_es_mayor = "SI" if visitante.edad >= 18 else "NO"
                    
                    if visitante.edad >= 18:
                        rnd_cerveza = random.random()
                        self.step_rnd_cerv_dec = round(rnd_cerveza, 4)
                        
                        if rnd_cerveza <= self.prob_cerveza:
                            visitante.tomo_cerveza = True
                            self.step_res_cerv_dec = "SI"
                            
                            if self._servidor_cerveza_libre():
                                min_c, max_c = self.parametros['cerveza']
                                t_servicio, rnd_s = self.generar_uniforme(min_c, max_c)
                                self.step_rnd_tpo_servir = round(rnd_s, 4)
                                self.step_tpo_serv = round(t_servicio, 2)
                                
                                visitante.rnd_tiempo_cerveza = rnd_s
                                visitante.duracion_cerveza = t_servicio
                                visitante.fin_cerveza_reloj = self.reloj + t_servicio
                                visitante.estado = "Siendo atendido (cerveza)"
                                visitante.sala_actual = "Stand Cerveza"
                                visitante.destino = "Degustación Cerveza"
                                visitante.inicio_cerveza = self.reloj
                                
                                self._iniciar_servicio_cerveza(visitante, t_servicio)
                                self.eventos[f'Fin_Servicio_Cerveza_{visitante.id}'] = self.reloj + t_servicio
                            else:
                                visitante.inicio_cola_cerveza = self.reloj
                                visitante.estado = "En cola de cerveza"
                                visitante.sala_actual = "Cola Cerveza"
                                visitante.destino = "Stand Cerveza"
                                self.cola_cerveza.append(visitante)
                                self.max_cola_cerveza = max(self.max_cola_cerveza, len(self.cola_cerveza))
                        else:
                            visitante.tomo_cerveza = False
                            self.step_res_cerv_dec = "NO"
                            
                            # Va directo a fotografía
                            self.personas_en_fotografia += 1
                            visitante.estado = "En Fotografia"
                            visitante.sala_actual = "Fotografia"
                            visitante.destino = "Salida"
                            visitante.inicio_fotografia = self.reloj
                            t_foto, rnd_foto1, rnd_foto2 = self.determinar_tiempo_sala("Fotografia")
                            
                            self.step_rnd_tiempo_foto = f"{rnd_foto1:.4f}, {rnd_foto2:.4f}" if rnd_foto2 is not None else f"{rnd_foto1:.4f}"
                            self.step_dur_tiempo_foto = round(t_foto, 2)
                            self.step_fin_tiempo_foto = round(self.reloj + t_foto, 2)
                            
                            visitante.rnd_tiempo_fotografia = (rnd_foto1, rnd_foto2)
                            visitante.duracion_fotografia = t_foto
                            visitante.fin_fotografia_reloj = self.reloj + t_foto
                            self.eventos[f'Fin_Fotografia_{visitante.id}'] = self.reloj + t_foto
                    else:
                        # Menor de edad
                        self.step_rnd_cerv_dec = ""
                        self.step_res_cerv_dec = "NO (Menor)"
                        visitante.tomo_cerveza = False
                        
                        # Va directo a fotografía
                        self.personas_en_fotografia += 1
                        visitante.estado = "En Fotografia"
                        visitante.sala_actual = "Fotografia"
                        visitante.destino = "Salida"
                        visitante.inicio_fotografia = self.reloj
                        t_foto, rnd_foto1, rnd_foto2 = self.determinar_tiempo_sala("Fotografia")
                        
                        self.step_rnd_tiempo_foto = f"{rnd_foto1:.4f}, {rnd_foto2:.4f}" if rnd_foto2 is not None else f"{rnd_foto1:.4f}"
                        self.step_dur_tiempo_foto = round(t_foto, 2)
                        self.step_fin_tiempo_foto = round(self.reloj + t_foto, 2)
                        
                        visitante.rnd_tiempo_fotografia = (rnd_foto1, rnd_foto2)
                        visitante.duracion_fotografia = t_foto
                        visitante.fin_fotografia_reloj = self.reloj + t_foto
                        self.eventos[f'Fin_Fotografia_{visitante.id}'] = self.reloj + t_foto
                else:
                    visitante.fue_a_fotografia = False
                    self.step_res_foto_dec = "NO"
                    
                    visitante.estado = "Salio"
                    visitante.sala_actual = "Fuera"
                    visitante.destino = "Salida"
                    visitante.reloj_salida = self.reloj
                    self.metrica_abandonos_post_pintura += 1

            # --- LE ENTREGAN LA CERVEZA (empieza la degustación) ---
            elif evento_actual.startswith('Fin_Servicio_Cerveza_'):
                id_vis = int(evento_actual.split('_')[-1])
                visitante = self.visitantes_activos[id_vis]
                visitante.fin_cerveza = self.reloj
                self.metrica_total_cervezas += 1
                self.metrica_suma_edades_cerveza += visitante.edad
                
                self._finalizar_servicio_cerveza(id_vis)

                # Atender al siguiente en la cola stand cerveza si hay
                if len(self.cola_cerveza) > 0:
                    siguiente = self.cola_cerveza.pop(0)
                    min_c, max_c = self.parametros['cerveza']
                    t_servicio, rnd_s = self.generar_uniforme(min_c, max_c)
                    
                    self.step_rnd_tpo_servir = round(rnd_s, 4)
                    self.step_tpo_serv = round(t_servicio, 2)
                    
                    siguiente.rnd_tiempo_cerveza = rnd_s
                    siguiente.duracion_cerveza = t_servicio
                    siguiente.fin_cerveza_reloj = self.reloj + t_servicio
                    siguiente.estado = "Siendo atendido (cerveza)"
                    siguiente.sala_actual = "Stand Cerveza"
                    siguiente.destino = "Degustación Cerveza"
                    siguiente.inicio_cerveza = self.reloj
                    
                    self._iniciar_servicio_cerveza(siguiente, t_servicio)
                    self.eventos[f'Fin_Servicio_Cerveza_{siguiente.id}'] = self.reloj + t_servicio

                # Iniciar la degustación de cerveza
                tiempo_degustacion, tabla_rk = calcular_tiempo_degustacion(visitante.edad, self.paso_h)
                self.step_tpo_tomar_rk = round(tiempo_degustacion, 2)
                
                self.tablas_rk_generadas[
                    f"Visitante {visitante.id} (Edad: {visitante.edad}, Dia {self.dia_actual})"
                ] = tabla_rk

                visitante.estado = "Degustando cerveza"
                visitante.sala_actual = "Stand Cerveza"
                visitante.destino = "Fotografía"
                visitante.inicio_degustacion = self.reloj
                self.eventos[f'Fin_Degustacion_{visitante.id}'] = self.reloj + tiempo_degustacion

            # --- TERMINA DE BEBER ---
            elif evento_actual.startswith('Fin_Degustacion_'):
                id_vis = int(evento_actual.split('_')[-1])
                visitante = self.visitantes_activos[id_vis]
                visitante.fin_degustacion = self.reloj

                self.personas_en_fotografia += 1
                visitante.estado = "En Fotografia"
                visitante.sala_actual = "Fotografia"
                visitante.destino = "Salida"
                visitante.inicio_fotografia = self.reloj
                t_foto, rnd_foto1, rnd_foto2 = self.determinar_tiempo_sala("Fotografia")
                
                self.step_rnd_tiempo_foto = f"{rnd_foto1:.4f}, {rnd_foto2:.4f}" if rnd_foto2 is not None else f"{rnd_foto1:.4f}"
                self.step_dur_tiempo_foto = round(t_foto, 2)
                self.step_fin_tiempo_foto = round(self.reloj + t_foto, 2)
                
                visitante.rnd_tiempo_fotografia = (rnd_foto1, rnd_foto2)
                visitante.duracion_fotografia = t_foto
                visitante.fin_fotografia_reloj = self.reloj + t_foto
                self.eventos[f'Fin_Fotografia_{visitante.id}'] = self.reloj + t_foto

            # --- FIN DE RECORRIDO (sale de fotografía) ---
            elif evento_actual.startswith('Fin_Fotografia_'):
                id_vis = int(evento_actual.split('_')[-1])
                visitante = self.visitantes_activos[id_vis]
                visitante.fin_fotografia = self.reloj
                visitante.estado = "Salio"
                visitante.sala_actual = "Fuera"
                visitante.destino = "Salida"
                visitante.reloj_salida = self.reloj
                self.personas_en_fotografia -= 1

                tiempo_permanencia = self.reloj - visitante.reloj_llegada
                self.acumulador_tiempo_permanencia += tiempo_permanencia
                self.visitantes_finalizados += 1

                del self.visitantes_activos[visitante.id]

            # --- CONTROL CADA 15 MINUTOS ---
            elif evento_actual == 'Control_15min':
                self.eventos['Control_15min'] = self.reloj + (15 * 60)
                self.metricas_15_min.append({
                    'Dia': self.dia_actual,
                    'Hora': self._formatear_hora(),
                    'Reloj_Global': round(self.reloj, 2),
                    'En_Pintura': self.personas_en_pintura,
                    'En_Fotografia': self.personas_en_fotografia,
                })

            # Limpieza de eventos puntuales ya disparados (los recurrentes
            # ya fueron reprogramados arriba con la misma clave)
            eventos_recurrentes = ('Llegada_A', 'Llegada_B', 'Llegada_C', 'Control_15min', 'Fin_Jornada')
            if evento_actual not in eventos_recurrentes and evento_actual in self.eventos:
                del self.eventos[evento_actual]

            # --- GUARDADO DE LA FILA EN EL VECTOR DE ESTADO ---
            fila = self._snapshot_sistema(evento_actual)
            self.vector_estado.append(fila)

            self.iteracion += 1

        return self.vector_estado

    # ------------------------------------------------------------------
    # Resumen de métricas, listo para mostrar en la interfaz
    # ------------------------------------------------------------------
    def obtener_metricas(self):
        prom_permanencia = (
            self.acumulador_tiempo_permanencia / self.visitantes_finalizados
            if self.visitantes_finalizados > 0 else 0.0
        )
        prom_cola_v1 = (
            self.acumulador_espera_v1 / self.visitantes_esperaron_v1
            if self.visitantes_esperaron_v1 > 0 else 0.0
        )
        prom_cola_v2 = (
            self.acumulador_espera_v2 / self.visitantes_esperaron_v2
            if self.visitantes_esperaron_v2 > 0 else 0.0
        )
        prom_edad_cerveza = (
            self.metrica_suma_edades_cerveza / self.metrica_total_cervezas
            if self.metrica_total_cervezas > 0 else 0.0
        )

        return {
            'prom_permanencia': prom_permanencia,
            'prom_cola_v1': prom_cola_v1,
            'prom_cola_v2': prom_cola_v2,
            'visitantes_totales': self.visitantes_totales,
            'visitantes_finalizados': self.visitantes_finalizados,
            'total_folletos': self.metrica_total_folletos,
            'total_cervezas': self.metrica_total_cervezas,
            'prom_edad_cerveza': prom_edad_cerveza,
            'total_fotografia': self.metrica_total_fotografia,
            'abandonos_post_pintura': self.metrica_abandonos_post_pintura,
            'max_cola_cerveza': self.max_cola_cerveza,
        }
