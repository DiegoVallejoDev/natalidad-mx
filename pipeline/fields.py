"""Alias de campos por vintage SINAC y definiciones de cohortes.

SINAC (Secretaría de Salud / DGIS) publica nacimientos en tres layouts:
- 2010-2016 : snake_case, residencia como NOMBRES literales
- 2017-2019 : abreviado SCREAMING, claves SaS numéricas
- 2020-2025 : SCREAMING largo, claves SaS numéricas
"""

# campo canónico -> aliases posibles (lowercase, sin comillas)
ALIASES = {
    "fecha_nacimiento": [
        "fechanacimiento", "fecha_nacimiento_nac_vivo", "fech_nach",
        "fecha_nacimiento", "fech_nac", "fecha_nac",
    ],
    "ent_residencia": [
        "entidadresidencia", "entidad_residencia_madre", "ent_res",
        "entidad_residencia", "ent_residencia_madre",
    ],
    "mun_residencia": [
        "municipioresidencia", "municipio_residencia_madre", "mpo_res",
        "municipio_residencia", "mpo_residencia_madre",
    ],
    "edad_madre": ["edad", "edad_madre", "edadm"],
    "ent_parto": [
        "entidadfederativaparto", "entidad_nacimiento", "ent_nac",
        "entidad_parto",
    ],
    "mun_parto": [
        "municipioparto", "municipio_nacimiento", "mpo_nac",
        "municipio_parto",
    ],
}

# cohortes de edad materna: (id, etiqueta, min, max)
COHORTES = [
    ("adol",   "Adolescentes (<20)", None, 19),
    ("e20_24", "20–24",            20,   24),
    ("e25_29", "25–29",            25,   29),
    ("e30_34", "30–34",            30,   34),
    ("e35_39", "35–39",            35,   39),
    ("e40mas", "40+",              40,  120),
    ("ne",     "No especificada",  None, None),  # edad inválida/faltante
]
COHORDER = [c[0] for c in COHORTES]

# claves SaS de entidad que NO son mapeables a INEGI (33-35 extranjero, 36 EUM, 99 NE)
ENT_SAS_EXTRANJERO = {"33", "34", "35"}
ENT_SAS_NOESP = {"99", "98", "36"}
MUN_NOESP = {"999", "998", "997"}

# estados "extranjero" que pueden aparecer como nombre literal (layout viejo)
NOMBRE_ENT_EXTRANJERO = {
    "ESTADOS UNIDOS DE NORTEAMERICA", "ESTADOS UNIDOS",
    "OTROS PAISES DE LATINOAMERICA", "OTROS PAISES",
    "EN EL EXTRANJERO", "EXTRANJERO",
}
NOMBRE_ENT_NOESP = {"NO ESPECIFICADO", "NE", "SE IGNORA", "IGNORADO"}

UMBRAL_BAJA_ESCALA = 10_000  # RF-03.1: poblacion < 10k -> flag
JALISCO = "14"
ANIO_MIN, ANIO_MAX = 2010, 2030


def norm_txt(s: str) -> str:
    """Normaliza nombre de entidad/municipio para emparejamiento: sin acentos,
    mayúsculas, sin puntuación, espacios colapsados."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Z0-9 ]", " ", s.upper())
    return re.sub(r"\s+", " ", s).strip()
