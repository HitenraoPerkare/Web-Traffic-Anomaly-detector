from flask import Blueprint, jsonify, request

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/home', methods=['GET'])
def home():
    return jsonify({"status": "success", "message": "Home page visit tracked"})

@api_bp.route('/products', methods=['GET'])
def products():
    return jsonify({"status": "success", "message": "Products page visit tracked"})

@api_bp.route('/search', methods=['GET'])
def search():
    # We still accept query args here so middleware can extract them for the anomaly engine
    return jsonify({"status": "success", "message": "Search tracked"})

@api_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return jsonify({"status": "success", "message": "Login page visit tracked"})

    # Extract credentials from JSON or Form body
    data = request.get_json(silent=True) or request.form or {}
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', '')).strip()

    # 1. Admin login credentials
    if username == "admin" and password == "admin123":
        return jsonify({
            "status": "success",
            "role": "admin",
            "username": "admin",
            "redirect": "admin.html",
            "message": "Admin login successful! Redirecting to SecOps Dashboard..."
        }), 200

    # 2. User login credentials
    if username == "user@try" and password == "user123":
        return jsonify({
            "status": "success",
            "role": "user",
            "username": "user@try",
            "redirect": "index.html",
            "message": "User login successful! Redirecting to Storefront..."
        }), 200

    # 3. Invalid credentials
    return jsonify({
        "status": "error",
        "message": "Invalid username or password"
    }), 401

@api_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    return jsonify({"status": "success", "message": "Contact form tracked"})

@api_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    return jsonify({"status": "success", "message": "Cart add tracked"})
