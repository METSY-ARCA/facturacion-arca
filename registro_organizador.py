import base64
import requests
import os
from flask import request, redirect

BASE_URL = "https://www.facturapi.io/v2/organizations"

def registrar_organizador():
    razon_social = request.form.get("org_razon_social")
    rfc = request.form.get("org_rfc")
    contrasena = request.form.get("org_contrasena")
    archivo_cer = request.files.get("archivo_cer")
    archivo_key = request.files.get("archivo_key")

    if not (razon_social and rfc and contrasena and archivo_cer and archivo_key):
        return "Faltan datos para registrar el organizador.", 400

    try:
        cer_b64 = base64.b64encode(archivo_cer.read()).decode('utf-8')
        key_b64 = base64.b64encode(archivo_key.read()).decode('utf-8')

        payload = {
            "legal_name": razon_social,
            "tax_id": rfc,
            "certificates": {
                "cer": cer_b64,
                "key": key_b64,
                "password": contrasena
            }
        }

        headers = {
            "Authorization": f"Bearer {os.getenv('FACTURAPI_KEY')}",
            "Content-Type": "application/json"
        }

        response = requests.post(BASE_URL, headers=headers, json=payload)
        response.raise_for_status()

        return "Organizador creado exitosamente. Puedes regresar a la página anterior."
    except Exception as e:
        print("Error al registrar organizador:", e)
        return f"Error al registrar organizador: {str(e)}", 500