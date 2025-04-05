# init_db.py
import sqlite3
import os

DATABASE = 'database.db'

# Define categories (name, slug, type ['goods' or 'services'])
categories_data = [
    ('All Products & Services', 'all', 'meta'), # Special category for filter logic
    ('Goods', 'goods', 'meta'),               # Broad category
    ('Services', 'services', 'meta'),         # Broad category
    ('iPhone', 'iphone', 'goods'),
    ('MacBook', 'macbook', 'goods'),
    ('iPad', 'ipad', 'goods'),
    ('Apple Watch', 'watch', 'goods'),
    ('Apple Music', 'music', 'services'),
    ('iCloud+', 'icloud', 'services'),
    ('Apple TV+', 'tv', 'services'),
    ('Apple Arcade', 'arcade', 'services')
]

# Define products (name, price, image_url, category_slug)
# Note: image_url should now point to the path within the static folder
products_data = [
    ('iPhone 15 Pro', 'From $999', '/static/images/product1.jpg', 'iphone'),
    ('MacBook Air M3', 'From $1099', '/static/images/product2.jpg', 'macbook'),
    ('iPad Pro', 'From $799', '/static/images/product3.jpg', 'ipad'),
    ('Apple Watch Series 9', 'From $399', '/static/images/product4.jpg', 'watch'),
    ('Apple Music', '$10.99/month', '/static/images/service1.png', 'music'),
    ('iCloud+', 'From $0.99/month', '/static/images/service2.png', 'icloud'),
    ('Apple TV+', '$9.99/month', '/static/images/service3.png', 'tv'),
    ('Apple Arcade', '$6.99/month', '/static/images/service4.png', 'arcade'),
    ('iPhone 15', 'From $799', '/static/images/product1.jpg', 'iphone'), # Placeholder image
    ('MacBook Pro M3', 'From $1599', '/static/images/product2.jpg', 'macbook'), # Placeholder image
    ('Apple Watch Ultra 2', 'From $799', '/static/images/product4.jpg', 'watch'), # Placeholder image
    ('iPad Air', 'From $599', '/static/images/product3.jpg', 'ipad'), # Placeholder image
    # Add 8 more varied products to test pagination easily
    ('MacBook Pro 16"', 'From $2499', '/static/images/product2.jpg', 'macbook'),
    ('iPad Mini', 'From $499', '/static/images/product3.jpg', 'ipad'),
    ('iPhone SE', 'From $429', '/static/images/product1.jpg', 'iphone'),
    ('Apple Watch SE', 'From $249', '/static/images/product4.jpg', 'watch'),
    ('HomePod', '$299', '/static/images/placeholder.jpg', 'goods'), # Assuming a general 'goods' category exists or add one
    ('AirPods Pro', '$249', '/static/images/placeholder.jpg', 'goods'),
    ('Apple Pencil', 'From $99', '/static/images/placeholder.jpg', 'goods'),
    ('Magic Keyboard', 'From $299', '/static/images/placeholder.jpg', 'goods'),
]

def init_db():
    """Initializes the database."""
    if os.path.exists(DATABASE):
        print(f"Removing existing database: {DATABASE}")
        os.remove(DATABASE)

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    print("Creating tables...")

    # --- Create Categories Table ---
    cursor.execute('''
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK(type IN ('goods', 'services', 'meta'))
        );
    ''')

    # --- Create Products Table ---
    cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price TEXT NOT NULL,         -- Storing as TEXT for flexibility (e.g., "From $X", "$Y/month")
            image_url TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories (id)
                ON DELETE RESTRICT -- Prevent deleting category if products exist
                ON UPDATE CASCADE
        );
    ''')
    print("Tables created.")

    # --- Populate Categories ---
    print("Populating categories...")
    try:
        cursor.executemany('INSERT INTO categories (name, slug, type) VALUES (?, ?, ?)', categories_data)
        print(f"{cursor.rowcount} categories inserted.")
    except sqlite3.Error as e:
        print(f"Error inserting categories: {e}")


    # --- Populate Products ---
    print("Populating products...")
    # Need category IDs first
    category_map = {slug: id for id, name, slug, type in cursor.execute('SELECT id, name, slug, type FROM categories').fetchall()}

    products_to_insert = []
    for name, price, img, cat_slug in products_data:
        if cat_slug in category_map:
            products_to_insert.append((name, price, img, category_map[cat_slug]))
        else:
             # Fallback or add a default category like 'uncategorized'/'goods' if needed
             # For now, we skip if slug doesn't match exactly
             print(f"Warning: Category slug '{cat_slug}' not found for product '{name}'. Skipping.")
             # Example fallback: use general 'goods' if available
             # if 'goods' in category_map:
             #    products_to_insert.append((name, price, img, category_map['goods']))


    if products_to_insert:
        try:
            cursor.executemany('''
                INSERT INTO products (name, price, image_url, category_id)
                VALUES (?, ?, ?, ?)
            ''', products_to_insert)
            print(f"{cursor.rowcount} products inserted.")
        except sqlite3.Error as e:
            print(f"Error inserting products: {e}")

    # Commit changes and close connection
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()
