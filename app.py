import os
from flask import Flask, render_template_string, request, redirect, url_for, session
import requests
import re

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "drc_secret_key_ultra_secure_98765")

BASE_ID = "appelWhPRlzcmpKcc"
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")

def get_headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }

# HTML del Login con campo CUIT y CLAVE
HTML_LOGIN = '''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Iniciar Sesión - Estudio DRC</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>body { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); height: 100vh; display: flex; align-items: center; justify-content: center; }.login-card { border: none; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); width: 100%; max-width: 420px; background: white; padding: 40px; }</style></head><body><div class="login-card text-center"><h3 class="fw-bold text-dark mb-2">Estudio DRC</h3><p class="text-muted mb-4">Ingresá tus credenciales para acceder</p>{% if error %}<div class="alert alert-danger py-2 fs-7">{{ error }}</div>{% endif %}<form method="POST"><div class="mb-3 text-start"><label class="form-label text-secondary fw-semibold">CUIT del Contribuyente</label><input type="text" name="cuit" class="form-control form-control-lg text-center" placeholder="30-12345678-9" required autocomplete="off"></div><div class="mb-4 text-start"><label class="form-label text-secondary fw-semibold">Clave de Acceso</label><input type="password" name="clave" class="form-control form-control-lg text-center" placeholder="••••••••" required></div><button type="submit" class="btn btn-primary btn-lg w-100 fw-bold shadow-sm" style="background-color: #2563eb;">Ingresar al Portal</button></form></div></body></html>'''

def obtener_layout_completo(contenido_dinamico, active_page='impuestos'):
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Portal de Clientes - Estudio DRC</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }}
        .sidebar {{ height: 100vh; position: fixed; top: 0; left: 0; width: 260px; background-color: #1e293b; color: white; padding-top: 20px; z-index: 1000; }}
        .sidebar a {{ color: #cbd5e1; text-decoration: none; padding: 12px 20px; display: block; font-weight: 500; transition: all 0.3s; }}
        .sidebar a:hover, .sidebar a.active {{ background-color: #334155; color: white; border-left: 4px solid #3b82f6; }}
        .main-content {{ margin-left: 260px; padding: 40px; }}
        .card-custom {{ border: none; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        .bg-gradient-drc {{ background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: white; }}
    </style>
</head>
<body>
    <div class="sidebar d-flex flex-column">
        <div class="px-4 mb-4">
            <h4 class="fw-bold mb-0 text-white"><i class="fa-solid fa-calculator me-2"></i>Estudio DRC</h4>
            <small class="text-muted">Portal de Clientes</small>
        </div>
        <hr class="mx-3 opacity-25">
        <a href="{ url_for('impuestos') }" class="{"active" if active_page == 'impuestos' else ''}"><i class="fa-solid fa-file-invoice-dollar me-2"></i>Impuestos</a>
        <a href="{ url_for('laboral') }" class="{"active" if active_page == 'laboral' else ''}"><i class="fa-solid fa-users-gear me-2"></i>Área Laboral</a>
        <hr class="mx-3 opacity-25 mt-auto">
        <a href="{ url_for('logout') }" class="text-warning mb-4"><i class="fa-solid fa-right-from-bracket me-2"></i>Cerrar Sesión</a>
    </div>
    <div class="main-content">
        <div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h2 class="fw-bold text-dark mb-1">¡Hola, { session.get('razon_social', 'Cliente') }!</h2>
                    <p class="text-muted mb-0">Panel de control de tus obligaciones fiscales.</p>
                </div>
                <span class="badge bg-secondary px-3 py-2 fs-6">CUIT: { session.get('cuit', '') }</span>
            </div>
            {contenido_dinamico}
        </div>
    </div>
</body>
</html>'''

HTML_TABLA_IMPUESTOS = '''
<div class="row g-4 mb-4">
    <div class="col-md-4">
        <div class="card card-custom bg-gradient-drc p-4 text-white">
            <h6 class="text-uppercase opacity-75 fw-bold fs-7 mb-1">Total a Pagar Seleccionado</h6>
            <h2 class="fw-bold mb-0">$ {{ "{:,.2f}".format(saldo_total).replace(",", "X").replace(".", ",").replace("X", ".") }}</h2>
        </div>
    </div>
</div>
<div class="card card-custom bg-white p-4">
    <h5 class="fw-bold text-dark mb-3"><i class="fa-solid fa-list-check me-2 text-primary"></i>Impuestos del Período</h5>
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th>Impuesto</th>
                    <th>Período</th>
                    <th class="text-end">Importe</th>
                    <th class="text-center">Vencimiento</th>
                    <th class="text-center">Acciones</th>
                </tr>
            </thead>
            <tbody>
                {% for imp in lista_filtrada %}
                <tr>
                    <td><span class="fw-bold text-dark">{{ imp['impuesto'] }}</span></td>
                    <td>{{ imp['periodo'] }}</td>
                    <td class="text-end fw-bold text-danger">$ {{ "{:,.2f}".format(imp['importe']).replace(",", "X").replace(".", ",").replace("X", ".") }}</td>
                    <td class="text-center"><span class="badge bg-light text-dark border px-2 py-1">{{ imp['vencimiento'] }}</span></td>
                    <td class="text-center">
                        <div class="d-flex gap-2 justify-content-center">
                            {% if imp['link_ddjj'] and imp['link_ddjj'] != "#" %}
                            <a href="{{ imp['link_ddjj'] }}" target="_blank" class="btn btn-sm btn-outline-secondary"><i class="fa-solid fa-file-pdf me-1"></i> Ver DDJJ</a>
                            {% else %}
                            <button class="btn btn-sm btn-outline-secondary" disabled><i class="fa-solid fa-ban me-1"></i> No DDJJ</button>
                            {% endif %}
                            {% if imp['link_vep'] and imp['link_vep'] != "#" %}
                            <a href="{{ imp['link_vep'] }}" target="_blank" class="btn btn-sm btn-primary"><i class="fa-solid fa-download me-1"></i> Descargar VEP</a>
                            {% else %}
                            <button class="btn btn-sm btn-primary" disabled><i class="fa-solid fa-ban me-1"></i> No VEP</button>
                            {% endif %}
                        </div>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="5" class="text-center py-4 text-muted">No se registran obligaciones pendientes cargadas para este período en Airtable.</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>'''

@app.route('/', methods=['GET', 'POST'])
def home():
    if 'usuario_id' in session:
        return redirect(url_for('impuestos'))
    error = None
    if request.method == 'POST':
        cuit_ingresado = re.sub(r'\D', '', request.form.get('cuit', ''))
        clave_ingresada = request.form.get('clave', '').strip()
        
        url = "https://api.airtable.com/v0/" + BASE_ID + "/Clientes?filterByFormula=SUBSTITUTE(SUBSTITUTE({CUIT},'-',''),' ','')='" + cuit_ingresado + "'"
        try:
            res = requests.get(url, headers=get_headers()).json()
            records = res.get("records", [])
            if records:
                fields = records[0]['fields']
                
                # ADAPTACIÓN: Leemos 'password_hash' en lugar de 'Clave'
                clave_airtable = str(fields.get('password_hash', '')).strip()
                
                if clave_airtable and clave_ingresada == clave_airtable:
                    session['usuario_id'] = records[0]['id']
                    session['razon_social'] = fields.get('Razón Social', 'Cliente')
                    session['cuit'] = fields.get('CUIT', cuit_ingresado)
                    return redirect(url_for('impuestos'))
                else:
                    error = "La clave ingresada es incorrecta."
            else:
                error = "El CUIT ingresado no corresponde a un cliente activo."
        except Exception as e:
            error = "Error de comunicación con la base de datos."
    return render_template_string(HTML_LOGIN, error=error)

@app.route('/impuestos')
def impuestos():
    if 'usuario_id' not in session:
        return redirect(url_for('home'))
        
    saldo_total = 0.0
    lista_filtrada = []
    TABLA_REAL = "Impuestos y Vencimientos"
    
    url = "https://api.airtable.com/v0/" + BASE_ID + "/" + TABLA_REAL + "?filterByFormula={Cliente}='" + session['usuario_id'] + "'"
    
    try:
        res = requests.get(url, headers=get_headers()).json()
        for rec in res.get("records", []):
            f = rec.get("fields", {})
            
            monto_crudo = f.get("Importe VEP", 0.0)
            if isinstance(monto_crudo, list):
                monto_crudo = monto_crudo[0] if len(monto_crudo) > 0 else 0.0
            try:
                monto = float(monto_crudo) if monto_crudo is not None else 0.0
            except (ValueError, TypeError):
                monto = 0.0
                
            saldo_total += monto
            
            link_v = f.get("Link VEP", "#")
            if isinstance(link_v, list): link_v = link_v[0] if len(link_v) > 0 else "#"
            
            link_d = f.get("Link DDJJ", "#")
            if isinstance(link_d, list): link_d = link_d[0] if len(link_d) > 0 else "#"

            lista_filtrada.append({
                "impuesto": f.get("Impuesto", "Impuesto"),
                "periodo": f.get("Período", "N/A"),
                "importe": monto,
                "vencimiento": f.get("Vencimiento", "N/A"),
                "link_vep": link_v if link_v else "#",
                "link_ddjj": link_d if link_d else "#"
            })
    except Exception as e:
        print(f"Error en consulta de impuestos: {e}")

    cuerpo_renderizado = render_template_string(HTML_TABLA_IMPUESTOS, saldo_total=saldo_total, lista_filtrada=lista_filtrada)
    return obtener_layout_completo(cuerpo_renderizado, active_page='impuestos')

@app.route('/laboral')
def laboral():
    if 'usuario_id' not in session:
        return redirect(url_for('home'))
    contenido = "<div class='card card-custom bg-white p-4'><h5>Área Laboral</h5><p class='text-muted mt-2'>Espacio reservado para liquidaciones y recibos de sueldo.</p></div>"
    return obtener_layout_completo(contenido, active_page='laboral')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
