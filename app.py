from flask import Flask, render_template, request
import requests
import os
from datetime import datetime
import json
from dotenv import load_dotenv
from registro_organizador import registrar_organizador

# Cargar variables de entorno desde .env
load_dotenv()

app = Flask(__name__)

# Clave segura de Facturapi (requiere variable de entorno)
API_KEY = os.getenv("FACTURAPI_KEY")
if not API_KEY:
    raise ValueError("La clave de Facturapi no está configurada.")

BASE_URL = "https://www.facturapi.io/v2"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

@app.before_request
def proteger_endpoints():
    if request.endpoint in ["generar_factura", "previsualizar_factura"]:
        token = request.form.get("token") or request.args.get("token")
        if token != os.getenv("SECURE_TOKEN"):
            return "🔒 Acceso no autorizado", 403

def crear_cliente(legal_name, tax_id, postal_code, regimen_fiscal):
    url = f"{BASE_URL}/customers"
    datos_cliente = {
        "legal_name": legal_name,
        "tax_id": tax_id,
        "tax_system": regimen_fiscal,
        "address": {"zip": postal_code, "country": "MEX"}
    }
    try:
        respuesta = requests.post(url, headers=HEADERS, json=datos_cliente)
        respuesta.raise_for_status()
        return respuesta.json()["id"]
    except requests.exceptions.RequestException as e:
        print("Error al crear cliente:", e)
        return None

def crear_producto(description, price, impuestos):
    url = f"{BASE_URL}/products"
    datos_producto = {
        "description": description,
        "product_key": "84111506",
        "price": price,
        "unit": "H87",
        "tax_included": True,
        "taxes": impuestos
    }
    try:
        respuesta = requests.post(url, headers=HEADERS, json=datos_producto)
        respuesta.raise_for_status()
        return respuesta.json()["id"]
    except requests.exceptions.RequestException as e:
        print("Error al crear producto:", e)
        return None

def crear_factura(cliente_id, producto_id, quantity, cfdi_use, tipo_cfdi, forma_pago, moneda, tipo_cambio):
    url = f"{BASE_URL}/invoices"
    datos_factura = {
        "customer": cliente_id,
        "items": [{"quantity": quantity, "product": producto_id}],
        "payment_form": forma_pago,
        "use": cfdi_use,
        "type": tipo_cfdi,
        "series": "A",
        "folio_number": 1,
        "currency": moneda or "MXN"
    }
    if moneda and moneda != "MXN":
        try:
            datos_factura["exchange_rate"] = float(tipo_cambio)
        except ValueError:
            datos_factura["exchange_rate"] = 1.0
    try:
        respuesta = requests.post(url, headers=HEADERS, json=datos_factura)
        respuesta.raise_for_status()
        return respuesta.json().get("pdf_url")
    except requests.exceptions.RequestException as e:
        print("Error al crear factura:", e)
        return None

@app.route("/")
def index():
    return render_template("facturacion_facturapi_ui.html")

@app.route("/generar_factura", methods=["POST"])
def generar_factura():
    try:
        legal_name = request.form['legal_name']
        tax_id = request.form['tax_id']
        postal_code = request.form['postal_code']
        cfdi_use = request.form['cfdi_use']
        tipo_cfdi = request.form['tipo_cfdi']
        forma_pago = request.form['forma_pago']
        moneda = request.form.get('moneda', 'MXN')
        tipo_cambio = request.form.get('tipo_cambio', '1.0')
        regimen_fiscal = "616" if tax_id.upper() == "XAXX010101000" else request.form['regimen_fiscal']

        cliente_id = crear_cliente(legal_name, tax_id, postal_code, regimen_fiscal)
        if not cliente_id:
            return "Error al crear el cliente."

        impuestos = []
        try:
            tasa_iva = float(request.form.get('iva_tasa', 0.0))
        except ValueError:
            tasa_iva = 0.0
        try:
            tasa_isr = float(request.form.get('isr_tasa', 0.0))
        except ValueError:
            tasa_isr = 0.0
        try:
            tasa_ieps = float(request.form.get('ieps_tasa', 0.0))
        except ValueError:
            tasa_ieps = 0.0

        if 'usar_iva' in request.form:
            tipo = request.form.get('iva_tipo', 'trasladado')
            impuestos.append({"type": "IVA", "rate": tasa_iva, "withholding": tipo == "retenido"})
        if 'usar_isr' in request.form:
            impuestos.append({"type": "ISR", "rate": tasa_isr, "withholding": True})
        if 'usar_ieps' in request.form:
            impuestos.append({"type": "IEPS", "rate": tasa_ieps, "withholding": False})

        if 'agregar_producto' in request.form and request.form['agregar_producto'] == "1":
            description = request.form['description']
            price = float(request.form['price'])
            quantity = int(request.form['quantity'])
            if not description or price <= 0 or quantity <= 0:
                return "Error: Datos del producto inválidos."
            producto_id = crear_producto(description, price, impuestos)
        else:
            producto_id = crear_producto("Servicio general", 100.00, impuestos)
            quantity = 1

        if not producto_id:
            return "Error al crear el producto."

        pdf_url = crear_factura(cliente_id, producto_id, quantity, cfdi_use, tipo_cfdi, forma_pago, moneda, tipo_cambio)
        if not pdf_url:
            return "Error al generar la factura."

        return f"""
        <p>Factura creada exitosamente.</p>
        <p>Puedes descargarla <a href=\"{pdf_url}\" target=\"_blank\">aquí</a>.</p>
        """
    except Exception as e:
        print("Error inesperado:", e)
        return "Ocurrió un error inesperado."

@app.route("/previsualizar_factura", methods=["POST"])
def previsualizar_factura():
    datos_form = request.form.to_dict()
    impuestos = []

    if 'usar_iva' in request.form:
        impuestos.append({"type": "IVA", "rate": request.form.get('iva_tasa', 0), "withholding": request.form.get('iva_tipo', 'trasladado') == 'retenido'})
    if 'usar_isr' in request.form:
        impuestos.append({"type": "ISR", "rate": request.form.get('isr_tasa', 0), "withholding": True})
    if 'usar_ieps' in request.form:
        impuestos.append({"type": "IEPS", "rate": request.form.get('ieps_tasa', 0), "withholding": False})

    datos_form.setdefault("description", "Servicio general")
    datos_form.setdefault("price", "100.00")
    datos_form.setdefault("quantity", "1")
    datos_form.setdefault("tipo_cambio", "1.0")

    return render_template("previsualizar.html",
        legal_name=datos_form.get("legal_name"),
        tax_id=datos_form.get("tax_id"),
        postal_code=datos_form.get("postal_code"),
        regimen_fiscal=datos_form.get("regimen_fiscal", "616"),
        cfdi_use=datos_form.get("cfdi_use"),
        forma_pago=datos_form.get("forma_pago"),
        moneda=datos_form.get("moneda", "MXN"),
        tipo_cambio=datos_form.get("tipo_cambio"),
        description=datos_form.get("description"),
        price=datos_form.get("price"),
        quantity=datos_form.get("quantity"),
        fecha_emision=datos_form.get("fecha_emision"),
        hora_emision=datos_form.get("hora_emision"),
        impuestos=impuestos,
        datos_form=datos_form
    )

@app.route("/registrar_organizador", methods=["POST"])
def handle_registro_organizador():
    return registrar_organizador()

# Producción con Waitress
if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))