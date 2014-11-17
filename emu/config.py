#!/usr/bin/env python
# -*- coding: utf-8 -*-

config = {
    'EPROM': {
        'razon_social': "CARLOS, AUGUSTO Y GERMAN ROCCASALVA S.H.",
        'cuit': "30-71128142-4",
        'ib': "0619591",
        'inicio': "02-09-05",
        'pv': "3",
        'last_counter_A': 365,
        'last_counter_B': 790,
    },
    # Maximo 40 caracteres 
    # 0xf4 - Doble ancho 20 caracteres
    'FANTASY': {
        1: "\xf4      RIO PLOMO     ",
        2: "",
    },
    'HEADERTRAILER': {
        # encabezado
         1: "COLON 125 GODOY CRUZ MENDOZA (M5501ARC)",
         2: "ESTAB: 05-0619591-02 - S.TIMB: 01 S.C.",
         3: "",
         4: "",
        # luego de comprador
         5: "", # No en 615
         6: "", # No en 615
         7: "", # No en 615
         8: "",
         9: "",
        10: "",
        # cola
        11: "",
        12: "",
        13: "",
        14: "",
        # No se usa
        15: "",
        16: "",
        17: "",
        18: "",
        19: "",
        20: "",
    },
}
