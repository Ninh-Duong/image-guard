# 🏷️ 04 - Personality Taxonomy & Multilingual Engine (Taxonomy & i18n)

This document defines the user personality taxonomy, social setting classifications, automated caption/tag generation rules, and the multilingual & timezone engine.

---

## 1. 11 Primary Interest Categories (Taxonomy)

The engine analyzes visual entities detected by YOLOv8 and the Multi-Signal Visual Analyzer to assign lifestyle profile attributes:

| Primary Interest ID (`primary_interest`) | Display Label (English) | Trigger Entities / Signals | Social / App Significance |
| :--- | :--- | :--- | :--- |
| `food_and_dining` | **Food & Culinary Delights** | `pizza, sandwich, cake, bowl, cup, wine glass, dining table` | Culinary lover, cafe hopping, dining experiences |
| `work_and_study` | **Work & Tech Productivity** | `laptop, keyboard, mouse, cell phone, book` | Career-oriented, productive, tech enthusiast |
| `movies_and_chill` | **Movies & Cozy Entertainment** | `tv, remote, couch, bed` | Home chill, movie buff, relaxing at home |
| `travel_and_explore` | **Travel & Adventure** | `airplane, bus, train, boat, suitcase, backpack, bicycle, car` | Wanderlust, active traveler, road trips |
| `pet_lover` | **Pets & Animal Companions** | `dog, cat, bird, horse, sheep, cow` | Pet owner, animal lover |
| `sports_and_fitness` | **Sports & Healthy Fitness** | `sports ball, baseball bat, tennis racket, skateboard, surfboard` | Active, sports player, fitness enthusiast |
| `social_and_gathering` | **Social Gatherings & Friends** | $\ge 2$ people or dining table combined with multiple persons | Socializer, group gatherings, community events |
| `signboard_and_commercial` | **Billboards & Commercial Signage** | High text density, commercial keywords, domains (`.com`, `.vn`), business names | Check-ins, billboard photography, location info |
| `screenshot_and_app` | **Screenshots & App Interfaces** | Smartphone screen ratio ($> 1.70$), UI text blocks | App bookmarks, visual notes, screen captures |
| `document_and_receipt` | **Documents & Financial Receipts** | Financial keywords (`tong tien`, `vat`, `receipt`, `vnd`), tabulated lines | Expense tracking, receipts, document management |
| `sunset_and_nature` | **Sunsets & Natural Landscapes** | High color warmth ($R/B > 1.40$), sky gradients, landscapes | Nature lover, outdoor scenery, sunset photography |
| `general_photo` | **Life Moments & Scenery (Fallback)**| Does not match specific categories above | Daily memory capture, ambient photography |

---

## 2. Social Setting Detection

Classified dynamically based on the number of detected `person` bounding boxes:

| People Detected (`people_count`) | Context ID (`social_setting`) | English Label | Vietnamese Label | Contextual Tags |
| :---: | :--- | :--- | :--- | :--- |
| $0$ | `no_person` | Still Life / Scenery | Không có người | `#Scenery`, `#Perspective`, `#StillLife` |
| $1$ | `solo` | Solo Moment | Khoảnh khắc một mình | `#Solo`, `#Chill`, `#MeTime` |
| $2$ | `duo` | Duo Moment | Khoảnh khắc hai người | `#Duo`, `#Bestie`, `#Together` |
| $3 - 5$ | `group` | Friends Gathering | Nhóm bạn thân | `#SquadGoals`, `#Friends`, `#Gathering` |
| $> 5$ | `crowd` | Event / Crowd | Đám đông / Sự kiện | `#Crowd`, `#Festival`, `#Event` |

---

## 3. Quad-Language Support (Localization Engine)

The system supports 4 native locales defined centrally in [`core/i18n.py`](file:///d:/Visual%20Studio%20Code/image-guard/core/i18n.py). Clients select target locales via `?lang=...`:

* **`en` (English)**:
  - Label: `"Food & Culinary Delights"`
  - Caption: `"A delicious meal to recharge energy! 🍜🍰"`
  - Tags: `["#Foodie", "#FoodPorn", "#Yummy", "#DiningOut"]`
* **`vi` (Vietnamese - Default)**:
  - Label: `"Ẩm thực & Thưởng thức món ngon"`
  - Caption: `"Một bữa ăn thật ngon để nạp đầy năng lượng! 🍜🍰"`
  - Tags: `["#AmThuc", "#Foodie", "#NgonMoiNgay", "#AnUong"]`
* **`ja` (Japanese - 日本語)**:
  - Label: `"グルメ・美味しい食事"`
  - Caption: `"美味しい食事でエネルギーチャージ！ 🍜🍰"`
  - Tags: `["#グルメ", "#飯テロ", "#美味しい", "#カフェ巡り"]`
* **`ko` (Korean - 한국어)**:
  - Label: `"미식 & 맛있는 식사"`
  - Caption: `"에너지를 충전하는 맛있는 한 끼! 🍜🍰"`
  - Tags: `["#맛집", "#먹스타그램", "#맛있다", "#푸드스타그램"]`

---

## 4. Timezone Engine & Time of Day

Clients provide timezone information via query parameters:
- **IANA Strings**: `?tz=Asia/Ho_Chi_Minh`, `?tz=America/New_York`, `?tz=Asia/Tokyo`
- **UTC Offsets**: `?tz=+07:00`, `?tz=-04:00`, `?tz=+09:00`

### Time of Day Categorization:
| Local Hour ($H$) | Segment (`time_of_day`) | English Tags | Vietnamese Tags |
| :---: | :--- | :--- | :--- |
| $05:00 \le H < 11:00$ | `morning` | `#Morning`, `#StartTheDay`, `#MorningVibes` | `#BuoiSang`, `#NgayMoi`, `#StartTheDay` |
| $11:00 \le H < 14:00$ | `noon` | `#Noon`, `#LunchTime` | `#BuoiTrua`, `#NghiTrua` |
| $14:00 \le H < 18:00$ | `afternoon` | `#Afternoon`, `#SunsetVibes` | `#BuoiChieu`, `#ChieuHoangHon` |
| $18:00 \le H < 22:00$ | `evening` | `#Evening`, `#DinnerTime` | `#BuoiToi`, `#ThuGian` |
| $22:00 \le H < 05:00$ | `night` | `#LateNight`, `#NightVibes` | `#DemMuon`, `#NightOwl` |

---

## 5. Tag Merging & Database-Ready Schema

Tags are merged with strict precedence:
1. **Interest Tags**: Category-level lifestyle tags (`#Foodie`, `#BienQuangCao`).
2. **Object Tags**: Specific detected entities (`#Pizza`, `#Bourbon`).
3. **Social Tags**: Presence count (`#Solo`, `#DoiBanThan`).
4. **Timezone Tags**: Contextual time-of-day tags (`#MorningVibes`, `#ChieuHoangHon`).

The resulting `database_payload` is formatted for immediate storage:
```json
{
  "memory_id": "mem_20261003_091921_c64985",
  "dhash": "0x1818181818000000",
  "moderation_status": "APPROVED",
  "is_allowed": true,
  "guard_scores": {"safe": 0.9962, "nsfw": 0.0038},
  "user_profile": {
    "primary_interest": "signboard_and_commercial",
    "interest_label": "Biển hiệu & Bảng quảng cáo",
    "confidence": 0.9,
    "social_setting": "no_person",
    "people_count": 0,
    "scene_summary": "Phát hiện thông tin bảng hiệu / thương mại: Bourbon"
  },
  "note_metadata": {
    "suggested_caption": "Dừng chân ghi lại một bảng hiệu / địa điểm trên hành trình 📍"
  },
  "tags": {
    "merged_tags": ["#BienQuangCao", "#DiaDiem", "#CheckIn", "#Bourbon", "#DoanhNghiep"],
    "primary_tags": ["#BienQuangCao", "#DiaDiem", "#CheckIn", "#DoanhNghiep"],
    "object_tags": ["#Bourbon"],
    "time_tags": ["#BuoiChieu"]
  }
}
```
