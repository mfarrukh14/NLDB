import sys
import os
import sqlite3
from dotenv import load_dotenv
from langchain_groq import ChatGroq

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QListWidget, QTabWidget, QMessageBox, 
    QGraphicsDropShadowEffect, QFrame
)
from PyQt5.QtGui import (
    QColor, QLinearGradient, QPainter, QPixmap, 
    QBrush, QFont
)

load_dotenv()
groq_api_key = 'key'
llm = ChatGroq(
    groq_api_key=groq_api_key,
    model_name="llama3-70b-8192",
    temperature=0.0,
)

import os
import sys

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# --- Database functions ---
def query_database(sql_query, db_path):
    """Execute an SQL query on the database and return the fetched rows."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(sql_query)
    rows = c.fetchall()
    conn.close()
    return rows

def get_db_schema(db_path):
    """
    Retrieve a detailed schema of the SQLite database.
    Includes table names, column details, primary keys, foreign keys, and sample data.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = c.fetchall()
    
    schema_parts = []
    for table in tables:
        table_name = table[0]
        table_info = []
        table_info.append(f"Table: {table_name}")
        
        c.execute(f"PRAGMA table_info({table_name})")
        columns = c.fetchall()
        column_details = []
        primary_keys = []
        
        for col in columns:
            col_id, col_name, col_type, not_null, default_val, is_pk = col
            constraints = []
            
            if is_pk:
                constraints.append("PRIMARY KEY")
                primary_keys.append(col_name)
            if not_null:
                constraints.append("NOT NULL")
            if default_val is not None:
                constraints.append(f"DEFAULT {default_val}")
                
            constraints_str = " ".join(constraints)
            column_details.append(f"{col_name} ({col_type}) {constraints_str}".strip())
        
        table_info.append("Columns: " + ", ".join(column_details))
        
        c.execute(f"PRAGMA foreign_key_list({table_name})")
        foreign_keys = c.fetchall()
        if foreign_keys:
            fk_details = []
            for fk in foreign_keys:
                id, seq, ref_table, from_col, to_col, on_update, on_delete, match = fk
                fk_details.append(f"{from_col} -> {ref_table}({to_col})")
            table_info.append("Foreign Keys: " + ", ".join(fk_details))

        c.execute(f"PRAGMA index_list({table_name})")
        indexes = c.fetchall()
        if indexes:
            index_details = []
            for idx in indexes:
                idx_name = idx[1]
                if not idx_name.startswith('sqlite_'):  # Skip SQLite internal indexes
                    c.execute(f"PRAGMA index_info({idx_name})")
                    idx_columns = c.fetchall()
                    idx_cols = [columns[col_idx[2]][1] for col_idx in idx_columns]  # Get column names
                    index_details.append(f"{idx_name} on ({', '.join(idx_cols)})")
            if index_details:
                table_info.append("Indexes: " + ", ".join(index_details))

        try:
            c.execute(f"SELECT * FROM {table_name} LIMIT 3")
            sample_data = c.fetchall()
            if sample_data:
                sample_rows = []
                for row in sample_data:
                    formatted_row = [f"'{val}'" if isinstance(val, str) else str(val) for val in row]
                    sample_rows.append("(" + ", ".join(formatted_row) + ")")
                table_info.append("Sample Data: " + "; ".join(sample_rows))
        except:
            pass
        
        try:
            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = c.fetchone()[0]
            table_info.append(f"Row Count: {count}")
        except:
            pass
            
        schema_parts.append("\n".join(table_info))
    
    conn.close()
    return "\n\n" + "\n\n".join(schema_parts)

def generate_sql_query(natural_language_query, schema, llm):
    """
    Use the Groq LLM to generate an SQL query.
    The prompt includes the schema and instructs the model to output only the SQL query.
    """
    prompt = f"""
# SQL Query Generator

You are an expert SQL generator that translates natural language queries into valid SQLite SQL queries.

## TASK
Convert the following natural language query into a correct SQLite SQL query using all information from the provided schema.

## IMPORTANT RULES
- Output ONLY the SQL query without any explanation, comments, or additional text
- Use ONLY tables and columns listed in the schema
- Ensure correct SQLite syntax
- Generate complete, executable SQL statements
- Do not generate invalid commands like ``` or incomplete commands

## DATABASE SCHEMA
{schema}

## QUERY TECHNIQUES TO CONSIDER
1. **Basic Queries**
   - Use WHERE clauses for filtering
   - Use LIKE with % for pattern matching

2. **Joins and Relationships**
   - JOIN tables when information spans multiple tables
   - Use appropriate join types (INNER, LEFT, etc.) based on query needs

3. **Aggregation**
   - Use GROUP BY for grouped statistics
   - Apply COUNT(), SUM(), AVG(), MIN(), MAX() as needed
   - Use HAVING for filtering grouped results

4. **Sorting and Limiting**
   - ORDER BY for sorting (ASC/DESC)
   - LIMIT for restricting result size

5. **Date Handling**
   - Use DATE(), STRFTIME() for date manipulation
   - Handle date ranges with comparison operators

6. **Advanced Techniques**
   - Subqueries for complex filtering
   - CASE statements for conditional logic
   - NOT IN / EXISTS for exclusion queries

## EXAMPLE QUERIES AND THEIR SQL EQUIVALENTS

### Basic Queries
1. **Find all customers from New York.**
   
   SELECT * FROM customers WHERE city = 'New York';
   

2. **List all orders placed after January 1, 2024.**
   
   SELECT * FROM orders WHERE order_date > '2024-01-01';
   

3. **Get all employees who have "Manager" in their job title.**
   
   SELECT * FROM employees WHERE job_title LIKE '%Manager%';
   

### Aggregation Queries
1. **Find the total revenue generated from all transactions.**
   
   SELECT SUM(amount) AS total_revenue FROM transactions;
   

2. **Count the number of orders placed by each customer.**
   
   SELECT customer_id, COUNT(*) AS total_orders FROM orders GROUP BY customer_id;
   

3. **Find the average salary of employees in each department.**
   
   SELECT department_id, AVG(salary) AS avg_salary FROM employees GROUP BY department_id;
   

### Sorting and Filtering
1. **List the top 10 highest-paying customers.**
   
   SELECT customer_id, SUM(amount) AS total_spent 
   FROM transactions 
   GROUP BY customer_id 
   ORDER BY total_spent DESC 
   LIMIT 10;
   

2. **Find the five most expensive products.**
   
   SELECT * FROM products ORDER BY price DESC LIMIT 5;
   

### Complex Queries with JOINs
1. **Get a list of customers who have placed orders along with their total spending.**
   
   SELECT customers.name, customers.email, SUM(orders.total_price) AS total_spent 
   FROM customers 
   JOIN orders ON customers.id = orders.customer_id 
   GROUP BY customers.id 
   ORDER BY total_spent DESC;
   

2. **Find all employees and their department names.**
   
   SELECT employees.name, departments.name AS department_name 
   FROM employees 
   JOIN departments ON employees.department_id = departments.id;
   

3. **List all orders with product names and quantities.**
   
   SELECT orders.id AS order_id, products.name AS product_name, order_items.quantity 
   FROM orders 
   JOIN order_items ON orders.id = order_items.order_id 
   JOIN products ON order_items.product_id = products.id;
   

### Date-Based Queries
1. **Get the total sales revenue for March 2024.**
   
   SELECT SUM(amount) FROM transactions WHERE strftime('%Y-%m', transaction_date) = '2024-03';
  

2. **Find employees who were hired in the last 6 months.**
   
   SELECT * FROM employees WHERE hire_date >= DATE('now', '-6 months');
  

### Subqueries & Advanced Filtering
1. **Find all customers who have never placed an order.**
   
   SELECT * FROM customers WHERE id NOT IN (SELECT DISTINCT customer_id FROM orders);
   

2. **Find the product that has been sold the most.**
   
   SELECT product_id, COUNT(*) AS sales_count 
   FROM order_items 
   GROUP BY product_id 
   ORDER BY sales_count DESC 
   LIMIT 1;
   

3. **Get the employees who earn more than the company's average salary.**
   
   SELECT * FROM employees WHERE salary > (SELECT AVG(salary) FROM employees);
   

## NATURAL LANGUAGE QUERY
{natural_language_query}

## SQL QUERY
"""
    
    response = llm.invoke(prompt)
    response_text = response.content.strip()
    sql_query = response_text.split('\n')[0]
    return sql_query

def generate_natural_response(natural_language_query, sql_query, query_result, llm):
    """Generate a natural-sounding response based on the query results."""
    if not query_result:
        return f"No, there is no {natural_language_query.lower().replace('is there any', '').strip()} in the database."

    prompt = (
        "You are a serious and professional assistant. Given the following data, answer the question in a natural and brief way.\n\n"
        f"Natural Language Query: {natural_language_query}\n"
        f"SQL Query: {sql_query}\n"
        f"SQL Query Result: {query_result}\n\n"
        "Respond in a conversational and friendly manner:"
    )
    
    return llm.invoke(prompt).content.strip()

# --- StyleSheeet ---
STYLESHEET = """
QMainWindow {
    /* Blue-to-red gradient with a dark overlay effect */
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 rgba(0, 0, 139, 0.8),  /* Dark blue with 80% opacity */
                                stop:1 rgba(139, 0, 0, 0.8)); /* Dark red with 80% opacity */
}

QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #000000;  /* Use black for main text */
}

QTabWidget::pane {
    border: none;
    background: transparent;
}

QTabWidget::tab-bar {
    alignment: center;
}

QTabBar::tab {
    background: rgba(135, 206, 235, 0.5);  /* Sky blue (semi-transparent) */
    border: 1px solid rgba(135, 206, 235, 0.3);
    border-radius: 10px;
    padding: 8px 16px;
    margin: 4px;
    color: #000000;  /* Black text */
    font-weight: bold;
}

QTabBar::tab:selected {
    background: rgba(135, 206, 235, 0.25);  /* Lighter sky overlay for selected tab */
    color: #000000;
    border: 1px solid rgba(135, 206, 235, 0.5);
}

QTabBar::tab:hover {
    background: rgba(135, 206, 235, 0.2);
}

QLabel {
    color: #000000;
    font-weight: bold;
    padding: 5px;
}

QPushButton {
    background: #ffffff;  /* Sky blue */
    color: #000000;       /* Black text */
    border: none;
    border-radius: 15px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background: #fffff0;  /* Slightly darker sky blue on hover */
}

QPushButton:pressed {
    background: #6495ED;  /* Even darker blue when pressed */
}

QLineEdit {
    background: rgba(255, 255, 255, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.7);
    border-radius: 15px;
    padding: 8px 16px;
    color: #000000;
}

QTextEdit {
    background: rgba(255, 255, 255, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.7);
    border-radius: 15px;
    padding: 15px;
    color: #000000;
}

QListWidget {
    background: rgba(255, 255, 255, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.7);
    border-radius: 15px;
    padding: 15px;
    color: #000000;
}

QListWidget::item {
    padding: 5px;
    border-radius: 5px;
}

QListWidget::item:selected {
    background: rgba(135, 206, 235, 0.2);
    color: #000000;
}

QListWidget::item:hover {
    background: rgba(135, 206, 235, 0.1);
}

GlassmorphicFrame {
    background: rgba(255, 255, 255, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.7);
    border-radius: 20px;
}

QScrollBar {
    background: rgba(255, 255, 255, 0.3);
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle {
    background: rgba(135, 206, 235, 0.5);
    border-radius: 5px;
}

QScrollBar::add-line, QScrollBar::sub-line {
    height: 0px;
}
"""

class GlassmorphicFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("glassmorphicFrame")
        
        self.setAttribute(Qt.WA_TranslucentBackground)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(255, 255, 255, 165))
        gradient.setColorAt(1, QColor(255, 255, 255, 140))
        

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(self.rect(), 20, 20)
        

        painter.setPen(QColor(255, 255, 255, 100))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 20, 20)

class BackgroundWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.backgroundImage = QPixmap(resource_path("assets/bg.jpg"))
        self.setAutoFillBackground(False)  

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()

        if not self.backgroundImage.isNull():
            painter.drawPixmap(rect, self.backgroundImage)

        overlay_color = QColor(0, 0, 0, 100) 
        painter.fillRect(rect, overlay_color)


class DatabaseManagerWidget(GlassmorphicFrame):

    db_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_databases()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        self.label = QLabel("Available Databases:")
        self.label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(self.label)

        self.db_list = QListWidget()
        self.db_list.setFont(QFont("Segoe UI", 10))
        self.db_list.itemDoubleClicked.connect(self.select_database)
        layout.addWidget(self.db_list)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setMinimumHeight(40)
        self.refresh_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.refresh_btn.clicked.connect(self.load_databases)
        btn_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_databases(self):
        self.db_list.clear()
        db_files = [f for f in os.listdir(".") if f.endswith(".db")]
        if not db_files:
            self.db_list.addItem("No databases found.")
        else:
            for db in db_files:
                self.db_list.addItem(db)

    def select_database(self, item):
        db_name = item.text()
        if not db_name.endswith(".db"):
            return
        QMessageBox.information(self, "Database Selected", f"Selected database: {db_name}")
        self.db_selected.emit(db_name)

class ChatWidget(GlassmorphicFrame):
    def __init__(self):
        super().__init__()
        self.db_path = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        self.info_label = QLabel("No database selected. Please select a database from the Database Manager tab.")
        self.info_label.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self.info_label)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.chat_display)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter your natural language query here...")
        self.input_field.setMinimumHeight(40)
        self.input_field.setFont(QFont("Segoe UI", 10))
        input_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumHeight(40)
        self.send_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.send_btn.clicked.connect(self.handle_query)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)
        self.setLayout(layout)

    def set_database(self, db_path):
        self.db_path = db_path
        self.info_label.setText(f"Using database: {db_path}")

    def handle_query(self):
        if not self.db_path:
            QMessageBox.warning(self, "No Database", "Please select a database before sending queries.")
            return

        user_query = self.input_field.text().strip()
        if not user_query:
            return

        self.chat_display.append(f"<b>User:</b> {user_query}")
        self.input_field.clear()

        try:

            schema = get_db_schema(self.db_path)
            
            sql_query = generate_sql_query(user_query, schema, llm)
            self.chat_display.append(f"<b>Generated SQL:</b> <span style='color:#5c6ac4;'>{sql_query}</span>")
            
            result = query_database(sql_query, self.db_path)
            
            natural_response = generate_natural_response(user_query, sql_query, result, llm)
            self.chat_display.append(f"<b>Assistant:</b> <span style='color:#3f3d56;'>{natural_response}</span><br>")
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            self.chat_display.append(f"<b>Error:</b> <span style='color:#e74c3c;'>{error_msg}</span><br>")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task 1")
        self.resize(900, 700)
        self.init_ui()
        
        self.setStyleSheet(STYLESHEET)

    def init_ui(self):
        self.central_container = BackgroundWidget()
        self.setCentralWidget(self.central_container)
        
        main_layout = QVBoxLayout(self.central_container)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        title_label = QLabel("Farrukh's Task 1")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #FFFFFF;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        main_layout.addWidget(self.tabs)

        self.db_manager = DatabaseManagerWidget()
        self.db_manager.db_selected.connect(self.on_db_selected)
        self.tabs.addTab(self.db_manager, "Database Manager")

        self.chat_widget = ChatWidget()
        self.tabs.addTab(self.chat_widget, "Chat")

    def on_db_selected(self, db_path):
        self.chat_widget.set_database(db_path)
        self.tabs.setCurrentWidget(self.chat_widget)

if __name__ == "__main__":

    app = QApplication(sys.argv)
    
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())