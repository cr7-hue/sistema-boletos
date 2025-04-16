from flask import Flask, render_template, request, redirect, url_for, Response
import sqlite3
from datetime import datetime, timedelta
import csv
from io import StringIO
import locale

app = Flask(__name__)

# Configurar el idioma español para las fechas
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')  # Para Linux/Mac
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES')  # Para Windows
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')  # Fallback

# Filtro personalizado para formatear fechas
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%A, %d de %B de %Y %H:%M'):
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return value
    # Formato para fechas sin hora (usado en el dropdown)
    if format == 'date_only':
        formatted_date = value.strftime('%A, %d de %B de %Y').capitalize()
        # Reemplazar " 0" con " " para quitar el cero inicial en el día (ej. " 04" -> " 4")
        formatted_date = formatted_date.replace(' 0', ' ')
        return formatted_date
    # Formato por defecto con hora (usado en la tabla)
    formatted_date = value.strftime(format).capitalize()
    # Reemplazar " 0" con " " para quitar el cero inicial en el día
    formatted_date = formatted_date.replace(' 0', ' ')
    return formatted_date

# Función para generar el siguiente código
def get_next_codigo(ultimo_codigo=None):
    if ultimo_codigo:
        prefix = ultimo_codigo[:4]  # Tomar los primeros 4 dígitos (ej. "0135")
        suffix = int(ultimo_codigo[4:]) if ultimo_codigo[4:] else 0  # Tomar los últimos 2 dígitos (ej. "05")
        nuevo_suffix = suffix + 1
        # Asegurar que el sufijo tenga 2 dígitos, rellenando con ceros a la izquierda
        nuevo_suffix_str = str(nuevo_suffix).zfill(2)
        nuevo_codigo = f"{prefix}{nuevo_suffix_str}"
        return nuevo_codigo

    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('SELECT codigo_boleto FROM boletos ORDER BY codigo_boleto DESC LIMIT 1')
    result = cursor.fetchone()
    conn.close()

    if result:
        ultimo_codigo = result[0]
        prefix = ultimo_codigo[:4]  # Tomar los primeros 4 dígitos (ej. "0135")
        suffix = int(ultimo_codigo[4:]) if ultimo_codigo[4:] else 0  # Tomar los últimos 2 dígitos (ej. "05")
        nuevo_suffix = suffix + 1
        # Asegurar que el sufijo tenga 2 dígitos, rellenando con ceros a la izquierda
        nuevo_suffix_str = str(nuevo_suffix).zfill(2)
        nuevo_codigo = f"{prefix}{nuevo_suffix_str}"
        return nuevo_codigo
    return "0123001"

# Función para contar asientos
def contar_asientos(asiento_str):
    if not asiento_str:
        return 0
    asiento_str = asiento_str.replace('-', ',')
    asientos = asiento_str.split(',')
    return len([a for a in asientos if a.strip()])

@app.route('/')
def index():
    # Verificar si se quiere mostrar el historial completo
    show_all = request.args.get('show_all', 'false') == 'true'
    selected_date = request.args.get('fecha', None)
    
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()

    # Obtener la fecha actual y el límite de 30 días atrás
    today = datetime.now()
    date_limit = today - timedelta(days=30)
    
    # Obtener las fechas únicas de los últimos 30 días (solo si no se muestra el historial completo)
    fechas = []
    if not show_all:
        cursor.execute('''
            SELECT DISTINCT DATE(fecha_registro)
            FROM boletos
            WHERE fecha_registro >= ?
            ORDER BY fecha_registro DESC
        ''', (date_limit,))
        fechas = [row[0] for row in cursor.fetchall()]
    
    # Si no se quiere mostrar todo, y no hay fecha seleccionada, usar la más reciente
    if not show_all:
        if not selected_date and fechas:
            selected_date = fechas[0]
        elif not selected_date:
            selected_date = today.strftime('%Y-%m-%d')

    # Obtener los boletos
    if show_all:
        # Mostrar todos los boletos
        cursor.execute('SELECT * FROM boletos ORDER BY fecha_registro DESC')
        boletos = cursor.fetchall()
    else:
        # Filtrar boletos por la fecha seleccionada
        cursor.execute('''
            SELECT * FROM boletos
            WHERE DATE(fecha_registro) = ?
            ORDER BY fecha_registro DESC
        ''', (selected_date,))
        boletos = cursor.fetchall()
    
    boletos_con_conteo = []
    for boleto in boletos:
        conteo = contar_asientos(boleto[4]) if boleto[4] is not None else 0
        boletos_con_conteo.append((boleto, conteo))
    
    # Calcular estadísticas
    total_ingresos = sum(boleto[2] for boleto in boletos if boleto[2] is not None)
    total_boletos = len([b for b in boletos if b[2] is not None])
    total_anulados = len([b for b in boletos if b[2] is None])
    total_asientos = sum(contar_asientos(boleto[4]) for boleto in boletos if boleto[4] is not None)
    
    desglose_vendedor = {}
    for boleto in boletos:
        if boleto[2] is not None:
            vendedor = boleto[6]
            if vendedor not in desglose_vendedor:
                desglose_vendedor[vendedor] = {'boletos': 0, 'ingresos': 0}
            desglose_vendedor[vendedor]['boletos'] += 1
            desglose_vendedor[vendedor]['ingresos'] += boleto[2]
    
    conn.close()
    proximo_codigo = get_next_codigo()
    return render_template('index.html', boletos=boletos_con_conteo, proximo_codigo=proximo_codigo,
                         fechas=fechas, selected_date=selected_date, show_all=show_all,
                         total_ingresos=total_ingresos, total_boletos=total_boletos,
                         total_anulados=total_anulados, total_asientos=total_asientos,
                         desglose_vendedor=desglose_vendedor)

@app.route('/vender', methods=['POST'])
def vender():
    costo = float(request.form['costo'])
    asiento = request.form['asiento']
    codigo = request.form['codigo']
    vendedor = request.form['vendedor']

    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO boletos (fecha_registro, costo_boleto, numero_asiento, codigo_boleto, vendedor)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now(), costo, asiento, codigo, vendedor))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM boletos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/anular', methods=['POST'])
def anular():
    codigo = get_next_codigo()
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO boletos (fecha_registro, costo_boleto, numero_asiento, codigo_boleto, vendedor)
        VALUES (?, NULL, NULL, ?, NULL)
    ''', (datetime.now(), codigo))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/editar/<int:id>', methods=['GET'])
def editar(id):
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM boletos WHERE id = ?', (id,))
    boleto = cursor.fetchone()
    conn.close()
    return render_template('editar.html', boleto=boleto)

@app.route('/actualizar/<int:id>', methods=['POST'])
def actualizar(id):
    costo = float(request.form['costo'])
    asiento = request.form['asiento']
    codigo = request.form['codigo']
    vendedor = request.form['vendedor']

    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE boletos 
        SET costo_boleto = ?, numero_asiento = ?, codigo_boleto = ?, vendedor = ?
        WHERE id = ?
    ''', (costo, asiento, codigo, vendedor, id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/exportar')
def exportar():
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM boletos ORDER BY fecha_registro DESC')
    boletos = cursor.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['ID', 'Fecha', 'Costo (Bs)', 'Asiento', 'Código', 'Vendedor'])
    for boleto in boletos:
        writer.writerow([
            boleto[0],
            boleto[1],
            boleto[2] if boleto[2] is not None else 'ANULADO',
            boleto[4] if boleto[4] is not None else 'ANULADO',
            boleto[5],
            boleto[6] if boleto[6] is not None else 'ANULADO'
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=boletos.csv"}
    )

if __name__ == '__main__':
    # Crear un índice en fecha_registro para mejorar el rendimiento de las consultas
    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fecha_registro ON boletos(fecha_registro)')
    conn.commit()
    conn.close()

    conn = sqlite3.connect('boletos.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS boletos
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   fecha_registro TIMESTAMP,
                   costo_boleto REAL,
                   fecha_boleto DATE,
                   numero_asiento TEXT,
                   codigo_boleto TEXT,
                   vendedor TEXT)''')
    conn.commit()
    conn.close()
    app.run(debug=True)
