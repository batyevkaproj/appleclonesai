# app.py
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g, flash, abort

DATABASE = 'database.db'

app = Flask(__name__)
# Secret key needed for flashing messages
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/' # Change this to a random secret key

# --- Database Helper Functions ---
def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        # Return rows as dictionary-like objects
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    """Queries the database and returns results."""
    try:
        cur = get_db().execute(query, args)
        rv = cur.fetchall()
        cur.close()
        # Return None if no rows found, or the single row if 'one' is True
        return (rv[0] if rv else None) if one else rv
    except sqlite3.Error as e:
        print(f"Database query error: {e}")
        print(f"Query: {query}")
        print(f"Args: {args}")
        flash(f"Database error: {e}", "error") # Show error to admin user maybe
        return None # Or handle differently


# --- Routes ---

@app.route('/')
def index():
    # If you have a separate index.html, render it here
    # return render_template('index.html')
    # For now, redirect to the shop page
    return redirect(url_for('shop_page'))

@app.route('/shop')
def shop_page():
    """Renders the main shop page, fetching data from DB."""
    # Fetch products with their category info
    products = query_db('''
        SELECT p.id, p.name, p.price, p.image_url, c.name as category_name, c.slug as category_slug, c.type as category_type
        FROM products p
        JOIN categories c ON p.category_id = c.id
        ORDER BY p.name
    ''')

    # Fetch categories for the filter list (exclude meta-categories for direct filtering)
    categories = query_db("SELECT id, name, slug, type FROM categories WHERE type != 'meta' ORDER BY name")

    # Fetch meta categories separately if needed for the UI (like 'All', 'Goods', 'Services')
    meta_categories = query_db("SELECT id, name, slug, type FROM categories WHERE type = 'meta' ORDER BY name")


    if products is None or categories is None or meta_categories is None:
        # Handle database query errors (e.g., show an error page)
        # query_db already flashes an error for admin, but maybe show generic user error
         flash("Could not load shop data. Please try again later.", "error")
         products = []
         categories = []
         meta_categories = []


    return render_template('shop.html',
                           products=products,
                           categories=categories,
                           meta_categories=meta_categories)


# --- Admin Routes (Simple CRUD) ---

@app.route('/admin')
def admin_page():
    """Shows the admin dashboard to manage categories and products."""
    categories = query_db("SELECT id, name, slug, type FROM categories ORDER BY type, name")
    products = query_db('''
        SELECT p.id, p.name, p.price, p.image_url, c.name as category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        ORDER BY c.name, p.name
    ''')

    if categories is None or products is None:
         flash("Could not load admin data.", "error")
         categories = []
         products = []

    return render_template('admin.html', categories=categories, products=products)

# -- Categories CRUD --

@app.route('/admin/categories/add', methods=['POST'])
def add_category():
    name = request.form.get('name')
    slug = request.form.get('slug')
    cat_type = request.form.get('type')

    if not name or not slug or not cat_type:
        flash("Missing required category fields.", "error")
        return redirect(url_for('admin_page'))

    if cat_type not in ['goods', 'services', 'meta']:
         flash("Invalid category type.", "error")
         return redirect(url_for('admin_page'))

    try:
        db = get_db()
        db.execute('INSERT INTO categories (name, slug, type) VALUES (?, ?, ?)', (name, slug, cat_type))
        db.commit()
        flash(f"Category '{name}' added successfully.", "success")
    except sqlite3.IntegrityError:
        flash(f"Category name or slug ('{name}' / '{slug}') already exists.", "error")
    except sqlite3.Error as e:
        flash(f"Database error adding category: {e}", "error")

    return redirect(url_for('admin_page'))

@app.route('/admin/categories/delete/<int:cat_id>', methods=['POST']) # Use POST for actions
def delete_category(cat_id):
     # Check if category has products associated
    products_in_category = query_db('SELECT 1 FROM products WHERE category_id = ?', [cat_id], one=True)

    if products_in_category:
        flash("Cannot delete category: it still contains products.", "error")
        return redirect(url_for('admin_page'))

    try:
        db = get_db()
        # Fetch name before deleting for the flash message
        cat_name_row = query_db('SELECT name FROM categories WHERE id = ?', [cat_id], one=True)
        cat_name = cat_name_row['name'] if cat_name_row else f"ID {cat_id}"

        cursor = db.execute('DELETE FROM categories WHERE id = ?', [cat_id])
        db.commit()
        if cursor.rowcount > 0:
             flash(f"Category '{cat_name}' deleted successfully.", "success")
        else:
             flash(f"Category with ID {cat_id} not found.", "warning")

    except sqlite3.Error as e:
        flash(f"Database error deleting category: {e}", "error")

    return redirect(url_for('admin_page'))

# -- Products CRUD --

@app.route('/admin/products/add', methods=['POST'])
def add_product():
    name = request.form.get('name')
    price = request.form.get('price')
    image_url = request.form.get('image_url') # Consider file upload for real app
    category_id = request.form.get('category_id', type=int)

    if not name or not price or not image_url or category_id is None:
         flash("Missing required product fields.", "error")
         return redirect(url_for('admin_page'))

     # Basic validation for image_url format
    if not image_url.startswith('/static/images/'):
         flash("Image URL must start with /static/images/", "error")
         # You might want more robust validation or a file upload mechanism here
         return redirect(url_for('admin_page'))


    try:
        db = get_db()
        db.execute('INSERT INTO products (name, price, image_url, category_id) VALUES (?, ?, ?, ?)',
                   (name, price, image_url, category_id))
        db.commit()
        flash(f"Product '{name}' added successfully.", "success")
    except sqlite3.Error as e:
        flash(f"Database error adding product: {e}", "error")

    return redirect(url_for('admin_page'))

@app.route('/admin/products/delete/<int:prod_id>', methods=['POST']) # Use POST
def delete_product(prod_id):
    try:
        db = get_db()
        # Fetch name before deleting for the flash message
        prod_name_row = query_db('SELECT name FROM products WHERE id = ?', [prod_id], one=True)
        prod_name = prod_name_row['name'] if prod_name_row else f"ID {prod_id}"

        cursor = db.execute('DELETE FROM products WHERE id = ?', [prod_id])
        db.commit()

        if cursor.rowcount > 0:
            flash(f"Product '{prod_name}' deleted successfully.", "success")
        else:
            flash(f"Product with ID {prod_id} not found.", "warning")

    except sqlite3.Error as e:
        flash(f"Database error deleting product: {e}", "error")

    return redirect(url_for('admin_page'))


# --- Run the App ---
if __name__ == '__main__':
    # Use debug=True only for development!
    # host='0.0.0.0' makes it accessible on your network
    print("Starting Flask app...")
    print("Access Shop at: http://127.0.0.1:5000/shop (or your server IP)")
    print("Access Admin at: http://127.0.0.1:5000/admin")
    app.run(debug=True, host='0.0.0.0', port=5000) # Use port 5000 commonly for Flask
