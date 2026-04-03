# SPDX-License-Identifier: LGPL-2.1-or-later
# BNC CAD — Google Sign-In Dialog
# Shows a login screen on first launch, similar to Claude Desktop app.
# Users authenticate with their Google account via OAuth 2.0.

import os
import sys
import json
import hashlib
import secrets
import base64
import webbrowser
import http.server
import threading
import urllib.parse

import FreeCAD

try:
    from PySide import QtCore, QtGui
    QtWidgets = QtGui
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets


# ─── Token Storage ────────────────────────────────────────────────────────────
_TOKEN_FILE = os.path.join(FreeCAD.getUserAppDataDir(), "bnc_auth.json")


def _load_session():
    """Load saved auth session from disk."""
    if not os.path.isfile(_TOKEN_FILE):
        return None
    try:
        with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("email") and data.get("name"):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_session(data):
    """Persist auth session to disk."""
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_logged_in():
    """Return True if a valid BNC session exists."""
    return _load_session() is not None


def get_user_info():
    """Return saved user info dict or None."""
    return _load_session()


def logout():
    """Remove saved session."""
    if os.path.isfile(_TOKEN_FILE):
        os.remove(_TOKEN_FILE)


# ─── OAuth Config ─────────────────────────────────────────────────────────────
# Replace these with your real Google OAuth 2.0 credentials.
# Create them at https://console.cloud.google.com/apis/credentials
_OAUTH_CONFIG_FILE = os.path.join(FreeCAD.getUserAppDataDir(), "bnc_oauth.json")

# Default placeholder values — users/admins drop their own bnc_oauth.json
_DEFAULT_CLIENT_ID = "YOUR_CLIENT_ID.apps.googleusercontent.com"
_DEFAULT_CLIENT_SECRET = "YOUR_CLIENT_SECRET"


def _oauth_config():
    """Load OAuth client id/secret from config file or fall back to defaults."""
    if os.path.isfile(_OAUTH_CONFIG_FILE):
        try:
            with open(_OAUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("client_id", _DEFAULT_CLIENT_ID), cfg.get("client_secret", _DEFAULT_CLIENT_SECRET)
        except (json.JSONDecodeError, OSError):
            pass
    return _DEFAULT_CLIENT_ID, _DEFAULT_CLIENT_SECRET


# ─── PKCE + OAuth Flow ───────────────────────────────────────────────────────
_REDIRECT_PORT = 8491
_REDIRECT_URI = f"http://localhost:{_REDIRECT_PORT}/callback"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Tiny HTTP handler that captures the OAuth redirect."""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        self.server.auth_code = code

        # Respond with a simple success page
        html = (
            "<html><body style='font-family:Segoe UI,sans-serif;text-align:center;"
            "padding:60px;background:#f8f9fa'>"
            "<h2 style='color:#1a73e8'>&#10004; Signed in to BNC CAD</h2>"
            "<p>You can close this tab and return to BNC CAD.</p>"
            "</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass  # Suppress console output


def _exchange_code(code, verifier):
    """Exchange authorization code for tokens and fetch user info."""
    client_id, client_secret = _oauth_config()

    # Use urllib (stdlib) to avoid requiring `requests`
    import urllib.request

    # 1. Exchange code → tokens
    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": _REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }).encode()

    req = urllib.request.Request(_TOKEN_URL, data=token_data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=15) as resp:
        tokens = json.loads(resp.read())

    access_token = tokens.get("access_token")
    if not access_token:
        return None

    # 2. Fetch user profile
    profile_req = urllib.request.Request(_USERINFO_URL)
    profile_req.add_header("Authorization", f"Bearer {access_token}")
    with urllib.request.urlopen(profile_req, timeout=15) as resp:
        profile = json.loads(resp.read())

    return {
        "email": profile.get("email", ""),
        "name": profile.get("name", ""),
        "picture": profile.get("picture", ""),
    }


# ─── Google Sign-In Button SVG ───────────────────────────────────────────────
_GOOGLE_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 48 48">
  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
</svg>"""


# ─── Login Dialog ─────────────────────────────────────────────────────────────
class BNCLoginDialog(QtWidgets.QDialog):
    """
    A modern Google Sign-In dialog for BNC CAD.
    Styled similarly to the Claude Desktop login screen.
    """

    login_successful = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sign in to BNC CAD")
        self.setFixedSize(460, 560)
        self.setWindowFlags(
            QtCore.Qt.Dialog
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.CustomizeWindowHint
        )

        self._build_ui()
        self._apply_styles()

    # ── UI Construction ──────────────────────────────────────────────────
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        # Top spacer
        layout.addSpacing(20)

        # ── Logo / Brand area ──
        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(QtCore.Qt.AlignCenter)
        logo_label.setText(
            '<span style="font-size:42px; font-weight:700; color:#1a1a2e;">'
            'BNC&nbsp;<span style="color:#1a73e8;">CAD</span></span>'
        )
        layout.addWidget(logo_label)

        layout.addSpacing(8)

        version_label = QtWidgets.QLabel("Version 1.1")
        version_label.setAlignment(QtCore.Qt.AlignCenter)
        version_label.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(version_label)

        layout.addSpacing(40)

        # ── Welcome text ──
        welcome = QtWidgets.QLabel("Welcome back")
        welcome.setAlignment(QtCore.Qt.AlignCenter)
        welcome.setStyleSheet("font-size: 22px; font-weight: 600; color: #1a1a2e;")
        layout.addWidget(welcome)

        layout.addSpacing(8)

        subtitle = QtWidgets.QLabel("Sign in to your BNC account to continue")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #666;")
        layout.addWidget(subtitle)

        layout.addSpacing(36)

        # ── Google Sign-In button ──
        self._google_btn = QtWidgets.QPushButton("  Sign in with Google")
        self._google_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._google_btn.setMinimumHeight(48)
        self._google_btn.setObjectName("googleBtn")

        # Google "G" icon
        svg_bytes = QtCore.QByteArray(_GOOGLE_ICON_SVG.encode())
        svg_pixmap = QtGui.QPixmap()
        svg_pixmap.loadFromData(svg_bytes, "SVG")
        if not svg_pixmap.isNull():
            self._google_btn.setIcon(QtGui.QIcon(svg_pixmap))
            self._google_btn.setIconSize(QtCore.QSize(20, 20))

        self._google_btn.clicked.connect(self._on_google_signin)
        layout.addWidget(self._google_btn)

        layout.addSpacing(16)

        # ── Status label (spinner / errors) ──
        self._status = QtWidgets.QLabel("")
        self._status.setAlignment(QtCore.Qt.AlignCenter)
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size: 12px; color: #d32f2f;")
        layout.addWidget(self._status)

        layout.addStretch()

        # ── Footer ──
        footer = QtWidgets.QLabel(
            '<span style="color:#aaa; font-size:11px;">'
            'By signing in, you agree to the BNC CAD Terms of Service'
            '</span>'
        )
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setWordWrap(True)
        layout.addWidget(footer)

        layout.addSpacing(10)

        # ── Skip link ──
        skip_btn = QtWidgets.QPushButton("Continue without signing in")
        skip_btn.setObjectName("skipBtn")
        skip_btn.setCursor(QtCore.Qt.PointingHandCursor)
        skip_btn.setFlat(True)
        skip_btn.clicked.connect(self._on_skip)
        layout.addWidget(skip_btn, alignment=QtCore.Qt.AlignCenter)

    # ── Stylesheet (Claude Desktop-like) ─────────────────────────────────
    def _apply_styles(self):
        self.setStyleSheet("""
            BNCLoginDialog {
                background-color: #ffffff;
            }

            #googleBtn {
                background-color: #ffffff;
                color: #3c4043;
                border: 1.5px solid #dadce0;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                padding: 0 24px;
                font-family: "Segoe UI", "Google Sans", Roboto, Arial, sans-serif;
            }
            #googleBtn:hover {
                background-color: #f7f8f8;
                border-color: #c6c9cc;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            }
            #googleBtn:pressed {
                background-color: #eef0f2;
                border-color: #b0b3b6;
            }

            #skipBtn {
                color: #1a73e8;
                font-size: 12px;
                border: none;
                padding: 6px 12px;
                font-family: "Segoe UI", Roboto, Arial, sans-serif;
            }
            #skipBtn:hover {
                color: #1557b0;
                text-decoration: underline;
            }
        """)

    # ── Actions ──────────────────────────────────────────────────────────
    def _on_google_signin(self):
        """Start Google OAuth 2.0 PKCE flow."""
        client_id, _ = _oauth_config()
        if client_id == _DEFAULT_CLIENT_ID:
            self._status.setStyleSheet("font-size: 12px; color: #d32f2f;")
            self._status.setText(
                "OAuth not configured. Place your bnc_oauth.json\n"
                f"in: {FreeCAD.getUserAppDataDir()}"
            )
            return

        self._google_btn.setEnabled(False)
        self._google_btn.setText("  Opening browser…")
        self._status.setStyleSheet("font-size: 12px; color: #666;")
        self._status.setText("Waiting for sign-in in your browser…")

        # Generate PKCE pair
        self._verifier, challenge = _generate_pkce()

        # Build authorization URL
        params = urllib.parse.urlencode({
            "client_id": client_id,
            "redirect_uri": _REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "select_account",
        })
        auth_url = f"{_AUTH_URL}?{params}"

        # Start callback server in background thread
        self._server = http.server.HTTPServer(("127.0.0.1", _REDIRECT_PORT), _OAuthCallbackHandler)
        self._server.auth_code = None
        self._server.timeout = 120

        def _wait_for_callback():
            self._server.handle_request()  # Blocks until one request comes in

        thread = threading.Thread(target=_wait_for_callback, daemon=True)
        thread.start()

        # Open browser
        webbrowser.open(auth_url)

        # Poll for the callback result
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.timeout.connect(self._check_auth_result)
        self._poll_timer.start(500)

    def _check_auth_result(self):
        """Poll until the OAuth callback is received."""
        code = getattr(self._server, "auth_code", None)
        if code is None:
            return  # Still waiting

        self._poll_timer.stop()
        self._status.setText("Verifying…")

        try:
            user_info = _exchange_code(code, self._verifier)
            if user_info and user_info.get("email"):
                _save_session(user_info)
                self._status.setStyleSheet("font-size: 12px; color: #2e7d32;")
                self._status.setText(f"Signed in as {user_info['name']}")
                FreeCAD.Console.PrintMessage(
                    f"BNC CAD: Signed in as {user_info['email']}\n"
                )
                self.login_successful.emit(user_info)
                QtCore.QTimer.singleShot(800, self.accept)
                return
            else:
                self._status.setStyleSheet("font-size: 12px; color: #d32f2f;")
                self._status.setText("Sign-in failed. Please try again.")
        except Exception as e:
            self._status.setStyleSheet("font-size: 12px; color: #d32f2f;")
            self._status.setText(f"Error: {e}")
            FreeCAD.Console.PrintError(f"BNC CAD: OAuth error — {e}\n")

        self._google_btn.setEnabled(True)
        self._google_btn.setText("  Sign in with Google")

    def _on_skip(self):
        """Allow user to continue without signing in."""
        FreeCAD.Console.PrintMessage("BNC CAD: User skipped sign-in\n")
        self.reject()

    def closeEvent(self, event):
        """Prevent closing with X — user must choose an action."""
        event.ignore()


# ─── Public API ───────────────────────────────────────────────────────────────
def show_login_if_needed():
    """
    Show the login dialog if the user hasn't signed in yet.
    Called once during BNC CAD startup.
    Returns True if signed in, False if skipped.
    """
    if is_logged_in():
        info = get_user_info()
        FreeCAD.Console.PrintMessage(
            f"BNC CAD: Already signed in as {info.get('email', '?')}\n"
        )
        return True

    mw = FreeCADGui.getMainWindow() if hasattr(FreeCADGui, "getMainWindow") else None
    dialog = BNCLoginDialog(mw)
    result = dialog.exec_()
    return result == QtWidgets.QDialog.Accepted
