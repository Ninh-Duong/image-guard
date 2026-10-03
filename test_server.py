"""
test_server.py - Integration tests for Layered Image Guard, Profiling & AI Process Logs.
"""
import io
import json
import sys
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def run_tests():
    blocklist_path = "blocklist.jsonl"
    orig_blocklist = None
    try:
        with open(blocklist_path, "r", encoding="utf-8") as f:
            orig_blocklist = f.read()
    except Exception:
        pass

    # 1. Start server on test port 8899
    proc = subprocess.Popen([sys.executable, "server.py", "8899"])
    time.sleep(1.5)

    try:
        # 2. Test GET / (HTML Dashboard)
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

        # 4. Generate test image
        img = Image.new("RGB", (160, 160), color="white")
        for x in range(80):
            for y in range(80):
                img.putpixel((x, y), (255, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        # 5. Test POST /check (Safe photo -> Guard approved + User Profile extracted)
        req = urllib.request.Request(
            "http://localhost:8899/check?max_nsfw=0.7&min_safe=0.0",
            data=img_bytes,
            headers={"Content-Type": "image/jpeg"},
            method="POST"
        )
        res = urllib.request.urlopen(req)
        assert res.status == 200, f"POST /check failed: {res.status}"
        data = json.loads(res.read().decode("utf-8"))
        assert data["allowed"] is True, f"Expected allowed=True, got: {data}"
        assert "guard" in data and data["guard"]["allowed"] is True, "Missing guard result"
        assert "profile" in data and data["profile"] is not None, "Missing user profile result"
        assert "trace_id" in data and data["trace_id"] is not None, "Missing trace_id in response"
        assert "merged_tags" in data and len(data["merged_tags"]) > 0, "Missing merged_tags in response"
        assert "db_record" in data and data["db_record"] is not None, "Missing db_record in response"
        assert data["db_record"]["moderation_status"] == "APPROVED", "db_record status should be APPROVED"
        print("[PASS] 3. POST /check passed guardrail and extracted user profile:")
        print("         -> Primary Interest:", data["profile"]["interest_label"])
        print("         -> Merged Tags (DB-Ready):", data["merged_tags"])
        print("         -> DB Record ID:", data["db_record"]["memory_id"])
        print("         -> Suggested Caption:", data["profile"]["suggested_note_caption"])
        print("         -> Trace ID:", data["trace_id"])
        print("         -> Latency:", data.get("execution_time_ms"), "ms")

        # 6. Test Fail-Fast on Strict Threshold (NSFW violation -> Profiling skipped)
        req_strict = urllib.request.Request(
            "http://localhost:8899/check?max_nsfw=0.00001",
            data=img_bytes,
            headers={"Content-Type": "image/jpeg"},
            method="POST"
        )
        res_strict = urllib.request.urlopen(req_strict)
        data_strict = json.loads(res_strict.read().decode("utf-8"))
        assert data_strict["allowed"] is False, "Image should have been blocked"
        assert data_strict["profile"] is None, "Profiling should be SKIPPED on violation (Fail-Fast optimization)"
        print("[PASS] 4. Fail-Fast optimization verified: profiling skipped on violation.")

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
        print("[PASS] 5. POST /blocklist successfully saved hash. Total:", block_data["total_blocked"])

        # 8. Test dHash Tier 1 instant rejection on banned hash
        res_banned = urllib.request.urlopen(req)
        data_banned = json.loads(res_banned.read().decode("utf-8"))
        assert data_banned["allowed"] is False, "Banned image should be blocked"
        assert data_banned["reason"] == "BANNED_HASH_MATCH", "Expected BANNED_HASH_MATCH"
        print("[PASS] 6. Tier 1 dHash rejected banned image in 0ms.")

        # 9. Test Invalid Image Payload -> 400 Bad Request (Security Guardrail)
        req_bad = urllib.request.Request(
            "http://localhost:8899/check",
            data=b"not_an_image_data",
            headers={"Content-Type": "image/jpeg"},
            method="POST"
        )
        try:
            urllib.request.urlopen(req_bad)
            assert False, "Expected 400 Bad Request on invalid payload"
        except urllib.error.HTTPError as err:
            assert err.code == 400, f"Expected HTTP 400, got {err.code}"
            err_body = json.loads(err.read().decode("utf-8"))
            assert err_body.get("reason") == "INVALID_IMAGE_PAYLOAD"
            print("[PASS] 7. Invalid image payload rejected with HTTP 400 Bad Request.")

        # 10. Test CORS preflight OPTIONS
        req_options = urllib.request.Request("http://localhost:8899/check", method="OPTIONS")
        res_options = urllib.request.urlopen(req_options)
        assert res_options.status == 204, f"OPTIONS failed with {res_options.status}"
        assert res_options.headers.get("Access-Control-Allow-Origin") == "*", "Missing CORS origin"
        print("[PASS] 8. CORS OPTIONS preflight handled successfully.")

        # 11. Test GET /logs/latest (AI Agent Telemetry Verification)
        res_log = urllib.request.urlopen("http://localhost:8899/logs/latest")
        assert res_log.status == 200, f"GET /logs/latest failed: {res_log.status}"
        log_json = json.loads(res_log.read().decode("utf-8"))
        assert "trace_id" in log_json, "Process log missing trace_id"
        assert "pipeline_stages" in log_json, "Process log missing pipeline_stages"
        assert "performance_breakdown" in log_json, "Process log missing performance_breakdown"
        assert "bottleneck_stage" in log_json["performance_breakdown"], "Missing bottleneck_stage"
        assert "agent_telemetry" in log_json, "Process log missing agent_telemetry"
        assert "database_payload" in log_json, "Process log missing database_payload"
        assert "merged_tags" in log_json, "Process log missing merged_tags"
        print("[PASS] 9. GET /logs/latest returned structured trace for AI Agent:")
        print("         -> Bottleneck Stage:", log_json["performance_breakdown"]["bottleneck_stage"])
        print("         -> Database Payload Present:", log_json["database_payload"] is not None)
        print("         -> Stages Logged:", list(log_json["pipeline_stages"].keys()))

        # 12. Test GET /logs/summary (AI Agent Aggregated Metrics Verification)
        res_sum = urllib.request.urlopen("http://localhost:8899/logs/summary")
        assert res_sum.status == 200, f"GET /logs/summary failed: {res_sum.status}"
        sum_json = json.loads(res_sum.read().decode("utf-8"))
        assert sum_json.get("total_runs", 0) > 0, "Summary total_runs should be > 0"
        print("[PASS] 10. GET /logs/summary returned rolling metrics. Total runs recorded:", sum_json["total_runs"])

        # 13. Test Multilingual (EN) & Timezone (America/New_York)
        img_en_obj = Image.new("RGB", (160, 160), color="blue")
        buf_en = io.BytesIO()
        img_en_obj.save(buf_en, format="JPEG")
        img_en_bytes = buf_en.getvalue()

        req_en = urllib.request.Request(
            "http://localhost:8899/check?lang=en&timezone=America/New_York&max_nsfw=0.7&min_safe=0.0",
            data=img_en_bytes,
            headers={"Content-Type": "image/jpeg"},
            method="POST"
        )
        res_en = urllib.request.urlopen(req_en)
        assert res_en.status == 200, f"POST /check (en) failed: {res_en.status}"
        data_en = json.loads(res_en.read().decode("utf-8"))
        assert data_en["allowed"] is True, f"Expected allowed=True for img_en, got {data_en}"
        assert data_en["db_record"]["user_language"] == "en", "Expected user_language == 'en'"
        assert data_en["db_record"]["user_timezone"] == "America/New_York", "Expected timezone America/New_York"
        assert "local_created_at" in data_en["db_record"], "Missing local_created_at"
        assert data_en["profile"]["interest_label"] == "Scenery & Atmosphere", f"Unexpected EN label: {data_en['profile']['interest_label']}"
        assert any("#Scenery" in t or "#Perspective" in t for t in data_en["merged_tags"]), "Expected English merged tags"
        print("[PASS] 11. Multilingual (EN) & Timezone (America/New_York) verified:")
        print("         -> Language:", data_en["db_record"]["user_language"])
        print("         -> Timezone:", data_en["db_record"]["user_timezone"])
        print("         -> Local Time:", data_en["db_record"]["local_created_at"])
        print("         -> Time of Day:", data_en["db_record"]["time_of_day"])
        print("         -> Merged Tags (EN):", data_en["merged_tags"])
        print("         -> English Caption:", data_en["profile"]["suggested_note_caption"])

        # 14. Test GET /languages & Japanese (JA) + Asia/Tokyo
        res_langs = urllib.request.urlopen("http://localhost:8899/languages")
        assert res_langs.status == 200, f"GET /languages failed: {res_langs.status}"
        langs_data = json.loads(res_langs.read().decode("utf-8"))
        supported = [l["code"] for l in langs_data["supported_languages"]]
        assert "vi" in supported and "en" in supported and "ja" in supported and "ko" in supported, "Missing supported languages"
        print("[PASS] 12. GET /languages returned Source Supported Languages:", supported)

        # Post photo with Japanese locale
        req_ja = urllib.request.Request(
            "http://localhost:8899/check?lang=ja&timezone=Asia/Tokyo&max_nsfw=0.7&min_safe=0.0",
            data=img_en_bytes,
            headers={"Content-Type": "image/jpeg"},
            method="POST"
        )
        res_ja = urllib.request.urlopen(req_ja)
        assert res_ja.status == 200, f"POST /check (ja) failed: {res_ja.status}"
        data_ja = json.loads(res_ja.read().decode("utf-8"))
        assert data_ja["db_record"]["user_language"] == "ja", "Expected user_language == 'ja'"
        assert data_ja["db_record"]["user_timezone"] == "Asia/Tokyo", "Expected timezone Asia/Tokyo"
        assert data_ja["profile"]["interest_label"] == "風景＆雰囲気", f"Unexpected JA label: {data_ja['profile']['interest_label']}"
        assert any("#風景" in t for t in data_ja["merged_tags"]), "Expected Japanese merged tags"
        print("         -> Japanese Caption:", data_ja["profile"]["suggested_note_caption"])
        print("         -> Japanese Merged Tags:", data_ja["merged_tags"])

        # 15. Test Multi-Signal Billboard Detection (BOURBON AN HOA Real-world Case)
        billboard_sample = Path("C:/Users/ninh/.gemini/antigravity/brain/f6cb1977-01c1-47a3-91b7-380523245c87/.user_uploaded/media_1791017473719.jpg")
        if billboard_sample.exists():
            bb_bytes = billboard_sample.read_bytes()
            req_bb = urllib.request.Request(
                "http://localhost:8899/check?lang=vi&timezone=Asia/Ho_Chi_Minh",
                data=bb_bytes,
                headers={"Content-Type": "image/jpeg"},
                method="POST"
            )
            res_bb = urllib.request.urlopen(req_bb)
            assert res_bb.status == 200, f"POST /check (billboard) failed: {res_bb.status}"
            data_bb = json.loads(res_bb.read().decode("utf-8"))
            assert data_bb["profile"]["primary_interest"] == "signboard_and_commercial", f"Expected signboard_and_commercial, got: {data_bb['profile']['primary_interest']}"
            assert data_bb["profile"]["interest_label"] == "Biển hiệu & Bảng quảng cáo", f"Expected 'Biển hiệu & Bảng quảng cáo', got: {data_bb['profile']['interest_label']}"
            assert any("#BienQuangCao" in t or "#Bourbon" in t for t in data_bb["merged_tags"]), "Expected billboard tags"
            print("[PASS] 13. Multi-Signal Billboard Detection (BOURBON AN HOA) verified:")
            print("         -> Primary Interest:", data_bb["profile"]["primary_interest"])
            print("         -> Interest Label:", data_bb["profile"]["interest_label"])
            print("         -> Caption:", data_bb["profile"]["suggested_note_caption"])
            print("         -> Merged Tags:", data_bb["merged_tags"][:5])

        print("\n=======================================================")
        print(" [ALL TESTS PASSED] AI Process Logs & Telemetry OK!   ")
        print("=======================================================\n")

    finally:
        proc.terminate()
        proc.wait()
        if orig_blocklist is not None:
            try:
                with open(blocklist_path, "w", encoding="utf-8") as f:
                    f.write(orig_blocklist)
            except Exception:
                pass


if __name__ == "__main__":
    run_tests()
