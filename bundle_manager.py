import os
import json
import base64
import logging

logger = logging.getLogger("BundleManager")
BASE_DIR = os.path.dirname(__file__)
BUNDLE_FILE = os.path.join(BASE_DIR, "bot_secrets.bundle")

FILES_TO_PACK = [
    "config.json",
    "codespaces_pool.json",
    "user_api_keys.json",
    "gemini_keys.json",
    "commander_db.sqlite"
]

def pack_bundle():
    bundle_data = {}
    for filename in FILES_TO_PACK:
        path = os.path.join(BASE_DIR, filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                content_b64 = base64.b64encode(f.read()).decode("utf-8")
                bundle_data[filename] = content_b64
    
    with open(BUNDLE_FILE, "w", encoding="utf-8") as f:
        json.dump(bundle_data, f)
    logger.info(f"Successfully packed {len(bundle_data)} files into {BUNDLE_FILE}")
    print(f"Packed {len(bundle_data)} files into {BUNDLE_FILE}")

def unpack_bundle():
    if not os.path.exists(BUNDLE_FILE):
        logger.warning("No bundle file found to unpack.")
        return False
    try:
        with open(BUNDLE_FILE, "r", encoding="utf-8") as f:
            bundle_data = json.load(f)
        for filename, content_b64 in bundle_data.items():
            dest = os.path.join(BASE_DIR, filename)
            # Only unpack if file doesn't exist or is empty
            if not os.path.exists(dest) or os.path.getsize(dest) == 0:
                raw_bytes = base64.b64decode(content_b64)
                with open(dest, "wb") as f:
                    f.write(raw_bytes)
                logger.info(f"Unpacked {filename} ({len(raw_bytes)} bytes)")
        return True
    except Exception as e:
        logger.error(f"Failed to unpack bundle: {e}")
        return False

if __name__ == "__main__":
    pack_bundle()
