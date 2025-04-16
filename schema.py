import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect('boletos.db')
cursor = conn.cursor()

# Crear tabla de boletos
cursor.execute('''
CREATE TABLE IF NOT EXISTS boletos (
    id INTEGER PRIMARY KEY,
    fecha_registro DATETIME,
    costo_boleto REAL,
    fecha_boleto DATE,
    numero_asiento TEXT,
    codigo_boleto TEXT UNIQUE,
    vendedor TEXT
)
''')

conn.commit()
conn.close()
print("Base de datos creada correctamente!")
