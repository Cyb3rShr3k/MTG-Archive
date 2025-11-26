"""Application entry point - Flask web server."""
import os
from flask import Flask, send_from_directory, jsonify, request, session
from werkzeug.utils import secure_filename
from backend import Api
from core.user_auth import UserAuth

app = Flask(__name__, static_folder='web', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())  # For sessions
api = Api()
user_auth = UserAuth()

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Authentication routes
@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    result = user_auth.register_user(username, email, password)
    return jsonify(result)

@app.route('/api/login', methods=['POST'])
def login():
    """Login a user."""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    result = user_auth.login_user(username, password)
    if result.get('success'):
        # Store session token in Flask session
        session['session_token'] = result['session_token']
        session['user_id'] = result['user_id']
        session['username'] = result['username']
    
    return jsonify(result)

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout current user."""
    session_token = session.get('session_token')
    if session_token:
        user_auth.logout_user(session_token)
    session.clear()
    return jsonify({'success': True})

@app.route('/api/current_user', methods=['GET'])
def current_user():
    """Get current logged-in user info."""
    session_token = session.get('session_token')
    if not session_token:
        return jsonify({'logged_in': False})
    
    user_id = user_auth.verify_session(session_token)
    if not user_id:
        session.clear()
        return jsonify({'logged_in': False})
    
    user_info = user_auth.get_user_info(user_id)
    return jsonify({'logged_in': True, 'user': user_info})

# Serve static HTML files
@app.route('/')
def index():
    return send_from_directory('web', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('web', path)

# File upload endpoint for CSV imports
@app.route('/api/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV file uploads."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and file.filename.endswith('.csv'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Call the import function with the file path
        try:
            result = api.run_importscryfall(filepath)
            return jsonify(result)
        finally:
            # Clean up uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return jsonify({'error': 'Invalid file type'}), 400

# API routes - convert all Api methods to Flask endpoints
@app.route('/api/<method_name>', methods=['GET', 'POST'])
def api_proxy(method_name):
    """Proxy API calls to the Api class methods."""
    # Check if user is logged in for protected endpoints
    session_token = session.get('session_token')
    user_id = None
    
    if session_token:
        user_id = user_auth.verify_session(session_token)
        if not user_id:
            session.clear()
    
    # Allow some methods without authentication (for backward compatibility)
    public_methods = ['get_card_names', 'search_cards', 'list_precon_decks', 
                      'get_decklist_deck_cards', 'search_decklist_db']
    
    if not user_id and method_name not in public_methods:
        # For now, default to user_id=1 for single-user compatibility
        user_id = 1
    
    if not hasattr(api, method_name):
        return jsonify({'error': 'Method not found'}), 404
    
    method = getattr(api, method_name)
    
    # Get parameters from JSON body or query params
    if request.method == 'POST':
        params = request.get_json() or {}
    else:
        params = request.args.to_dict()
    
    # Inject user_id into params for methods that need it
    if user_id:
        api._current_user_id = user_id
    
    try:
        # Call the method with parameters
        if params:
            result = method(**params)
        else:
            result = method()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)