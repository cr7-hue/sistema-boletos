import pandas as pd
import sqlite3
from datetime import datetime
import msoffcrypto
from io import BytesIO

def decrypt_excel(input_path, password):
    decrypted_data = BytesIO()
    with open(input_path, "rb") as file:
        office_file = msoffcrypto.OfficeFile(file)
        office_file.load_key(password=password)
        office_file.decrypt(decrypted_data)
    decrypted_data.seek(0)
    return decrypted_data

PASSWORD = "123456"  # <-- ¡Cambia esto!

# Desencriptar y leer
decrypted = decrypt_excel("boletos.xlsm", PASSWORD)
df = pd.read_excel(decrypted, engine='openpyxl')

# Resto del código (insertar en SQLite)
conn = sqlite3.connect('boletos.db')
cursor = conn.cursor()

for index, row in df.iterrows():
    cursor.execute('''
        INSERT INTO boletos (fecha_registro, costo_boleto, fecha_boleto, numero_asiento, codigo_boleto, vendedor)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now(),
        row['Costo de Boleto (Bs)'],
        row['Fecha del Boleto'],
        row['Número de Asiento(s)'],
        row['Código de Boleto'],
        'Mamá' if 'MAM' in row['Código de Boleto'] else 'Hermana'
    ))

conn.commit()
conn.close()
print("¡Datos migrados exitosamente!")
