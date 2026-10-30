
from flask import Flask, render_template, jsonify
from collections import Counter
from datetime import datetime
import requests
import unicodedata
import re

# ==========================================
# CONFIGURACIÓN
# ==========================================

app = Flask(__name__, template_folder=".")

URL = "https://www.datos.gov.co/resource/3jdh-nmwu.json"
LIMITE = 2000


# ==========================================
# NORMALIZACIÓN DE CAMPOS
# ==========================================

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto))

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    return re.sub(r"[^a-z0-9]", "", texto.lower())


def encontrar_campo(registros, opciones):
    if not registros:
        return None

    campos = {
        normalizar(clave): clave
        for registro in registros[:100]
        for clave in registro.keys()
    }

    for opcion in opciones:
        clave = campos.get(normalizar(opcion))

        if clave:
            return clave

    return None


# ==========================================
# CONSUMIR API DATOS ABIERTOS
# ==========================================

def consultar_capturas():
    parametros = {
        "$limit": LIMITE
    }

    respuesta = requests.get(
        URL,
        params=parametros,
        timeout=30
    )

    respuesta.raise_for_status()

    datos = respuesta.json()

    if not isinstance(datos, list):
        raise ValueError("La API devolvió un formato inesperado.")

    return datos


# ==========================================
# PROCESAMIENTO DE DATOS
# ==========================================

def obtener_estadisticas(registros):

    campos = {
        "departamento": encontrar_campo(
            registros,
            ["departamento"]
        ),

        "municipio": encontrar_campo(
            registros,
            ["municipio", "ciudad"]
        ),

        "delito": encontrar_campo(
            registros,
            [
                "descripcion_conducta_captura",
                "delito",
                "descripcion_conducta",
                "conducta"
            ]
        ),

        "fecha": encontrar_campo(
            registros,
            [
                "fecha_hecho",
                "fecha_captura",
                "fecha"
            ]
        ),

        "cantidad": encontrar_campo(
            registros,
            ["cantidad"]
        )
    }

    # --------------------------------------
    # OBTENER CANTIDAD DE CAPTURAS
    # --------------------------------------

    def obtener_cantidad(registro):
        campo = campos["cantidad"]

        if not campo:
            return 1

        try:
            return int(registro.get(campo) or 0)
        except (ValueError, TypeError):
            return 0

    # --------------------------------------
    # TOTAL DE CAPTURAS
    # --------------------------------------

    total_capturas = sum(
        obtener_cantidad(registro)
        for registro in registros
    )

    # --------------------------------------
    # DEPARTAMENTOS Y MUNICIPIOS
    # --------------------------------------

    def valores(tipo):
        campo = campos[tipo]

        if not campo:
            return []

        return [
            str(registro[campo]).strip()
            for registro in registros
            if registro.get(campo)
        ]

    departamentos = valores("departamento")
    municipios = valores("municipio")

    # --------------------------------------
    # RANKING POR DEPARTAMENTO O DELITO
    # --------------------------------------

    def ranking(tipo, cantidad=10):
        campo = campos[tipo]

        if not campo:
            return []

        contador = Counter()

        for registro in registros:
            nombre = registro.get(campo)

            if nombre:
                contador[str(nombre).strip()] += (
                    obtener_cantidad(registro)
                )

        return [
            {
                "nombre": nombre,
                "total": total
            }
            for nombre, total in contador.most_common(cantidad)
        ]

    # --------------------------------------
    # ESTADÍSTICAS POR MES
    # --------------------------------------

    meses = Counter()

    if campos["fecha"]:

        for registro in registros:
            fecha = str(
                registro.get(campos["fecha"], "")
            ).strip()

            fecha_objeto = None

            formatos = [
                "%d/%m/%Y",
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S"
            ]

            for formato in formatos:
                try:
                    fecha_objeto = datetime.strptime(
                        fecha, formato
                    )
                    break
                except ValueError:
                    continue

            if fecha_objeto:
                mes = fecha_objeto.strftime("%Y-%m")

                meses[mes] += obtener_cantidad(
                    registro
                )

    # --------------------------------------
    # RESPUESTA PARA EL HTML
    # --------------------------------------

    return {
        "total": total_capturas,
        "registros": len(registros),
        "limite": LIMITE,

        "campos": campos,

        "departamentos": len(set(departamentos)),
        "municipios": len(set(municipios)),

        "por_departamento": ranking("departamento"),
        "por_delito": ranking("delito"),

        "por_mes": [
            {
                "nombre": mes,
                "total": total
            }
            for mes, total in sorted(meses.items())
        ]
    }


# ==========================================
# RUTAS FLASK
# ==========================================

@app.route("/")
def inicio():
    return render_template("prueba.html")


@app.route("/api/estadisticas")
def estadisticas():

    try:
        registros = consultar_capturas()

        resultado = obtener_estadisticas(registros)

        return jsonify(resultado)

    except requests.exceptions.RequestException as error:
        return jsonify({
            "error": "No fue posible consultar Datos Abiertos Colombia.",
            "detalle": str(error)
        }), 502

    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 500


# ==========================================
# RUTA PARA VERIFICAR DATOS
# ==========================================

@app.route("/api/verificar")
def verificar():

    try:
        registros = consultar_capturas()

        return jsonify({
            "total_registros": len(registros),

            "columnas": (
                list(registros[0].keys())
                if registros else []
            ),

            "primer_registro": (
                registros[0]
                if registros else {}
            )
        })

    except (requests.exceptions.RequestException, ValueError) as error:
        return jsonify({
            "error": str(error)
        }), 502


# ==========================================
# INICIAR SERVIDOR
# ==========================================

if __name__ == "__main__":
    print("=" * 55)
    print("DASHBOARD DE CAPTURAS")
    print("POLICÍA NACIONAL DE COLOMBIA")
    print("=" * 55)

    print("Servidor: http://127.0.0.1:5000")
    print("API: /api/estadisticas")
    print("Verificación: /api/verificar")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
