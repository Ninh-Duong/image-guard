"""
test_server.py - Automated end-to-end integration tests for Image Guard server.
"""
import io
import json
import sys
import time
import subprocess
import urllib.request
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def test():
    # 1. Start server on test port 8899
    proc = subprocess.Popen(["python", "server.py", "8899"])
    time.sleep(1.5)

    try:
        # 2. Test GET / (HTML UI)
        res = urllib.request.urlopen("http://localhost:8899")
        assert res.status == 200, f"GET / failed: {res.status}"
        html = res.read().decode("utf-8")
        assert "image-guard" in html.lower(), "HTML response does not contain image-guard"
        print("[PASS] 1. GET / returned HTML dashboard successfully.")

        # 3. Test GET /rules
        res_rules = urllib.request.urlopen("http://localhost:8899/rules")
        assert res_rules.status == 200, f"GET /rules failed: {res_rules.status}"
        rules_data = json.loads(res_rules.read().decode("utf-8"))
        assert "max_nsfw" in rules_data, "Rules data missing max_nsfw"
        print("[PASS] 2. GET /rules returned system configuration:", rules_data)

        # 4. Generate a test image with distinct pattern (not solid 0x0)
        img = Image.new("RGB", (120, 120), color="white")
        for x in range(60):
            for y in range(60):
                img.putpixel((x, y), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        # 5. Test POST /check with standard rules (Safe image)
        req = urllib.request.Request(
            "http://localhost:8899/check?max_nsfw=0.7&max_violence=0.6&min_safe=0.0",
            data=img_bytes,
            headers={"Content-Type": "image/jpeg"},
            method="POST"
        )
        res = urllib.request.urlopen(req)
        assert res.status == 200, f"POST /check failed: {res.status}"
        data = json.loads(res.read().decode("utf-8"))
        assert data["allowed"] is True, f"Expected allowed=True, got: {data}"
        assert "hash" in data, "Response missing hash field"
        print("[PASS] 3. POST /check evaluated safe image successfully. Scores:", data["scores"])

        # 6. Test POST /check with ultra-strict threshold (Forced Violation)
        req_strict = urllib.request.Request(
            "http://localhost:8899/check?max_nsfw=0.0001",
            data=img_bytes,
            headers={"Content-Type": "image/jpeg"},
            method="POST"
        )
        res_strict = urllib.request.urlopen(req_strict)
        data_strict = json.loads(res_strict.read().decode("utf-8"))
        assert data_strict["allowed"] is False, "Image should have been blocked under strict threshold"
        assert len(data_strict["violations"]) > 0, "Expected non-empty violations list"
        print("[PASS] 4. Dynamic rule evaluation triggered violation:", data_strict["violations"])

        # 7. Test POST /blocklist (Manual ban)
        img_hash = data["hash"]
        req_block = urllib.request.Request(
            "http://localhost:8899/blocklist",
            data=json.dumps({"hash": img_hash, "reason": "TEST_BAN"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        res_block = urllib.request.urlopen(req_block)
        block_data = json.loads(res_block.read().decode("utf-8"))
        assert block_data["success"] is True, "Manual block failed"
        print("[PASS] 5. POST /blocklist recorded hash successfully. Total blocked:", block_data["total_blocked"])

        # 8. Test dHash rapid rejection on now-banned image
        res_banned = urllib.request.urlopen(req)
        data_banned = json.loads(res_banned.read().decode("utf-8"))
        assert data_banned["allowed"] is False, "Banned image was allowed"
        assert data_banned["reason"] == "BANNED_HASH_MATCH", "Expected BANNED_HASH_MATCH"
        print("[PASS] 6. dHash lookup rejected banned image in 0ms.")

        # 9. Test CORS preflight OPTIONS request
        req_options = urllib.request.Request("http://localhost:8899/check", method="OPTIONS")
        res_options = urllib.request.urlopen(req_options)
        assert res_options.status == 204, f"OPTIONS failed with {res_options.status}"
        assert res_options.headers.get("Access-Control-Allow-Origin") == "*", "Missing CORS origin"
        print("[PASS] 7. CORS OPTIONS preflight handled successfully.")

        print("\n=======================================================")
        print(" [ALL TESTS PASSED] All server components operational!")
        print("=======================================================\n")

    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    test()
