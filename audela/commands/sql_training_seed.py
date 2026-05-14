"""
SQL Training Content Seeder

Populates the database with sample SQL training modules.
Run with: flask --app app seed-sql-training
"""

import click
from audela import create_app
from audela.extensions import db
from audela.models.sql_training import (
    SQLTrainingModule,
    SQLTrainingLesson,
    SQLTrainingExercise,
)


# Sample database DDL
SAMPLE_DATABASE_SCHEMA_SQL101 = """
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    country TEXT,
    created_at DATE
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date DATE NOT NULL,
    amount DECIMAL(10, 2),
    status TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT,
    price DECIMAL(10, 2),
    stock INT
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INT,
    unit_price DECIMAL(10, 2),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

SAMPLE_DATA_SQL101 = """
INSERT INTO customers (customer_id, first_name, last_name, email, country, created_at) VALUES
(1, 'João', 'Silva', 'joao.silva@example.com', 'Brasil', '2024-01-15'),
(2, 'Maria', 'Santos', 'maria.santos@example.com', 'Brasil', '2024-02-20'),
(3, 'Pierre', 'Dupont', 'pierre.dupont@example.com', 'France', '2024-01-10'),
(4, 'Anna', 'Rossi', 'anna.rossi@example.com', 'Italia', '2024-03-05'),
(5, 'Carlos', 'Garcia', 'carlos.garcia@example.com', 'España', '2024-01-25');

INSERT INTO products (product_id, product_name, category, price, stock) VALUES
(1, 'Laptop', 'Electronics', 999.99, 50),
(2, 'Mouse', 'Electronics', 29.99, 200),
(3, 'Keyboard', 'Electronics', 79.99, 150),
(4, 'Monitor', 'Electronics', 299.99, 75),
(5, 'USB Cable', 'Accessories', 9.99, 500);

INSERT INTO orders (order_id, customer_id, order_date, amount, status) VALUES
(1, 1, '2024-03-01', 1009.98, 'completed'),
(2, 2, '2024-03-03', 1299.98, 'completed'),
(3, 3, '2024-03-05', 79.99, 'shipped'),
(4, 1, '2024-03-07', 299.99, 'pending'),
(5, 4, '2024-03-10', 29.99, 'completed'),
(6, 5, '2024-03-12', 379.97, 'shipped');

INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 1, 999.99),
(2, 1, 2, 1, 9.99),
(3, 2, 4, 1, 299.99),
(4, 2, 3, 1, 79.99),
(5, 3, 3, 1, 79.99),
(6, 4, 4, 1, 299.99),
(7, 5, 2, 1, 29.99),
(8, 6, 1, 1, 999.99),
(9, 6, 5, 10, 9.99);
"""

SAMPLE_DATABASE_SCHEMA_INTERMEDIATE = """
CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    department TEXT,
    salary DECIMAL(10, 2),
    hire_date DATE
);

CREATE TABLE projects (
    project_id INTEGER PRIMARY KEY,
    project_name TEXT,
    start_date DATE,
    end_date DATE,
    budget DECIMAL(12, 2)
);

CREATE TABLE assignments (
    assignment_id INTEGER PRIMARY KEY,
    employee_id INTEGER,
    project_id INTEGER,
    hours_allocated INT,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
"""

SAMPLE_DATA_INTERMEDIATE = """
INSERT INTO employees VALUES
(1, 'Alice', 'Johnson', 'Engineering', 75000, '2022-01-15'),
(2, 'Bob', 'Smith', 'Engineering', 70000, '2022-03-20'),
(3, 'Carol', 'White', 'Sales', 60000, '2021-06-10'),
(4, 'David', 'Brown', 'HR', 55000, '2023-01-05'),
(5, 'Eve', 'Davis', 'Engineering', 72000, '2022-09-12');

INSERT INTO projects VALUES
(1, 'Website Redesign', '2024-01-01', '2024-06-30', 50000),
(2, 'Mobile App', '2024-02-15', '2024-12-31', 100000),
(3, 'API Integration', '2024-03-01', '2024-05-31', 25000);

INSERT INTO assignments VALUES
(1, 1, 1, 40),
(2, 2, 1, 35),
(3, 1, 2, 30),
(4, 3, 3, 20),
(5, 2, 3, 25),
(6, 4, 2, 10);
"""


def create_sql101_module():
    """Create SQL 101 Beginner Module"""
    module = SQLTrainingModule(
        code="sql_101",
        title_i18n={
            "pt": "SQL 101 - Fundamentos",
            "en": "SQL 101 - Fundamentals",
            "fr": "SQL 101 - Fondamentaux",
            "es": "SQL 101 - Fundamentos",
            "it": "SQL 101 - Fondamenti",
            "de": "SQL 101 - Grundlagen",
        },
        description_i18n={
            "pt": "Aprenda os conceitos básicos do SQL: SELECT, WHERE, ORDER BY e muito mais.",
            "en": "Learn SQL basics: SELECT, WHERE, ORDER BY and more.",
            "fr": "Apprenez les bases du SQL: SELECT, WHERE, ORDER BY et bien plus.",
            "es": "Aprenda lo básico de SQL: SELECT, WHERE, ORDER BY y más.",
            "it": "Impara le basi di SQL: SELECT, WHERE, ORDER BY e altro.",
            "de": "Lernen Sie SQL-Grundlagen: SELECT, WHERE, ORDER BY und mehr.",
        },
        level="beginner",
        order=1,
        sample_database_schema=SAMPLE_DATABASE_SCHEMA_SQL101,
        sample_data_sql=SAMPLE_DATA_SQL101,
        total_lessons=3,
        total_exercises=9,
        estimated_hours=2.0,
        pass_threshold=80,
    )
    
    db.session.add(module)
    db.session.commit()
    
    # Lesson 1: SELECT Basics
    lesson1 = SQLTrainingLesson(
        module_id=module.id,
        code="lesson_01_select",
        order=1,
        title_i18n={
            "pt": "Introdução ao SELECT",
            "en": "Introduction to SELECT",
        },
        description_i18n={
            "pt": "Aprenda como usar a instrução SELECT para recuperar dados",
            "en": "Learn how to use the SELECT statement to retrieve data",
        },
        content_html_i18n={
            "pt": """
            <h3>SELECT - A Instruçao Fundamental</h3>
            <p>SELECT é a instrução SQL mais básica e importante. Ela permite recuperar dados das tabelas.</p>
            <h4>Sintaxe Basic:</h4>
            <pre>SELECT coluna1, coluna2, ...
FROM tabela;</pre>
            <p><strong>Exemplo:</strong></p>
            <pre>SELECT first_name, last_name, email
FROM customers;</pre>
            """,
            "en": """
            <h3>SELECT - The Fundamental Statement</h3>
            <p>SELECT is the most basic and important SQL statement. It allows you to retrieve data from tables.</p>
            <h4>Basic Syntax:</h4>
            <pre>SELECT column1, column2, ...
FROM table;</pre>
            <p><strong>Example:</strong></p>
            <pre>SELECT first_name, last_name, email
FROM customers;</pre>
            """,
        },
        key_concepts_i18n={
            "pt": ["SELECT retrieves columns", "Wildcard * selects all columns", "Specify table name with FROM"],
            "en": ["SELECT retrieves columns", "Wildcard * selects all columns", "Specify table name with FROM"],
        },
    )
    db.session.add(lesson1)
    db.session.commit()
    
    # Exercise 1.1
    ex1 = SQLTrainingExercise(
        lesson_id=lesson1.id,
        code="ex_01_01_select_all",
        order=1,
        type="sql_query",
        title_i18n={"pt": "Selecionar Todos os Clientes", "en": "Select All Customers"},
        instruction_i18n={
            "pt": "Escreva uma consulta para selecionar todos os clientes da tabela customers",
            "en": "Write a query to select all customers from the customers table",
        },
        hint_i18n={"pt": "Use SELECT * FROM customers", "en": "Use SELECT * FROM customers"},
        expected_sql="SELECT * FROM customers",
        points=10,
    )
    db.session.add(ex1)
    
    # Exercise 1.2
    ex2 = SQLTrainingExercise(
        lesson_id=lesson1.id,
        code="ex_01_02_select_columns",
        order=2,
        type="sql_query",
        title_i18n={"pt": "Selecionar Colunas Específicas", "en": "Select Specific Columns"},
        instruction_i18n={
            "pt": "Selecione apenas first_name e last_name dos clientes",
            "en": "Select only first_name and last_name from customers",
        },
        expected_sql="SELECT first_name, last_name FROM customers",
        points=10,
    )
    db.session.add(ex2)
    db.session.commit()
    
    # Lesson 2: WHERE Clause
    lesson2 = SQLTrainingLesson(
        module_id=module.id,
        code="lesson_02_where",
        order=2,
        title_i18n={"pt": "Filtragem com WHERE", "en": "Filtering with WHERE"},
        description_i18n={"pt": "Use WHERE para filtrar dados", "en": "Use WHERE to filter data"},
        content_html_i18n={
            "pt": "<h3>WHERE - Filtrando Dados</h3><pre>SELECT * FROM customers WHERE country = 'Brasil';</pre>",
            "en": "<h3>WHERE - Filtering Data</h3><pre>SELECT * FROM customers WHERE country = 'Brasil';</pre>",
        },
    )
    db.session.add(lesson2)
    db.session.commit()
    
    # Exercise 2.1
    ex3 = SQLTrainingExercise(
        lesson_id=lesson2.id,
        code="ex_02_01_where_basic",
        order=1,
        type="sql_query",
        title_i18n={"pt": "Filtrar por País", "en": "Filter by Country"},
        instruction_i18n={"pt": "Selecione clientes do Brasil", "en": "Select customers from Brazil"},
        expected_sql="SELECT * FROM customers WHERE country = 'Brasil'",
        points=15,
    )
    db.session.add(ex3)
    db.session.commit()
    
    # Lesson 3: INSERT, UPDATE, DELETE
    lesson3 = SQLTrainingLesson(
        module_id=module.id,
        code="lesson_03_dml",
        order=3,
        title_i18n={"pt": "DML: INSERT, UPDATE, DELETE", "en": "DML: INSERT, UPDATE, DELETE"},
        description_i18n={"pt": "Modifique dados com DML", "en": "Modify data with DML"},
    )
    db.session.add(lesson3)
    db.session.commit()
    
    # Exercise 3.1: INSERT
    ex4 = SQLTrainingExercise(
        lesson_id=lesson3.id,
        code="ex_03_01_insert",
        order=1,
        type="sql_dml",
        dml_operation="INSERT",
        title_i18n={"pt": "Inserir um Cliente", "en": "Insert a Customer"},
        instruction_i18n={
            "pt": "Insira um novo cliente: customer_id=6, first_name='Test', last_name='User', country='USA'",
            "en": "Insert a new customer: customer_id=6, first_name='Test', last_name='User', country='USA'",
        },
        validation_query="SELECT * FROM customers WHERE customer_id = 6",
        points=15,
    )
    db.session.add(ex4)
    db.session.commit()


def create_intermediate_module():
    """Create Intermediate SQL Module"""
    module = SQLTrainingModule(
        code="sql_intermediate",
        title_i18n={
            "pt": "SQL Intermediário - JOINs e Agregações",
            "en": "SQL Intermediate - JOINs and Aggregations",
        },
        description_i18n={
            "pt": "Aprenda JOINs, GROUP BY, HAVING e funções agregadas",
            "en": "Learn JOINs, GROUP BY, HAVING and aggregate functions",
        },
        level="intermediate",
        order=2,
        sample_database_schema=SAMPLE_DATABASE_SCHEMA_INTERMEDIATE,
        sample_data_sql=SAMPLE_DATA_INTERMEDIATE,
        total_lessons=2,
        total_exercises=4,
        estimated_hours=3.0,
        pass_threshold=80,
    )
    
    db.session.add(module)
    db.session.commit()
    
    print("✓ Created sample SQL training modules")


@click.group()
def cli():
    """SQL Training CLI"""
    pass


@cli.command()
def seed():
    """Seed sample SQL training content"""
    app = create_app()
    with app.app_context():
        # Check if SQL101 already exists
        existing = SQLTrainingModule.query.filter_by(code="sql_101").first()
        if existing:
            print("SQL Training modules already exist. Skipping.")
            return
        
        create_sql101_module()
        create_intermediate_module()
        print("✓ SQL Training modules created successfully!")


if __name__ == "__main__":
    cli()
