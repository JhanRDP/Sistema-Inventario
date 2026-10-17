from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database import get_db_connection

app = Flask(__name__)
app.secret_key = 'clave_inventario_pos_secreta'

# --- 1. RUTA PRINCIPAL: PUNTO DE VENTA (POS) ---
@app.route('/')
def pos():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Obtenemos productos disponibles
    cursor.execute("SELECT * FROM productos WHERE stock > 0 ORDER BY nombre ASC")
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('pos.html', productos=productos)

# --- 2. PROCESAR LA VENTA (TRANSACCIÓN COMPLEJA SQL) ---
@app.route('/procesar_venta', methods=['POST'])
def procesar_venta():
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
        
    datos = request.get_json()
    carrito = datos.get('carrito', [])
    total = datos.get('total', 0)
    
    if not carrito:
        return jsonify({'success': False, 'message': 'El carrito está vacío'}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Iniciar Transacción
        conn.start_transaction()
        
        # 1. Registrar la venta global
        # Obtenemos el id del usuario actual desde la BD o fijado
        cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (session['user'],))
        user_data = cursor.fetchone()
        user_id = user_data[0] if user_data else 1
        
        query_venta = "INSERT INTO ventas (total, usuario_id) VALUES (%s, %s)"
        cursor.execute(query_venta, (total, user_id))
        venta_id = cursor.lastrowid # ID generado para la venta
        
        # 2. Registrar el detalle de cada producto y descontar stock
        for item in carrito:
            producto_id = item['id']
            cantidad = int(item['cantidad'])
            precio = float(item['precio'])
            
            # Insertar en detalle_ventas
            query_detalle = """
                INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario) 
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query_detalle, (venta_id, producto_id, cantidad, precio))
            
            # Descontar stock del producto
            query_stock = "UPDATE productos SET stock = stock - %s WHERE id = %s"
            cursor.execute(query_stock, (cantidad, producto_id))
            
        # Si todo salió bien, guardamos los cambios definitivamente
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'venta_id': venta_id})
        
    except Exception as e:
        # Si hay cualquier error, revertimos los cambios en la BD
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

# --- 3. MÓDULO DE INVENTARIO / PRODUCTOS ---
@app.route('/inventario')
def inventario():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT *, (stock <= stock_minimo) AS stock_bajo FROM productos ORDER BY nombre ASC")
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('inventario.html', productos=productos)

# AGREGAR NUEVO PRODUCTO
@app.route('/inventario/agregar', methods=['POST'])
def agregar_producto():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    codigo = request.form['codigo']
    nombre = request.form['nombre']
    precio = request.form['precio']
    stock = request.form['stock']
    stock_min = request.form['stock_minimo']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "INSERT INTO productos (codigo_barras, nombre, precio, stock, stock_minimo) VALUES (%s, %s, %s, %s, %s)"
    cursor.execute(query, (codigo, nombre, precio, stock, stock_min))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario'))

# ACTUALIZAR STOCK DE UN PRODUCTO EXISTENTE
@app.route('/inventario/actualizar_stock/<int:id>', methods=['POST'])
def actualizar_stock(id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    nuevo_stock = request.form['nuevo_stock']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "UPDATE productos SET stock = stock + %s WHERE id = %s"
    # Usamos 'stock = stock + %s' para que sume lo que acaba de llegar al almacén
    cursor.execute(query, (nuevo_stock, id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('inventario'))
# --- 4. RUTA HISTORIAL DE VENTAS ---
@app.route('/ventas')
def ventas():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT v.id, v.total, v.fecha_venta, u.usuario 
        FROM ventas v 
        LEFT JOIN usuarios u ON v.usuario_id = u.id 
        ORDER BY v.fecha_venta DESC
    """)
    lista_ventas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('ventas.html', ventas=lista_ventas)

# --- 5. AUTENTICACIÓN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE usuario = %s AND password = %s", (usuario, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            session['user'] = user['usuario']
            session['rol'] = user['rol']
            return redirect(url_for('pos'))
        else:
            error = "Credenciales incorrectas"
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)