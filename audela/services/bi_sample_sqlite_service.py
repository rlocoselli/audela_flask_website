from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import random
import sqlite3


def _safe_slug(value: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in (value or ""))
    out = "_".join(part for part in out.split("_") if part)
    return out or "tenant"


def sample_sqlite_filename(tenant_id: int, tenant_name: str | None = None) -> str:
    slug = _safe_slug(tenant_name or "tenant")
    return f"audelasampledata_t{int(tenant_id)}_{slug}.db"


def create_audela_sample_sqlite(db_path: str | Path, *, seed: int = 1) -> dict[str, int]:
    """Create an AUDELA sample SQLite dataset with rich relational data.

    Returns row counts per table.
    """
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    if db_file.exists():
        db_file.unlink()

    rng = random.Random(seed)
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.executescript(
            """
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            );

            CREATE TABLE suppliers (
                id INTEGER PRIMARY KEY,
                company_name TEXT NOT NULL,
                contact_name TEXT,
                country TEXT,
                city TEXT
            );

            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                customer_code TEXT NOT NULL UNIQUE,
                company_name TEXT NOT NULL,
                contact_name TEXT,
                segment TEXT,
                country TEXT,
                city TEXT
            );

            CREATE TABLE employees (
                id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                title TEXT,
                hire_date TEXT,
                city TEXT,
                country TEXT
            );

            CREATE TABLE shippers (
                id INTEGER PRIMARY KEY,
                company_name TEXT NOT NULL,
                phone TEXT
            );

            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                sku TEXT NOT NULL UNIQUE,
                product_name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                cost_price REAL NOT NULL,
                units_in_stock INTEGER NOT NULL,
                discontinued INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                order_number TEXT NOT NULL UNIQUE,
                customer_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                shipper_id INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                required_date TEXT,
                shipped_date TEXT,
                status TEXT NOT NULL,
                ship_country TEXT,
                ship_city TEXT,
                freight REAL NOT NULL DEFAULT 0,
                discount_pct REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (shipper_id) REFERENCES shippers(id)
            );

            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                discount REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE inventory_movements (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL,
                movement_date TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                reason TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE VIEW v_sales_by_month AS
            SELECT
                substr(o.order_date, 1, 7) AS month,
                c.country AS customer_country,
                SUM(oi.quantity * oi.unit_price * (1.0 - oi.discount)) AS gross_sales,
                SUM(oi.quantity * p.cost_price) AS total_cost,
                SUM(oi.quantity * oi.unit_price * (1.0 - oi.discount)) - SUM(oi.quantity * p.cost_price) AS gross_margin
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN order_items oi ON oi.order_id = o.id
            JOIN products p ON p.id = oi.product_id
            GROUP BY substr(o.order_date, 1, 7), c.country;
            """
        )

        categories = [
            (1, "Beverages", "Soft drinks, coffee, tea"),
            (2, "Condiments", "Sauces and seasonings"),
            (3, "Confections", "Desserts and candies"),
            (4, "Dairy Products", "Cheese and milk products"),
            (5, "Grains/Cereals", "Bread and pasta"),
            (6, "Meat/Poultry", "Prepared meats"),
            (7, "Produce", "Dried fruit and bean curd"),
            (8, "Seafood", "Fish and seaweed"),
        ]
        conn.executemany("INSERT INTO categories(id, name, description) VALUES (?, ?, ?)", categories)

        suppliers = [
            (1, "Exotic Liquids", "Charlotte Cooper", "UK", "London"),
            (2, "New Orleans Cajun Delights", "Shelley Burke", "USA", "New Orleans"),
            (3, "Grandma Kelly's Homestead", "Regina Murphy", "USA", "Ann Arbor"),
            (4, "Tokyo Traders", "Yoshi Nagase", "Japan", "Tokyo"),
            (5, "Cooperativa de Quesos", "Antonio del Valle", "Spain", "Oviedo"),
            (6, "Nordic Food Trade", "Lars Iversen", "Denmark", "Copenhagen"),
            (7, "Mediterraneo Imports", "Giulia Sanna", "Italy", "Rome"),
            (8, "Atlantic Catch", "Maria Sullivan", "Ireland", "Dublin"),
            (9, "Sao Paulo Fine Foods", "Rafael Moura", "Brazil", "Sao Paulo"),
            (10, "Maple North Supplies", "Aline Beaulieu", "Canada", "Montreal"),
        ]
        conn.executemany(
            "INSERT INTO suppliers(id, company_name, contact_name, country, city) VALUES (?, ?, ?, ?, ?)",
            suppliers,
        )

        customer_countries = ["France", "Germany", "Spain", "Italy", "UK", "USA", "Brazil", "Canada", "Portugal", "Netherlands"]
        customer_segments = ["SMB", "Mid-Market", "Enterprise", "Public", "Retail"]
        customers = []
        for idx in range(1, 41):
            country = rng.choice(customer_countries)
            city = {
                "France": "Paris",
                "Germany": "Berlin",
                "Spain": "Madrid",
                "Italy": "Milan",
                "UK": "London",
                "USA": "New York",
                "Brazil": "Sao Paulo",
                "Canada": "Toronto",
                "Portugal": "Lisbon",
                "Netherlands": "Amsterdam",
            }.get(country, "City")
            customers.append(
                (
                    idx,
                    f"CUST{idx:04d}",
                    f"{country} Trading {idx}",
                    f"Contact {idx}",
                    rng.choice(customer_segments),
                    country,
                    city,
                )
            )
        conn.executemany(
            """
            INSERT INTO customers(id, customer_code, company_name, contact_name, segment, country, city)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            customers,
        )

        employees = [
            (1, "Nancy", "Davolio", "Sales Manager", "2016-03-11", "Seattle", "USA"),
            (2, "Andrew", "Fuller", "Regional Manager", "2014-08-14", "Tacoma", "USA"),
            (3, "Janet", "Leverling", "Sales Representative", "2017-04-01", "Kirkland", "USA"),
            (4, "Margaret", "Peacock", "Sales Representative", "2018-05-03", "Redmond", "USA"),
            (5, "Steven", "Buchanan", "Sales Representative", "2019-10-17", "London", "UK"),
            (6, "Laura", "Callahan", "Sales Coordinator", "2020-07-01", "Paris", "France"),
        ]
        conn.executemany(
            "INSERT INTO employees(id, first_name, last_name, title, hire_date, city, country) VALUES (?, ?, ?, ?, ?, ?, ?)",
            employees,
        )

        shippers = [
            (1, "Speedy Express", "+1 555 0101"),
            (2, "United Package", "+1 555 0102"),
            (3, "Federal Shipping", "+1 555 0103"),
            (4, "Blue Ocean Cargo", "+44 555 0104"),
        ]
        conn.executemany("INSERT INTO shippers(id, company_name, phone) VALUES (?, ?, ?)", shippers)

        product_names = [
            "Chai", "Chang", "Aniseed Syrup", "Chef Anton Seasoning", "Grandma Boysenberry Spread",
            "Queso Cabrales", "Queso Manchego", "Konbu", "Tofu", "Pavlova", "Alice Mutton",
            "Carnarvon Tigers", "Teatime Chocolate", "Sir Rodney Marmalade", "Gorgonzola", "Ravioli",
            "Singaporean Noodles", "Boston Crab Meat", "Ikura", "Longlife Tofu", "Filo Mix",
            "Tourtiere", "Pate Chinois", "Camembert Pierrot", "Nordic Herring", "Atlantic Salmon",
            "Brazilian Coffee", "AcaI Puree", "Maple Syrup", "Mediterranean Olive Mix",
        ]
        products = []
        for idx, name in enumerate(product_names, start=1):
            category_id = ((idx - 1) % 8) + 1
            supplier_id = ((idx - 1) % 10) + 1
            unit_price = round(rng.uniform(8.0, 95.0), 2)
            cost_price = round(unit_price * rng.uniform(0.45, 0.78), 2)
            stock = rng.randint(20, 450)
            discontinued = 1 if rng.random() < 0.08 else 0
            products.append(
                (
                    idx,
                    f"SKU-{idx:05d}",
                    name,
                    category_id,
                    supplier_id,
                    unit_price,
                    cost_price,
                    stock,
                    discontinued,
                )
            )
        conn.executemany(
            """
            INSERT INTO products(id, sku, product_name, category_id, supplier_id, unit_price, cost_price, units_in_stock, discontinued)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            products,
        )

        start_date = date.today() - timedelta(days=720)
        statuses = ["new", "processing", "shipped", "delivered", "cancelled"]
        orders = []
        order_items = []
        inv_movements = []

        order_id = 1
        line_id = 1
        inv_id = 1

        product_price = {p[0]: p[5] for p in products}

        for _ in range(220):
            customer_id = rng.randint(1, len(customers))
            employee_id = rng.randint(1, len(employees))
            shipper_id = rng.randint(1, len(shippers))
            order_dt = start_date + timedelta(days=rng.randint(0, 720))
            required_dt = order_dt + timedelta(days=rng.randint(2, 12))
            status = rng.choices(statuses, weights=[15, 25, 30, 25, 5], k=1)[0]
            shipped_dt = None
            if status in {"shipped", "delivered"}:
                shipped_dt = order_dt + timedelta(days=rng.randint(1, 7))

            customer_row = customers[customer_id - 1]
            freight = round(rng.uniform(8.0, 120.0), 2)
            discount_pct = round(rng.choice([0, 0, 0, 2.5, 5, 7.5, 10]) / 100.0, 4)

            orders.append(
                (
                    order_id,
                    f"SO-{order_id:06d}",
                    customer_id,
                    employee_id,
                    shipper_id,
                    order_dt.isoformat(),
                    required_dt.isoformat(),
                    shipped_dt.isoformat() if shipped_dt else None,
                    status,
                    customer_row[5],
                    customer_row[6],
                    freight,
                    discount_pct,
                )
            )

            line_count = rng.randint(2, 6)
            used_products = rng.sample(range(1, len(products) + 1), line_count)
            for pid in used_products:
                qty = rng.randint(1, 24)
                unit_price = product_price[pid]
                line_discount = round(rng.choice([0, 0, 0.05, 0.1, 0.15]), 3)
                order_items.append((line_id, order_id, pid, qty, unit_price, line_discount))

                inv_movements.append(
                    (
                        inv_id,
                        pid,
                        order_dt.isoformat(),
                        "OUT",
                        -qty,
                        f"Order SO-{order_id:06d}",
                    )
                )
                line_id += 1
                inv_id += 1

            order_id += 1

        # Add random inbound restocking events.
        for pid in range(1, len(products) + 1):
            for _ in range(rng.randint(2, 5)):
                mdt = start_date + timedelta(days=rng.randint(0, 720))
                qty = rng.randint(15, 120)
                inv_movements.append((inv_id, pid, mdt.isoformat(), "IN", qty, "Supplier replenishment"))
                inv_id += 1

        conn.executemany(
            """
            INSERT INTO orders(
                id, order_number, customer_id, employee_id, shipper_id,
                order_date, required_date, shipped_date, status,
                ship_country, ship_city, freight, discount_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            orders,
        )

        conn.executemany(
            "INSERT INTO order_items(id, order_id, product_id, quantity, unit_price, discount) VALUES (?, ?, ?, ?, ?, ?)",
            order_items,
        )

        conn.executemany(
            "INSERT INTO inventory_movements(id, product_id, movement_date, movement_type, quantity, reason) VALUES (?, ?, ?, ?, ?, ?)",
            inv_movements,
        )

        conn.executescript(
            """
            CREATE INDEX idx_orders_customer ON orders(customer_id);
            CREATE INDEX idx_orders_order_date ON orders(order_date);
            CREATE INDEX idx_order_items_order ON order_items(order_id);
            CREATE INDEX idx_order_items_product ON order_items(product_id);
            CREATE INDEX idx_products_category ON products(category_id);
            CREATE INDEX idx_inventory_product_date ON inventory_movements(product_id, movement_date);
            """
        )

        conn.commit()

        return {
            "categories": len(categories),
            "suppliers": len(suppliers),
            "customers": len(customers),
            "employees": len(employees),
            "shippers": len(shippers),
            "products": len(products),
            "orders": len(orders),
            "order_items": len(order_items),
            "inventory_movements": len(inv_movements),
        }
    finally:
        conn.close()
