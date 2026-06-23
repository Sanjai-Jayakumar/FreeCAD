# SPDX-License-Identifier: LGPL-2.1-or-later
import json
import platform
import threading
import urllib.request
import urllib.error
import ssl
import FreeCAD

CURRENT_VERSION = "1.1.2"   # <-- update this for each release
_API_URL = "https://bnc-ai.com/api/software/latest"
_API_KEY  = "dt_159391eaf5d473b843d92dc765b2668a386d756d54302c4a5951b7d38f6a558a"


def check_for_updates_async(callback):
    """Run the update API call in a background thread, then call callback(result)."""

    def _worker():
        result = {
            "update_available": False,
            "latest_version": "",
            "download_url": "",
            "notes": "",
            "error": None,
        }
        try:
            FreeCAD.Console.PrintLog("BNC: Calling update API...\n")
            payload = json.dumps({
                "version": CURRENT_VERSION,
                "os_type": platform.system(),
            }).encode("utf-8")
            req = urllib.request.Request(
                _API_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": _API_KEY,
                },
                method="POST",
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            FreeCAD.Console.PrintLog(f"BNC: Update API response: {raw[:300]}\n")
            body = json.loads(raw)
            data = body.get("data", body)
            result["update_available"] = bool(data.get("update_available", False))
            result["latest_version"]   = data.get("latest_version", "")
            result["download_url"]     = data.get("download_url", "")
            result["notes"]            = data.get("notes", "")
        except Exception as exc:
            result["error"] = str(exc)
            FreeCAD.Console.PrintError(f"BNC: Update API error: {exc}\n")
        callback(result)

    threading.Thread(target=_worker, daemon=True).start()
