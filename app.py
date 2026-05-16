"""
Smart Inventory Manager MVP
============================
A comprehensive inventory management system with AI-powered intelligence,
QR code scanning, and automated stock monitoring.
"""

import os
import io
import json
import base64
import sqlite3
import statistics
import random
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify, Response, g, send_file
from flask_cors import CORS

try:
    import qrcode
    # pyrefly: ignore [missing-import]
    from PIL import Image
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

try:
    # pyrefly: ignore [missing-import]
    from apscheduler.schedulers.background import BackgroundScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

# ============================================
# CONFIGURATION
# ============================================
app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inventory.db')

# ============================================
# DATABASE
# ============================================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.executescript('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            color TEXT DEFAULT '#06b6d4',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER,
            quantity INTEGER DEFAULT 0,
            threshold INTEGER DEFAULT 5,
            unit TEXT DEFAULT 'pcs',
            description TEXT DEFAULT '',
            sku TEXT DEFAULT '',
            qr_data TEXT DEFAULT '',
            last_checked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS transaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            quantity_change INTEGER DEFAULT 0,
            previous_quantity INTEGER DEFAULT 0,
            new_quantity INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alert_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_via TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        );
    ''')

    # Seed data if empty
    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        seed_data(cur)

    conn.commit()
    conn.close()

def seed_data(cur):
    """Insert sample data for demonstration."""
    categories = [
        ('Electronics', 'Electronic components and devices', '#8b5cf6'),
        ('Office Supplies', 'Stationery and office equipment', '#06b6d4'),
        ('Kitchen', 'Kitchen supplies and utensils', '#f59e0b'),
        ('Cleaning', 'Cleaning products and tools', '#10b981'),
        ('Hardware', 'Tools and hardware supplies', '#ef4444'),
    ]
    cur.executemany("INSERT INTO categories (name, description, color) VALUES (?, ?, ?)", categories)

    items = [
        ('USB-C Cables', 1, 45, 10, 'pcs', 'High-speed USB-C charging cables'),
        ('Wireless Mouse', 1, 3, 5, 'pcs', 'Ergonomic wireless mouse'),
        ('HDMI Adapters', 1, 8, 10, 'pcs', 'HDMI to USB-C adapters'),
        ('A4 Paper Reams', 2, 25, 8, 'reams', 'White A4 printer paper'),
        ('Ballpoint Pens', 2, 150, 30, 'pcs', 'Blue ballpoint pens'),
        ('Sticky Notes', 2, 2, 15, 'packs', '3x3 inch sticky note pads'),
        ('Paper Towels', 3, 12, 5, 'rolls', 'Absorbent paper towels'),
        ('Dish Soap', 3, 4, 3, 'bottles', 'Concentrated dish soap'),
        ('Floor Cleaner', 4, 1, 3, 'bottles', 'Multi-surface floor cleaner'),
        ('Screwdriver Set', 5, 7, 2, 'sets', 'Phillips and flathead set'),
        ('Batteries AA', 1, 6, 20, 'pcs', 'AA alkaline batteries'),
        ('Printer Ink', 2, 2, 3, 'cartridges', 'Black ink cartridges'),
    ]
    for item in items:
        cur.execute(
            "INSERT INTO items (name, category_id, quantity, threshold, unit, description) VALUES (?, ?, ?, ?, ?, ?)",
            item
        )

    # Seed transaction logs for AI analysis
    now = datetime.now()
    for item_idx in range(1, len(items) + 1):
        for day_offset in range(30, 0, -1):
            if random.random() > 0.4:
                change = -random.randint(1, 4)
                ts = (now - timedelta(days=day_offset)).strftime('%Y-%m-%d %H:%M:%S')
                cur.execute(
                    "INSERT INTO transaction_logs (item_id, action_type, quantity_change, previous_quantity, new_quantity, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (item_idx, 'consumed', change, 0, 0, 'Daily usage', ts)
                )
            if random.random() > 0.85:
                change = random.randint(10, 50)
                ts = (now - timedelta(days=day_offset)).strftime('%Y-%m-%d %H:%M:%S')
                cur.execute(
                    "INSERT INTO transaction_logs (item_id, action_type, quantity_change, previous_quantity, new_quantity, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (item_idx, 'restocked', change, 0, 0, 'Restock delivery', ts)
                )


# ============================================
# AI INTELLIGENCE ENGINE
# ============================================
class InventoryAI:
    """AI-powered inventory analysis and prediction engine."""

    @staticmethod
    def get_consumption_data(db, item_id, days=30):
        rows = db.execute(
            "SELECT quantity_change, created_at FROM transaction_logs WHERE item_id = ? AND action_type = 'consumed' AND created_at >= datetime('now', ?) ORDER BY created_at",
            (item_id, f'-{days} days')
        ).fetchall()
        return rows

    @staticmethod
    def calculate_consumption_rate(db, item_id, days=30):
        rows = InventoryAI.get_consumption_data(db, item_id, days)
        if not rows:
            return 0.0
        total_consumed = sum(abs(r['quantity_change']) for r in rows)
        return round(total_consumed / days, 2)

    @staticmethod
    def predict_depletion(db, item_id):
        item = db.execute("SELECT quantity, threshold, name FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return None
        rate = InventoryAI.calculate_consumption_rate(db, item_id)
        if rate <= 0:
            return {'days_until_empty': None, 'days_until_threshold': None, 'rate': 0, 'status': 'no_data'}

        days_empty = round(item['quantity'] / rate, 1) if rate > 0 else None
        days_threshold = round(max(0, item['quantity'] - item['threshold']) / rate, 1) if rate > 0 else None

        status = 'critical' if (days_threshold is not None and days_threshold <= 3) else \
                 'warning' if (days_threshold is not None and days_threshold <= 7) else 'healthy'

        return {
            'item_name': item['name'],
            'current_stock': item['quantity'],
            'daily_rate': rate,
            'days_until_empty': days_empty,
            'days_until_threshold': days_threshold,
            'status': status
        }

    @staticmethod
    def suggest_threshold(db, item_id, buffer_days=7):
        rate = InventoryAI.calculate_consumption_rate(db, item_id)
        if rate <= 0:
            return None
        suggested = int(rate * buffer_days) + 1
        rows = InventoryAI.get_consumption_data(db, item_id)
        if len(rows) >= 5:
            daily_vals = [abs(r['quantity_change']) for r in rows]
            try:
                std = statistics.stdev(daily_vals)
                suggested += int(std * 1.5)
            except statistics.StatisticsError:
                pass
        return max(1, suggested)

    @staticmethod
    def detect_anomalies(db, item_id):
        rows = InventoryAI.get_consumption_data(db, item_id, 60)
        if len(rows) < 10:
            return []
        vals = [abs(r['quantity_change']) for r in rows]
        mean = statistics.mean(vals)
        try:
            std = statistics.stdev(vals)
        except statistics.StatisticsError:
            return []
        if std == 0:
            return []
        anomalies = []
        for r in rows:
            z = (abs(r['quantity_change']) - mean) / std
            if abs(z) > 2:
                anomalies.append({
                    'date': r['created_at'],
                    'quantity': abs(r['quantity_change']),
                    'z_score': round(z, 2),
                    'type': 'spike' if z > 0 else 'drop'
                })
        return anomalies[-5:]

    @staticmethod
    def get_insights(db):
        items = db.execute("SELECT id, name, quantity, threshold FROM items").fetchall()
        insights = []
        critical = []
        for item in items:
            pred = InventoryAI.predict_depletion(db, item['id'])
            if pred and pred['status'] == 'critical':
                critical.append({'id': item['id'], 'name': item['name'], 'days': pred.get('days_until_threshold')})
            if pred and pred['daily_rate'] > 0:
                suggested = InventoryAI.suggest_threshold(db, item['id'])
                if suggested and abs(suggested - item['threshold']) > 3:
                    insights.append({
                        'type': 'threshold_adjustment',
                        'item_id': item['id'],
                        'item_name': item['name'],
                        'current_threshold': item['threshold'],
                        'suggested_threshold': suggested,
                        'message': f"Consider adjusting threshold for '{item['name']}' from {item['threshold']} to {suggested} based on usage patterns."
                    })

        if critical:
            insights.insert(0, {
                'type': 'critical_stock',
                'items': critical,
                'message': f"{len(critical)} item(s) will hit low-stock within 3 days."
            })

        total = len(items)
        low = sum(1 for i in items if i['quantity'] <= i['threshold'])
        out = sum(1 for i in items if i['quantity'] == 0)
        insights.append({
            'type': 'summary',
            'total_items': total,
            'low_stock': low,
            'out_of_stock': out,
            'health_score': round(max(0, (1 - (low + out * 2) / max(total, 1)) * 100))
        })
        return insights

    @staticmethod
    def forecast_demand(db, item_id, future_days=14):
        rows = InventoryAI.get_consumption_data(db, item_id, 30)
        if len(rows) < 5:
            return None
        daily = {}
        for r in rows:
            day = r['created_at'][:10]
            daily[day] = daily.get(day, 0) + abs(r['quantity_change'])
        vals = list(daily.values())
        if not vals:
            return None
        avg = statistics.mean(vals)
        item = db.execute("SELECT quantity FROM items WHERE id = ?", (item_id,)).fetchone()
        forecast = []
        stock = item['quantity'] if item else 0
        for d in range(1, future_days + 1):
            usage = max(0, round(avg + random.gauss(0, max(1, avg * 0.2))))
            stock = max(0, stock - usage)
            forecast.append({'day': d, 'predicted_usage': usage, 'predicted_stock': stock})
        return forecast


# ============================================
# QR CODE MODULE
# ============================================
def generate_qr(data, size=10):
    if not QR_AVAILABLE:
        return None
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    # pyrefly: ignore [unexpected-keyword]
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


# ============================================
# STOCK CHECK AUTOMATION
# ============================================
def check_stock_levels():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    items = cur.execute("SELECT id, name, quantity, threshold FROM items WHERE quantity <= threshold").fetchall()
    for item in items:
        existing = cur.execute(
            "SELECT id FROM alert_logs WHERE item_id = ? AND created_at >= datetime('now', '-24 hours')",
            (item['id'],)
        ).fetchone()
        if not existing:
            msg = f"Low stock alert: '{item['name']}' has {item['quantity']} units (threshold: {item['threshold']})"
            cur.execute(
                "INSERT INTO alert_logs (item_id, alert_type, message, sent_via) VALUES (?, ?, ?, ?)",
                (item['id'], 'low_stock', msg, 'system')
            )
    conn.commit()
    conn.close()


# ============================================
# API ROUTES
# ============================================

# --- Items ---
@app.route('/api/items', methods=['GET'])
def get_items():
    db = get_db()
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    sort = request.args.get('sort', 'name')

    sql = '''SELECT i.*, c.name as category_name, c.color as category_color
             FROM items i LEFT JOIN categories c ON i.category_id = c.id WHERE 1=1'''
    params = []

    if query:
        sql += " AND (i.name LIKE ? OR i.sku LIKE ? OR i.description LIKE ?)"
        params.extend([f'%{query}%'] * 3)
    if category:
        sql += " AND i.category_id = ?"
        params.append(category)
    if status == 'low':
        sql += " AND i.quantity <= i.threshold AND i.quantity > 0"
    elif status == 'out':
        sql += " AND i.quantity = 0"
    elif status == 'ok':
        sql += " AND i.quantity > i.threshold"

    sort_map = {'name': 'i.name ASC', 'quantity': 'i.quantity ASC', 'recent': 'i.updated_at DESC', 'category': 'c.name ASC'}
    sql += f" ORDER BY {sort_map.get(sort, 'i.name ASC')}"

    items = db.execute(sql, params).fetchall()
    return jsonify([dict(r) for r in items])

@app.route('/api/items', methods=['POST'])
def create_item():
    db = get_db()
    data = request.json
    cur = db.execute(
        "INSERT INTO items (name, category_id, quantity, threshold, unit, description, sku) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (data['name'], data.get('category_id'), data.get('quantity', 0),
         data.get('threshold', 5), data.get('unit', 'pcs'), data.get('description', ''), data.get('sku', ''))
    )
    db.commit()
    item_id = cur.lastrowid

    # Auto-generate QR
    if data.get('auto_qr', True):
        qr_data = json.dumps({'id': item_id, 'name': data['name'], 'type': 'inventory_item'})
        db.execute("UPDATE items SET qr_data = ? WHERE id = ?", (qr_data, item_id))
        db.commit()

    # Log transaction
    db.execute(
        "INSERT INTO transaction_logs (item_id, action_type, quantity_change, previous_quantity, new_quantity, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (item_id, 'created', data.get('quantity', 0), 0, data.get('quantity', 0), 'Item created')
    )
    db.commit()

    item = db.execute("SELECT i.*, c.name as category_name, c.color as category_color FROM items i LEFT JOIN categories c ON i.category_id = c.id WHERE i.id = ?", (item_id,)).fetchone()
    return jsonify(dict(item)), 201

@app.route('/api/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    db = get_db()
    item = db.execute("SELECT i.*, c.name as category_name, c.color as category_color FROM items i LEFT JOIN categories c ON i.category_id = c.id WHERE i.id = ?", (item_id,)).fetchone()
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    result = dict(item)

    # Generate QR code image
    qr_payload = item['qr_data'] or json.dumps({'id': item_id, 'name': item['name']})
    result['qr_image'] = generate_qr(qr_payload) if QR_AVAILABLE else None

    # Get recent transactions
    txns = db.execute("SELECT * FROM transaction_logs WHERE item_id = ? ORDER BY created_at DESC LIMIT 10", (item_id,)).fetchall()
    result['transactions'] = [dict(t) for t in txns]

    # AI predictions
    result['prediction'] = InventoryAI.predict_depletion(db, item_id)
    result['suggested_threshold'] = InventoryAI.suggest_threshold(db, item_id)
    result['anomalies'] = InventoryAI.detect_anomalies(db, item_id)

    return jsonify(result)

@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    db = get_db()
    data = request.json
    old = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not old:
        return jsonify({'error': 'Item not found'}), 404

    db.execute(
        "UPDATE items SET name=?, category_id=?, quantity=?, threshold=?, unit=?, description=?, sku=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (data.get('name', old['name']), data.get('category_id', old['category_id']),
         data.get('quantity', old['quantity']), data.get('threshold', old['threshold']),
         data.get('unit', old['unit']), data.get('description', old['description']),
         data.get('sku', old['sku']), item_id)
    )

    if data.get('quantity') is not None and data['quantity'] != old['quantity']:
        change = data['quantity'] - old['quantity']
        db.execute(
            "INSERT INTO transaction_logs (item_id, action_type, quantity_change, previous_quantity, new_quantity, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, 'adjusted', change, old['quantity'], data['quantity'], 'Manual adjustment')
        )
    db.commit()

    item = db.execute("SELECT i.*, c.name as category_name, c.color as category_color FROM items i LEFT JOIN categories c ON i.category_id = c.id WHERE i.id = ?", (item_id,)).fetchone()
    return jsonify(dict(item))

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    db = get_db()
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/items/<int:item_id>/increment', methods=['POST'])
def increment_item(item_id):
    db = get_db()
    amount = request.json.get('amount', 1) if request.json else 1
    item = db.execute("SELECT quantity FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        return jsonify({'error': 'Not found'}), 404
    new_qty = item['quantity'] + amount
    db.execute("UPDATE items SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_qty, item_id))
    db.execute(
        "INSERT INTO transaction_logs (item_id, action_type, quantity_change, previous_quantity, new_quantity, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (item_id, 'restocked', amount, item['quantity'], new_qty, 'Quick increment')
    )
    db.commit()
    return jsonify({'quantity': new_qty})

@app.route('/api/items/<int:item_id>/decrement', methods=['POST'])
def decrement_item(item_id):
    db = get_db()
    amount = request.json.get('amount', 1) if request.json else 1
    item = db.execute("SELECT quantity FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        return jsonify({'error': 'Not found'}), 404
    new_qty = max(0, item['quantity'] - amount)
    db.execute("UPDATE items SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_qty, item_id))
    db.execute(
        "INSERT INTO transaction_logs (item_id, action_type, quantity_change, previous_quantity, new_quantity, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (item_id, 'consumed', -amount, item['quantity'], new_qty, 'Quick decrement')
    )
    db.commit()
    return jsonify({'quantity': new_qty})

# --- Categories ---
@app.route('/api/categories', methods=['GET'])
def get_categories():
    db = get_db()
    cats = db.execute(
        "SELECT c.*, COUNT(i.id) as item_count FROM categories c LEFT JOIN items i ON c.id = i.category_id GROUP BY c.id ORDER BY c.name"
    ).fetchall()
    return jsonify([dict(c) for c in cats])

@app.route('/api/categories', methods=['POST'])
def create_category():
    db = get_db()
    data = request.json
    cur = db.execute("INSERT INTO categories (name, description, color) VALUES (?, ?, ?)",
                     (data['name'], data.get('description', ''), data.get('color', '#06b6d4')))
    db.commit()
    cat = db.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(cat)), 201

@app.route('/api/categories/<int:cat_id>', methods=['DELETE'])
def delete_category(cat_id):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    db.commit()
    return jsonify({'success': True})

# --- Analytics ---
@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    db = get_db()
    insights = InventoryAI.get_insights(db)
    return jsonify(insights)

@app.route('/api/analytics/<int:item_id>', methods=['GET'])
def get_item_analytics(item_id):
    db = get_db()
    return jsonify({
        'prediction': InventoryAI.predict_depletion(db, item_id),
        'suggested_threshold': InventoryAI.suggest_threshold(db, item_id),
        'anomalies': InventoryAI.detect_anomalies(db, item_id),
        'forecast': InventoryAI.forecast_demand(db, item_id),
        'consumption_rate': InventoryAI.calculate_consumption_rate(db, item_id),
    })

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    db = get_db()
    alerts = db.execute(
        "SELECT a.*, i.name as item_name FROM alert_logs a JOIN items i ON a.item_id = i.id ORDER BY a.created_at DESC LIMIT 20"
    ).fetchall()
    return jsonify([dict(a) for a in alerts])

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    db = get_db()
    limit = request.args.get('limit', 20, type=int)
    txns = db.execute(
        "SELECT t.*, i.name as item_name FROM transaction_logs t JOIN items i ON t.item_id = i.id ORDER BY t.created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return jsonify([dict(t) for t in txns])

@app.route('/api/qr/<int:item_id>', methods=['GET'])
def get_qr(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        return jsonify({'error': 'Not found'}), 404
    qr_payload = item['qr_data'] or json.dumps({'id': item_id, 'name': item['name']})
    img_b64 = generate_qr(qr_payload)
    if img_b64:
        return jsonify({'qr_image': img_b64, 'qr_data': qr_payload})
    return jsonify({'error': 'QR generation not available'}), 500

@app.route('/api/check-stock', methods=['POST'])
def manual_stock_check():
    check_stock_levels()
    return jsonify({'success': True, 'message': 'Stock check completed'})

# --- Serve Frontend ---
@app.route('/')
def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'index.html')
    with open(html_path, 'r') as f:
        return Response(f.read(), content_type='text/html')


# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    init_db()
    check_stock_levels()

    if SCHEDULER_AVAILABLE:
        scheduler = BackgroundScheduler()
        scheduler.add_job(check_stock_levels, 'interval', hours=24, id='stock_check')
        scheduler.start()
        print("[Scheduler] Daily stock check enabled.")

    print("=" * 50)
    print("  Smart Inventory Manager MVP")
    print("  Running on http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
