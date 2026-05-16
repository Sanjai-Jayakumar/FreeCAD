"""
BNCAuthFromUrl — called at FreeCAD startup when launched via the bnccad:// protocol.

If the protocol URL contains ?email=...&name=... (injected by the web launcher after
Google login), we write bnc_auth.json immediately so BNCLoginDialog.is_logged_in()
returns True and the auth dialog is skipped entirely.
"""

import sys
import json
import os

try:
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs  # Python 2 fallback (unlikely in FC)


def _apply():
    """Check sys.argv for a bnccad:// URL and persist auth data if present."""
    url_arg = None
    for arg in sys.argv[1:]:
        if arg.lower().startswith("bnccad://"):
            url_arg = arg
            break

    if not url_arg:
        return

    try:
        parsed = urlparse(url_arg)
        params = parse_qs(parsed.query)

        email = (params.get("email") or [""])[0].strip()
        name  = (params.get("name")  or [""])[0].strip()

        if not email:
            return

        import FreeCAD
        token_file = os.path.join(FreeCAD.getUserAppDataDir(), "bnc_auth.json")

        # Always write the email coming from the web launcher so the logged-in
        # user is always up to date (e.g. a different user logs in on the web).
        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        session = {"email": email, "name": name, "source": "web_launcher"}
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2)

        FreeCAD.Console.PrintLog(f"BNC CAD: web auth saved for {email}\n")

    except Exception as exc:
        try:
            import FreeCAD
            FreeCAD.Console.PrintWarning(f"BNC CAD: BNCAuthFromUrl error: {exc}\n")
        except Exception:
            pass


_apply()
