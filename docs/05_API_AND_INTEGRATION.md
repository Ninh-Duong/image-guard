# 🔌 05 - REST API Specification & Integration Guide

This document provides the complete HTTP REST API specification for `image-guard` alongside client integration snippets for mobile frameworks (Flutter, React Native) and backend services.

---

## 1. API Endpoints Overview

| Method | Endpoint | Description | Auth |
| :---: | :--- | :--- | :---: |
| `POST` | `/check` (or `/guard`) | Ingest photo for content moderation & user profiling | None (Local Edge) |
| `GET` | `/rules` | Fetch active moderation thresholds (`max_nsfw`, `min_safe`...) | None |
| `GET` | `/blocklist` | Export current list of banned perceptual dHashes | None |
| `POST` | `/blocklist` | Manually append a hash to the persistent blocklist | None |
| `GET` | `/languages` | Fetch supported locales (`vi`, `en`, `ja`, `ko`) & sample timezones | None |
| `GET` | `/logs/latest` | Inspect microsecond execution trace of the most recent request | None |
| `GET` | `/logs/summary` | Query aggregate rolling metrics (P50, P95, bottlenecks) | None |
| `GET` | `/` | Web UI Playground & interactive testing console | None |

---

## 2. Image Inspection Endpoint: `POST /check`

### 1. Request Details
- **Headers**:
  - `Content-Type: image/jpeg`, `image/png`, `application/octet-stream`, or `multipart/form-data`
- **Query Parameters**:
  - `lang` *(optional, string)*: Output language: `vi` (default), `en`, `ja`, `ko`.
  - `tz` *(optional, string)*: Client device timezone (e.g. `Asia/Ho_Chi_Minh`, `+07:00`, `America/New_York`).
- **Body**: Binary image payload (Hard ceiling: `20MB`).

### 2. Response: 200 OK (Clean Image Approved)
```json
{
  "is_allowed": true,
  "status": "APPROVED",
  "dhash": "0x1818181818000000",
  "guard_scores": {
    "safe": 0.9962,
    "nsfw": 0.0038
  },
  "user_profile": {
    "primary_interest": "signboard_and_commercial",
    "interest_label": "Biển hiệu & Bảng quảng cáo",
    "confidence": 0.9,
    "detected_objects": ["signboard", "text_spotting"],
    "people_count": 0,
    "social_setting": "no_person",
    "scene_summary": "Phát hiện thông tin bảng hiệu / thương mại: Bourbon"
  },
  "note_metadata": {
    "suggested_caption": "Dừng chân ghi lại một bảng hiệu / địa điểm trên hành trình 📍",
    "lifestyle_tags": ["#BienQuangCao", "#DiaDiem", "#CheckIn", "#DoanhNghiep"],
    "object_tags": ["#Bourbon"],
    "merged_tags": ["#BienQuangCao", "#DiaDiem", "#CheckIn", "#Bourbon", "#DoanhNghiep"],
    "time_context": {
      "timezone": "Asia/Ho_Chi_Minh",
      "local_time": "2026-10-03T16:20:00+07:00",
      "time_of_day": "afternoon"
    }
  },
  "trace_id": "trace_20261003_092000_a1b2c3",
  "latency_ms": 42.15
}
```

### 3. Response: 200 OK (NSFW Violation - Fail-Fast Early Exit)
> When a violation occurs, the **Fail-Fast** protocol sets `user_profile` and `note_metadata` to `null` to minimize CPU utilization:
```json
{
  "is_allowed": false,
  "status": "BLOCKED",
  "reason": "NSFW_VIOLATION",
  "dhash": "0xa3c8f1e2903b41d5",
  "guard_scores": {
    "safe": 0.0512,
    "nsfw": 0.9488
  },
  "user_profile": null,
  "note_metadata": null,
  "trace_id": "trace_20261003_092100_f4e5d6",
  "latency_ms": 18.42
}
```

---

## 3. Client Integration Code Snippets

### 1. cURL
```bash
curl -X POST "http://localhost:8000/check?lang=en&tz=America/New_York" \
     -H "Content-Type: image/jpeg" \
     --data-binary "@vacation_photo.jpg"
```

### 2. Flutter / Dart (Mobile Application)
```dart
import 'dart:io';
import 'package:http/http.dart' as http;

Future<void> uploadMemoryPhoto(File imageFile) async {
  final uri = Uri.parse('http://10.0.2.2:8000/check?lang=en&tz=America/New_York');
  
  final bytes = await imageFile.readAsBytes();
  final response = await http.post(
    uri,
    headers: {'Content-Type': 'image/jpeg'},
    body: bytes,
  );

  if (response.statusCode == 200) {
    print('Guard result: ${response.body}');
  } else if (response.statusCode == 413) {
    print('Payload exceeded maximum limit (20MB)');
  }
}
```

### 3. React Native / TypeScript
```typescript
export async function verifyAndProfileImage(imageUri: string) {
  const response = await fetch('http://localhost:8000/check?lang=en&tz=America/New_York', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/octet-stream',
    },
    body: {
      uri: imageUri,
      type: 'image/jpeg',
      name: 'photo.jpg',
    } as any,
  });

  const result = await response.json();
  if (!result.is_allowed) {
    alert('Upload rejected: ' + result.reason);
    return null;
  }
  return result;
}
```

### 4. Python Backend Service
```python
import requests

with open("photo.jpg", "rb") as f:
    resp = requests.post(
        "http://localhost:8000/check",
        params={"lang": "en", "tz": "America/New_York"},
        data=f.read(),
        headers={"Content-Type": "image/jpeg"}
    )
data = resp.json()
print("Allowed:", data["is_allowed"])
print("Suggested Caption:", data["note_metadata"]["suggested_caption"])
```
