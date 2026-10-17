import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',            # Cambia si tienes contraseña en MySQL
        database='inventario_db'
    )
    return connection