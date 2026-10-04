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
    return jsonify({"status": "success", "message": "Login attempt tracked"})

@api_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    return jsonify({"status": "success", "message": "Contact form tracked"})

@api_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    return jsonify({"status": "success", "message": "Cart add tracked"})
