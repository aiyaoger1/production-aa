import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
from datetime import datetime

app = Flask(__name__)
DATABASE = 'production.db'

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # 创建产品表
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            spec TEXT,
            unit TEXT,
            price REAL
        )
    ''')
    
    # 创建客户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            address TEXT
        )
    ''')
    
    # 创建订单表
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE,
            customer_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            order_date TEXT,
            delivery_date TEXT,
            status TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # 插入示例数据
    # 产品
    products = [
        ('P001', '手机外壳', 'ABS材料', '个', 15.5),
        ('P002', '数据线', '1.5米Type-C', '条', 8.9),
        ('P003', '充电器', '18W快充', '个', 25.0),
        ('P004', '保护膜', '钢化膜', '张', 5.5)
    ]
    
    c.executemany('INSERT OR IGNORE INTO products (code, name, spec, unit, price) VALUES (?, ?, ?, ?, ?)', products)
    
    # 客户
    customers = [
        ('华为科技', '13800138000', '深圳市龙岗区'),
        ('小米通讯', '13900139000', '北京市海淀区'),
        ('OPPO电子', '13600136000', '东莞市长安镇'),
        ('VIVO移动', '13500135000', '东莞市长安镇')
    ]
    
    c.executemany('INSERT OR IGNORE INTO customers (name, contact, address) VALUES (?, ?, ?)', customers)
    
    conn.commit()
    conn.close()

# 数据库查询辅助函数
def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

# 路由
@app.route('/')
def index():
    return render_template('index.html')

# 获取所有订单
@app.route('/api/orders')
def get_orders():
    orders = query_db('''
        SELECT o.*, c.name as customer_name, p.name as product_name, p.code as product_code 
        FROM orders o 
        LEFT JOIN customers c ON o.customer_id = c.id 
        LEFT JOIN products p ON o.product_id = p.id 
        ORDER BY o.order_date DESC
    ''')
    return jsonify([dict(order) for order in orders])

# 创建新订单
@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    order_number = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    order_id = execute_db('''
        INSERT INTO orders (order_number, customer_id, product_id, quantity, 
                          order_date, delivery_date, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order_number,
        data['customer_id'],
        data['product_id'],
        data['quantity'],
        datetime.now().strftime('%Y-%m-%d'),
        data.get('delivery_date', ''),
        'pending',
        data.get('notes', '')
    ))
    
    return jsonify({'success': True, 'order_id': order_id, 'order_number': order_number})

# 更新订单状态
@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    data = request.json
    execute_db('UPDATE orders SET status = ? WHERE id = ?', (data['status'], order_id))
    return jsonify({'success': True})

# 获取所有产品
@app.route('/api/products')
def get_products():
    products = query_db('SELECT * FROM products ORDER BY code')
    return jsonify([dict(product) for product in products])

# 获取所有客户
@app.route('/api/customers')
def get_customers():
    customers = query_db('SELECT * FROM customers ORDER BY name')
    return jsonify([dict(customer) for customer in customers])

# 添加新产品
@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    product_id = execute_db('''
        INSERT INTO products (code, name, spec, unit, price)
        VALUES (?, ?, ?, ?, ?)
    ''', (data['code'], data['name'], data['spec'], data['unit'], data['price']))
    return jsonify({'success': True, 'product_id': product_id})

# 添加新客户
@app.route('/api/customers', methods=['POST'])
def add_customer():
    data = request.json
    customer_id = execute_db('''
        INSERT INTO customers (name, contact, address)
        VALUES (?, ?, ?)
    ''', (data['name'], data['contact'], data['address']))
    return jsonify({'success': True, 'customer_id': customer_id})

# 统计数据
@app.route('/api/stats')
def get_stats():
    # 订单统计
    stats = query_db('''
        SELECT 
            COUNT(*) as total_orders,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending_orders,
            SUM(CASE WHEN status='in_production' THEN 1 ELSE 0 END) as production_orders,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_orders
        FROM orders
    ''', one=True)
    
    # 最近订单
    recent_orders = query_db('''
        SELECT o.order_number, c.name as customer_name, p.name as product_name, 
               o.quantity, o.order_date, o.status
        FROM orders o 
        LEFT JOIN customers c ON o.customer_id = c.id 
        LEFT JOIN products p ON o.product_id = p.id 
        ORDER BY o.order_date DESC LIMIT 5
    ''')
    
    return jsonify({
        'stats': dict(stats),
        'recent_orders': [dict(order) for order in recent_orders]
    })

if __name__ == '__main__':
    # 初始化数据库
    if not os.path.exists(DATABASE):
        init_db()
        print(f"数据库已初始化: {DATABASE}")
    
    print("生产下单系统启动中...")
    print("访问地址: http://127.0.0.1:5000")
    print("按 Ctrl+C 停止程序")
    
    app.run(debug=True, host='0.0.0.0', port=5000)