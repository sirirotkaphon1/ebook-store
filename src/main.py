import os
import sqlite3
import uuid
from flask import Flask, render_template_string, request, redirect, url_for, session, abort, flash, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "team-04-ecommerce-secret-key-2026"
DB_NAME = "ebook_store.db"
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# เพิ่มคอลัมน์ stock_quantity ในตาราง ebooks อัตโนมัติถ้ายังไม่มี
def setup_stock_column():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE ebooks ADD COLUMN stock_quantity INTEGER DEFAULT 10")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()

setup_stock_column()

# ดึงหรือสร้าง cart_id ประจำตัวผู้ใช้
def get_user_cart_id(conn, user_id):
    cart = conn.execute("SELECT cart_id FROM carts WHERE user_id = ?", (user_id,)).fetchone()
    if cart:
        return cart['cart_id']
    cur = conn.cursor()
    cur.execute("INSERT INTO carts (user_id) VALUES (?)", (user_id,))
    conn.commit()
    return cur.lastrowid

# นับจำนวนสินค้าในตะกร้าเพื่อนำไปโชว์ badge บน Navbar
@app.context_processor
def inject_cart_count():
    if 'user_id' in session:
        conn = get_db()
        count = conn.execute("""
            SELECT COALESCE(SUM(ci.quantity), 0) as total
            FROM carts c
            JOIN cart_items ci ON c.cart_id = ci.cart_id
            WHERE c.user_id = ?
        """, (session['user_id'],)).fetchone()['total']
        return dict(cart_count=count)
    return dict(cart_count=0)

# บังคับเข้าสู่ระบบก่อนใช้งาน (ยกเว้นหน้า login, register)
@app.before_request
def require_login():
    allowed_endpoints = ['login', 'register', 'static']
    if request.endpoint not in allowed_endpoints and 'user_id' not in session:
        return redirect(url_for('login'))

def render_page(title, content_html, **kwargs):
    html = f"""
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - ReadDee E-Book Store</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
        <style>
            body {{ background-color: #f8f9fa; font-family: system-ui, -apple-system, sans-serif; }}
            .navbar-brand {{ font-weight: 800; letter-spacing: -0.5px; color: #ff5722 !important; }}
            .book-card {{ border: none; border-radius: 12px; transition: transform .2s, box-shadow .2s; overflow: hidden; }}
            .book-card:hover {{ transform: translateY(-4px); box-shadow: 0 10px 20px rgba(0,0,0,0.08); }}
            .btn-primary {{ background-color: #ff5722; border-color: #ff5722; }}
            .btn-primary:hover {{ background-color: #e64a19; border-color: #e64a19; }}
            .btn-outline-primary {{ color: #ff5722; border-color: #ff5722; }}
            .btn-outline-primary:hover {{ background-color: #ff5722; color: #fff; }}
            .badge-cart {{ font-size: 0.75rem; vertical-align: top; }}
            .toast-container-custom {{ position: fixed; top: 20px; right: 20px; z-index: 1090; }}
            html {{ scroll-behavior: smooth; }}

            /* ปุ่มลอยสำหรับกลับขึ้นด้านบน */
            #btnBackToTop {{
                position: fixed;
                bottom: 30px;
                right: 30px;
                display: none;
                z-index: 1080;
                width: 50px;
                height: 50px;
                border-radius: 50%;
                box-shadow: 0 4px 15px rgba(0,0,0,0.25);
                transition: transform 0.2s, background-color 0.2s;
            }}
            #btnBackToTop:hover {{
                transform: translateY(-4px);
            }}
        </style>
    </head>
    <body>
    <div class="toast-container-custom">
      {{% with messages = get_flashed_messages(with_categories=true) %}}
        {{% if messages %}}
          {{% for category, message in messages %}}
            <div class="alert alert-{{{{ category }}}} alert-dismissible fade show shadow-lg border-0 rounded-4 px-4 py-3 mb-2" role="alert">
              <strong>{{{{ message }}}}</strong>
              <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
          {{% endfor %}}
        {{% endif %}}
      {{% endwith %}}
    </div>

    <nav class="navbar navbar-expand-lg navbar-dark bg-dark sticky-top shadow-sm py-2">
      <div class="container">
        <a class="navbar-brand fs-4" href="/">📖 ReadDee</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navMenu">
          <div class="navbar-nav ms-auto align-items-center">
            {{% if session.get('user_id') %}}
              {{% if session.get('role') == 'admin' %}}
                <a class="btn btn-warning btn-sm text-dark px-3 me-3 fw-bold shadow-sm" href="/admin">
                  <i class="bi bi-gear-fill"></i> จัดการร้านหลังบ้าน
                </a>
              {{% endif %}}

              <a class="nav-link position-relative me-3 text-white" href="/cart">
                <i class="bi bi-cart3 fs-5"></i> ตะกร้าของฉัน
                {{% if cart_count > 0 %}}
                  <span class="badge rounded-pill bg-danger badge-cart">{{{{ cart_count }}}}</span>
                {{% endif %}}
              </a>
              <a class="nav-link text-white me-3" href="/my-orders"><i class="bi bi-bag-check"></i> คำสั่งซื้อ</a>

              <a class="nav-link text-white me-3" href="/profile" title="ตั้งค่าบัญชี">
                <i class="bi bi-person-circle"></i> {{{{ session['full_name'] }}}}
              </a>
              
              <a class="btn btn-outline-light btn-sm" href="/logout">ออกจากระบบ</a>
            {{% endif %}}
          </div>
        </div>
      </div>
    </nav>

    <div class="container py-4">
        {content_html}
    </div>

    <!-- ปุ่มลอย Back to Top -->
    <button type="button" class="btn btn-warning text-dark fw-bold d-flex align-items-center justify-content-center p-0" id="btnBackToTop" title="กลับขึ้นด้านบน">
        <i class="bi bi-arrow-up fs-4"></i>
    </button>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
      setTimeout(function() {{
        let alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {{
          let bsAlert = new bootstrap.Alert(alert);
          bsAlert.close();
        }});
      }}, 3500);

      // ควบคุมการแสดงผลของปุ่ม Back to Top
      let mybutton = document.getElementById("btnBackToTop");
      window.onscroll = function () {{
          if (document.body.scrollTop > 250 || document.documentElement.scrollTop > 250) {{
              mybutton.style.display = "flex";
          }} else {{
              mybutton.style.display = "none";
          }}
      }};

      mybutton.addEventListener("click", function () {{
          window.scrollTo({{ top: 0, behavior: 'smooth' }});
      }});
    </script>
    </body>
    </html>
    """
    html = html.replace("{{%", "{%").replace("%}}", "%}").replace("{{{{", "{{").replace("}}}}", "}}")
    return render_template_string(html, **kwargs)

# 1. หน้าร้านค้า
@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    selected_cat = request.args.get('cat', '')
    
    conn = get_db()
    query = """
        SELECT e.*, c.name as category_name, a.name as author_name 
        FROM ebooks e
        JOIN categories c ON e.category_id = c.category_id
        JOIN authors a ON e.author_id = a.author_id
        WHERE e.is_active = 1
    """
    params = []
    if q:
        query += " AND (e.title LIKE ? OR a.name LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if selected_cat:
        query += " AND e.category_id = ?"
        params.append(selected_cat)
        
    books = conn.execute(query, params).fetchall()
    categories = conn.execute("SELECT * FROM categories").fetchall()
    
    content = """
    <div class="p-4 p-md-5 mb-4 rounded text-white bg-dark shadow-sm" style="background: linear-gradient(135deg, #1f2937, #111827);">
      <div class="col-md-8 px-0">
        <h1 class="display-6 fw-bold">ศูนย์รวม E-Book ดิจิทัลคุณภาพ</h1>
        <p class="lead my-3 text-secondary">ค้นหา คัดสรร และสั่งซื้อ E-Book เล่มโปรด พร้อมอ่านได้ทันทีบนทุกอุปกรณ์</p>
        <form class="d-flex gap-2 mt-3" method="GET" action="/">
            <input type="hidden" name="cat" value="{{ selected_cat }}">
            <input class="form-control form-control-lg" name="q" placeholder="ค้นหาชื่อหนังสือ หรือนักเขียน..." value="{{ q }}">
            <button class="btn btn-primary px-4 fw-bold" type="submit"><i class="bi bi-search"></i> ค้นหา</button>
            {% if q or selected_cat %}
              <a href="/" class="btn btn-outline-secondary">ล้างการค้นหา</a>
            {% endif %}
        </form>
      </div>
    </div>

    <div class="d-flex align-items-center gap-2 overflow-auto pb-3 mb-4 border-bottom">
        <span class="text-muted fw-bold me-2"><i class="bi bi-tags"></i> หมวดหมู่:</span>
        <a href="/?q={{ q }}" class="btn btn-sm {% if not selected_cat %}btn-primary text-white fw-bold{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3">
            ทั้งหมด
        </a>
        {% for c in categories %}
        <a href="/?cat={{ c['category_id'] }}&q={{ q }}" 
           class="btn btn-sm {% if selected_cat|string == c['category_id']|string %}btn-primary text-white fw-bold{% else %}btn-outline-secondary bg-white{% endif %} rounded-pill px-3 text-nowrap">
            {{ c['name'] }}
        </a>
        {% endfor %}
    </div>

    <div class="row row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-lg-4 g-4">
        {% for b in books %}
        <div class="col">
            <div class="card h-100 shadow-sm book-card bg-white">
                <div class="position-relative">
                    <img src="{{ b['cover_url'] or 'https://placehold.co/300x400?text=No+Cover' }}" class="card-img-top" style="height: 240px; object-fit: cover;">
                    <span class="badge bg-dark position-absolute top-0 end-0 m-2 opacity-75">{{ b['category_name'] }}</span>
                </div>
                <div class="card-body d-flex flex-column">
                    <h6 class="card-title fw-bold text-truncate mb-1" title="{{ b['title'] }}">{{ b['title'] }}</h6>
                    <p class="text-muted small mb-2"><i class="bi bi-pen"></i> {{ b['author_name'] }}</p>
                    <p class="card-text text-muted small flex-grow-1" style="display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                        {{ b['description'] }}
                    </p>
                    
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="small text-muted">คงเหลือ:</span>
                        {% if (b['stock_quantity'] or 0) > 0 %}
                            <span class="badge bg-success-subtle text-success border border-success">มีสินค้า ({{ b['stock_quantity'] or 10 }} เล่ม)</span>
                        {% else %}
                            <span class="badge bg-danger-subtle text-danger border border-danger">สินค้าหมด</span>
                        {% endif %}
                    </div>

                    <div class="d-flex justify-content-between align-items-center pt-2 border-top">
                        <span class="fs-5 fw-bold text-danger">฿{{ "{:,.2f}".format(b['price']) }}</span>
                        {% if (b['stock_quantity'] or 0) > 0 %}
                        <form action="/cart/add/{{ b['ebook_id'] }}" method="POST" class="m-0">
                            <button class="btn btn-outline-primary btn-sm rounded-pill px-3 fw-bold" type="submit">
                                <i class="bi bi-cart-plus"></i> ใส่ตะกร้า
                            </button>
                        </form>
                        {% else %}
                        <button class="btn btn-secondary btn-sm rounded-pill px-3 fw-bold" disabled>หมด</button>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        {% else %}
        <div class="col-12 text-center py-5">
            <i class="bi bi-inbox text-muted display-3"></i>
            <h5 class="text-muted mt-3">ไม่พบรายการ E-Book</h5>
            <a href="/" class="btn btn-sm btn-primary mt-2">ดูหนังสือทั้งหมด</a>
        </div>
        {% endfor %}
    </div>
    """
    return render_page("หน้าร้านค้า", content, books=books, categories=categories, q=q, selected_cat=selected_cat)

# 2. เพิ่มสินค้าลงตะกร้า
@app.route('/cart/add/<int:ebook_id>', methods=['POST'])
def add_to_cart(ebook_id):
    conn = get_db()
    cart_id = get_user_cart_id(conn, session['user_id'])
    
    ebook = conn.execute("SELECT title, stock_quantity FROM ebooks WHERE ebook_id = ?", (ebook_id,)).fetchone()
    if not ebook or (ebook['stock_quantity'] or 0) <= 0:
        flash("❌ ขออภัย สินค้ารายการนี้หมดแล้ว", "danger")
        return redirect(request.referrer or url_for('index'))

    item = conn.execute("SELECT cart_item_id, quantity FROM cart_items WHERE cart_id = ? AND ebook_id = ?",
                        (cart_id, ebook_id)).fetchone()
    if item:
        conn.execute("UPDATE cart_items SET quantity = quantity + 1 WHERE cart_item_id = ?", (item['cart_item_id'],))
    else:
        conn.execute("INSERT INTO cart_items (cart_id, ebook_id, quantity) VALUES (?, ?, 1)", (cart_id, ebook_id))
    conn.commit()

    flash(f"🛒 เพิ่ม \"{ebook['title']}\" ลงตะกร้าเรียบร้อยแล้ว!", "success")
    return redirect(request.referrer or url_for('index'))

# 3. หน้าตะกร้าสินค้า
@app.route('/cart')
def view_cart():
    conn = get_db()
    cart_id = get_user_cart_id(conn, session['user_id'])
    
    items = conn.execute("""
        SELECT ci.cart_item_id, ci.quantity, e.ebook_id, e.title, e.price, e.cover_url, c.name as category_name
        FROM cart_items ci
        JOIN ebooks e ON ci.ebook_id = e.ebook_id
        JOIN categories c ON e.category_id = c.category_id
        WHERE ci.cart_id = ?
    """, (cart_id,)).fetchall()
    
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    
    content = """
    <div class="row g-4">
        <div class="col-lg-8">
            <div class="card shadow-sm border-0 rounded-3">
                <div class="card-header bg-white py-3 border-0">
                    <h5 class="mb-0 fw-bold"><i class="bi bi-cart3 text-danger"></i> ตะกร้าสินค้าของคุณ ({{ items|length }} รายการ)</h5>
                </div>
                <div class="card-body p-0">
                    {% if items %}
                    <div class="table-responsive">
                        <table class="table align-middle mb-0">
                            <thead class="table-light small text-muted">
                                <tr>
                                    <th class="ps-3">สินค้า</th>
                                    <th>ราคาต่อหน่วย</th>
                                    <th class="text-center">จำนวน</th>
                                    <th>รวม</th>
                                    <th class="text-center">ลบ</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for item in items %}
                                <tr>
                                    <td class="ps-3">
                                        <div class="d-flex align-items-center">
                                            <img src="{{ item['cover_url'] or 'https://placehold.co/50x70' }}" class="rounded me-3" style="width: 50px; height: 70px; object-fit: cover;">
                                            <div>
                                                <h6 class="mb-0 fw-bold">{{ item['title'] }}</h6>
                                                <span class="badge bg-light text-dark small border">{{ item['category_name'] }}</span>
                                            </div>
                                        </div>
                                    </td>
                                    <td>฿{{ "{:,.2f}".format(item['price']) }}</td>
                                    <td>
                                        <div class="d-flex align-items-center justify-content-center">
                                            <form action="/cart/update/{{ item['cart_item_id'] }}" method="POST" class="d-inline m-0">
                                                <input type="hidden" name="action" value="decrease">
                                                <button class="btn btn-outline-secondary btn-sm px-2 py-0" type="submit">-</button>
                                            </form>
                                            <span class="mx-3 fw-bold">{{ item['quantity'] }}</span>
                                            <form action="/cart/update/{{ item['cart_item_id'] }}" method="POST" class="d-inline m-0">
                                                <input type="hidden" name="action" value="increase">
                                                <button class="btn btn-outline-secondary btn-sm px-2 py-0" type="submit">+</button>
                                            </form>
                                        </div>
                                    </td>
                                    <td class="fw-bold text-danger">฿{{ "{:,.2f}".format(item['price'] * item['quantity']) }}</td>
                                    <td class="text-center">
                                        <form action="/cart/remove/{{ item['cart_item_id'] }}" method="POST" class="d-inline">
                                            <button class="btn btn-link text-danger p-0" type="submit" title="ลบออกจากตะกร้า">
                                                <i class="bi bi-trash fs-5"></i>
                                            </button>
                                        </form>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                    {% else %}
                    <div class="text-center py-5">
                        <i class="bi bi-cart-x text-muted display-4"></i>
                        <p class="text-muted mt-3">ไม่มีสินค้าในตะกร้า</p>
                        <a href="/" class="btn btn-primary btn-sm px-4">ไปเลือกซื้อหนังสือ</a>
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>

        <div class="col-lg-4">
            <div class="card shadow-sm border-0 rounded-3 sticky-top" style="top: 80px;">
                <div class="card-header bg-white py-3 border-0">
                    <h5 class="mb-0 fw-bold">สรุปคำสั่งซื้อ</h5>
                </div>
                <div class="card-body">
                    <div class="d-flex justify-content-between mb-2">
                        <span class="text-muted">ยอดรวมสินค้า:</span>
                        <span>฿{{ "{:,.2f}".format(subtotal) }}</span>
                    </div>
                    <div class="d-flex justify-content-between mb-3">
                        <span class="text-muted">ส่วนลด:</span>
                        <span class="text-success">-฿0.00</span>
                    </div>
                    <hr>
                    <div class="d-flex justify-content-between mb-4">
                        <span class="fs-5 fw-bold">ยอดชำระสุทธิ:</span>
                        <span class="fs-4 fw-bold text-danger">฿{{ "{:,.2f}".format(subtotal) }}</span>
                    </div>

                    {% if items %}
                    <a href="/checkout" class="btn btn-danger w-100 py-3 fw-bold fs-5 shadow-sm rounded-pill">
                        <i class="bi bi-credit-card"></i> ไปที่หน้าชำระเงิน
                    </a>
                    {% else %}
                    <button class="btn btn-secondary w-100 py-3 fw-bold rounded-pill" disabled>ไปที่หน้าชำระเงิน</button>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
    """
    return render_page("ตะกร้าสินค้า", content, items=items, subtotal=subtotal)

@app.route('/cart/update/<int:item_id>', methods=['POST'])
def update_cart_item(item_id):
    action = request.form.get('action')
    conn = get_db()
    item = conn.execute("SELECT quantity FROM cart_items WHERE cart_item_id = ?", (item_id,)).fetchone()
    if item:
        if action == 'increase':
            conn.execute("UPDATE cart_items SET quantity = quantity + 1 WHERE cart_item_id = ?", (item_id,))
        elif action == 'decrease':
            if item['quantity'] > 1:
                conn.execute("UPDATE cart_items SET quantity = quantity - 1 WHERE cart_item_id = ?", (item_id,))
            else:
                conn.execute("DELETE FROM cart_items WHERE cart_item_id = ?", (item_id,))
        conn.commit()
    return redirect(url_for('view_cart'))

@app.route('/cart/remove/<int:item_id>', methods=['POST'])
def remove_cart_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM cart_items WHERE cart_item_id = ?", (item_id,))
    conn.commit()
    flash("🗑️ นำสินค้าออกจากตะกร้าแล้ว", "info")
    return redirect(url_for('view_cart'))

# 4. หน้าชำระเงิน
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    conn = get_db()
    cart_id = get_user_cart_id(conn, session['user_id'])
    items = conn.execute("""
        SELECT ci.quantity, e.ebook_id, e.title, e.price, e.stock_quantity
        FROM cart_items ci
        JOIN ebooks e ON ci.ebook_id = e.ebook_id
        WHERE ci.cart_id = ?
    """, (cart_id,)).fetchall()
    
    if not items:
        return redirect(url_for('index'))
        
    total_amount = sum(item['price'] * item['quantity'] for item in items)
    
    if request.method == 'POST':
        method = request.form.get('payment_method', 'PromptPay')
        
        slip_file = request.files.get('slip_image')
        proof_url = 'https://placehold.co/400x600?text=Mock+Slip'
        if slip_file and slip_file.filename != '':
            ext = os.path.splitext(slip_file.filename)[1]
            unique_name = f"slip_{uuid.uuid4().hex[:10]}{ext}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            slip_file.save(file_path)
            proof_url = f"/static/uploads/{unique_name}"

        cur = conn.cursor()
        cur.execute("INSERT INTO orders (user_id, total_amount, status) VALUES (?, ?, 'pending')",
                    (session['user_id'], total_amount))
        order_id = cur.lastrowid
        
        for it in items:
            cur.execute("INSERT INTO order_items (order_id, ebook_id, price) VALUES (?, ?, ?)",
                        (order_id, it['ebook_id'], it['price']))
            order_item_id = cur.lastrowid
            
            token = str(uuid.uuid4())
            cur.execute("INSERT INTO download_links (order_item_id, download_token, file_url) VALUES (?, ?, ?)",
                        (order_item_id, token, f"https://mock-storage.local/ebooks/{it['ebook_id']}.pdf"))
            
            cur.execute("UPDATE ebooks SET stock_quantity = MAX(0, stock_quantity - ?) WHERE ebook_id = ?",
                        (it['quantity'], it['ebook_id']))
        
        cur.execute("""
            INSERT INTO payments (order_id, amount, payment_method, payment_status, proof_url)
            VALUES (?, ?, ?, 'pending_verification', ?)
        """, (order_id, total_amount, method, proof_url))
        
        cur.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
        conn.commit()

        return redirect(url_for('my_orders'))
        
    content = """
    <div class="row justify-content-center">
        <div class="col-md-7">
            <div class="card shadow-sm border-0 rounded-3">
                <div class="card-header bg-white py-3 border-0">
                    <h5 class="mb-0 fw-bold"><i class="bi bi-wallet2 text-primary"></i> เช็คเอาท์และชำระเงินจำลอง</h5>
                </div>
                <div class="card-body">
                    <h6 class="fw-bold mb-3">สรุปรายการที่จะชำระ:</h6>
                    <ul class="list-group mb-3">
                        {% for it in items %}
                        <li class="list-group-item d-flex justify-content-between lh-sm">
                            <div>
                                <h6 class="my-0">{{ it['title'] }}</h6>
                                <small class="text-muted">จำนวน: {{ it['quantity'] }} เล่ม</small>
                            </div>
                            <span class="text-muted">฿{{ "{:,.2f}".format(it['price'] * it['quantity']) }}</span>
                        </li>
                        {% endfor %}
                        <li class="list-group-item d-flex justify-content-between bg-light">
                            <span class="fw-bold">ยอดที่ต้องชำระทั้งสิ้น</span>
                            <strong class="text-danger fs-5">฿{{ "{:,.2f}".format(total_amount) }}</strong>
                        </li>
                    </ul>

                    <form method="POST" enctype="multipart/form-data">
                        <h6 class="fw-bold mb-2">เลือกวิธีชำระเงิน:</h6>
                        <div class="form-check mb-2 p-3 border rounded">
                            <input class="form-check-input ms-0 me-2" type="radio" name="payment_method" value="PromptPay QR" checked>
                            <label class="form-check-label fw-bold">
                                <i class="bi bi-qr-code"></i> สแกน QR Code พร้อมเพย์ (จำลอง)
                            </label>
                        </div>
                        <div class="form-check mb-3 p-3 border rounded">
                            <input class="form-check-input ms-0 me-2" type="radio" name="payment_method" value="Bank Transfer">
                            <label class="form-check-label fw-bold">
                                <i class="bi bi-bank"></i> โอนผ่านบัญชีธนาคาร (แนบสลิปจำลอง)
                            </label>
                        </div>

                        <div class="mb-4 p-3 bg-light rounded border">
                            <label class="form-label fw-bold mb-1"><i class="bi bi-paperclip"></i> แนบภาพหลักฐานการชำระเงิน (สลิปโอนเงิน)</label>
                            <input type="file" class="form-control" name="slip_image" accept="image/*">
                            <small class="text-muted">* สามารถเลือกไฟล์รูปสลิปจำลองเพื่อให้อาจารย์/แอดมินตรวจสอบได้</small>
                        </div>

                        <button class="btn btn-danger w-100 py-3 fw-bold rounded-pill shadow-sm" type="submit">
                            <i class="bi bi-check2-circle"></i> ยืนยันการสั่งซื้อและแจ้งชำระเงิน (฿{{ "{:,.2f}".format(total_amount) }})
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """
    return render_page("ชำระเงิน", content, items=items, total_amount=total_amount)

# 5. ประวัติการสั่งซื้อ (User)
@app.route('/my-orders')
def my_orders():
    conn = get_db()
    orders = conn.execute("""
        SELECT o.order_id, o.status, o.total_amount,
               datetime(o.created_at, '+7 hours') as created_at,
               p.payment_method, p.payment_status,
               COUNT(oi.order_item_id) as total_items
        FROM orders o
        LEFT JOIN payments p ON o.order_id = p.order_id
        LEFT JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.user_id = ?
        GROUP BY o.order_id
        ORDER BY o.order_id DESC
    """, (session['user_id'],)).fetchall()
    
    downloads = conn.execute("""
        SELECT o.order_id, e.ebook_id, e.title, e.cover_url, dl.download_token,
               datetime(o.created_at, '+7 hours') as created_at
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN ebooks e ON oi.ebook_id = e.ebook_id
        JOIN download_links dl ON oi.order_item_id = dl.order_item_id
        WHERE o.user_id = ? AND o.status = 'confirmed'
        ORDER BY o.order_id DESC
    """, (session['user_id'],)).fetchall()

    content = """
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h3 class="fw-bold mb-1"><i class="bi bi-bag-check-fill text-danger"></i> ประวัติคำสั่งซื้อและชั้นหนังสือ</h3>
            <p class="text-muted small m-0">ตรวจสอบสถานะการชำระเงิน และดาวน์โหลด E-Book ที่ได้รับการอนุมัติ</p>
        </div>
        <a href="/" class="btn btn-outline-dark btn-sm rounded-pill px-3"><i class="bi bi-arrow-left"></i> กลับไปเลือกซื้อเพิ่ม</a>
    </div>

    <div class="card border-0 shadow-sm rounded-4 mb-5 overflow-hidden">
        <div class="card-header bg-success text-white py-3 px-4 d-flex justify-content-between align-items-center">
            <span class="fw-bold fs-5"><i class="bi bi-journal-bookmark-fill"></i> ชั้นหนังสือของฉัน (พร้อมดาวน์โหลด {{ downloads|length }} เล่ม)</span>
            <span class="badge bg-light text-success fw-bold">Active</span>
        </div>
        <div class="card-body p-4 bg-light">
            {% if downloads %}
            <div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3">
                {% for d in downloads %}
                <div class="col">
                    <div class="card h-100 border-0 shadow-sm p-3 bg-white rounded-3">
                        <div class="d-flex align-items-center">
                            <img src="{{ d['cover_url'] or 'https://placehold.co/60x85' }}" class="rounded me-3 shadow-sm" style="width: 60px; height: 85px; object-fit: cover;">
                            <div class="flex-grow-1">
                                <h6 class="fw-bold mb-1 text-truncate" style="max-width: 180px;">{{ d['title'] }}</h6>
                                <div class="text-muted small mb-2">คำสั่งซื้อ: #{{ d['order_id'] }}</div>
                                <a href="/download/{{ d['download_token'] }}" class="btn btn-success btn-sm w-100 fw-bold rounded-pill">
                                    <i class="bi bi-cloud-arrow-down-fill"></i> ดาวน์โหลด E-Book
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="text-center py-4 bg-white rounded-3 border">
                <i class="bi bi-lock-fill text-muted fs-1 mb-2 d-block"></i>
                <h6 class="fw-bold text-dark">ยังไม่มีหนังสือที่พร้อมดาวน์โหลด</h6>
                <p class="text-muted small m-0">เมื่อแอดมินอนุมัติคำสั่งซื้อ ลิงก์ดาวน์โหลดจะแสดงในส่วนนี้ทันที</p>
            </div>
            {% endif %}
        </div>
    </div>

    <h5 class="fw-bold mb-3"><i class="bi bi-clock-history"></i> รายการคำสั่งซื้อทั้งหมดของคุณ</h5>
    <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-4">
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-light small">
                        <tr>
                            <th class="ps-4">เลขออเดอร์</th>
                            <th>วัน-เวลาสั่งซื้อ</th>
                            <th>จำนวนสินค้า</th>
                            <th>ยอดสุทธิ</th>
                            <th>ช่องทางชำระเงิน</th>
                            <th>สถานะคำสั่งซื้อ</th>
                            <th class="text-center pe-4">สิทธิ์ดาวน์โหลด</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for o in orders %}
                        <tr>
                            <td class="ps-4 fw-bold text-primary">#{{ o['order_id'] }}</td>
                            <td class="small text-muted">{{ o['created_at'] }}</td>
                            <td>{{ o['total_items'] }} เล่ม</td>
                            <td class="fw-bold text-danger">฿{{ "{:,.2f}".format(o['total_amount']) }}</td>
                            <td>
                                <span class="badge bg-light text-dark border">{{ o['payment_method'] or 'PromptPay QR' }}</span>
                            </td>
                            <td>
                                {% if o['status'] == 'confirmed' %}
                                    <span class="badge bg-success-subtle text-success border border-success px-2 py-1">
                                        <i class="bi bi-check-circle-fill"></i> ชำระเงินสำเร็จ
                                    </span>
                                {% elif o['status'] == 'pending' %}
                                    <span class="badge bg-warning-subtle text-dark border border-warning px-2 py-1">
                                        <i class="bi bi-hourglass-split"></i> รอแอดมินตรวจสอบ
                                    </span>
                                {% else %}
                                    <span class="badge bg-danger-subtle text-danger border border-danger px-2 py-1">
                                        <i class="bi bi-x-circle-fill"></i> ยกเลิกคำสั่งซื้อแล้ว
                                    </span>
                                {% endif %}
                            </td>
                            <td class="text-center pe-4">
                                {% if o['status'] == 'confirmed' %}
                                    <span class="text-success small fw-bold"><i class="bi bi-unlock-fill"></i> ปลดล็อกแล้ว</span>
                                {% elif o['status'] == 'pending' %}
                                    <span class="text-muted small"><i class="bi bi-lock-fill text-warning"></i> รออนุมัติ...</span>
                                {% else %}
                                    <span class="text-danger small"><i class="bi bi-slash-circle"></i> ปิดสิทธิ์</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="7" class="text-center py-5 text-muted">คุณยังไม่มีรายการสั่งซื้อ</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_page("คำสั่งซื้อของฉัน", content, orders=orders, downloads=downloads)

# 6. ดาวน์โหลดไฟล์
@app.route('/download/<token>')
def download(token):
    conn = get_db()
    data = conn.execute("""
        SELECT dl.file_url, o.status, e.title
        FROM download_links dl
        JOIN order_items oi ON dl.order_item_id = oi.order_item_id
        JOIN orders o ON oi.order_id = o.order_id
        JOIN ebooks e ON oi.ebook_id = e.ebook_id
        WHERE dl.download_token = ?
    """, (token,)).fetchone()
    
    if not data:
        abort(404, "ไม่พบลิงก์ดาวน์โหลด")
    if data['status'] != 'confirmed':
        abort(403, "คำสั่งซื้อยังไม่ได้รับการยืนยันการชำระเงิน ไม่อนุญาตให้ดาวน์โหลด")
        
    return f"""
    <div style='font-family:sans-serif; text-align:center; padding:50px;'>
        <h2 style='color:#198754;'>✅ เริ่มการดาวน์โหลด: {data['title']}</h2>
        <p>URL ไฟล์จำลอง: <code>{data['file_url']}</code></p>
        <a href='/my-orders' style='display:inline-block; margin-top:20px; padding:10px 20px; background:#0d6efd; color:#fff; text-decoration:none; border-radius:5px;'>กลับหน้ารายการสั่งซื้อ</a>
    </div>
    """

# 7. แอดมิน Dashboard (จัดการข้อมูล, บัญชีผู้ใช้, วิเคราะห์พฤติกรรมลูกค้า, ตรวจสอบยอดขายและคนซื้อรายเล่ม)
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return "<h3>เฉพาะผู้ดูแลระบบ (Admin) เท่านั้น</h3><a href='/'>กลับหน้าร้าน</a>", 403
    
    conn = get_db()
    
    # ดึงรายการหนังสือ พร้อมคำนวณจำนวนเล่มที่ขายได้จริง (นับเฉพาะออเดอร์ confirmed)
    ebooks_list = conn.execute("""
        SELECT e.*, c.name as category_name, a.name as author_name,
               COUNT(CASE WHEN o.status = 'confirmed' THEN oi.order_item_id END) as total_sold
        FROM ebooks e
        JOIN categories c ON e.category_id = c.category_id
        JOIN authors a ON e.author_id = a.author_id
        LEFT JOIN order_items oi ON e.ebook_id = oi.ebook_id
        LEFT JOIN orders o ON oi.order_id = o.order_id
        GROUP BY e.ebook_id
        ORDER BY e.ebook_id DESC
    """).fetchall()

    categories = conn.execute("""
        SELECT c.*, COUNT(e.ebook_id) as book_count
        FROM categories c
        LEFT JOIN ebooks e ON c.category_id = e.category_id AND e.is_active = 1
        GROUP BY c.category_id
    """).fetchall()
    
    authors = conn.execute("SELECT * FROM authors").fetchall()

    # ดึงรายการออเดอร์ พร้อมปรับเวลา created_at เป็นเวลาไทย (+7 hours)
    orders = conn.execute("""
        SELECT o.order_id, u.full_name, u.email, o.total_amount, o.status,
               datetime(o.created_at, '+7 hours') as created_at,
               p.payment_method, p.payment_status, p.proof_url
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        LEFT JOIN payments p ON o.order_id = p.order_id
        ORDER BY o.order_id DESC
    """).fetchall()
    
    # ดึงข้อมูลบัญชีผู้ใช้ทั้งหมด พร้อมปรับเวลาสมัครเป็นเวลาไทย (+7 hours)[cite: 1]
    all_users = conn.execute("""
        SELECT u.user_id, u.email, u.full_name,
               datetime(u.created_at, '+7 hours') as created_at,
               r.role_id, r.role_name
        FROM users u
        JOIN roles r ON u.role_id = r.role_id
        ORDER BY u.user_id ASC
    """).fetchall()

    total_users_count = len(all_users)
    total_admins_count = sum(1 for u in all_users if u['role_name'] == 'admin')

    # วิเคราะห์พฤติกรรมการซื้อของลูกค้าแต่ละคน (Behavior Analytics / RFM)
    user_behaviors = conn.execute("""
        SELECT 
            u.user_id,
            u.full_name,
            u.email,
            COUNT(DISTINCT CASE WHEN o.status = 'confirmed' THEN o.order_id END) AS completed_orders,
            COALESCE(SUM(CASE WHEN o.status = 'confirmed' THEN o.total_amount ELSE 0 END), 0) AS total_spent,
            MAX(CASE WHEN o.status = 'confirmed' THEN datetime(o.created_at, '+7 hours') END) AS last_purchase_date,
            (
                SELECT c.name
                FROM order_items oi2
                JOIN ebooks eb2 ON oi2.ebook_id = eb2.ebook_id
                JOIN categories c ON eb2.category_id = c.category_id
                JOIN orders o2 ON oi2.order_id = o2.order_id
                WHERE o2.user_id = u.user_id AND o2.status = 'confirmed'
                GROUP BY c.category_id
                ORDER BY COUNT(oi2.order_item_id) DESC
                LIMIT 1
            ) AS favorite_category,
            (
                SELECT COUNT(ci.cart_item_id)
                FROM carts cr
                JOIN cart_items ci ON cr.cart_id = ci.cart_id
                WHERE cr.user_id = u.user_id
            ) AS pending_cart_items
        FROM users u
        LEFT JOIN orders o ON u.user_id = o.user_id
        GROUP BY u.user_id
        ORDER BY total_spent DESC, completed_orders DESC
    """).fetchall()

    active_buyers_count = sum(1 for ub in user_behaviors if ub['completed_orders'] > 0)
    abandoned_carts_count = sum(1 for ub in user_behaviors if (ub['pending_cart_items'] or 0) > 0)

    # 4 รายงานเชิงสถิติ (ตัดยอดรายวันตามเวลาไทย)[cite: 1]
    r1 = conn.execute("""
        SELECT DATE(datetime(created_at, '+7 hours')) as sale_date, COUNT(order_id) as total_orders, 
               SUM(total_amount) as total_sales, AVG(total_amount) as avg_sales
        FROM orders WHERE status = 'confirmed'
        GROUP BY DATE(datetime(created_at, '+7 hours')) ORDER BY sale_date DESC LIMIT 5
    """).fetchall()

    r2 = conn.execute("""
        SELECT e.title, COUNT(oi.order_item_id) as total_sold, SUM(oi.price) as revenue
        FROM order_items oi
        JOIN ebooks e ON oi.ebook_id = e.ebook_id
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.status = 'confirmed'
        GROUP BY e.ebook_id ORDER BY total_sold DESC LIMIT 5
    """).fetchall()

    r3 = conn.execute("""
        SELECT c.name as category_name, COUNT(oi.order_item_id) as items_sold, SUM(oi.price) as category_revenue
        FROM categories c
        JOIN ebooks e ON c.category_id = e.category_id
        JOIN order_items oi ON e.ebook_id = oi.ebook_id
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.status = 'confirmed'
        GROUP BY c.category_id ORDER BY category_revenue DESC
    """).fetchall()

    r4 = conn.execute("""
        SELECT u.full_name, u.email, COUNT(o.order_id) as total_orders,
               SUM(CASE WHEN o.status = 'confirmed' THEN o.total_amount ELSE 0 END) as total_spent
        FROM users u
        JOIN orders o ON u.user_id = o.user_id
        GROUP BY u.user_id HAVING total_orders > 0
        ORDER BY total_spent DESC LIMIT 5
    """).fetchall()

    content = """
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3 class="fw-bold m-0"><i class="bi bi-gear-fill text-warning"></i> ระบบจัดการร้านค้าหลังบ้าน (Admin)</h3>
        <div class="d-flex flex-wrap gap-2">
            <a href="#reportsSection" class="btn btn-outline-dark fw-bold rounded-pill px-3">
                <i class="bi bi-bar-chart-line-fill text-primary"></i> 4 รายงานเชิงสถิติ
            </a>
            <a href="#booksSection" class="btn btn-outline-dark fw-bold rounded-pill px-3">
                <i class="bi bi-book"></i> รายการหนังสือและยอดขาย
            </a>
            <a href="#behaviorSection" class="btn btn-outline-success fw-bold rounded-pill px-3">
                <i class="bi bi-graph-up"></i> วิเคราะห์พฤติกรรมลูกค้า
            </a>
            <a href="#usersSection" class="btn btn-outline-info fw-bold rounded-pill px-3">
                <i class="bi bi-people-fill"></i> จัดการบัญชีผู้ใช้
            </a>
            <button class="btn btn-outline-primary fw-bold rounded-pill px-3" data-bs-toggle="modal" data-bs-target="#addCategoryModal">
                <i class="bi bi-tag"></i> + เพิ่มหมวดหมู่ใหม่
            </button>
            <button class="btn btn-success fw-bold rounded-pill px-4" data-bs-toggle="modal" data-bs-target="#addBookModal">
                <i class="bi bi-plus-circle"></i> + เพิ่มหนังสือใหม่
            </button>
        </div>
    </div>

    <!-- ส่วนวิเคราะห์พฤติกรรมการซื้อของลูกค้า (Customer Behavior Insights) -->
    <div class="card mb-4 border-0 shadow-sm rounded-3" id="behaviorSection">
        <div class="card-header bg-primary text-white fw-bold py-2 d-flex justify-content-between align-items-center">
            <span><i class="bi bi-pie-chart-fill"></i> รายงานวิเคราะห์พฤติกรรมการซื้อของลูกค้า (Customer Buying Behavior)</span>
            <span class="badge bg-light text-dark">
                ลูกค้าที่เคยซื้อสำเร็จ {{ active_buyers_count }} คน | ตะกร้าค้างชำระ {{ abandoned_carts_count }} คน
            </span>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-light small">
                        <tr>
                            <th>ลูกค้า</th>
                            <th class="text-center">สั่งซื้อสำเร็จ</th>
                            <th class="text-end">ยอดซื้อรวม (บาท)</th>
                            <th class="text-center">ซื้อล่าสุดเมื่อ</th>
                            <th>แนวหนังสือที่ชอบ</th>
                            <th class="text-center">ของที่ค้างในตะกร้า</th>
                            <th class="text-center">กลุ่มพฤติกรรม (Segment)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for ub in user_behaviors %}
                        <tr>
                            <td>
                                <div class="fw-bold">{{ ub['full_name'] }}</div>
                                <small class="text-muted">{{ ub['email'] }}</small>
                            </td>
                            <td class="text-center">
                                <span class="badge bg-light text-dark border">{{ ub['completed_orders'] }} ครั้ง</span>
                            </td>
                            <td class="text-end fw-bold text-success">
                                ฿{{ "{:,.2f}".format(ub['total_spent']) }}
                            </td>
                            <td class="text-center small text-muted">
                                {{ ub['last_purchase_date'] or 'ยังไม่เคยซื้อ' }}
                            </td>
                            <td>
                                {% if ub['favorite_category'] %}
                                    <span class="badge bg-info text-dark"><i class="bi bi-book-half"></i> {{ ub['favorite_category'] }}</span>
                                {% else %}
                                    <span class="text-muted small">-</span>
                                {% endif %}
                            </td>
                            <td class="text-center">
                                {% if (ub['pending_cart_items'] or 0) > 0 %}
                                    <button type="button" class="btn btn-sm btn-warning text-dark fw-bold rounded-pill px-2 py-1 shadow-sm"
                                            onclick="viewUserCart('{{ ub['user_id'] }}', '{{ ub['full_name'] }}')"
                                            title="คลิกเพื่อดูหนังสือที่ค้างในตะกร้า">
                                        <i class="bi bi-cart3"></i> ค้าง {{ ub['pending_cart_items'] }} เล่ม (ดูของ)
                                    </button>
                                {% else %}
                                    <span class="text-muted small">-</span>
                                {% endif %}
                            </td>
                            <td class="text-center">
                                {% if ub['total_spent'] >= 1000 %}
                                    <span class="badge bg-danger"><i class="bi bi-trophy-fill"></i> VIP Spender</span>
                                {% elif ub['completed_orders'] >= 2 %}
                                    <span class="badge bg-success"><i class="bi bi-star-fill"></i> ลูกค้าประจำ</span>
                                {% elif ub['completed_orders'] == 1 %}
                                    <span class="badge bg-primary">ลูกค้าใหม่</span>
                                {% elif (ub['pending_cart_items'] or 0) > 0 %}
                                    <span class="badge bg-warning text-dark">ลังเล (มีของในตะกร้า)</span>
                                {% else %}
                                    <span class="badge bg-secondary">ผู้เยี่ยมชม</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Modal แสดงรายการหนังสือที่ค้างในตะกร้าของลูกค้า -->
    <div class="modal fade" id="userCartModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header bg-dark text-white">
                    <h5 class="modal-title fw-bold" id="userCartModalTitle">🛒 รายการหนังสือที่ค้างในตะกร้า</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body p-0">
                    <div id="userCartLoading" class="text-center py-4">
                        <div class="spinner-border text-warning" role="status"></div>
                        <p class="text-muted mt-2 mb-0">กำลังโหลดรายการในตะกร้า...</p>
                    </div>
                    <div id="userCartContent" class="d-none">
                        <div class="table-responsive">
                            <table class="table table-hover align-middle mb-0">
                                <thead class="table-light small">
                                    <tr>
                                        <th class="ps-3">รูปปก</th>
                                        <th>ชื่อหนังสือ</th>
                                        <th>หมวดหมู่</th>
                                        <th class="text-center">จำนวนในตะกร้า</th>
                                        <th class="text-end pe-3">ราคา/เล่ม</th>
                                    </tr>
                                </thead>
                                <tbody id="userCartTableBody">
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <div id="userCartEmpty" class="text-center py-4 d-none text-muted">
                        <i class="bi bi-cart-x fs-2 d-block"></i>
                        ไม่มีสินค้าค้างในตะกร้าแล้ว
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิด</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    function viewUserCart(userId, userName) {
        document.getElementById('userCartModalTitle').innerText = '🛒 สินค้าในตะกร้าของคุณ ' + userName;
        document.getElementById('userCartLoading').classList.remove('d-none');
        document.getElementById('userCartContent').classList.add('d-none');
        document.getElementById('userCartEmpty').classList.add('d-none');

        var modal = new bootstrap.Modal(document.getElementById('userCartModal'));
        modal.show();

        fetch('/admin/user/' + userId + '/cart')
            .then(res => res.json())
            .then(data => {
                document.getElementById('userCartLoading').classList.add('d-none');
                if (data.items && data.items.length > 0) {
                    var rowsHtml = '';
                    data.items.forEach(it => {
                        rowsHtml += `
                            <tr>
                                <td class="ps-3">
                                    <img src="${it.cover_url || 'https://placehold.co/40x55'}" style="width: 40px; height: 55px; object-fit: cover;" class="rounded">
                                </td>
                                <td><div class="fw-bold">${it.title}</div></td>
                                <td><span class="badge bg-light text-dark border">${it.category_name}</span></td>
                                <td class="text-center fw-bold"><span class="badge bg-warning text-dark">${it.quantity} เล่ม</span></td>
                                <td class="text-end pe-3 fw-bold text-danger">฿${parseFloat(it.price).toLocaleString('th-TH', {minimumFractionDigits: 2})}</td>
                            </tr>
                        `;
                    });
                    document.getElementById('userCartTableBody').innerHTML = rowsHtml;
                    document.getElementById('userCartContent').classList.remove('d-none');
                } else {
                    document.getElementById('userCartEmpty').classList.remove('d-none');
                }
            })
            .catch(err => {
                document.getElementById('userCartLoading').classList.add('d-none');
                alert('เกิดข้อผิดพลาดในการโหลดข้อมูลตะกร้า');
            });
    }
    </script>

    <!-- ส่วนจัดการบัญชีผู้ใช้และมอบสิทธิ์ Admin[cite: 1] -->
    <div class="card mb-4 border-0 shadow-sm rounded-3" id="usersSection">
        <div class="card-header bg-dark text-white fw-bold py-2 d-flex justify-content-between align-items-center">
            <span>👥 จัดการบัญชีผู้ใช้ทั้งหมด ({{ total_users_count }} บัญชี)</span>
            <span class="badge bg-warning text-dark">แอดมิน {{ total_admins_count }} คน / สมาชิกทั่วไป {{ total_users_count - total_admins_count }} คน</span>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-light small">
                        <tr>
                            <th style="width: 70px;">ID</th>
                            <th>ชื่อ-นามสกุล</th>
                            <th>อีเมล</th>
                            <th>วันที่สมัคร (เวลาไทย)</th>
                            <th>ระดับสิทธิ์</th>
                            <th class="text-center" style="width: 200px;">จัดการสิทธิ์</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for u in all_users %}
                        <tr>
                            <td class="fw-bold">#{{ u['user_id'] }}</td>
                            <td>{{ u['full_name'] }}</td>
                            <td>{{ u['email'] }}</td>
                            <td class="small text-muted">{{ u['created_at'] }}</td>
                            <td>
                                {% if u['role_name'] == 'admin' %}
                                    <span class="badge bg-danger"><i class="bi bi-shield-lock-fill"></i> Admin</span>
                                {% else %}
                                    <span class="badge bg-secondary"><i class="bi bi-person"></i> Customer</span>
                                {% endif %}
                            </td>
                            <td class="text-center">
                                {% if u['role_name'] == 'admin' %}
                                    <button class="btn btn-sm btn-outline-danger rounded-pill px-3" 
                                            onclick="openRoleModal('{{ u['user_id'] }}', '{{ u['full_name'] }}', 'customer', 'ปลดสิทธิ์ Admin')">
                                        <i class="bi bi-person-dash"></i> ปลดสิทธิ์ Admin
                                    </button>
                                {% else %}
                                    <button class="btn btn-sm btn-outline-success rounded-pill px-3" 
                                            onclick="openRoleModal('{{ u['user_id'] }}', '{{ u['full_name'] }}', 'admin', 'แต่งตั้งเป็น Admin')">
                                        <i class="bi bi-shield-plus"></i> ตั้งเป็น Admin
                                    </button>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Modal ยืนยันรหัสผ่านเพื่อเปลี่ยนสิทธิ์ผู้ใช้[cite: 1] -->
    <div class="modal fade" id="changeRoleModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form action="/admin/user/change-role" method="POST">
                    <div class="modal-header bg-dark text-white">
                        <h6 class="modal-title fw-bold" id="roleModalTitle">ยืนยันการเปลี่ยนสิทธิ์</h6>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p id="roleModalDesc" class="mb-3"></p>
                        <input type="hidden" name="target_user_id" id="targetUserId">
                        <input type="hidden" name="new_role_name" id="newRoleName">
                        
                        <div class="alert alert-warning small py-2 mb-3">
                            <i class="bi bi-shield-lock"></i> ต้องยืนยันรหัสผ่านของบัญชีแอดมินที่กำลังใช้งานอยู่ก่อนดำเนินการ
                        </div>

                        <div class="mb-2">
                            <label class="form-label fw-bold">รหัสผ่านของคุณ (Admin):</label>
                            <input type="password" class="form-control" name="admin_password" placeholder="กรอกรหัสผ่านเพื่อยืนยัน" required>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                        <button type="submit" class="btn btn-primary btn-sm fw-bold px-3" id="roleModalSubmitBtn">ยืนยัน</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
    function openRoleModal(userId, userName, targetRole, actionText) {
        document.getElementById('targetUserId').value = userId;
        document.getElementById('newRoleName').value = targetRole;
        document.getElementById('roleModalTitle').innerText = actionText;
        document.getElementById('roleModalDesc').innerHTML = 'คุณกำลังจะทำการ <strong>' + actionText + '</strong> ให้กับคุณ <strong>' + userName + '</strong>';
        
        var submitBtn = document.getElementById('roleModalSubmitBtn');
        if (targetRole === 'admin') {
            submitBtn.className = 'btn btn-success btn-sm fw-bold px-3';
        } else {
            submitBtn.className = 'btn btn-danger btn-sm fw-bold px-3';
        }
        
        var myModal = new bootstrap.Modal(document.getElementById('changeRoleModal'));
        myModal.show();
    }
    </script>

    <!-- ส่วนจัดการหมวดหมู่สินค้า[cite: 1] -->
    <div class="card mb-4 border-0 shadow-sm rounded-3">
        <div class="card-header bg-secondary text-white fw-bold py-2 d-flex justify-content-between align-items-center">
            <span>🏷️ หมวดหมู่หนังสือทั้งหมด ({{ categories|length }} หมวด)</span>
            <small>* กำหนดและเพิ่มหมวดหมู่ให้ E-Book ได้ที่นี่</small>
        </div>
        <div class="card-body p-3">
            <div class="d-flex flex-wrap gap-2">
                {% for c in categories %}
                <span class="badge bg-light text-dark border p-2 d-flex align-items-center gap-2">
                    <span class="fw-bold">{{ c['name'] }}</span>
                    <span class="badge bg-primary rounded-pill">{{ c['book_count'] }} เล่ม</span>
                    {% if c['book_count'] == 0 %}
                    <a href="/admin/category/delete/{{ c['category_id'] }}" class="text-danger ms-1" onclick="return confirm('ยืนยันลบหมวดหมู่นี้?')" title="ลบหมวดหมู่">
                        <i class="bi bi-x"></i>
                    </a>
                    {% endif %}
                </span>
                {% endfor %}
            </div>
        </div>
    </div>

    <!-- Modal เพิ่มหมวดหมู่ใหม่[cite: 1] -->
    <div class="modal fade" id="addCategoryModal" tabindex="-1">
        <div class="modal-dialog modal-sm">
            <div class="modal-content">
                <form action="/admin/category/add" method="POST">
                    <div class="modal-header bg-dark text-white">
                        <h6 class="modal-title fw-bold">+ เพิ่มหมวดหมู่ใหม่</h6>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <label class="form-label fw-bold">ชื่อหมวดหมู่</label>
                        <input type="text" class="form-control" name="category_name" placeholder="เช่น วิทยาศาสตร์, ภาษาศาสตร์" required>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                        <button type="submit" class="btn btn-primary btn-sm fw-bold">บันทึก</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- จัดการรายการหนังสือ + แสดงยอดขายจริง + ปุ่มดูรายชื่อคนซื้อ -->
    <div class="card mb-4 border-0 shadow-sm rounded-3" id="booksSection">
        <div class="card-header bg-dark text-white fw-bold py-3 d-flex justify-content-between align-items-center">
            <span>📚 จัดการรายการหนังสือและยอดขายจริง (ปรับราคา / สต็อก / ตรวจสอบคนซื้อ)</span>
            <span class="badge bg-secondary">ทั้งหมด {{ ebooks_list|length }} เล่ม</span>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table align-middle table-hover mb-0">
                    <thead class="table-light small">
                        <tr>
                            <th>รูปปก</th>
                            <th>ชื่อหนังสือ</th>
                            <th>หมวดหมู่</th>
                            <th>ผู้แต่ง</th>
                            <th style="width: 130px;">ราคา (บาท)</th>
                            <th style="width: 140px;" class="text-center">ขายได้แล้ว</th>
                            <th style="width: 120px;">คงเหลือ</th>
                            <th class="text-center" style="width: 220px;">จัดการ</th>
                        </tr>
                    </thead>
                    <tbody>
                    {% for b in ebooks_list %}
                    <tr class="{% if not b['is_active'] %}table-secondary text-muted{% endif %}">
                        <td>
                            <img src="{{ b['cover_url'] or 'https://placehold.co/40x55' }}" style="width: 40px; height: 55px; object-fit: cover;" class="rounded">
                        </td>
                        <td>
                            <div class="fw-bold">{{ b['title'] }}</div>
                            {% if not b['is_active'] %}<span class="badge bg-danger small">ปิดการขายแล้ว</span>{% endif %}
                        </td>
                        <td><span class="badge bg-light text-dark border">{{ b['category_name'] }}</span></td>
                        <td class="small">{{ b['author_name'] }}</td>
                        
                        <form action="/admin/book/update/{{ b['ebook_id'] }}" method="POST">
                            <td>
                                <input type="number" step="0.01" class="form-control form-control-sm" name="price" value="{{ b['price'] }}" required>
                            </td>
                            <td class="text-center">
                                <span class="badge bg-success-subtle text-success border border-success fw-bold px-2 py-1 fs-6">
                                    {{ b['total_sold'] or 0 }} เล่ม
                                </span>
                            </td>
                            <td>
                                <input type="number" class="form-control form-control-sm {% if (b['stock_quantity'] or 0) <= 0 %}border-danger bg-danger-subtle{% endif %}" name="stock_quantity" value="{{ b['stock_quantity'] or 0 }}" required>
                            </td>
                            <td class="text-center">
                                <div class="d-flex justify-content-center gap-1">
                                    <button type="button" class="btn btn-sm btn-outline-info rounded-pill px-2" 
                                            onclick="viewBookBuyers('{{ b['ebook_id'] }}', '{{ b['title'] }}')" title="ดูว่าใครซื้อหนังสือเล่มนี้บ้าง">
                                        <i class="bi bi-people-fill"></i> ดูคนซื้อ
                                    </button>
                                    <button type="submit" class="btn btn-sm btn-primary rounded-pill px-2" title="บันทึกราคาและสต็อก">
                                        <i class="bi bi-save"></i>
                                    </button>
                        </form>
                                    <a href="/admin/book/delete/{{ b['ebook_id'] }}" class="btn btn-sm btn-outline-danger rounded-pill px-2" onclick="return confirm('ยืนยันลบหนังสือเล่มนี้?')" title="ลบหนังสือ">
                                        <i class="bi bi-trash"></i>
                                    </a>
                                </div>
                            </td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Modal แสดงรายชื่อลูกค้าที่ซื้อหนังสือเล่มนั้นๆ -->
    <div class="modal fade" id="bookBuyersModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header bg-dark text-white">
                    <h5 class="modal-title fw-bold" id="buyersModalTitle">👥 รายชื่อผู้ซื้อหนังสือ</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body p-0">
                    <div id="buyersLoading" class="text-center py-4">
                        <div class="spinner-border text-primary" role="status"></div>
                        <p class="text-muted mt-2 mb-0">กำลังโหลดรายชื่อผู้ซื้อ...</p>
                    </div>
                    <div id="buyersContent" class="d-none">
                        <div class="table-responsive">
                            <table class="table table-hover align-middle mb-0">
                                <thead class="table-light small">
                                    <tr>
                                        <th>เลขออเดอร์</th>
                                        <th>ชื่อลูกค้า</th>
                                        <th>อีเมล</th>
                                        <th>วันที่ซื้อ (เวลาไทย)</th>
                                        <th>ราคาตอนซื้อ</th>
                                    </tr>
                                </thead>
                                <tbody id="buyersTableBody">
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <div id="buyersEmpty" class="text-center py-4 d-none text-muted">
                        <i class="bi bi-inbox fs-2 d-block"></i>
                        ยังไม่มีลูกค้าสั่งซื้อหนังสือเล่มนี้สำเร็จ
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิด</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    function viewBookBuyers(ebookId, title) {
        document.getElementById('buyersModalTitle').innerText = '👥 ผู้ซื้อหนังสือ: ' + title;
        document.getElementById('buyersLoading').classList.remove('d-none');
        document.getElementById('buyersContent').classList.add('d-none');
        document.getElementById('buyersEmpty').classList.add('d-none');
        
        var modal = new bootstrap.Modal(document.getElementById('bookBuyersModal'));
        modal.show();

        fetch('/admin/book/' + ebookId + '/buyers')
            .then(res => res.json())
            .then(data => {
                document.getElementById('buyersLoading').classList.add('d-none');
                if (data.buyers && data.buyers.length > 0) {
                    var rowsHtml = '';
                    data.buyers.forEach(b => {
                        rowsHtml += `
                            <tr>
                                <td class="fw-bold text-primary">#${b.order_id}</td>
                                <td class="fw-bold">${b.full_name}</td>
                                <td class="text-muted">${b.email}</td>
                                <td class="small">${b.created_at}</td>
                                <td class="fw-bold text-success">฿${parseFloat(b.price).toLocaleString('th-TH', {minimumFractionDigits: 2})}</td>
                            </tr>
                        `;
                    });
                    document.getElementById('buyersTableBody').innerHTML = rowsHtml;
                    document.getElementById('buyersContent').classList.remove('d-none');
                } else {
                    document.getElementById('buyersEmpty').classList.remove('d-none');
                }
            })
            .catch(err => {
                document.getElementById('buyersLoading').classList.add('d-none');
                alert('เกิดข้อผิดพลาดในการโหลดข้อมูลผู้ซื้อ');
            });
    }
    </script>

    <!-- Modal เพิ่มหนังสือใหม่[cite: 1] -->
    <div class="modal fade" id="addBookModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form action="/admin/book/add" method="POST">
                    <div class="modal-header bg-dark text-white">
                        <h5 class="modal-title fw-bold">+ เพิ่มหนังสือ E-Book ใหม่</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label fw-bold">ชื่อหนังสือ</label>
                            <input type="text" class="form-control" name="title" required>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">หมวดหมู่</label>
                                <select class="form-select" name="category_id" required>
                                    {% for c in categories %}
                                    <option value="{{ c['category_id'] }}">{{ c['name'] }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">ผู้แต่ง</label>
                                <select class="form-select" name="author_id" id="authorSelect" onchange="toggleNewAuthor(this)">
                                    {% for a in authors %}
                                    <option value="{{ a['author_id'] }}">{{ a['name'] }}</option>
                                    {% endfor %}
                                    <option value="new" class="text-primary fw-bold">+ พิมพ์ชื่อผู้แต่งใหม่เอง...</option>
                                </select>
                            </div>
                        </div>

                        <div class="mb-3 d-none" id="newAuthorBox">
                            <label class="form-label fw-bold text-primary">ระบุชื่อผู้แต่งใหม่</label>
                            <input type="text" class="form-control border-primary" name="new_author_name" placeholder="ชื่อ-นามสกุล ผู้แต่ง">
                        </div>

                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">ราคา (บาท)</label>
                                <input type="number" step="0.01" class="form-control" name="price" placeholder="250.00" required>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">จำนวนสต็อกคงเหลือ</label>
                                <input type="number" class="form-control" name="stock_quantity" value="20" required>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold">URL รูปภาพหน้าปก</label>
                            <input type="url" class="form-control" name="cover_url" placeholder="https://..." value="https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=300">
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold">คำอธิบายย่อ</label>
                            <textarea class="form-control" name="description" rows="2"></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">ยกเลิก</button>
                        <button type="submit" class="btn btn-success fw-bold px-4">บันทึกหนังสือใหม่</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
    function toggleNewAuthor(select) {
        var box = document.getElementById('newAuthorBox');
        if (select.value === 'new') {
            box.classList.remove('d-none');
            box.querySelector('input').required = true;
        } else {
            box.classList.add('d-none');
            box.querySelector('input').required = false;
        }
    }
    </script>

    <!-- ตารางคำสั่งซื้อ + ปุ่มดูสลิปโอนเงินจำลอง[cite: 1] -->
    <div class="card mb-4 border-0 shadow-sm rounded-3">
        <div class="card-header bg-dark text-white fw-bold py-3 d-flex justify-content-between align-items-center">
            <span>รายการคำสั่งซื้อทั้งหมด (เรียงจากใหม่สุด)</span>
            <small class="text-warning">* ออเดอร์ที่สถานะ "รอแอดมินตรวจสอบ" จะมีปุ่มดูสลิปและปุ่มอนุมัติ</small>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table align-middle table-hover mb-0">
                    <thead class="table-light small">
                        <tr>
                            <th>เลขออเดอร์</th>
                            <th>วัน-เวลา (เวลาไทย)</th>
                            <th>ลูกค้า</th>
                            <th>ยอดชำระ</th>
                            <th>การชำระเงิน</th>
                            <th>หลักฐานสลิป</th>
                            <th>สถานะปัจจุบัน</th>
                            <th class="text-center">การดำเนินการ (Action)</th>
                        </tr>
                    </thead>
                    <tbody>
                    {% for o in orders %}
                    <tr class="{% if o['status'] == 'pending' %}table-warning bg-opacity-25{% endif %}">
                        <td class="fw-bold">#{{ o['order_id'] }}</td>
                        <td class="small text-muted">{{ o['created_at'] }}</td>
                        <td>
                            <div class="fw-bold">{{ o['full_name'] }}</div>
                            <small class="text-muted">{{ o['email'] }}</small>
                        </td>
                        <td class="fw-bold text-danger">฿{{ "{:,.2f}".format(o['total_amount']) }}</td>
                        <td>
                            <span class="badge bg-light text-dark border">{{ o['payment_method'] or 'PromptPay' }}</span>
                        </td>
                        <td>
                            {% if o['proof_url'] %}
                            <a href="{{ o['proof_url'] }}" target="_blank" class="btn btn-sm btn-outline-info rounded-pill px-2">
                                <i class="bi bi-image"></i> ดูสลิป
                            </a>
                            {% else %}
                            <span class="text-muted small">-</span>
                            {% endif %}
                        </td>
                        <td>
                            {% if o['status'] == 'confirmed' %}
                                <span class="badge bg-success"><i class="bi bi-check-circle"></i> ยืนยันแล้ว</span>
                            {% elif o['status'] == 'pending' %}
                                <span class="badge bg-warning text-dark"><i class="bi bi-hourglass-split"></i> รอดำเนินการ</span>
                            {% else %}
                                <span class="badge bg-danger"><i class="bi bi-x-circle"></i> ยกเลิกแล้ว</span>
                            {% endif %}
                        </td>
                        <td class="text-center">
                            {% if o['status'] == 'pending' %}
                            <div class="btn-group" role="group">
                                <a href="/admin/approve/{{ o['order_id'] }}" class="btn btn-sm btn-success fw-bold px-3 shadow-sm">
                                    <i class="bi bi-check-lg"></i> อนุมัติ & เปิดสิทธิ์
                                </a>
                                <a href="/admin/reject/{{ o['order_id'] }}" class="btn btn-sm btn-outline-danger" onclick="return confirm('ยืนยันยกเลิกออเดอร์นี้?')">
                                    ยกเลิก
                                </a>
                            </div>
                            {% elif o['status'] == 'confirmed' %}
                                <span class="text-success small fw-bold"><i class="bi bi-unlock-fill"></i> ปลดล็อกให้ลูกค้าแล้ว</span>
                            {% else %}
                                <span class="text-muted small">ปิดรายการแล้ว</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- 4 รายงานวิเคราะห์ตามเกณฑ์ พร้อม Anchor ID สำหรับปุ่มเลื่อนหน้าจอ -->
    <div id="reportsSection" class="pt-2">
        <h4 class="fw-bold mb-3"><i class="bi bi-graph-up-arrow text-primary"></i> รายงานวิเคราะห์จากฐานข้อมูล (4 รายงาน)</h4>
    </div>
    <div class="row g-3">
        <div class="col-md-6">
            <div class="card h-100 shadow-sm border-0">
                <div class="card-header bg-primary text-white fw-bold">1. ยอดขายตามช่วงเวลา</div>
                <div class="card-body p-0">
                    <table class="table table-sm mb-0">
                        <tr class="table-light"><th>วันที่</th><th>จำนวนออเดอร์</th><th>ยอดรวม</th><th>เฉลี่ย/ออเดอร์</th></tr>
                        {% for row in r1 %}<tr><td>{{ row['sale_date'] }}</td><td>{{ row['total_orders'] }}</td><td>฿{{ "{:,.2f}".format(row['total_sales']) }}</td><td>฿{{ "{:,.2f}".format(row['avg_sales']) }}</td></tr>{% endfor %}
                    </table>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card h-100 shadow-sm border-0">
                <div class="card-header bg-success text-white fw-bold">2. E-Book ขายดี (Top 5)</div>
                <div class="card-body p-0">
                    <table class="table table-sm mb-0">
                        <tr class="table-light"><th>ชื่อหนังสือ</th><th>ยอดขาย (เล่ม)</th><th>รายได้รวม</th></tr>
                        {% for row in r2 %}<tr><td>{{ row['title'] }}</td><td>{{ row['total_sold'] }}</td><td>฿{{ "{:,.2f}".format(row['revenue']) }}</td></tr>{% endfor %}
                    </table>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card h-100 shadow-sm border-0">
                <div class="card-header bg-warning text-dark fw-bold">3. ยอดขายตามหมวดหมู่</div>
                <div class="card-body p-0">
                    <table class="table table-sm mb-0">
                        <tr class="table-light"><th>หมวดหมู่</th><th>เล่มที่ขายได้</th><th>รายได้รวม</th></tr>
                        {% for row in r3 %}<tr><td>{{ row['category_name'] }}</td><td>{{ row['items_sold'] }}</td><td>฿{{ "{:,.2f}".format(row['category_revenue']) }}</td></tr>{% endfor %}
                    </table>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card h-100 shadow-sm border-0">
                <div class="card-header bg-info text-dark fw-bold">4. สรุปลูกค้าและยอดซื้อสะสม</div>
                <div class="card-body p-0">
                    <table class="table table-sm mb-0">
                        <tr class="table-light"><th>ลูกค้า</th><th>ออเดอร์ทั้งหมด</th><th>ยอดซื้อสะสม</th></tr>
                        {% for row in r4 %}<tr><td>{{ row['full_name'] }}</td><td>{{ row['total_orders'] }}</td><td>฿{{ "{:,.2f}".format(row['total_spent']) }}</td></tr>{% endfor %}
                    </table>
                </div>
            </div>
        </div>
    </div>
    """
    return render_page("Admin Dashboard", content, 
                       ebooks_list=ebooks_list, categories=categories, authors=authors, orders=orders, 
                       all_users=all_users, total_users_count=total_users_count, total_admins_count=total_admins_count, 
                       user_behaviors=user_behaviors, active_buyers_count=active_buyers_count, abandoned_carts_count=abandoned_carts_count,
                       r1=r1, r2=r2, r3=r3, r4=r4)


# Route ดึงข้อมูลสินค้าที่ค้างอยู่ในตะกร้าของลูกค้าแต่ละคน (ส่งกลับเป็น JSON สำหรับ Modal)
@app.route('/admin/user/<int:user_id>/cart')
def get_user_cart(user_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db()
    items = conn.execute("""
        SELECT ci.quantity, e.ebook_id, e.title, e.price, e.cover_url, c.name as category_name
        FROM carts cr
        JOIN cart_items ci ON cr.cart_id = ci.cart_id
        JOIN ebooks e ON ci.ebook_id = e.ebook_id
        JOIN categories c ON e.category_id = c.category_id
        WHERE cr.user_id = ?
    """, (user_id,)).fetchall()

    result = []
    for it in items:
        result.append({
            'ebook_id': it['ebook_id'],
            'title': it['title'],
            'price': it['price'],
            'quantity': it['quantity'],
            'cover_url': it['cover_url'],
            'category_name': it['category_name']
        })

    return jsonify({'items': result})


# Route ดึงประวัติผู้ซื้อของหนังสือเล่มใดเล่มหนึ่ง (ปรับเวลา created_at เป็นเวลาไทย +7 hours)
@app.route('/admin/book/<int:ebook_id>/buyers')
def get_book_buyers(ebook_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db()
    buyers = conn.execute("""
        SELECT u.user_id, u.full_name, u.email, o.order_id, oi.price,
               datetime(o.created_at, '+7 hours') as created_at
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN users u ON o.user_id = u.user_id
        WHERE oi.ebook_id = ? AND o.status = 'confirmed'
        ORDER BY o.order_id DESC
    """, (ebook_id,)).fetchall()

    result = []
    for b in buyers:
        result.append({
            'user_id': b['user_id'],
            'full_name': b['full_name'],
            'email': b['email'],
            'order_id': b['order_id'],
            'price': b['price'],
            'created_at': b['created_at']
        })

    return jsonify({'buyers': result})


# Route สำหรับเปลี่ยนสิทธิ์ผู้ใช้ พร้อมระบบตรวจสอบรหัสผ่าน Admin[cite: 1]
@app.route('/admin/user/change-role', methods=['POST'])
def admin_change_user_role():
    if session.get('role') != 'admin':
        return "<h3>เฉพาะผู้ดูแลระบบ (Admin) เท่านั้น</h3>", 403

    target_user_id = request.form.get('target_user_id')
    new_role_name = request.form.get('new_role_name')
    admin_password = request.form.get('admin_password')
    current_admin_id = session.get('user_id')

    conn = get_db()

    # 1. ตรวจสอบรหัสผ่านของแอดมินปัจจุบันก่อน[cite: 1]
    admin_user = conn.execute("SELECT * FROM users WHERE user_id = ?", (current_admin_id,)).fetchone()
    if not admin_user or (admin_user['password_hash'] != admin_password and admin_user.get('password') != admin_password):
        flash('รหัสผ่านแอดมินไม่ถูกต้อง ไม่สามารถเปลี่ยนสิทธิ์ได้!', 'danger')
        return redirect('/admin')

    # 2. ป้องกันไม่ให้แอดมินปลดสิทธิ์ตัวเอง[cite: 1]
    if str(target_user_id) == str(current_admin_id) and new_role_name != 'admin':
        flash('ไม่สามารถปลดสิทธิ์แอดมินของบัญชีตัวเองได้!', 'warning')
        return redirect('/admin')

    # 3. ค้นหา role_id จากชื่อ role[cite: 1]
    role_row = conn.execute("SELECT role_id FROM roles WHERE role_name = ?", (new_role_name,)).fetchone()
    if not role_row:
        target_role_id = 1 if new_role_name == 'admin' else 2
    else:
        target_role_id = role_row['role_id']

    # 4. บันทึกสิทธิ์ใหม่[cite: 1]
    conn.execute("UPDATE users SET role_id = ? WHERE user_id = ?", (target_role_id, target_user_id))
    conn.commit()

    flash('ปรับเปลี่ยนระดับสิทธิ์เรียบร้อยแล้ว!', 'success')
    return redirect('/admin')

# เพิ่มหมวดหมู่ใหม่ (Admin)[cite: 1]
@app.route('/admin/category/add', methods=['POST'])
def add_category():
    if session.get('role') != 'admin':
        abort(403)
    category_name = request.form['category_name'].strip()
    if category_name:
        conn = get_db()
        try:
            conn.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
            conn.commit()
            flash(f"🏷 เพิ่มหมวดหมู่ \"{category_name}\" สำเร็จ!", "success")
        except sqlite3.IntegrityError:
            flash(f"❌ หมวดหมู่ \"{category_name}\" มีอยู่แล้วในระบบ", "danger")
    return redirect(url_for('admin_dashboard'))

# ลบหมวดหมู่ที่ไม่มีหนังสือ (Admin)[cite: 1]
@app.route('/admin/category/delete/<int:cat_id>')
def delete_category(cat_id):
    if session.get('role') != 'admin':
        abort(403)
    conn = get_db()
    conn.execute("DELETE FROM categories WHERE category_id = ?", (cat_id,))
    conn.commit()
    flash("🗑️ ลบหมวดหมู่เรียบร้อยแล้ว", "info")
    return redirect(url_for('admin_dashboard'))

# เพิ่มหนังสือใหม่ (Admin)[cite: 1]
@app.route('/admin/book/add', methods=['POST'])
def add_book():
    if session.get('role') != 'admin':
        abort(403)
    title = request.form['title']
    category_id = request.form['category_id']
    author_id_input = request.form.get('author_id')
    new_author_name = request.form.get('new_author_name', '').strip()
    price = float(request.form['price'])
    stock_quantity = int(request.form['stock_quantity'])
    cover_url = request.form.get('cover_url') or 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=300'
    description = request.form.get('description', '')

    conn = get_db()
    cur = conn.cursor()

    if author_id_input == 'new' and new_author_name:
        existing_author = conn.execute("SELECT author_id FROM authors WHERE name = ?", (new_author_name,)).fetchone()
        if existing_author:
            author_id = existing_author['author_id']
        else:
            cur.execute("INSERT INTO authors (name) VALUES (?)", (new_author_name,))
            author_id = cur.lastrowid
    else:
        author_id = int(author_id_input)

    cur.execute("""
        INSERT INTO ebooks (title, category_id, author_id, price, stock_quantity, cover_url, description, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (title, category_id, author_id, price, stock_quantity, cover_url, description))
    conn.commit()
    flash(f"📚 เพิ่มหนังสือ \"{title}\" เข้าสู่ระบบเรียบร้อยแล้ว!", "success")
    return redirect(url_for('admin_dashboard'))

# อัปเดตราคาและสต็อกหนังสือ[cite: 1]
@app.route('/admin/book/update/<int:ebook_id>', methods=['POST'])
def update_book(ebook_id):
    if session.get('role') != 'admin':
        abort(403)
    price = float(request.form['price'])
    stock_quantity = int(request.form['stock_quantity'])

    conn = get_db()
    conn.execute("UPDATE ebooks SET price = ?, stock_quantity = ? WHERE ebook_id = ?",
                 (price, stock_quantity, ebook_id))
    conn.commit()
    flash("💾 ปรับปรุงราคาและสต็อกหนังสือสำเร็จ!", "success")
    return redirect(url_for('admin_dashboard'))

# ลบหนังสือ[cite: 1]
@app.route('/admin/book/delete/<int:ebook_id>')
def delete_book(ebook_id):
    if session.get('role') != 'admin':
        abort(403)
    conn = get_db()
    conn.execute("UPDATE ebooks SET is_active = 0 WHERE ebook_id = ?", (ebook_id,))
    conn.commit()
    flash("🗑️ นำหนังสือออกจากหน้าร้านเรียบร้อยแล้ว", "info")
    return redirect(url_for('admin_dashboard'))

# อนุมัติออเดอร์[cite: 1]
@app.route('/admin/approve/<int:order_id>')
def approve_order(order_id):
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    conn = get_db()
    conn.execute("UPDATE orders SET status = 'confirmed' WHERE order_id = ?", (order_id,))
    conn.execute("UPDATE payments SET payment_status = 'approved' WHERE order_id = ?", (order_id,))
    conn.commit()
    flash(f"✅ อนุมัติคำสั่งซื้อ #{order_id} และเปิดสิทธิ์ดาวน์โหลดให้ลูกค้าแล้ว!", "success")
    return redirect(url_for('admin_dashboard'))

# ยกเลิกออเดอร์[cite: 1]
@app.route('/admin/reject/<int:order_id>')
def reject_order(order_id):
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    conn = get_db()
    conn.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (order_id,))
    conn.execute("UPDATE payments SET payment_status = 'rejected' WHERE order_id = ?", (order_id,))
    conn.commit()
    flash(f"❌ ยกเลิกคำสั่งซื้อ #{order_id} เรียบร้อยแล้ว", "danger")
    return redirect(url_for('admin_dashboard'))

# 8. หน้าโปรไฟล์ / ตั้งค่าผู้ใช้[cite: 1]
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    conn = get_db()
    user_id = session['user_id']
    msg = None
    msg_type = None

    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        new_password = request.form['new_password'].strip()

        if new_password:
            conn.execute("UPDATE users SET full_name = ?, password_hash = ? WHERE user_id = ?",
                         (full_name, new_password, user_id))
            msg = "บันทึกข้อมูลชื่อและรหัสผ่านใหม่เรียบร้อยแล้ว!"
        else:
            conn.execute("UPDATE users SET full_name = ? WHERE user_id = ?", (full_name, user_id))
            msg = "บันทึกชื่อ-นามสกุลเรียบร้อยแล้ว!"
            
        conn.commit()
        session['full_name'] = full_name
        msg_type = "success"

    user = conn.execute("SELECT u.*, r.role_name FROM users u JOIN roles r ON u.role_id = r.role_id WHERE u.user_id = ?",
                        (user_id,)).fetchone()

    content = """
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card shadow-sm border-0 rounded-4">
                <div class="card-header bg-dark text-white py-3">
                    <h5 class="mb-0 fw-bold"><i class="bi bi-person-gear"></i> ตั้งค่าข้อมูลบัญชีผู้ใช้</h5>
                </div>
                <div class="card-body p-4">
                    {% if msg %}
                        <div class="alert alert-{{ msg_type }} py-2 small mb-3">{{ msg }}</div>
                    {% endif %}
                    
                    <form method="POST">
                        <div class="mb-3">
                            <label class="form-label text-muted small">อีเมลบัญชี (ไม่สามารถแก้ไขได้)</label>
                            <input type="text" class="form-control bg-light" value="{{ user['email'] }}" readonly>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-muted small">สิทธิ์การใช้งาน (Role)</label>
                            <input type="text" class="form-control bg-light" value="{{ user['role_name'] }}" readonly>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold">ชื่อ - นามสกุล</label>
                            <input type="text" class="form-control" name="full_name" value="{{ user['full_name'] }}" required>
                        </div>
                        <div class="mb-4">
                            <label class="form-label fw-bold">รหัสผ่านใหม่</label>
                            <input type="password" class="form-control" name="new_password" placeholder="เว้นว่างไว้หากไม่ต้องการเปลี่ยนรหัสผ่าน">
                            <small class="text-muted">กรอกเฉพาะกรณีที่ต้องการเปลี่ยนรหัสผ่านใหม่</small>
                        </div>
                        <button type="submit" class="btn btn-primary w-100 py-2 fw-bold rounded-pill">
                            <i class="bi bi-check-circle"></i> บันทึกการเปลี่ยนแปลง
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """
    return render_page("ตั้งค่าบัญชี", content, user=user, msg=msg, msg_type=msg_type)

# 9. เข้าสู่ระบบ[cite: 1]
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        conn = get_db()
        user = conn.execute("""
            SELECT u.*, r.role_name 
            FROM users u JOIN roles r ON u.role_id = r.role_id 
            WHERE u.email = ? AND u.password_hash = ?
        """, (email, password)).fetchone()
        
        if user:
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['role'] = user['role_name']
            if user['role_name'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            error = "อีเมลหรือรหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง"
            
    content = """
    <div class="row justify-content-center mt-5">
        <div class="col-md-5">
            <div class="card p-4 shadow-sm border-0 rounded-4">
                <h3 class="mb-2 text-center fw-bold text-danger">📖 ReadDee Store</h3>
                <p class="text-center text-muted small mb-4">เข้าสู่ระบบเพื่อสั่งซื้อ E-Book และรับลิงก์อ่าน</p>
                {% if error %}
                    <div class="alert alert-danger py-2 small">{{ error }}</div>
                {% endif %}
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label fw-bold">อีเมล</label>
                        <input type="email" class="form-control" name="email" placeholder="example@email.com" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">รหัสผ่าน</label>
                        <input type="password" class="form-control" name="password" placeholder="กรอกรหัสผ่านของคุณ" required>
                    </div>
                    <button class="btn btn-primary w-100 py-2 fw-bold" type="submit">เข้าสู่ระบบ</button>
                </form>
                <div class="text-center mt-3">
                    <span class="text-muted small">ยังไม่มีบัญชี?</span> 
                    <a href="/register" class="small fw-bold text-danger text-decoration-none">สมัครสมาชิกใหม่</a>
                </div>
            </div>
        </div>
    </div>
    """
    return render_page("เข้าสู่ระบบ", content, error=error)

# 10. สมัครสมาชิกใหม่ (กำหนดให้ default เป็น role_id = 2 หรือ customer เสมอ)
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        
        conn = get_db()
        exist = conn.execute("SELECT user_id FROM users WHERE email = ?", (email,)).fetchone()
        if exist:
            error = "อีเมลนี้ถูกใช้งานแล้ว โปรดใช้อีเมลอื่น"
        else:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (role_id, email, password_hash, full_name) VALUES (2, ?, ?, ?)", 
                        (email, password, full_name))
            conn.commit()
            
            session['user_id'] = cur.lastrowid
            session['full_name'] = full_name
            session['role'] = 'customer'
            return redirect(url_for('index'))
            
    content = """
    <div class="row justify-content-center mt-5">
        <div class="col-md-5">
            <div class="card p-4 shadow-sm border-0 rounded-4">
                <h3 class="mb-2 text-center fw-bold">สร้างบัญชีผู้ใช้ใหม่</h3>
                <p class="text-center text-muted small mb-4">สมัครสมาชิกง่ายๆ เพื่อเริ่มช้อปปิ้งหนังสือ</p>
                {% if error %}
                    <div class="alert alert-danger py-2 small">{{ error }}</div>
                {% endif %}
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">ชื่อ - นามสกุล</label>
                        <input class="form-control" name="full_name" placeholder="เช่น มานี มีตา" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">อีเมล</label>
                        <input type="email" class="form-control" name="email" placeholder="example@email.com" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">รหัสผ่าน</label>
                        <input type="password" class="form-control" name="password" placeholder="กำหนดรหัสผ่าน" required>
                    </div>
                    <button class="btn btn-success w-100 py-2 fw-bold" type="submit">ยืนยันสมัครสมาชิก</button>
                </form>
                <div class="text-center mt-3">
                    <span class="text-muted small">มีบัญชีอยู่แล้ว?</span> 
                    <a href="/login" class="small fw-bold text-decoration-none">เข้าสู่ระบบที่นี่</a>
                </div>
            </div>
        </div>
    </div>
    """
    return render_page("สมัครสมาชิก", content, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)