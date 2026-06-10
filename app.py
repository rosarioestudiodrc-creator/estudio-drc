import os
from flask import Flask, render_template, request, redirect, session, flash
from pyairtable import Table

app = Flask(__name__)
app.secret_key = "estudio_drc_secret_key"

BASE_ID = "appbYvXN2Y8r4r0vM"
API_KEY = os.environ.get("AIRTABLE_TOKEN")
TABLE_NAME = "Impuestos y Vencimientos"

table = Table(API_KEY, BASE_ID, TABLE_NAME) if API_KEY else None

MAPEO_CLIENTES = {
    "30715331191": "DREAD SRL",
    "33717038989": "Ideas torteras srl",
    "20315331191": "Ramirez Fernando"
}

def limpiar_nombre(texto):
    if not texto:
        return ""
    return str(texto).upper().replace(".", "").replace("-", "").strip()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cuit_ingresado = request.form.get("cuit", "").strip().replace("-", "")
        if not cuit_ingresado:
            flash("Por favor, ingrese un CUIT válido.")
            return redirect("/")
        
        if cuit_ingresado not in MAPEO_CLIENTES:
            flash("CUIT no registrado en el sistema.")
            return redirect("/")
            
        session["cuit"] = cuit_ingresado
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "cuit" not in session:
        return redirect("/")
    
    cuit_usuario = session["cuit"]
    nombre_objetivo = limpiar_nombre(MAPEO_CLIENTES.get(cuit_usuario))
    
    impuestos_usuario = []
    total_a_pagar = 0.0

    if table:
        try:
            all_records = table.all()
            
            for record in all_records:
                fields = record.get("fields", {})
                
                # LEER DEL LOOKUP SEGURO QUE YA TRABAJA COMO TEXTO
                c_razon = fields.get("Razón Social (from Cliente (CUIT))", "")
                
                if isinstance(c_razon, list) and len(c_razon) > 0:
                    cliente_nombre = str(c_razon[0]).strip()
                else:
                    cliente_nombre = str(c_razon).strip()
                
                if limpiar_nombre(cliente_nombre) == nombre_objetivo and nombre_objetivo != "":
                    estado = str(fields.get("Estado Pago", "")).strip()
                    monto = fields.get("Monto a Pagar", 0)
                    
                    try:
                        monto_float = float(monto)
                    except:
                        monto_float = 0.0

                    if estado == "Pendiente":
                        total_a_pagar += monto_float
                        importe_pantalla = f"$ {monto_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    else:
                        importe_pantalla = "Presentado / Al día" if monto_float == 0 else f"$ {monto_float:,.2f} ({estado if estado else 'Presentado'})"

                    # Captura del adjunto nativo en Airtable
                    adjuntos = fields.get("VEP / Cupón de Pago", [])
                    url_descarga = "#"
                    if isinstance(adjuntos, list) and len(adjuntos) > 0:
                        url_descarga = adjuntos[0].get("url", "#")

                    if url_descarga == "#":
                        link_vep = fields.get("Link VEP", "").strip()
                        link_ddjj = fields.get("Link DDJJ", "").strip()
                        url_descarga = link_vep if link_vep else link_ddjj
                        if not url_descarga:
                            url_descarga = "#"

                    impuestos_usuario.append({
                        "impuesto": fields.get("Impuesto", "Impuesto"),
                        "periodo": fields.get("Período", "N/A"),
                        "importe": importe_pantalla,
                        "vencimiento": fields.get("Vencimiento", "Consultar"),
                        "link_vep": url_descarga
                    })
        except Exception as e:
            print(f"Error crítico en Airtable: {e}")
    
    total_formateado = f"$ {total_a_pagar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return render_template("dashboard.html", 
                           cuit=cuit_usuario, 
                           nombre_cliente=MAPEO_CLIENTES.get(cuit_usuario),
                           impuestos=impuestos_usuario, 
                           total_a_pagar=total_formateado)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
