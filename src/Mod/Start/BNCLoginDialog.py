# SPDX-License-Identifier: LGPL-2.1-or-later
# BNC CAD — Google Sign-In Dialog
# Shows a login screen on first launch, similar to Claude Desktop app.
# Users authenticate with their Google account via OAuth 2.0.

import os
import sys
import json
import hashlib
import re
import secrets
import base64
import webbrowser
import http.server
import threading
import urllib.parse
import urllib.error

import FreeCAD
import FreeCADGui

# ─── Debug log (written to %TEMP% so we can diagnose first-launch issues) ─────
_LOG_PATH = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "bnc_cad_login.log")

def _dbg(msg):
    """Append a timestamped line to the debug log file."""
    try:
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

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
# OAuth credentials are loaded from bnc_oauth.json in the user's FreeCAD data dir.
# Create the file with: {"client_id": "YOUR_ID", "client_secret": "YOUR_SECRET"}
# Get credentials at https://console.cloud.google.com/apis/credentials
_OAUTH_CONFIG_FILE = os.path.join(FreeCAD.getUserAppDataDir(), "bnc_oauth.json")


def _oauth_config():
    """Load OAuth client id/secret from config file."""
    if os.path.isfile(_OAUTH_CONFIG_FILE):
        try:
            with open(_OAUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cid = cfg.get("client_id", "")
            csec = cfg.get("client_secret", "")
            if cid and csec:
                return cid, csec
        except (json.JSONDecodeError, OSError):
            pass
    FreeCAD.Console.PrintWarning("BNC CAD: OAuth config not found. Place bnc_oauth.json in " + FreeCAD.getUserAppDataDir() + "\n")
    return "", ""


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

# ─── BNC Logo PNG path ────────────────────────────────────────────────────────
_BNC_LOGO_PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freecad-icon-64.png")


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
        self.setFixedSize(460, 720)
        self.setWindowFlags(
            QtCore.Qt.Dialog
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.CustomizeWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setWindowModality(QtCore.Qt.ApplicationModal)

        self._build_ui()
        self._apply_styles()

    # ── UI Construction ──────────────────────────────────────────────────
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        # Top spacer
        layout.addSpacing(10)

        # ── BNC Logo ──
        logo_icon = QtWidgets.QLabel()
        logo_icon.setAlignment(QtCore.Qt.AlignCenter)
        png_pixmap = QtGui.QPixmap(_BNC_LOGO_PNG)
        if not png_pixmap.isNull():
            scaled = png_pixmap.scaled(
                QtCore.QSize(80, 80),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            logo_icon.setPixmap(scaled)
        layout.addWidget(logo_icon)

        layout.addSpacing(12)

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

        # ── Google section container (hidden when OTP is shown) ──
        self._google_container = QtWidgets.QWidget()
        gc_layout = QtWidgets.QVBoxLayout(self._google_container)
        gc_layout.setContentsMargins(0, 0, 0, 0)
        gc_layout.setSpacing(0)

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
        gc_layout.addWidget(self._google_btn)

        gc_layout.addSpacing(12)

        # ── Google status label ──
        self._google_status = QtWidgets.QLabel("")
        self._google_status.setAlignment(QtCore.Qt.AlignCenter)
        self._google_status.setWordWrap(True)
        self._google_status.setStyleSheet("font-size: 12px; color: #d32f2f;")
        gc_layout.addWidget(self._google_status)

        gc_layout.addSpacing(12)

        # ── OR divider ──
        divider_layout = QtWidgets.QHBoxLayout()
        divider_layout.setSpacing(12)
        line_left = QtWidgets.QFrame()
        line_left.setFrameShape(QtWidgets.QFrame.HLine)
        line_left.setStyleSheet("color: #dadce0; background-color: #dadce0; max-height: 1px;")
        or_label = QtWidgets.QLabel("OR")
        or_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #999;")
        or_label.setAlignment(QtCore.Qt.AlignCenter)
        line_right = QtWidgets.QFrame()
        line_right.setFrameShape(QtWidgets.QFrame.HLine)
        line_right.setStyleSheet("color: #dadce0; background-color: #dadce0; max-height: 1px;")
        divider_layout.addWidget(line_left)
        divider_layout.addWidget(or_label)
        divider_layout.addWidget(line_right)
        gc_layout.addLayout(divider_layout)

        layout.addWidget(self._google_container)

        layout.addSpacing(12)

        # ── Email input ──
        self._email_input = QtWidgets.QLineEdit()
        self._email_input.setPlaceholderText("Enter your work email")
        self._email_input.setMinimumHeight(44)
        self._email_input.setObjectName("emailInput")
        self._email_input.returnPressed.connect(self._on_email_continue)
        layout.addWidget(self._email_input)

        layout.addSpacing(6)

        # ── Email error label ──
        self._email_error = QtWidgets.QLabel("")
        self._email_error.setAlignment(QtCore.Qt.AlignLeft)
        self._email_error.setWordWrap(True)
        self._email_error.setStyleSheet("font-size: 11px; color: #d32f2f; padding-left: 4px;")
        self._email_error.setVisible(False)
        layout.addWidget(self._email_error)

        layout.addSpacing(8)

        # ── Continue with Email button ──
        self._email_btn = QtWidgets.QPushButton("Continue with Email")
        self._email_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._email_btn.setMinimumHeight(44)
        self._email_btn.setObjectName("emailBtn")
        self._email_btn.clicked.connect(self._on_email_continue)
        layout.addWidget(self._email_btn)

        layout.addSpacing(8)

        # ── Email status label ──
        self._email_status = QtWidgets.QLabel("")
        self._email_status.setAlignment(QtCore.Qt.AlignCenter)
        self._email_status.setWordWrap(True)
        self._email_status.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self._email_status)

        layout.addSpacing(4)

        # ── OTP section (hidden until email is validated) ──
        self._otp_container = QtWidgets.QWidget()
        otp_layout = QtWidgets.QVBoxLayout(self._otp_container)
        otp_layout.setContentsMargins(0, 0, 0, 0)
        otp_layout.setSpacing(8)

        otp_label = QtWidgets.QLabel("Enter the 6-digit code sent to your email")
        otp_label.setAlignment(QtCore.Qt.AlignCenter)
        otp_label.setWordWrap(True)
        otp_label.setStyleSheet("font-size: 13px; color: #3c4043;")
        otp_layout.addWidget(otp_label)

        self._otp_input = QtWidgets.QLineEdit()
        self._otp_input.setPlaceholderText("000000")
        self._otp_input.setMinimumHeight(48)
        self._otp_input.setMaxLength(6)
        self._otp_input.setAlignment(QtCore.Qt.AlignCenter)
        self._otp_input.setObjectName("otpInput")
        self._otp_input.returnPressed.connect(self._on_otp_submit)
        otp_layout.addWidget(self._otp_input)

        self._otp_error = QtWidgets.QLabel("")
        self._otp_error.setAlignment(QtCore.Qt.AlignCenter)
        self._otp_error.setWordWrap(True)
        self._otp_error.setStyleSheet("font-size: 11px; color: #d32f2f;")
        self._otp_error.setVisible(False)
        otp_layout.addWidget(self._otp_error)

        self._otp_submit_btn = QtWidgets.QPushButton("Submit")
        self._otp_submit_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._otp_submit_btn.setMinimumHeight(44)
        self._otp_submit_btn.setObjectName("otpSubmitBtn")
        self._otp_submit_btn.clicked.connect(self._on_otp_submit)
        otp_layout.addWidget(self._otp_submit_btn)

        self._otp_container.setVisible(False)
        layout.addWidget(self._otp_container)

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
            }
            #googleBtn:pressed {
                background-color: #eef0f2;
                border-color: #b0b3b6;
            }

            #emailInput {
                border: 1.5px solid #dadce0;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 14px;
                color: #3c4043;
                background-color: #ffffff;
                font-family: "Segoe UI", Roboto, Arial, sans-serif;
            }
            #emailInput:focus {
                border-color: #1a73e8;
            }

            #emailBtn {
                background-color: #1a73e8;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                padding: 0 24px;
                font-family: "Segoe UI", Roboto, Arial, sans-serif;
            }
            #emailBtn:hover {
                background-color: #1565c0;
            }
            #emailBtn:pressed {
                background-color: #0d47a1;
            }
            #emailBtn:disabled {
                background-color: #93c5fd;
            }

            #otpInput {
                border: 1.5px solid #dadce0;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 24px;
                font-weight: 600;
                letter-spacing: 12px;
                color: #1a1a2e;
                background-color: #ffffff;
                font-family: "Segoe UI", Roboto, Arial, sans-serif;
            }
            #otpInput:focus {
                border-color: #1a73e8;
            }

            #otpSubmitBtn {
                background-color: #1a73e8;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                padding: 0 24px;
                font-family: "Segoe UI", Roboto, Arial, sans-serif;
            }
            #otpSubmitBtn:hover {
                background-color: #1565c0;
            }
            #otpSubmitBtn:pressed {
                background-color: #0d47a1;
            }
            #otpSubmitBtn:disabled {
                background-color: #93c5fd;
            }

        """)

    # ── Actions ──────────────────────────────────────────────────────────
    # ── API Config ───────────────────────────────────────────────────────
    _REGISTER_URL = "https://bnc-ai.com/api/designing-users/public/register"
    _VERIFY_OTP_URL = "https://bnc-ai.com/api/designing-users/public/verify-otp"
    _API_KEY = "dt_159391eaf5d473b843d92dc765b2668a386d756d54302c4a5951b7d38f6a558a"

    # ── Email validation ─────────────────────────────────────────────────
    _EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

    def _on_email_continue(self):
        """Validate email and call register API, then show OTP on success."""
        email = self._email_input.text().strip()

        # Clear previous state
        self._email_error.setVisible(False)
        self._email_status.setText("")

        # Validation
        if not email:
            self._email_error.setText("Email address is required.")
            self._email_error.setVisible(True)
            self._email_input.setFocus()
            return

        if not self._EMAIL_RE.match(email):
            self._email_error.setText("Please enter a valid email address.")
            self._email_error.setVisible(True)
            self._email_input.setFocus()
            return

        # Show loading state
        self._email_btn.setEnabled(False)
        self._email_btn.setText("Sending…")
        self._email_input.setEnabled(False)
        self._email_status.setStyleSheet("font-size: 12px; color: #666;")
        self._email_status.setText("Registering…")
        QtWidgets.QApplication.processEvents()

        # Call the register API
        try:
            import urllib.request
            payload = json.dumps({"email": email, "project_id": 1}).encode("utf-8")
            req = urllib.request.Request(
                self._REGISTER_URL,
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            req.add_header("x-api-key", self._API_KEY)

            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())

            status = body.get("status", "")
            if status == "success":
                # Store email and API response data for OTP submission
                self._pending_email = email
                self._pending_api_data = body.get("data", [{}])

                # Hide Google section and email button, show OTP panel
                self._google_container.setVisible(False)
                self._email_btn.setVisible(False)
                self._email_input.setEnabled(False)
                self._email_status.setStyleSheet("font-size: 12px; color: #2e7d32;")
                self._email_status.setText(f"OTP sent to {email}")

                self._otp_container.setVisible(True)
                self._otp_input.setFocus()
                FreeCAD.Console.PrintMessage(f"BNC CAD: OTP requested for {email}\n")
            else:
                # API returned error status
                msg = body.get("message", "Registration failed. Please try again.")
                self._email_error.setText(msg)
                self._email_error.setVisible(True)
                self._email_btn.setEnabled(True)
                self._email_btn.setText("Continue with Email")
                self._email_input.setEnabled(True)
                self._email_input.setFocus()
                self._email_status.setText("")
                FreeCAD.Console.PrintWarning(f"BNC CAD: Register API error — {msg}\n")

        except urllib.error.HTTPError as http_err:
            # Try to parse error body from server
            msg = "Registration failed. Please try again."
            try:
                err_body = json.loads(http_err.read())
                msg = err_body.get("message", msg)
            except Exception:
                pass
            self._email_error.setText(msg)
            self._email_error.setVisible(True)
            self._email_btn.setEnabled(True)
            self._email_btn.setText("Continue with Email")
            self._email_input.setEnabled(True)
            self._email_input.setFocus()
            self._email_status.setText("")
            FreeCAD.Console.PrintError(f"BNC CAD: Register HTTP error {http_err.code} — {msg}\n")

        except Exception as exc:
            self._email_error.setText(f"Network error: {exc}")
            self._email_error.setVisible(True)
            self._email_btn.setEnabled(True)
            self._email_btn.setText("Continue with Email")
            self._email_input.setEnabled(True)
            self._email_input.setFocus()
            self._email_status.setText("")
            FreeCAD.Console.PrintError(f"BNC CAD: Register API exception — {exc}\n")

    def _on_otp_submit(self):
        """Validate the 6-digit OTP via API and sign in."""
        otp = self._otp_input.text().strip()
        self._otp_error.setVisible(False)

        # Validation: must be exactly 6 digits
        if not otp or len(otp) != 6 or not otp.isdigit():
            self._otp_error.setText("Please enter a valid 6-digit code.")
            self._otp_error.setVisible(True)
            self._otp_input.setFocus()
            return

        # Disable while verifying
        self._otp_submit_btn.setEnabled(False)
        self._otp_submit_btn.setText("Verifying…")
        self._otp_input.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        email = self._pending_email

        # Call verify-otp API
        try:
            import urllib.request
            payload = json.dumps({"email": email, "otp": otp}).encode("utf-8")
            req = urllib.request.Request(
                self._VERIFY_OTP_URL,
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            req.add_header("x-api-key", self._API_KEY)

            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())

            status = body.get("status", "")
            if status == "success":
                # Save verified email to local storage
                data = body.get("data", {})
                user_info = {
                    "email": data.get("email", email),
                    "name": data.get("email", email).split("@")[0].replace(".", " ").title(),
                    "picture": "",
                    "login_method": "email",
                    "verified": data.get("verified", True),
                }
                _save_session(user_info)

                self._otp_error.setVisible(False)
                self._email_status.setStyleSheet("font-size: 12px; color: #2e7d32;")
                self._email_status.setText("Account verified successfully!")
                FreeCAD.Console.PrintMessage(
                    f"BNC CAD: Account verified for {user_info['email']}\n"
                )
                self.login_successful.emit(user_info)
                QtCore.QTimer.singleShot(800, self.accept)
            else:
                # API returned error status
                msg = body.get("message", "OTP verification failed. Please try again.")
                self._otp_error.setText(msg)
                self._otp_error.setVisible(True)
                self._otp_submit_btn.setEnabled(True)
                self._otp_submit_btn.setText("Submit")
                self._otp_input.setEnabled(True)
                self._otp_input.setFocus()
                FreeCAD.Console.PrintWarning(f"BNC CAD: OTP verify error — {msg}\n")

        except urllib.error.HTTPError as http_err:
            msg = "OTP verification failed. Please try again."
            try:
                err_body = json.loads(http_err.read())
                msg = err_body.get("message", msg)
            except Exception:
                pass
            self._otp_error.setText(msg)
            self._otp_error.setVisible(True)
            self._otp_submit_btn.setEnabled(True)
            self._otp_submit_btn.setText("Submit")
            self._otp_input.setEnabled(True)
            self._otp_input.setFocus()
            FreeCAD.Console.PrintError(f"BNC CAD: OTP verify HTTP error {http_err.code} — {msg}\n")

        except Exception as exc:
            self._otp_error.setText(f"Network error: {exc}")
            self._otp_error.setVisible(True)
            self._otp_submit_btn.setEnabled(True)
            self._otp_submit_btn.setText("Submit")
            self._otp_input.setEnabled(True)
            self._otp_input.setFocus()
            FreeCAD.Console.PrintError(f"BNC CAD: OTP verify exception — {exc}\n")

    def _on_google_signin(self):
        """Start Google OAuth 2.0 PKCE flow."""
        client_id, _ = _oauth_config()

        self._google_btn.setEnabled(False)
        self._google_btn.setText("  Opening browser…")
        self._google_status.setStyleSheet("font-size: 12px; color: #666;")
        self._google_status.setText("Waiting for sign-in in your browser…")

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
        self._google_status.setText("Verifying…")

        try:
            user_info = _exchange_code(code, self._verifier)
            if user_info and user_info.get("email"):
                user_info["login_method"] = "google"
                _save_session(user_info)
                self._google_status.setStyleSheet("font-size: 12px; color: #2e7d32;")
                self._google_status.setText(f"Signed in as {user_info['name']}")
                FreeCAD.Console.PrintMessage(
                    f"BNC CAD: Signed in as {user_info['email']}\n"
                )
                self.login_successful.emit(user_info)
                QtCore.QTimer.singleShot(800, self.accept)
                return
            else:
                self._google_status.setStyleSheet("font-size: 12px; color: #d32f2f;")
                self._google_status.setText("Sign-in failed. Please try again.")
        except Exception as e:
            self._google_status.setStyleSheet("font-size: 12px; color: #d32f2f;")
            self._google_status.setText(f"Error: {e}")
            FreeCAD.Console.PrintError(f"BNC CAD: OAuth error — {e}\n")

        self._google_btn.setEnabled(True)
        self._google_btn.setText("  Sign in with Google")

    def closeEvent(self, event):
        """Close button exits the entire application — login is required."""
        FreeCAD.Console.PrintMessage("BNC CAD: User closed login — exiting application\n")
        QtWidgets.QApplication.instance().quit()


# ─── Public API ───────────────────────────────────────────────────────────────
def show_login_if_needed():
    """
    Show the login dialog if the user hasn't signed in yet.
    Called once during BNC CAD startup.
    Returns True if signed in, False if skipped.
    """
    _dbg("show_login_if_needed() called")
    if is_logged_in():
        info = get_user_info()
        _dbg(f"Already signed in as {info.get('email', '?')}")
        FreeCAD.Console.PrintMessage(
            f"BNC CAD: Already signed in as {info.get('email', '?')}\n"
        )
        return True

    _dbg("Not logged in — creating dialog")
    mw = FreeCADGui.getMainWindow() if hasattr(FreeCADGui, "getMainWindow") else None
    _dbg(f"Main window: {mw}, visible: {mw.isVisible() if mw else 'N/A'}")
    dialog = BNCLoginDialog(mw)
    _dbg("Dialog created, calling raise_ / activateWindow / exec_")
    dialog.raise_()
    dialog.activateWindow()
    result = dialog.exec_()
    _dbg(f"exec_() returned: {result} (Accepted={QtWidgets.QDialog.Accepted})")
    if result != QtWidgets.QDialog.Accepted:
        # User closed the dialog without signing in — exit the app
        FreeCAD.Console.PrintMessage("BNC CAD: Login required — exiting\n")
        _dbg("Login not accepted — quitting")
        QtWidgets.QApplication.instance().quit()
        return False
    _dbg("Login accepted")
    return True
