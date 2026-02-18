import csv
import io
import os
import sqlite3
from datetime import date, timedelta
from functools import wraps
from secrets import token_hex

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    send_from_directory,
    session,
    url_for,
)
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder=".", static_url_path="/static")
app.secret_key = "change-this-secret-key"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_SECURE_COOKIES", "0") == "1",
)

app.jinja_loader = ChoiceLoader(
    [
        FileSystemLoader(app.root_path),
        FileSystemLoader(os.path.join(app.root_path, "templates")),
    ]
)


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline';"
    )
    return response

DEFAULT_ADMIN_EMAIL = "swaadebihar01@gmail.com"
DEFAULT_ADMIN_PASSWORD = "admin123"
DB_PATH = os.path.join(app.root_path, "swaad.db")
UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

DASHBOARDS = {
    "menu": {
        "title": "Menu Dashboard",
        "description": "Track menu performance, pricing, and availability across the kitchen board.",
        "highlights": [
            "Top combos refreshed daily",
            "Low-stock items flagged",
            "Seasonal specials ready to promote",
        ],
        "kpis": [
            {"label": "Active dishes", "value": "24"},
            {"label": "Avg. prep time", "value": "18 min"},
            {"label": "Price updates", "value": "3"},
        ],
        "queue": [
            {"item": "Review chicken combo prices", "status": "Pending", "owner": "Kitchen"},
            {"item": "Publish weekend specials", "status": "Ready", "owner": "Ops"},
            {"item": "Audit allergen notes", "status": "In progress", "owner": "QA"},
        ],
    },
    "story": {
        "title": "Story Dashboard",
        "description": "Manage brand story updates, press highlights, and community moments.",
        "highlights": [
            "New founder story draft",
            "Press quote requests",
            "Community feedback roundup",
        ],
        "kpis": [
            {"label": "Story sections", "value": "5"},
            {"label": "New testimonials", "value": "12"},
            {"label": "Press mentions", "value": "2"},
        ],
        "queue": [
            {"item": "Approve storytelling visuals", "status": "Pending", "owner": "Creative"},
            {"item": "Schedule brand post", "status": "Ready", "owner": "Marketing"},
            {"item": "Update kitchen timeline", "status": "In progress", "owner": "Ops"},
        ],
    },
    "order": {
        "title": "Order Dashboard",
        "description": "Monitor live orders, delivery timing, and customer requests.",
        "highlights": [
            "Peak hour watch: 7-10 PM",
            "Priority orders flagged",
            "Delivery partners synced",
        ],
        "kpis": [
            {"label": "Open orders", "value": "16"},
            {"label": "On-time rate", "value": "94%"},
            {"label": "Avg. delivery", "value": "32 min"},
        ],
        "queue": [
            {"item": "Call back: spice level update", "status": "Pending", "owner": "Support"},
            {"item": "Reassign driver for Zone 2", "status": "Ready", "owner": "Dispatch"},
            {"item": "Confirm bulk order", "status": "In progress", "owner": "Kitchen"},
        ],
    },
    "cart": {
        "title": "Open Cart Dashboard",
        "description": "Review saved carts, abandoned checkouts, and customer follow-ups.",
        "highlights": [
            "Saved carts from last 24h",
            "High-value baskets flagged",
            "WhatsApp follow-ups queued",
        ],
        "kpis": [
            {"label": "Open carts", "value": "9"},
            {"label": "Recovery rate", "value": "22%"},
            {"label": "Avg. basket", "value": "₹312"},
        ],
        "queue": [
            {"item": "Send cart reminder", "status": "Ready", "owner": "Marketing"},
            {"item": "Apply loyalty discount", "status": "Pending", "owner": "Ops"},
            {"item": "Review refund request", "status": "In progress", "owner": "Support"},
        ],
    },
    "contact": {
        "title": "Contact Dashboard",
        "description": "Track inbound messages, catering inquiries, and service feedback.",
        "highlights": [
            "WhatsApp replies due",
            "Catering inquiry backlog",
            "Customer feedback trends",
        ],
        "kpis": [
            {"label": "Open tickets", "value": "7"},
            {"label": "Avg. response", "value": "14 min"},
            {"label": "CSAT", "value": "4.7"},
        ],
        "queue": [
            {"item": "Confirm tasting slot", "status": "Ready", "owner": "Sales"},
            {"item": "Reply to DM inquiry", "status": "Pending", "owner": "Support"},
            {"item": "Update FAQ notes", "status": "In progress", "owner": "Ops"},
        ],
    },
}


@app.route("/")
def home():
    context = get_home_context()
    context["order_status"] = request.args.get("order")
    return render_template("index.html", **context)


@app.route("/robots.txt")
def robots_txt():
    content = "User-agent: *\nAllow: /\nSitemap: " + url_for("sitemap_xml", _external=True) + "\n"
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    urls = [
        url_for("home", _external=True),
        url_for("menu_portal", _external=True),
        url_for("story_page", _external=True),
        url_for("order_page", _external=True),
        url_for("track_order", _external=True),
        url_for("cart_page", _external=True),
        url_for("contact_page", _external=True),
        url_for("login", _external=True),
        url_for("customer_register", _external=True),
    ]
    return (
        render_template("sitemap.xml", urls=urls, lastmod=date.today().isoformat()),
        200,
        {"Content-Type": "application/xml"},
    )


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html"), 500


@app.route("/customer")
def customer_home():
    return home()


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/menu")
def menu_portal():
    context = get_home_context()
    cart = session.get("cart", {})
    context["cart_qty"] = {int(key): value for key, value in cart.items()}
    return render_template("page_menu_portal.html", **context)


@app.route("/story")
def story_page():
    context = get_home_context()
    return render_template("page_story.html", **context)


@app.route("/order")
def order_page():
    context = get_home_context()
    context["order_status"] = request.args.get("order")
    return render_template("page_order.html", **context)


@app.route("/track", methods=["GET", "POST"])
def track_order():
    order = None
    events = []
    if request.method == "POST":
        order_reference = request.form.get("order_reference", "").strip()
        phone = request.form.get("phone", "").strip()
    else:
        order_reference = request.args.get("ref", "").strip()
        phone = request.args.get("phone", "").strip()
    if order_reference and phone:
        if not order_reference or not phone:
            flash("Order reference and phone are required.", "error")
            return redirect(url_for("track_order"))
        conn = get_db_connection()
        order = conn.execute(
            """
            SELECT * FROM orders
            WHERE (order_reference = ? OR CAST(id AS TEXT) = ?)
              AND phone = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (order_reference, order_reference, phone),
        ).fetchone()
        if not order:
            conn.close()
            flash("We could not find that order. Check the reference and phone.", "error")
            return redirect(url_for("track_order"))
        events = conn.execute(
            "SELECT * FROM order_events WHERE order_id = ? ORDER BY created_at DESC, id DESC",
            (order["id"],),
        ).fetchall()
        conn.close()
    return render_template(
        "page_track.html",
        order=order,
        events=events,
        prefill_ref=order_reference,
        prefill_phone=phone,
    )


@app.route("/cart")
def cart_page():
    cart = get_cart()
    cart_items, subtotal = get_cart_items(cart)
    delivery_fee = 20 if subtotal > 0 else 0
    total = subtotal + delivery_fee
    customer = get_customer_context()
    return render_template(
        "page_cart.html",
        cart_items=cart_items,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total,
        customer=customer,
    )


@app.route("/cart/checkout", methods=["POST"])
def cart_checkout():
    cart = get_cart()
    cart_items, subtotal = get_cart_items(cart)
    if not cart_items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart_page"))
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    area = request.form.get("area", "").strip()
    notes = request.form.get("notes", "").strip()
    if not name or not phone or not area:
        flash("Name, phone, and delivery area are required.", "error")
        return redirect(url_for("cart_page"))
    delivery_fee = 20 if subtotal > 0 else 0
    total = round(subtotal + delivery_fee, 2)
    items_text = ", ".join([f"{item['name']} x{item['qty']}" for item in cart_items])
    customer_id = session.get("customer_user_id")
    order_reference = generate_order_reference()
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO orders (
            customer_name,
            phone,
            delivery_area,
            items,
            total_amount,
            status,
            order_reference,
            payment_method,
            payment_status,
            source_channel,
            notes,
            customer_id,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            name,
            phone,
            area,
            items_text,
            total,
            "New",
            order_reference,
            "Cash",
            "Pending",
            "Website-Cart",
            notes,
            customer_id,
        ),
    )
    order_id = cursor.lastrowid
    log_order_event(conn, order_id, "New", "Cart checkout", "customer", customer_id)
    log_audit_event(
        conn,
        "customer",
        customer_id,
        "create",
        "order",
        order_id,
        f"order_reference={order_reference}",
    )
    conn.commit()
    conn.close()
    session.pop("cart", None)
    flash(f"Order placed. Reference: {order_reference}", "success")
    return redirect(url_for("track_order", ref=order_reference, phone=phone))


@app.route("/cart/add/<int:item_id>", methods=["POST"])
def cart_add(item_id: int):
    cart = get_cart()
    cart[str(item_id)] = cart.get(str(item_id), 0) + 1
    session["cart"] = cart
    return redirect(url_for("cart_page"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
def cart_remove(item_id: int):
    cart = get_cart()
    key = str(item_id)
    if key in cart:
        cart[key] -= 1
        if cart[key] <= 0:
            cart.pop(key)
    session["cart"] = cart
    return redirect(url_for("cart_page"))


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    session.pop("cart", None)
    return redirect(url_for("cart_page"))


@app.route("/contact")
def contact_page():
    context = get_home_context()
    return render_template("page_contact.html", **context)


@app.route("/dashboard/<string:key>")
def dashboard_page(key: str):
    return render_dashboard(key)


def customer_login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("customer_user_id"):
            return redirect(url_for("customer_login"))
        return view(**kwargs)

    return wrapped_view


def get_customer_context():
    customer = None
    if session.get("customer_user_id"):
        conn = get_db_connection()
        customer = conn.execute(
            "SELECT * FROM customer_users WHERE id = ?",
            (session["customer_user_id"],),
        ).fetchone()
        conn.close()
    return customer


@app.route("/dashboard/customer", methods=["GET", "POST"])
@customer_login_required
def customer_dashboard():
    customer = get_customer_context()
    conn = get_db_connection()
    orders = conn.execute(
        "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC, id DESC",
        (customer["id"],),
    ).fetchall()
    order_ids = [row["id"] for row in orders]
    events_by_order = {}
    if order_ids:
        placeholders = ",".join("?" for _ in order_ids)
        events = conn.execute(
            f"""
            SELECT * FROM order_events
            WHERE order_id IN ({placeholders})
            ORDER BY created_at DESC, id DESC
            """,
            order_ids,
        ).fetchall()
        for event in events:
            events_by_order.setdefault(event["order_id"], []).append(event)
    conn.close()
    return render_template(
        "customer_dashboard.html",
        orders=orders,
        customer=customer,
        events_by_order=events_by_order,
    )




def render_dashboard(key: str):
    data = DASHBOARDS.get(key)
    if not data:
        abort(404)
    return render_template("dashboard.html", key=key, **data)


def get_cart():
    return session.get("cart", {})


def get_cart_items(cart):
    if not cart:
        return [], 0
    ids = [int(item_id) for item_id in cart.keys()]
    placeholders = ",".join("?" for _ in ids)
    conn = get_db_connection()
    rows = conn.execute(
        f"SELECT * FROM menu_items WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    conn.close()

    items_by_id = {row["id"]: row for row in rows}
    cart_items = []
    subtotal = 0
    for item_id, qty in cart.items():
        item = items_by_id.get(int(item_id))
        if not item:
            continue
        price = float(item["price"]) if item["price"] is not None else 0
        line_total = round(price * qty, 2)
        subtotal += line_total
        cart_items.append(
            {
                "id": item["id"],
                "name": item["name"],
                "price": price,
                "qty": qty,
                "line_total": line_total,
            }
        )
    return cart_items, round(subtotal, 2)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def generate_order_reference() -> str:
    stamp = date.today().strftime("%Y%m%d")
    token = token_hex(3).upper()
    return f"ORD-{stamp}-{token}"


def log_audit_event(
    conn,
    actor_type: str,
    actor_id,
    action: str,
    entity_type: str,
    entity_id,
    details: str = "",
):
    conn.execute(
        """
        INSERT INTO audit_logs (actor_type, actor_id, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (actor_type, actor_id, action, entity_type, entity_id, details),
    )


def log_order_event(
    conn,
    order_id: int,
    status: str,
    note: str,
    actor_type: str,
    actor_id,
):
    conn.execute(
        """
        INSERT INTO order_events (order_id, status, note, actor_type, actor_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (order_id, status, note, actor_type, actor_id),
    )


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            sort_order INTEGER DEFAULT 0,
            image_path TEXT
        );

        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            delivery_area TEXT NOT NULL,
            items TEXT NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            order_reference TEXT,
            payment_method TEXT,
            payment_status TEXT,
            source_channel TEXT,
            legal_notes TEXT,
            notes TEXT,
            customer_id INTEGER,
            updated_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS order_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            actor_type TEXT NOT NULL,
            actor_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_type TEXT NOT NULL,
            actor_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS customer_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            discount_percent REAL DEFAULT 0.0,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS story_highlights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS story_panels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            value TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS contact_info (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            location TEXT NOT NULL,
            whatsapp TEXT NOT NULL
        );
        """
    )

    ensure_column(conn, "menu_items", "image_path", "TEXT")
    ensure_column(conn, "orders", "delivery_area", "TEXT")
    ensure_column(conn, "orders", "customer_id", "INTEGER")
    ensure_column(conn, "orders", "order_reference", "TEXT")
    ensure_column(conn, "orders", "payment_method", "TEXT")
    ensure_column(conn, "orders", "payment_status", "TEXT")
    ensure_column(conn, "orders", "source_channel", "TEXT")
    ensure_column(conn, "orders", "legal_notes", "TEXT")
    ensure_column(conn, "orders", "updated_at", "TEXT")
    ensure_column(conn, "admin_users", "email", "TEXT")

    cursor.execute(
        """
        UPDATE orders
        SET updated_at = created_at
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )

    cursor.execute("SELECT COUNT(*) FROM menu_items")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO menu_items (name, description, category, price, sort_order, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("2 PC CHICKEN + 2 LITTI", "Litti combo with chicken.", "Combo", 279, 1, None),
                ("4 PC CHICKEN + 4 LITTI", "Family combo with chicken.", "Combo", 429, 2, None),
                ("2 PC CHICKEN LEG + 2 LITTI", "Litti combo with chicken leg.", "Combo", 149, 3, None),
                ("4 PC CHICKEN LEG + 4 LITTI", "Family combo with chicken leg.", "Combo", 299, 4, None),
                ("2 PC LITTI + CHOKHA", "Classic litti with chokha.", "Classic", 90, 5, None),
                ("4 PC LITTI + CHOKHA", "Classic litti with chokha.", "Classic", 169, 6, None),
                ("HALF PLATE (4 PC) CHICKEN", "Chicken plate.", "Plate", 89, 7, None),
                ("FULL PLATE (8 PC) CHICKEN", "Chicken plate.", "Plate", 169, 8, None),
                ("CHICKEN THALI", "Thali meal.", "Thali", 119, 9, None),
                ("CHICKEN SATTU PARATHA THALI", "Thali meal with sattu paratha.", "Thali", 109, 10, None),
                ("HANDI CHICKEN THALI", "Thali meal.", "Thali", 129, 11, None),
                ("HANDI CHICKEN SATTU PARATHA THALI", "Thali meal with sattu paratha.", "Thali", 119, 12, None),
            ],
        )

    cursor.execute("SELECT COUNT(*) FROM story_highlights")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO story_highlights (title, body)
            VALUES (?, ?)
            """,
            [
                ("Small-batch cooking", "Freshly prepared twice a day, never stored overnight."),
                ("Chef-led spice blends", "House-milled masalas for depth without heaviness."),
                ("Eco packaging", "Heat-lock boxes with compostable cutlery."),
            ],
        )

    cursor.execute("SELECT COUNT(*) FROM story_panels")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO story_panels (label, value, sort_order)
            VALUES (?, ?, ?)
            """,
            [
                ("Made on order", "05:00 PM - 02:00 AM", 1),
                ("Delivery radius", "0 - 8 km", 2),
                ("Weekly specials", "Saturday to Sunday", 3),
                ("Chef hotline", "+91 79731-93983", 4),
            ],
        )

    cursor.execute("SELECT COUNT(*) FROM contact_info")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """
            INSERT INTO contact_info (id, phone, email, location, whatsapp)
            VALUES (1, ?, ?, ?, ?)
            """,
            ("+91 79731-93983", "swaadebihar01@gmail.com", "punjab, jalandhar", "https://wa.me/917973193983"),
        )

    cursor.execute(
        """
        UPDATE admin_users
        SET email = username
        WHERE email IS NULL OR email = ''
        """
    )
    cursor.execute(
        """
        UPDATE admin_users
        SET email = ?, username = ?
        WHERE id = 1 AND (email IS NULL OR email = '' OR email NOT LIKE '%@%' OR email != ?)
        """,
        (DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_EMAIL),
    )

    cursor.execute("SELECT COUNT(*) FROM admin_users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO admin_users (username, email, password_hash) VALUES (?, ?, ?)",
            (DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_EMAIL, generate_password_hash(DEFAULT_ADMIN_PASSWORD)),
        )

    conn.commit()
    conn.close()


def get_home_context():
    conn = get_db_connection()
    menu_items = conn.execute(
        "SELECT * FROM menu_items ORDER BY sort_order, id"
    ).fetchall()
    menu_items_count = conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    story_highlights = conn.execute(
        "SELECT * FROM story_highlights ORDER BY id"
    ).fetchall()
    story_panels = conn.execute(
        "SELECT * FROM story_panels ORDER BY sort_order, id"
    ).fetchall()
    contact = conn.execute("SELECT * FROM contact_info WHERE id = 1").fetchone()
    conn.close()
    return {
        "menu_items": menu_items,
        "menu_items_count": menu_items_count,
        "story_highlights": story_highlights,
        "story_panels": story_panels,
        "contact": contact,
    }


def apply_discount(menu_items, discount_percent: float):
    adjusted = []
    for item in menu_items:
        price = float(item["price"]) if item["price"] is not None else 0
        discounted = round(price * (1 - (discount_percent / 100)), 2)
        data = dict(item)
        data["display_price"] = discounted
        adjusted.append(data)
    return adjusted


def format_currency(amount: float) -> str:
    if amount >= 1:
        return f"₹{amount:,.0f}"
    return f"₹{amount:,.2f}"


def build_trend_series(rows, days: int, value_key: str):
    today = date.today()
    lookup = {row["day"]: dict(row) for row in rows}
    series = []
    values = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        value = float(lookup.get(key, {}).get(value_key, 0) or 0)
        series.append({"label": day.strftime("%a"), "value": value, "day": key})
        values.append(value)
    max_value = max(values) if values else 0
    for item in series:
        item["width"] = int((item["value"] / max_value) * 100) if max_value > 0 else 0
    return series


def get_admin_dashboard_context():
    conn = get_db_connection()
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0]
    orders_today = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE date(created_at, 'localtime') = date('now', 'localtime')"
    ).fetchone()[0]
    revenue_today = conn.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE date(created_at, 'localtime') = date('now', 'localtime')"
    ).fetchone()[0]
    completed_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'Completed'"
    ).fetchone()[0]
    pending_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status IN ('New', 'Preparing', 'Out for delivery')"
    ).fetchone()[0]
    unique_customers = conn.execute(
        "SELECT COUNT(DISTINCT phone) FROM orders"
    ).fetchone()[0]
    repeat_customers = conn.execute(
        "SELECT COUNT(*) FROM (SELECT phone FROM orders GROUP BY phone HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    menu_items_count = conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    category_rows = conn.execute(
        "SELECT category, COUNT(*) AS count FROM menu_items GROUP BY category ORDER BY count DESC"
    ).fetchall()
    trend_rows = conn.execute(
        """
        SELECT date(created_at, 'localtime') AS day,
               COUNT(*) AS orders,
               COALESCE(SUM(total_amount), 0) AS revenue
        FROM orders
        WHERE date(created_at, 'localtime') >= date('now', '-6 days')
        GROUP BY date(created_at, 'localtime')
        """
    ).fetchall()
    conn.close()

    avg_order_value = (total_revenue / total_orders) if total_orders else 0
    on_time_rate = (completed_orders / total_orders * 100) if total_orders else 0
    repeat_rate = (repeat_customers / unique_customers * 100) if unique_customers else 0

    revenue_trend = build_trend_series(trend_rows, 7, "revenue")
    orders_trend = build_trend_series(trend_rows, 7, "orders")

    category_total = sum(row["count"] for row in category_rows) or 1
    category_mix = [
        {
            "label": row["category"],
            "count": row["count"],
            "width": int((row["count"] / category_total) * 100),
        }
        for row in category_rows
    ]

    return {
        "kpis": {
            "today_revenue": format_currency(revenue_today),
            "orders_today": orders_today,
            "avg_order_value": format_currency(avg_order_value),
            "on_time_rate": f"{on_time_rate:.0f}%",
            "repeat_rate": f"{repeat_rate:.0f}%",
            "menu_items": menu_items_count,
            "pending_orders": pending_orders,
            "total_orders": total_orders,
            "total_revenue": format_currency(total_revenue),
        },
        "revenue_trend": revenue_trend,
        "orders_trend": orders_trend,
        "category_mix": category_mix,
    }


@app.route("/order/request", methods=["POST"])
def order_request():
    customer_name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    delivery_area = request.form.get("area", "").strip()
    items = request.form.get("items", "").strip()
    notes = request.form.get("notes", "").strip()
    if not customer_name or not phone or not delivery_area or not items:
        flash("Please fill all required fields before sending your order.", "error")
        return redirect(url_for("order_page"))
    customer_id = session.get("customer_user_id")
    conn = get_db_connection()
    order_reference = generate_order_reference()
    cursor = conn.execute(
        """
        INSERT INTO orders (
            customer_name,
            phone,
            delivery_area,
            items,
            total_amount,
            status,
            order_reference,
            payment_method,
            payment_status,
            source_channel,
            notes,
            customer_id,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            customer_name,
            phone,
            delivery_area,
            items,
            0,
            "New",
            order_reference,
            "Cash",
            "Pending",
            "Website",
            notes,
            customer_id,
        ),
    )
    order_id = cursor.lastrowid
    log_order_event(conn, order_id, "New", "Order requested", "customer", customer_id)
    log_audit_event(
        conn,
        "customer",
        customer_id,
        "create",
        "order",
        order_id,
        f"order_reference={order_reference}",
    )
    conn.commit()
    conn.close()
    flash("Order received! We will call to confirm shortly.", "success")
    return redirect(url_for("order_page"))


def ensure_column(conn, table_name: str, column_name: str, column_type: str):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if column_name not in columns:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


def allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


def save_uploaded_file(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    safe_name = secure_filename(file.filename)
    _, ext = os.path.splitext(safe_name)
    new_name = f"{token_hex(8)}{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, new_name))
    return new_name


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("admin_user_id"):
            return redirect(url_for("admin_login"))
        return view(**kwargs)

    return wrapped_view


@app.route("/dashboard/admin")
@login_required
def admin_dashboard_page():
    context = get_admin_dashboard_context()
    return render_template("admin_dashboard.html", **context)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_user_id"):
        return redirect(url_for("admin_dashboard"))
    if session.get("customer_user_id"):
        return redirect(url_for("customer_dashboard"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        conn = get_db_connection()
        admin_user = conn.execute(
            "SELECT * FROM admin_users WHERE email = ?", (email,)
        ).fetchone()
        if admin_user and check_password_hash(admin_user["password_hash"], password):
            session["admin_user_id"] = admin_user["id"]
            session["admin_email"] = admin_user["email"]
            conn.close()
            return redirect(url_for("admin_dashboard"))
        customer = conn.execute(
            "SELECT * FROM customer_users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()
        if customer and check_password_hash(customer["password_hash"], password):
            session["customer_user_id"] = customer["id"]
            return redirect(url_for("customer_dashboard"))
        error = "Invalid email or password."
    return render_template("login.html", error=error)


@app.route("/customer/login", methods=["GET"])
def customer_login():
    return redirect(url_for("login"))


@app.route("/customer/register", methods=["GET", "POST"])
def customer_register():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        password = request.form.get("password", "").strip()
        if not all([name, email, phone, address, password]):
            error = "All fields are required."
        else:
            conn = get_db_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO customer_users (name, email, phone, address, password_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, email, phone, address, generate_password_hash(password)),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                error = "This email is already registered."
            conn.close()
            if not error:
                flash("Account created. Please log in.", "success")
                return redirect(url_for("customer_login"))
    return render_template("customer_register.html", error=error)


@app.route("/customer/logout")
def customer_logout():
    session.pop("customer_user_id", None)
    return redirect(url_for("home"))


@app.route("/customer/profile", methods=["GET", "POST"])
@customer_login_required
def customer_profile():
    customer = get_customer_context()
    if not customer:
        return redirect(url_for("customer_login"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        if not all([name, phone, address]):
            flash("Name, phone, and address are required.", "error")
            return redirect(url_for("customer_profile"))
        conn = get_db_connection()
        conn.execute(
            "UPDATE customer_users SET name = ?, phone = ?, address = ? WHERE id = ?",
            (name, phone, address, customer["id"]),
        )
        conn.commit()
        conn.close()
        flash("Profile updated.", "success")
        return redirect(url_for("customer_profile"))
    return render_template("customer_profile.html", customer=customer)


@app.route("/admin/login", methods=["GET"])
def admin_login():
    return redirect(url_for("login"))


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    context = get_admin_dashboard_context()
    return render_template("admin_dashboard.html", **context)


@app.route("/admin/menu", methods=["GET", "POST"])
@login_required
def admin_menu():
    conn = get_db_connection()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        price_raw = request.form.get("price", "").strip()
        sort_order_raw = request.form.get("sort_order", "0").strip()
        if not name or not category or not price_raw:
            conn.close()
            flash("Name, category, and price are required.", "error")
            return redirect(url_for("admin_menu"))
        try:
            price = float(price_raw)
        except ValueError:
            conn.close()
            flash("Price must be a number.", "error")
            return redirect(url_for("admin_menu"))
        try:
            sort_order = int(sort_order_raw or 0)
        except ValueError:
            sort_order = 0
        image_path = save_uploaded_file(request.files.get("image"))
        conn.execute(
            """
            INSERT INTO menu_items (name, description, category, price, sort_order, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, description, category, price, sort_order, image_path),
        )
        conn.commit()
        conn.close()
        flash("Menu item added.", "success")
        return redirect(url_for("admin_menu"))
    menu_items = conn.execute(
        "SELECT * FROM menu_items ORDER BY sort_order, id"
    ).fetchall()
    conn.close()
    return render_template("admin_menu.html", menu_items=menu_items)


@app.route("/admin/menu/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def admin_menu_edit(item_id: int):
    conn = get_db_connection()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        price_raw = request.form.get("price", "").strip()
        sort_order_raw = request.form.get("sort_order", "0").strip()
        if not name or not category or not price_raw:
            conn.close()
            flash("Name, category, and price are required.", "error")
            return redirect(url_for("admin_menu_edit", item_id=item_id))
        try:
            price = float(price_raw)
        except ValueError:
            conn.close()
            flash("Price must be a number.", "error")
            return redirect(url_for("admin_menu_edit", item_id=item_id))
        try:
            sort_order = int(sort_order_raw or 0)
        except ValueError:
            sort_order = 0
        image_path = save_uploaded_file(request.files.get("image"))
        current = conn.execute(
            "SELECT image_path FROM menu_items WHERE id = ?", (item_id,)
        ).fetchone()
        final_image = image_path or (current["image_path"] if current else None)
        conn.execute(
            """
            UPDATE menu_items
            SET name = ?, description = ?, category = ?, price = ?, sort_order = ?, image_path = ?
            WHERE id = ?
            """,
            (
                name,
                description,
                category,
                price,
                sort_order,
                final_image,
                item_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("Menu item updated.", "success")
        return redirect(url_for("admin_menu"))
    item = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if not item:
        abort(404)
    return render_template("admin_menu_edit.html", item=item)


@app.route("/admin/menu/<int:item_id>/image/delete", methods=["POST"])
@login_required
def admin_menu_image_delete(item_id: int):
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT image_path FROM menu_items WHERE id = ?", (item_id,)
    ).fetchone()
    conn.execute(
        "UPDATE menu_items SET image_path = NULL WHERE id = ?", (item_id,)
    )
    conn.commit()
    conn.close()
    if existing and existing["image_path"]:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, existing["image_path"]))
        except OSError:
            pass
    flash("Menu image removed.", "success")
    return redirect(url_for("admin_menu_edit", item_id=item_id))


@app.route("/admin/menu/<int:item_id>/delete", methods=["POST"])
@login_required
def admin_menu_delete(item_id: int):
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT image_path FROM menu_items WHERE id = ?", (item_id,)
    ).fetchone()
    conn.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    if existing and existing["image_path"]:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, existing["image_path"]))
        except OSError:
            pass
    flash("Menu item deleted.", "success")
    return redirect(url_for("admin_menu"))


@app.route("/admin/story", methods=["GET", "POST"])
@login_required
def admin_story():
    conn = get_db_connection()
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "highlight":
            title = request.form.get("title", "").strip()
            body = request.form.get("body", "").strip()
            if not title or not body:
                conn.close()
                flash("Highlight title and body are required.", "error")
                return redirect(url_for("admin_story"))
            conn.execute(
                "INSERT INTO story_highlights (title, body) VALUES (?, ?)",
                (title, body),
            )
            flash("Story highlight added.", "success")
        elif form_type == "panel":
            label = request.form.get("label", "").strip()
            value = request.form.get("value", "").strip()
            sort_order_raw = request.form.get("sort_order", "0").strip()
            if not label or not value:
                conn.close()
                flash("Panel label and value are required.", "error")
                return redirect(url_for("admin_story"))
            try:
                sort_order = int(sort_order_raw or 0)
            except ValueError:
                sort_order = 0
            conn.execute(
                "INSERT INTO story_panels (label, value, sort_order) VALUES (?, ?, ?)",
                (label, value, sort_order),
            )
            flash("Story panel added.", "success")
        conn.commit()
    highlights = conn.execute("SELECT * FROM story_highlights ORDER BY id").fetchall()
    panels = conn.execute(
        "SELECT * FROM story_panels ORDER BY sort_order, id"
    ).fetchall()
    conn.close()
    return render_template("admin_story.html", highlights=highlights, panels=panels)


@app.route("/admin/story/highlight/<int:highlight_id>/edit", methods=["GET", "POST"])
@login_required
def admin_story_highlight_edit(highlight_id: int):
    conn = get_db_connection()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title or not body:
            conn.close()
            flash("Highlight title and body are required.", "error")
            return redirect(url_for("admin_story_highlight_edit", highlight_id=highlight_id))
        conn.execute(
            "UPDATE story_highlights SET title = ?, body = ? WHERE id = ?",
            (title, body, highlight_id),
        )
        conn.commit()
        conn.close()
        flash("Story highlight updated.", "success")
        return redirect(url_for("admin_story"))
    highlight = conn.execute(
        "SELECT * FROM story_highlights WHERE id = ?", (highlight_id,)
    ).fetchone()
    conn.close()
    if not highlight:
        abort(404)
    return render_template("admin_story_highlight_edit.html", highlight=highlight)


@app.route("/admin/story/highlight/<int:highlight_id>/delete", methods=["POST"])
@login_required
def admin_story_highlight_delete(highlight_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM story_highlights WHERE id = ?", (highlight_id,))
    conn.commit()
    conn.close()
    flash("Story highlight deleted.", "success")
    return redirect(url_for("admin_story"))


@app.route("/admin/story/panel/<int:panel_id>/edit", methods=["GET", "POST"])
@login_required
def admin_story_panel_edit(panel_id: int):
    conn = get_db_connection()
    if request.method == "POST":
        label = request.form.get("label", "").strip()
        value = request.form.get("value", "").strip()
        sort_order_raw = request.form.get("sort_order", "0").strip()
        if not label or not value:
            conn.close()
            flash("Panel label and value are required.", "error")
            return redirect(url_for("admin_story_panel_edit", panel_id=panel_id))
        try:
            sort_order = int(sort_order_raw or 0)
        except ValueError:
            sort_order = 0
        conn.execute(
            "UPDATE story_panels SET label = ?, value = ?, sort_order = ? WHERE id = ?",
            (label, value, sort_order, panel_id),
        )
        conn.commit()
        conn.close()
        flash("Story panel updated.", "success")
        return redirect(url_for("admin_story"))
    panel = conn.execute("SELECT * FROM story_panels WHERE id = ?", (panel_id,)).fetchone()
    conn.close()
    if not panel:
        abort(404)
    return render_template("admin_story_panel_edit.html", panel=panel)


@app.route("/admin/story/panel/<int:panel_id>/delete", methods=["POST"])
@login_required
def admin_story_panel_delete(panel_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM story_panels WHERE id = ?", (panel_id,))
    conn.commit()
    conn.close()
    flash("Story panel deleted.", "success")
    return redirect(url_for("admin_story"))


@app.route("/admin/contact", methods=["GET", "POST"])
@login_required
def admin_contact():
    conn = get_db_connection()
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        location = request.form.get("location", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        if not phone or not email or not location:
            conn.close()
            flash("Phone, email, and location are required.", "error")
            return redirect(url_for("admin_contact"))
        conn.execute(
            """
            UPDATE contact_info
            SET phone = ?, email = ?, location = ?, whatsapp = ?
            WHERE id = 1
            """,
            (phone, email, location, whatsapp),
        )
        conn.commit()
        flash("Contact details updated.", "success")
    contact = conn.execute("SELECT * FROM contact_info WHERE id = 1").fetchone()
    conn.close()
    return render_template("admin_contact.html", contact=contact)


@app.route("/admin/users", methods=["GET", "POST"])
@login_required
def admin_users():
    conn = get_db_connection()
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        if not email or not password:
            error = "Email and password are required."
        else:
            try:
                conn.execute(
                    "INSERT INTO admin_users (username, email, password_hash) VALUES (?, ?, ?)",
                    (email, email, generate_password_hash(password)),
                )
                conn.commit()
                flash("Admin user added.", "success")
                conn.close()
                return redirect(url_for("admin_users"))
            except sqlite3.IntegrityError:
                error = "Email already exists."
    users = conn.execute("SELECT * FROM admin_users ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin_users.html", users=users, error=error)


@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def admin_user_edit(user_id: int):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM admin_users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        abort(404)
    if request.method == "POST":
        new_password = request.form.get("password", "").strip()
        if not new_password:
            conn.close()
            flash("Enter a new password to reset.", "error")
            return redirect(url_for("admin_user_edit", user_id=user_id))
        conn.execute(
            "UPDATE admin_users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(new_password), user_id),
        )
        conn.commit()
        conn.close()
        flash("Password reset successful.", "success")
        return redirect(url_for("admin_users"))
    conn.close()
    return render_template("admin_user_edit.html", user=user)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_user_delete(user_id: int):
    if session.get("admin_user_id") == user_id:
        flash("You cannot delete the signed-in admin.", "error")
        return redirect(url_for("admin_users"))
    conn = get_db_connection()
    conn.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("Admin user deleted.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/orders", methods=["GET", "POST"])
@login_required
def admin_orders():
    conn = get_db_connection()
    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        delivery_area = request.form.get("delivery_area", "").strip()
        items = request.form.get("items", "").strip()
        total_raw = request.form.get("total_amount", "").strip()
        status = request.form.get("status", "New")
        order_reference = request.form.get("order_reference", "").strip()
        payment_method = request.form.get("payment_method", "").strip() or "Cash"
        payment_status = request.form.get("payment_status", "").strip() or "Unpaid"
        source_channel = request.form.get("source_channel", "").strip() or "Admin"
        legal_notes = request.form.get("legal_notes", "").strip()
        notes = request.form.get("notes", "").strip()
        if not customer_name or not phone or not delivery_area or not items:
            conn.close()
            flash("Customer name, phone, area, and items are required.", "error")
            return redirect(url_for("admin_orders"))
        try:
            total_amount = float(total_raw or 0)
        except ValueError:
            conn.close()
            flash("Total amount must be a number.", "error")
            return redirect(url_for("admin_orders"))
        if not order_reference:
            order_reference = generate_order_reference()
        conn.execute(
            """
            INSERT INTO orders (
                customer_name,
                phone,
                delivery_area,
                items,
                total_amount,
                status,
                order_reference,
                payment_method,
                payment_status,
                source_channel,
                legal_notes,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                customer_name,
                phone,
                delivery_area,
                items,
                total_amount,
                status,
                order_reference,
                payment_method,
                payment_status,
                source_channel,
                legal_notes,
                notes,
            ),
        )
        order_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        log_order_event(conn, order_id, status, "Order created", "admin", session.get("admin_user_id"))
        log_audit_event(
            conn,
            "admin",
            session.get("admin_user_id"),
            "create",
            "order",
            order_id,
            f"order_reference={order_reference}",
        )
        conn.commit()
        conn.close()
        flash("Order added.", "success")
        return redirect(url_for("admin_orders"))
    orders = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>/edit", methods=["GET", "POST"])
@login_required
def admin_order_edit(order_id: int):
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        abort(404)
    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        delivery_area = request.form.get("delivery_area", "").strip()
        items = request.form.get("items", "").strip()
        total_raw = request.form.get("total_amount", "").strip()
        status = request.form.get("status", "New")
        order_reference = request.form.get("order_reference", "").strip()
        payment_method = request.form.get("payment_method", "").strip() or "Cash"
        payment_status = request.form.get("payment_status", "").strip() or "Unpaid"
        source_channel = request.form.get("source_channel", "").strip() or "Admin"
        legal_notes = request.form.get("legal_notes", "").strip()
        notes = request.form.get("notes", "").strip()
        if not customer_name or not phone or not delivery_area or not items:
            conn.close()
            flash("Customer name, phone, area, and items are required.", "error")
            return redirect(url_for("admin_order_edit", order_id=order_id))
        try:
            total_amount = float(total_raw or 0)
        except ValueError:
            conn.close()
            flash("Total amount must be a number.", "error")
            return redirect(url_for("admin_order_edit", order_id=order_id))
        if not order_reference:
            order_reference = order["order_reference"] or generate_order_reference()
        conn.execute(
            """
            UPDATE orders
            SET customer_name = ?,
                phone = ?,
                delivery_area = ?,
                items = ?,
                total_amount = ?,
                status = ?,
                order_reference = ?,
                payment_method = ?,
                payment_status = ?,
                source_channel = ?,
                legal_notes = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                customer_name,
                phone,
                delivery_area,
                items,
                total_amount,
                status,
                order_reference,
                payment_method,
                payment_status,
                source_channel,
                legal_notes,
                notes,
                order_id,
            ),
        )
        if order["status"] != status:
            log_order_event(
                conn,
                order_id,
                status,
                f"Status changed from {order['status']}",
                "admin",
                session.get("admin_user_id"),
            )
        log_audit_event(
            conn,
            "admin",
            session.get("admin_user_id"),
            "update",
            "order",
            order_id,
            "Order details updated",
        )
        conn.commit()
        conn.close()
        flash("Order updated.", "success")
        return redirect(url_for("admin_orders"))
    conn.close()
    return render_template("admin_order_edit.html", order=order)


@app.route("/admin/orders/<int:order_id>/delete", methods=["POST"])
@login_required
def admin_order_delete(order_id: int):
    conn = get_db_connection()
    log_audit_event(
        conn,
        "admin",
        session.get("admin_user_id"),
        "delete",
        "order",
        order_id,
        "Order deleted",
    )
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    flash("Order deleted.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/orders/<int:order_id>/accept", methods=["POST"])
@login_required
def admin_order_accept(order_id: int):
    conn = get_db_connection()
    conn.execute(
        "UPDATE orders SET status = 'Preparing', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (order_id,),
    )
    log_order_event(
        conn,
        order_id,
        "Preparing",
        "Accepted by admin",
        "admin",
        session.get("admin_user_id"),
    )
    conn.commit()
    conn.close()
    flash("Order marked as preparing.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/orders/<int:order_id>/reject", methods=["POST"])
@login_required
def admin_order_reject(order_id: int):
    conn = get_db_connection()
    conn.execute(
        "UPDATE orders SET status = 'Cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (order_id,),
    )
    log_order_event(
        conn,
        order_id,
        "Cancelled",
        "Rejected by admin",
        "admin",
        session.get("admin_user_id"),
    )
    conn.commit()
    conn.close()
    flash("Order cancelled.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/orders/clear", methods=["POST"])
@login_required
def admin_orders_clear():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) AS total FROM orders").fetchone()["total"]
    conn.execute("DELETE FROM orders")
    log_audit_event(
        conn,
        "admin",
        session.get("admin_user_id"),
        "delete",
        "orders",
        0,
        f"Cleared {count} orders",
    )
    conn.commit()
    conn.close()
    flash("All orders cleared.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/orders/export")
@login_required
def admin_orders_export():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "order_reference",
            "customer_name",
            "phone",
            "delivery_area",
            "items",
            "total_amount",
            "status",
            "payment_method",
            "payment_status",
            "source_channel",
            "legal_notes",
            "notes",
            "customer_id",
            "updated_at",
            "created_at",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["order_reference"],
                row["customer_name"],
                row["phone"],
                row["delivery_area"],
                row["items"],
                row["total_amount"],
                row["status"],
                row["payment_method"],
                row["payment_status"],
                row["source_channel"],
                row["legal_notes"],
                row["notes"],
                row["customer_id"],
                row["updated_at"],
                row["created_at"],
            ]
        )
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=orders.csv"
    return response


@app.route("/admin/audit/export")
@login_required
def admin_audit_export():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM audit_logs ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "actor_type",
            "actor_id",
            "action",
            "entity_type",
            "entity_id",
            "details",
            "created_at",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["actor_type"],
                row["actor_id"],
                row["action"],
                row["entity_type"],
                row["entity_id"],
                row["details"],
                row["created_at"],
            ]
        )
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=audit_logs.csv"
    return response


def order_to_dict(row):
    return {
        "id": row["id"],
        "order_reference": row["order_reference"],
        "customer_name": row["customer_name"],
        "phone": row["phone"],
        "delivery_area": row["delivery_area"],
        "items": row["items"],
        "total_amount": row["total_amount"],
        "status": row["status"],
        "payment_method": row["payment_method"],
        "payment_status": row["payment_status"],
        "source_channel": row["source_channel"],
        "legal_notes": row["legal_notes"],
        "notes": row["notes"],
        "customer_id": row["customer_id"],
        "updated_at": row["updated_at"],
        "created_at": row["created_at"],
    }


@app.route("/api/orders", methods=["GET"])
@login_required
def api_orders():
    conn = get_db_connection()
    orders = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return jsonify({"orders": [order_to_dict(row) for row in orders]})


@app.route("/api/orders/<int:order_id>", methods=["GET"])
def api_order_detail(order_id: int):
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Order not found"}), 404
    is_admin = session.get("admin_user_id") is not None
    is_customer = session.get("customer_user_id") == order["customer_id"]
    if not is_admin and not is_customer:
        conn.close()
        return jsonify({"error": "Unauthorized"}), 403
    events = conn.execute(
        "SELECT * FROM order_events WHERE order_id = ? ORDER BY created_at DESC, id DESC",
        (order_id,),
    ).fetchall()
    conn.close()
    return jsonify(
        {
            "order": order_to_dict(order),
            "events": [
                {
                    "status": row["status"],
                    "note": row["note"],
                    "actor_type": row["actor_type"],
                    "actor_id": row["actor_id"],
                    "created_at": row["created_at"],
                }
                for row in events
            ],
        }
    )


@app.route("/api/customer/orders", methods=["GET"])
@customer_login_required
def api_customer_orders():
    customer_id = session.get("customer_user_id")
    conn = get_db_connection()
    orders = conn.execute(
        "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC, id DESC",
        (customer_id,),
    ).fetchall()
    conn.close()
    return jsonify({"orders": [order_to_dict(row) for row in orders]})


@app.route("/api/orders/<int:order_id>/status", methods=["POST"])
@login_required
def api_order_status_update(order_id: int):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()
    note = (payload.get("note") or "Status updated via API").strip()
    if not status:
        return jsonify({"error": "Status is required"}), 400
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Order not found"}), 404
    conn.execute(
        "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, order_id),
    )
    log_order_event(
        conn,
        order_id,
        status,
        note,
        "admin",
        session.get("admin_user_id"),
    )
    log_audit_event(
        conn,
        "admin",
        session.get("admin_user_id"),
        "update",
        "order",
        order_id,
        f"API status update: {status}",
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "order_id": order_id, "new_status": status})


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

