# core/user_auth.py
"""User authentication and session management for multi-user support."""
import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
"""

class UserAuth:
    def __init__(self, db_path: str = 'users.db'):
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize the user database with schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(USER_SCHEMA)
            conn.execute("PRAGMA journal_mode=WAL")
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt."""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}${pwd_hash}"
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, pwd_hash = stored_hash.split('$')
            test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return test_hash == pwd_hash
        except:
            return False
    
    def register_user(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Register a new user."""
        if len(password) < 6:
            return {'success': False, 'error': 'Password must be at least 6 characters'}
        
        if len(username) < 3:
            return {'success': False, 'error': 'Username must be at least 3 characters'}
        
        pwd_hash = self._hash_password(password)
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username.lower(), email.lower(), pwd_hash)
                )
                conn.commit()
                return {'success': True, 'message': 'User registered successfully'}
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                return {'success': False, 'error': 'Username already exists'}
            elif 'email' in str(e):
                return {'success': False, 'error': 'Email already exists'}
            return {'success': False, 'error': 'Registration failed'}
    
    def login_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate a user and create a session."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username.lower(),)
            )
            user = cursor.fetchone()
            
            if not user or not self._verify_password(password, user['password_hash']):
                return {'success': False, 'error': 'Invalid username or password'}
            
            # Create session token
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(days=7)  # 7-day session
            
            cursor.execute(
                "INSERT INTO sessions (user_id, session_token, expires_at) VALUES (?, ?, ?)",
                (user['id'], session_token, expires_at)
            )
            
            # Update last login
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user['id'],)
            )
            
            conn.commit()
            
            return {
                'success': True,
                'session_token': session_token,
                'user_id': user['id'],
                'username': user['username']
            }
    
    def verify_session(self, session_token: str) -> Optional[int]:
        """Verify a session token and return user_id if valid."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT user_id FROM sessions 
                   WHERE session_token = ? AND expires_at > CURRENT_TIMESTAMP""",
                (session_token,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    
    def logout_user(self, session_token: str) -> bool:
        """Invalidate a session token."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))
            conn.commit()
            return cursor.rowcount > 0
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions from the database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP")
            conn.commit()
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user information by ID."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, created_at, last_login FROM users WHERE id = ?",
                (user_id,)
            )
            user = cursor.fetchone()
            return dict(user) if user else None
