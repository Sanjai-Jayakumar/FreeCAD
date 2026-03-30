"""
BNC CAD GUI Initialization
Sets up macro shortcuts and custom configurations
"""

import FreeCAD
import FreeCADGui
import os
import sys
import json
import urllib.request
import urllib.error
import ssl
import uuid
import platform

# ============================================
# BNC CAD Subscription Authentication System
# ============================================

# Auth server configuration (localhost for testing)
AUTH_SERVER_URL = os.getenv('BNC_AUTH_SERVER', 'http://localhost:5000')
TOKEN_FILE = os.path.join(os.path.expanduser('~'), '.bnc_cad_auth.json')

def _get_machine_id():
    """Generate a unique machine identifier"""
    try:
        node = uuid.getnode()
        machine = platform.machine()
        system = platform.system()
        return f"{node}-{system}-{machine}"
    except:
        return "unknown"

def _load_saved_token():
    """Load saved authentication token"""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                data = json.load(f)
                return data.get('access_token'), data.get('refresh_token')
    except:
        pass
    return None, None

def _save_token(access_token, refresh_token, user_info=None):
    """Save authentication token for future sessions"""
    try:
        data = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user_info
        }
        with open(TOKEN_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"Could not save auth token: {e}\n")

def _clear_saved_token():
    """Clear saved token on auth failure"""
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
    except:
        pass

def _api_request(endpoint, data=None, method='POST'):
    """Make API request to auth server"""
    url = f"{AUTH_SERVER_URL}{endpoint}"
    
    try:
        if data:
            data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        
        # Allow insecure for localhost testing
        ctx = ssl.create_default_context()
        if 'localhost' in url or '127.0.0.1' in url:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
            return json.loads(response.read().decode('utf-8')), response.status
    except urllib.error.HTTPError as e:
        try:
            error_body = json.loads(e.read().decode('utf-8'))
            return error_body, e.code
        except:
            return {'error': str(e)}, e.code
    except urllib.error.URLError as e:
        return {'error': f'Cannot connect to server: {e.reason}'}, 0
    except Exception as e:
        return {'error': str(e)}, 0

def _validate_subscription(access_token):
    """Check if user has valid subscription"""
    machine_id = _get_machine_id()
    result, status = _api_request('/api/license/validate', {
        'access_token': access_token,
        'machine_id': machine_id
    })
    
    if status == 200 and result.get('valid'):
        return True, result
    return False, result

def _bnc_authenticate():
    """Show login dialog and validate subscription"""
    try:
        from PySide2 import QtWidgets, QtCore, QtGui
    except ImportError:
        try:
            from PySide import QtWidgets, QtCore, QtGui
        except ImportError:
            FreeCAD.Console.PrintError("PySide not available for authentication\n")
            return False
    
    # First try saved token
    access_token, refresh_token = _load_saved_token()
    if access_token:
        valid, result = _validate_subscription(access_token)
        if valid:
            user = result.get('user', {})
            FreeCAD.Console.PrintMessage(f"✓ Welcome back, {user.get('name', user.get('email', 'User'))}!\n")
            return True
        else:
            _clear_saved_token()
    
    class SubscriptionLoginDialog(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super(SubscriptionLoginDialog, self).__init__(parent)
            self.setWindowTitle("BNC CAD - Sign In")
            self.setFixedSize(420, 380)
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
            self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
            
            # Modern styling
            self.setStyleSheet("""
                QDialog {
                    background-color: #1a1a2e;
                }
                QLabel {
                    color: #ffffff;
                }
                QLineEdit {
                    background-color: rgba(255,255,255,0.1);
                    border: 1px solid rgba(255,255,255,0.2);
                    border-radius: 8px;
                    padding: 12px;
                    color: white;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border-color: #667eea;
                }
                QPushButton#loginBtn {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #667eea, stop:1 #764ba2);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 14px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton#loginBtn:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #764ba2, stop:1 #667eea);
                }
                QPushButton#loginBtn:disabled {
                    background: #555;
                }
                QPushButton#exitBtn {
                    background-color: transparent;
                    color: #aaaaaa;
                    border: 1px solid #555;
                    border-radius: 8px;
                    padding: 14px;
                    font-size: 14px;
                }
                QPushButton#exitBtn:hover {
                    background-color: rgba(255,255,255,0.1);
                }
                QPushButton#registerBtn {
                    background-color: transparent;
                    color: #667eea;
                    border: none;
                    font-size: 13px;
                    text-decoration: underline;
                }
                QPushButton#registerBtn:hover {
                    color: #764ba2;
                }
            """)
            
            # Center on screen
            screen = QtWidgets.QApplication.primaryScreen().geometry()
            self.move((screen.width() - self.width()) // 2, 
                     (screen.height() - self.height()) // 2)
            
            layout = QtWidgets.QVBoxLayout(self)
            layout.setSpacing(12)
            layout.setContentsMargins(35, 35, 35, 35)
            
            # Logo/Title
            title = QtWidgets.QLabel("BNC CAD")
            title.setStyleSheet("font-size: 28px; font-weight: bold; color: white;")
            title.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(title)
            
            subtitle = QtWidgets.QLabel("Sign in with your subscription")
            subtitle.setStyleSheet("font-size: 14px; color: #888;")
            subtitle.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(subtitle)
            
            layout.addSpacing(15)
            
            # Email
            email_label = QtWidgets.QLabel("Email")
            email_label.setStyleSheet("font-size: 12px; color: #aaa;")
            layout.addWidget(email_label)
            self.email_input = QtWidgets.QLineEdit()
            self.email_input.setPlaceholderText("your@email.com")
            layout.addWidget(self.email_input)
            
            # Password
            pass_label = QtWidgets.QLabel("Password")
            pass_label.setStyleSheet("font-size: 12px; color: #aaa;")
            layout.addWidget(pass_label)
            self.pass_input = QtWidgets.QLineEdit()
            self.pass_input.setEchoMode(QtWidgets.QLineEdit.Password)
            self.pass_input.setPlaceholderText("Enter password")
            self.pass_input.returnPressed.connect(self.do_login)
            layout.addWidget(self.pass_input)
            
            # Error/Status message
            self.status_label = QtWidgets.QLabel("")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            self.status_label.setAlignment(QtCore.Qt.AlignCenter)
            self.status_label.setWordWrap(True)
            layout.addWidget(self.status_label)
            
            # Buttons
            btn_layout = QtWidgets.QHBoxLayout()
            btn_layout.setSpacing(10)
            
            self.exit_btn = QtWidgets.QPushButton("Exit")
            self.exit_btn.setObjectName("exitBtn")
            self.exit_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.exit_btn.clicked.connect(self.reject)
            
            self.login_btn = QtWidgets.QPushButton("Sign In")
            self.login_btn.setObjectName("loginBtn")
            self.login_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.login_btn.clicked.connect(self.do_login)
            
            btn_layout.addWidget(self.exit_btn)
            btn_layout.addWidget(self.login_btn)
            layout.addLayout(btn_layout)
            
            layout.addSpacing(10)
            
            # Register link
            register_layout = QtWidgets.QHBoxLayout()
            no_account = QtWidgets.QLabel("Don't have a subscription?")
            no_account.setStyleSheet("font-size: 12px; color: #888;")
            register_btn = QtWidgets.QPushButton("Subscribe Now")
            register_btn.setObjectName("registerBtn")
            register_btn.setCursor(QtCore.Qt.PointingHandCursor)
            register_btn.clicked.connect(self.open_subscribe)
            register_layout.addStretch()
            register_layout.addWidget(no_account)
            register_layout.addWidget(register_btn)
            register_layout.addStretch()
            layout.addLayout(register_layout)
            
            self.authenticated = False
            self.user_info = None
        
        def do_login(self):
            email = self.email_input.text().strip()
            password = self.pass_input.text()
            
            if not email or not password:
                self.status_label.setText("Please enter email and password")
                self.status_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
                return
            
            # Disable button during login
            self.login_btn.setEnabled(False)
            self.login_btn.setText("Signing in...")
            self.status_label.setText("")
            QtWidgets.QApplication.processEvents()
            
            machine_id = _get_machine_id()
            
            # Login to get tokens
            result, status = _api_request('/api/auth/login', {
                'email': email,
                'password': password,
                'machine_id': machine_id
            })
            
            if status == 200:
                access_token = result.get('access_token')
                refresh_token = result.get('refresh_token')
                user = result.get('user', {})
                
                # Check subscription status
                sub_status = user.get('subscription_status', 'none')
                
                if sub_status == 'active':
                    # Validate license
                    valid, validate_result = _validate_subscription(access_token)
                    
                    if valid:
                        _save_token(access_token, refresh_token, user)
                        self.authenticated = True
                        self.user_info = user
                        self.accept()
                    else:
                        error = validate_result.get('error', 'License validation failed')
                        self.status_label.setText(error)
                        self.status_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
                else:
                    self.status_label.setText("No active subscription. Please subscribe to continue.")
                    self.status_label.setStyleSheet("color: #ffa500; font-size: 12px;")
            elif status == 0:
                # Server not reachable
                self.status_label.setText("Cannot connect to authentication server.\nPlease check your internet connection.")
                self.status_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            else:
                error = result.get('error', 'Login failed')
                self.status_label.setText(error)
                self.status_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Sign In")
        
        def open_subscribe(self):
            """Open subscription page in browser"""
            import webbrowser
            webbrowser.open(f"{AUTH_SERVER_URL}/subscribe")
        
        def closeEvent(self, event):
            if not self.authenticated:
                event.ignore()
    
    # Show login dialog
    try:
        app = QtWidgets.QApplication.instance()
        dialog = SubscriptionLoginDialog()
        result = dialog.exec_()
        
        if not dialog.authenticated:
            FreeCAD.Console.PrintError("Authentication required. Closing BNC CAD.\n")
            try:
                FreeCADGui.getMainWindow().close()
            except:
                pass
            sys.exit(1)
        
        user = dialog.user_info or {}
        FreeCAD.Console.PrintMessage(f"✓ Welcome, {user.get('name', user.get('email', 'User'))}!\n")
        return True
    except Exception as e:
        FreeCAD.Console.PrintError(f"Authentication error: {e}\n")
        sys.exit(1)

# Run authentication on startup
try:
    _bnc_authenticate()
except Exception as e:
    FreeCAD.Console.PrintError(f"Authentication system error: {e}\n")

# ============================================
# Normal Initialization continues below
# ============================================

# Add parent Mod directory to path
mod_path = os.path.dirname(os.path.dirname(__file__))
if mod_path not in sys.path:
    sys.path.append(mod_path)

# Import and run macro setup
try:
    import BNC_MacroSetup
    FreeCAD.Console.PrintMessage("✓ BNC CAD initialized successfully\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD initialization error: {e}\n")
