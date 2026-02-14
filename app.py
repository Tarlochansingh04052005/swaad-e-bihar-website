import os
import sqlite3
from functools import wraps
from secrets import token_hex

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder=".", static_url_path="/static")
app.secret_key = "change-this-secret-key"

app.jinja_loader = ChoiceLoader(
    [
        FileSystemLoader(app.root_path),
        FileSystemLoader(os.path.join(app.root_path, "templates")),
    ]
)

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


@app.route("/cart")
def cart_page():
    cart = get_cart()
    cart_items, subtotal = get_cart_items(cart)
    delivery_fee = 20 if subtotal > 0 else 0
    total = subtotal + delivery_fee
    return render_template(
        "page_cart.html",
        cart_items=cart_items,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total,
    )


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
    conn.close()
    return render_template("customer_dashboard.html", orders=orders, customer=customer)




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
            notes TEXT,
            customer_id INTEGER,
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
    ensure_column(conn, "admin_users", "email", "TEXT")

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


@app.route("/order/request", methods=["POST"])
def order_request():
    customer_name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    delivery_area = request.form.get("area", "").strip()
    items = request.form.get("items", "").strip()
    notes = request.form.get("notes", "").strip()
    if not customer_name or not phone or not delivery_area or not items:
        return redirect(url_for("home", order="error"))
    customer_id = session.get("customer_user_id")
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO orders (customer_name, phone, delivery_area, items, total_amount, status, notes, customer_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (customer_name, phone, delivery_area, items, 0, "New", notes, customer_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home", order="success"))


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
    return render_template("admin_dashboard.html")


@app.route("/customer/login", methods=["GET", "POST"])
def customer_login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        conn = get_db_connection()
        customer = conn.execute(
            "SELECT * FROM customer_users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()
        if customer and check_password_hash(customer["password_hash"], password):
            session["customer_user_id"] = customer["id"]
            return redirect(url_for("customer_dashboard"))
        error = "Invalid email or password."
    return render_template("customer_login.html", error=error)


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
        conn = get_db_connection()
        conn.execute(
            "UPDATE customer_users SET name = ?, phone = ?, address = ? WHERE id = ?",
            (name, phone, address, customer["id"]),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("customer_profile"))
    return render_template("customer_profile.html", customer=customer)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_user_id"):
        return redirect(url_for("admin_dashboard"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        conn = get_db_connection()
        admin_user = conn.execute(
            "SELECT * FROM admin_users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()
        if admin_user and check_password_hash(admin_user["password_hash"], password):
            session["admin_user_id"] = admin_user["id"]
            session["admin_email"] = admin_user["email"]
            return redirect(url_for("admin_dashboard"))
        error = "Invalid email or password."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    return render_template("admin_dashboard.html")


@app.route("/admin/menu", methods=["GET", "POST"])
@login_required
def admin_menu():
    conn = get_db_connection()
    if request.method == "POST":
        image_path = save_uploaded_file(request.files.get("image"))
        conn.execute(
            """
            INSERT INTO menu_items (name, description, category, price, sort_order, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.form.get("name", "").strip(),
                request.form.get("description", "").strip(),
                request.form.get("category", "").strip(),
                float(request.form.get("price", "0") or 0),
                int(request.form.get("sort_order", "0") or 0),
                image_path,
            ),
        )
        conn.commit()
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
                request.form.get("name", "").strip(),
                request.form.get("description", "").strip(),
                request.form.get("category", "").strip(),
                float(request.form.get("price", "0") or 0),
                int(request.form.get("sort_order", "0") or 0),
                final_image,
                item_id,
            ),
        )
        conn.commit()
        conn.close()
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
    return redirect(url_for("admin_menu"))


@app.route("/admin/story", methods=["GET", "POST"])
@login_required
def admin_story():
    conn = get_db_connection()
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "highlight":
            conn.execute(
                "INSERT INTO story_highlights (title, body) VALUES (?, ?)",
                (
                    request.form.get("title", "").strip(),
                    request.form.get("body", "").strip(),
                ),
            )
        elif form_type == "panel":
            conn.execute(
                "INSERT INTO story_panels (label, value, sort_order) VALUES (?, ?, ?)",
                (
                    request.form.get("label", "").strip(),
                    request.form.get("value", "").strip(),
                    int(request.form.get("sort_order", "0") or 0),
                ),
            )
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
        conn.execute(
            "UPDATE story_highlights SET title = ?, body = ? WHERE id = ?",
            (
                request.form.get("title", "").strip(),
                request.form.get("body", "").strip(),
                highlight_id,
            ),
        )
        conn.commit()
        conn.close()
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
    return redirect(url_for("admin_story"))


@app.route("/admin/story/panel/<int:panel_id>/edit", methods=["GET", "POST"])
@login_required
def admin_story_panel_edit(panel_id: int):
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            "UPDATE story_panels SET label = ?, value = ?, sort_order = ? WHERE id = ?",
            (
                request.form.get("label", "").strip(),
                request.form.get("value", "").strip(),
                int(request.form.get("sort_order", "0") or 0),
                panel_id,
            ),
        )
        conn.commit()
        conn.close()
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
    return redirect(url_for("admin_story"))


@app.route("/admin/contact", methods=["GET", "POST"])
@login_required
def admin_contact():
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            """
            UPDATE contact_info
            SET phone = ?, email = ?, location = ?, whatsapp = ?
            WHERE id = 1
            """,
            (
                request.form.get("phone", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("location", "").strip(),
                request.form.get("whatsapp", "").strip(),
            ),
        )
        conn.commit()
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
        if new_password:
            conn.execute(
                "UPDATE admin_users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password), user_id),
            )
            conn.commit()
        conn.close()
        return redirect(url_for("admin_users"))
    conn.close()
    return render_template("admin_user_edit.html", user=user)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_user_delete(user_id: int):
    if session.get("admin_user_id") == user_id:
        return redirect(url_for("admin_users"))
    conn = get_db_connection()
    conn.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_users"))


@app.route("/admin/orders", methods=["GET", "POST"])
@login_required
def admin_orders():
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO orders (customer_name, phone, delivery_area, items, total_amount, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form.get("customer_name", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("delivery_area", "").strip(),
                request.form.get("items", "").strip(),
                float(request.form.get("total_amount", "0") or 0),
                request.form.get("status", "New"),
                request.form.get("notes", "").strip(),
            ),
        )
        conn.commit()
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
        conn.execute(
            """
            UPDATE orders
            SET customer_name = ?, phone = ?, delivery_area = ?, items = ?, total_amount = ?, status = ?, notes = ?
            WHERE id = ?
            """,
            (
                request.form.get("customer_name", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("delivery_area", "").strip(),
                request.form.get("items", "").strip(),
                float(request.form.get("total_amount", "0") or 0),
                request.form.get("status", "New"),
                request.form.get("notes", "").strip(),
                order_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_orders"))
    conn.close()
    return render_template("admin_order_edit.html", order=order)


@app.route("/admin/orders/<int:order_id>/delete", methods=["POST"])
@login_required
def admin_order_delete(order_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_orders"))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
