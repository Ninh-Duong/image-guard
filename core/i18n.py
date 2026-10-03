"""
core/i18n.py - Internationalization (i18n) and Timezone Engine for Image Guard.
Provides language localization (VI, EN, JA, KO), timezone resolution, time-of-day contextual tagging,
and localized taxonomy mappings for user profiling and DB persistence.
"""
from typing import Dict, Any, List, Set, Tuple, Optional
from datetime import datetime, timezone, timedelta
import re

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception


# =====================================================================
# SOURCE SUPPORTED LANGUAGES METADATA
# =====================================================================

SUPPORTED_LANGUAGES: Dict[str, Dict[str, Any]] = {
    "vi": {
        "code": "vi",
        "name": "Tiếng Việt (Vietnamese)",
        "native_name": "Tiếng Việt",
        "flag": "🇻🇳",
        "is_default": True,
        "description": "Ngôn ngữ mặc định cho ứng dụng kỷ niệm tại Việt Nam",
    },
    "en": {
        "code": "en",
        "name": "English (International)",
        "native_name": "English",
        "flag": "🇺🇸",
        "is_default": False,
        "description": "Global English standard for international audience",
    },
    "ja": {
        "code": "ja",
        "name": "日本語 (Japanese)",
        "native_name": "日本語",
        "flag": "🇯🇵",
        "is_default": False,
        "description": "日本市場向けの自然なライフスタイル＆キャプション",
    },
    "ko": {
        "code": "ko",
        "name": "한국어 (Korean)",
        "native_name": "한국어",
        "flag": "🇰🇷",
        "is_default": False,
        "description": "한국 사용자를 위한 일상 기록 및 인스타그램 감성 태그",
    },
}

DEFAULT_LANGUAGE = "vi"
DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"


def get_supported_languages() -> List[Dict[str, Any]]:
    """Returns the list of languages natively supported by the source engine."""
    return list(SUPPORTED_LANGUAGES.values())


def resolve_timezone(tz_name: Optional[str] = None) -> Tuple[str, Any]:
    """
    Safely resolves timezone from IANA string ('Asia/Ho_Chi_Minh', 'Asia/Tokyo'),
    offset ('+07:00', 'UTC+7'), or falls back to DEFAULT_TIMEZONE.
    Returns (normalized_name, tz_object).
    """
    if not tz_name or not tz_name.strip():
        tz_name = DEFAULT_TIMEZONE

    cleaned = tz_name.strip()

    # 1. Try ZoneInfo (standard IANA)
    if ZoneInfo is not None:
        try:
            return cleaned, ZoneInfo(cleaned)
        except Exception:
            pass

    # 2. Try parsing offset strings: '+07:00', '-05:00', 'UTC+7', 'GMT-4'
    offset_match = re.search(r'([+-])(\d{1,2})(?::?(\d{2}))?', cleaned)
    if offset_match:
        sign = 1 if offset_match.group(1) == '+' else -1
        hours = int(offset_match.group(2))
        mins = int(offset_match.group(3) or 0)
        tz_obj = timezone(sign * timedelta(hours=hours, minutes=mins))
        return cleaned, tz_obj

    # 3. Handle UTC directly
    if cleaned.upper() in ("UTC", "GMT", "Z"):
        return "UTC", timezone.utc

    # 4. Fallback to Asia/Ho_Chi_Minh or UTC
    if ZoneInfo is not None:
        try:
            return DEFAULT_TIMEZONE, ZoneInfo(DEFAULT_TIMEZONE)
        except Exception:
            pass

    # Safe stdlib fallback: UTC+7 for Vietnam
    return DEFAULT_TIMEZONE, timezone(timedelta(hours=7))


def resolve_language(
    lang: Optional[str] = None,
    accept_language: Optional[str] = None,
    tz_name: Optional[str] = None,
) -> str:
    """
    Resolves client language preference with graceful fallback.
    Order of precedence:
    1. Explicit query parameter `lang` (e.g. 'vi', 'en', 'ja', 'ko')
    2. HTTP `Accept-Language` header
    3. Inferred language from timezone (e.g. Asia/Tokyo -> 'ja', Asia/Seoul -> 'ko')
    4. DEFAULT_LANGUAGE ('vi')
    """
    if lang:
        code = lang.strip().lower()[:2]
        if code in SUPPORTED_LANGUAGES:
            return code

    if accept_language:
        # e.g. "vi-VN,vi;q=0.9,en-US;q=0.8,ja;q=0.7"
        for part in accept_language.split(","):
            token = part.split(";")[0].strip().lower()
            code = token[:2]
            if code in SUPPORTED_LANGUAGES:
                return code

    if tz_name:
        tz_lower = tz_name.lower()
        if any(c in tz_lower for c in ["ho_chi_minh", "saigon", "vietnam"]):
            return "vi"
        if any(c in tz_lower for c in ["tokyo", "japan"]):
            return "ja"
        if any(c in tz_lower for c in ["seoul", "korea"]):
            return "ko"
        if any(c in tz_lower for c in ["new_york", "london", "chicago", "los_angeles", "sydney", "toronto"]):
            return "en"

    return DEFAULT_LANGUAGE


def get_time_of_day(now_dt: datetime) -> str:
    """Returns 'morning', 'afternoon', 'evening', or 'night' based on local hour."""
    hour = now_dt.hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"


# =====================================================================
# LOCALIZED DICTIONARIES (VI / EN / JA / KO)
# =====================================================================

TIME_OF_DAY_CONFIG = {
    "vi": {
        "morning": {"tags": ["#BuoiSang", "#ChaoNgayMoi"], "label": "Buổi sáng"},
        "afternoon": {"tags": ["#BuoiChieu", "#ChieuHoangHon"], "label": "Buổi chiều"},
        "evening": {"tags": ["#BuoiToi", "#GocToi"], "label": "Buổi tối"},
        "night": {"tags": ["#DemMuon", "#NightOwl"], "label": "Đêm muộn"},
    },
    "en": {
        "morning": {"tags": ["#MorningVibes", "#StartTheDay"], "label": "Morning"},
        "afternoon": {"tags": ["#AfternoonVibes", "#GoldenHour"], "label": "Afternoon"},
        "evening": {"tags": ["#EveningVibes", "#NightOut"], "label": "Evening"},
        "night": {"tags": ["#LateNight", "#NightOwl"], "label": "Night"},
    },
    "ja": {
        "morning": {"tags": ["#朝の風景", "#おはよう"], "label": "朝"},
        "afternoon": {"tags": ["#午後のひととき", "#夕暮れ"], "label": "午後"},
        "evening": {"tags": ["#夜の風景", "#ディナータイム"], "label": "夕方・夜"},
        "night": {"tags": ["#深夜", "#夜更かし"], "label": "深夜"},
    },
    "ko": {
        "morning": {"tags": ["#아침감성", "#좋은아침"], "label": "아침"},
        "afternoon": {"tags": ["#오후의여유", "#노을"], "label": "오후"},
        "evening": {"tags": ["#저녁시간", "#나이트라이프"], "label": "저녁"},
        "night": {"tags": ["#심야", "#밤샘"], "label": "심야"},
    },
}

CATEGORIES_I18N = {
    "food_and_dining": {
        "objects": {
            "pizza", "sandwich", "cake", "donut", "hot dog", "apple", "banana", "orange",
            "broccoli", "carrot", "bowl", "cup", "bottle", "wine glass", "fork", "knife",
            "spoon", "dining table"
        },
        "vi": {
            "label": "Ẩm thực & Thưởng thức món ngon",
            "primary_tag": "#AmThuc",
            "tags": ["#Foodie", "#AnUong", "#NgonMoiNgay", "#CafeChill"],
            "caption": "Một bữa ăn thật ngon để nạp đầy năng lượng và tận hưởng trọn vẹn hương vị cuộc sống! 🍜🍰",
        },
        "en": {
            "label": "Food & Dining Experience",
            "primary_tag": "#FoodAndDining",
            "tags": ["#Foodie", "#Delicious", "#FoodPhotography", "#CafeChill"],
            "caption": "A delightful meal to recharge energy and savor every moment of life! 🍜🍰",
        },
        "ja": {
            "label": "グルメ＆美味しい食事",
            "primary_tag": "#グルメ",
            "tags": ["#Foodie", "#美味しい", "#カフェ巡り", "#ごちそう"],
            "caption": "エネルギーを満たし、人生の美味しさを楽しむ最高の一杯！🍜🍰",
        },
        "ko": {
            "label": "미식 & 맛집 탐방",
            "primary_tag": "#맛집",
            "tags": ["#Foodie", "#먹스타그램", "#맛있다", "#카페투어"],
            "caption": "에너지를 충전하고 인생의 맛을 만끽하는 맛있는 식사! 🍜🍰",
        },
    },
    "work_and_study": {
        "objects": {"laptop", "keyboard", "mouse", "cell phone", "book"},
        "vi": {
            "label": "Làm việc & Học tập / Công nghệ",
            "primary_tag": "#CongNghe",
            "tags": ["#WorkHard", "#StudyGram", "#TechLife", "#NangSuat"],
            "caption": "Tập trung cao độ cho mục tiêu hôm nay. Cố gắng mỗi ngày một chút để chạm tới thành công! 💻📚",
        },
        "en": {
            "label": "Work & Study / Technology",
            "primary_tag": "#TechLife",
            "tags": ["#WorkHard", "#StudyGram", "#Productivity", "#TechLife"],
            "caption": "Fully focused on today's goals. Small steps every day lead to great success! 💻📚",
        },
        "ja": {
            "label": "仕事＆勉強 / テクノロジー",
            "primary_tag": "#仕事効率化",
            "tags": ["#WorkHard", "#勉強垢", "#TechLife", "#集中"],
            "caption": "今日の目標に向けて全集中。毎日の積み重ねが成功への道！💻📚",
        },
        "ko": {
            "label": "업무 & 공부 / 테크",
            "primary_tag": "#열일",
            "tags": ["#WorkHard", "#공스타그램", "#TechLife", "#생산성"],
            "caption": "오늘의 목표에 집중. 매일의 작은 노력이 성공으로 이어집니다! 💻📚",
        },
    },
    "movies_and_chill": {
        "objects": {"tv", "remote", "couch", "bed"},
        "vi": {
            "label": "Xem phim & Giải trí thư giãn",
            "primary_tag": "#GiaiTri",
            "tags": ["#MovieBuff", "#ChillAtHome", "#ThuGianCuoiTuan", "#Cozy"],
            "caption": "Góc bình yên cuối ngày, bật bộ phim yêu thích và thả lỏng tâm hồn 🎬🍿",
        },
        "en": {
            "label": "Movies & Entertainment Chill",
            "primary_tag": "#Entertainment",
            "tags": ["#MovieBuff", "#ChillAtHome", "#WeekendVibes", "#Cozy"],
            "caption": "A peaceful corner at the end of the day, watching a favorite movie and unwinding 🎬🍿",
        },
        "ja": {
            "label": "映画＆リラックス",
            "primary_tag": "#映画鑑賞",
            "tags": ["#MovieBuff", "#おうち時間", "#リラックス", "#まったり"],
            "caption": "一日の終わりに好きな映画を観て心を癒やすひととき 🎬🍿",
        },
        "ko": {
            "label": "영화 & 힐링 휴식",
            "primary_tag": "#영화",
            "tags": ["#MovieBuff", "#홈캉스", "#주말힐링", "#포근함"],
            "caption": "하루의 끝, 좋아하는 영화를 보며 마음을 편안하게 🎬🍿",
        },
    },
    "travel_and_explore": {
        "objects": {
            "airplane", "bus", "train", "boat", "suitcase", "backpack", "car", "motorcycle", "bicycle"
        },
        "vi": {
            "label": "Du lịch & Khám phá / Di chuyển",
            "primary_tag": "#DuLich",
            "tags": ["#Traveler", "#DiVaTraiNghiem", "#Wanderlust", "#ChuyenDiKiniem"],
            "caption": "Xách ba lô lên và đi! Cuộc đời là những chuyến đi và lưu giữ từng khoảnh khắc đáng nhớ ✈️🎒",
        },
        "en": {
            "label": "Travel & Exploration",
            "primary_tag": "#Travel",
            "tags": ["#Traveler", "#Wanderlust", "#Adventure", "#Memories"],
            "caption": "Pack your bags and explore! Life is a journey made of unforgettable moments ✈️🎒",
        },
        "ja": {
            "label": "旅行＆探検 / お出かけ",
            "primary_tag": "#旅行",
            "tags": ["#Traveler", "#旅の思い出", "#お出かけ", "#旅写真"],
            "caption": "リュックを背負って旅へ出よう！人生は忘れられない思い出の積み重ね ✈️🎒",
        },
        "ko": {
            "label": "여행 & 탐험 / 나들이",
            "primary_tag": "#여행",
            "tags": ["#Traveler", "#여행스타그램", "#추억", "#떠나요"],
            "caption": "배낭을 메고 떠나요! 잊지 못할 추억들로 가득한 인생의 여정 ✈️🎒",
        },
    },
    "pet_lover": {
        "objects": {"dog", "cat", "bird", "horse", "sheep", "cow"},
        "vi": {
            "label": "Yêu thú cưng & Động vật",
            "primary_tag": "#ThuCung",
            "tags": ["#PetLover", "#BossVaSen", "#KhoanhKhacDangYeu", "#Petstagram"],
            "caption": "Niềm vui giản dị mỗi ngày chính là được ở bên người bạn bốn chân đáng yêu này 🐾❤️",
        },
        "en": {
            "label": "Pet Lovers & Animals",
            "primary_tag": "#PetLover",
            "tags": ["#PetLover", "#FurryFriend", "#CuteMoments", "#Petstagram"],
            "caption": "Simple daily happiness is spending time with this lovely companion 🐾❤️",
        },
        "ja": {
            "label": "ペット愛好＆動物",
            "primary_tag": "#ペット",
            "tags": ["#PetLover", "#可愛い", "#愛犬", "#愛猫"],
            "caption": "日常の小さな幸せは、この愛らしい仲間と一緒に過ごす時間 🐾❤️",
        },
        "ko": {
            "label": "반려동물 & 동물 사랑",
            "primary_tag": "#반려동물",
            "tags": ["#PetLover", "#댕댕이", "#냥스타그램", "#귀여워"],
            "caption": "소소한 일상의 행복은 사랑스러운 네 발 친구와 함께하는 것 🐾❤️",
        },
    },
    "sports_and_fitness": {
        "objects": {
            "sports ball", "frisbee", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket"
        },
        "vi": {
            "label": "Thể thao & Lối sống năng động",
            "primary_tag": "#TheThao",
            "tags": ["#ActiveLife", "#TheThao", "#Fitness", "#KhoeMoiNgay"],
            "caption": "Năng lượng tích cực và rèn luyện thể chất để luôn tràn đầy sức sống! ⚽🎾",
        },
        "en": {
            "label": "Sports & Active Lifestyle",
            "primary_tag": "#Sports",
            "tags": ["#ActiveLife", "#Sports", "#Fitness", "#HealthyLiving"],
            "caption": "Positive energy and staying active to live life to the fullest! ⚽🎾",
        },
        "ja": {
            "label": "スポーツ＆アクティブライフ",
            "primary_tag": "#スポーツ",
            "tags": ["#ActiveLife", "#スポーツ", "#フィットネス", "#健康"],
            "caption": "ポジティブなエネルギーと運動で、毎日を元気に楽しもう！⚽🎾",
        },
        "ko": {
            "label": "스포츠 & 액티브 라이프",
            "primary_tag": "#운동",
            "tags": ["#ActiveLife", "#운동스타그램", "#피트니스", "#오운완"],
            "caption": "긍정적인 에너지와 운동으로 활기찬 하루를! ⚽🎾",
        },
    },
}

DEFAULT_INTERESTS_I18N = {
    "vi": {
        "social_and_community": {
            "label": "Hoạt động xã hội / Gặp gỡ bạn bè / Từ thiện",
            "primary_tag": "#ThienNguyen",
            "tags": ["#LanToaYeuThuong", "#BanBe", "#KyNiemVuiVe"],
            "caption": "Kỷ niệm tuyệt vời cùng những người bạn đồng hành tràn đầy nhiệt huyết! ✨🤝",
        },
        "lifestyle_portrait": {
            "label": "Lối sống & Kỷ niệm thường nhật",
            "primary_tag": "#ChanDung",
            "tags": ["#DailyLife", "#KhoanhKhac", "#GocBinhYen"],
            "caption": "Lưu giữ một góc kỷ niệm đẹp của ngày hôm nay ✨",
        },
        "signboard_and_commercial": {
            "label": "Biển hiệu & Bảng quảng cáo",
            "primary_tag": "#BienQuangCao",
            "tags": ["#BienHieu", "#DoanhNghiep", "#DiaDiem", "#CheckIn"],
            "caption": "Dừng chân ghi lại một bảng hiệu / địa điểm trên hành trình 📍",
        },
        "screenshot_and_app": {
            "label": "Ảnh chụp màn hình & Ứng dụng",
            "primary_tag": "#Screenshot",
            "tags": ["#ChupManHinh", "#LuuTru", "#GhiNho", "#ManHinh"],
            "caption": "Lưu giữ một ảnh chụp màn hình quan trọng cần nhớ 📱",
        },
        "document_and_receipt": {
            "label": "Hóa đơn & Tài liệu ghi nhớ",
            "primary_tag": "#HoaDon",
            "tags": ["#ChungTu", "#ChiTieu", "#CheckOut", "#GhiNho"],
            "caption": "Lưu lại hóa đơn và chi tiêu cần nhớ 🧾",
        },
        "sunset_and_nature": {
            "label": "Hoàng hôn & Thiên nhiên bầu trời",
            "primary_tag": "#HoangHon",
            "tags": ["#BinhMinh", "#ThienNhien", "#GocBinhYen", "#MauTroi"],
            "caption": "Bầu trời hoàng hôn êm ả buông nắng cuối ngày 🌅",
        },
        "general_photo": {
            "label": "Không gian & Cảnh vật",
            "primary_tag": "#PhongCanh",
            "tags": ["#PhotoOfTheDay", "#KhongGian", "#GocNhin"],
            "caption": "Một khoảnh khắc bình dị được ghi lại qua ống kính 📷",
        },
    },
    "en": {
        "social_and_community": {
            "label": "Social Gathering & Community Event",
            "primary_tag": "#Community",
            "tags": ["#Together", "#Friends", "#GoodVibes"],
            "caption": "Great memories shared with wonderful and inspiring friends! ✨🤝",
        },
        "lifestyle_portrait": {
            "label": "Lifestyle & Daily Memories",
            "primary_tag": "#Portrait",
            "tags": ["#DailyLife", "#Moments", "#PeacefulCorner"],
            "caption": "Capturing a beautiful memory of today ✨",
        },
        "signboard_and_commercial": {
            "label": "Signboard & Commercial Landmark",
            "primary_tag": "#Signboard",
            "tags": ["#Billboard", "#Landmark", "#Commercial", "#TravelSign"],
            "caption": "Noticing a notable landmark and signboard along the way 📍",
        },
        "screenshot_and_app": {
            "label": "Screenshot & App Screen",
            "primary_tag": "#Screenshot",
            "tags": ["#ScreenCapture", "#Memory", "#SaveForLater", "#DigitalLife"],
            "caption": "Saved an important screenshot for future reference 📱",
        },
        "document_and_receipt": {
            "label": "Receipt & Document Memory",
            "primary_tag": "#Receipt",
            "tags": ["#Invoice", "#Expenses", "#Document", "#CheckOut"],
            "caption": "Recorded a receipt and expense note 🧾",
        },
        "sunset_and_nature": {
            "label": "Sunset & Nature Sky",
            "primary_tag": "#Sunset",
            "tags": ["#GoldenHour", "#SkyLovers", "#NatureVibes", "#Peaceful"],
            "caption": "Golden sunset glowing quietly across the sky 🌅",
        },
        "general_photo": {
            "label": "Scenery & Atmosphere",
            "primary_tag": "#Scenery",
            "tags": ["#PhotoOfTheDay", "#Perspective", "#Atmosphere"],
            "caption": "A peaceful moment captured through the lens 📷",
        },
    },
    "ja": {
        "social_and_community": {
            "label": "ソーシャルイベント / 仲間と集い / ボランティア",
            "primary_tag": "#仲間",
            "tags": ["#友達", "#最高の仲間", "#楽しい時間"],
            "caption": "情熱あふれる仲間たちと過ごす素晴らしい思い出！✨🤝",
        },
        "lifestyle_portrait": {
            "label": "ライフスタイル＆日常の記録",
            "primary_tag": "#日常",
            "tags": ["#DailyLife", "#日常の風景", "#思い出"],
            "caption": "今日の素敵なひとコマを写真に残して ✨",
        },
        "signboard_and_commercial": {
            "label": "看板＆商業ランドマーク",
            "primary_tag": "#看板",
            "tags": ["#看板デザイン", "#ランドマーク", "#スポット", "#街歩き"],
            "caption": "道中で見かけた印象的な看板やランドマークを記録 📍",
        },
        "screenshot_and_app": {
            "label": "スクリーンショット＆アプリ画面",
            "primary_tag": "#スクショ",
            "tags": ["#スクリーンショット", "#メモ", "#記録", "#スマホ"],
            "caption": "大切なスクリーンショットを記録として保存 📱",
        },
        "document_and_receipt": {
            "label": "レシート＆書類メモ",
            "primary_tag": "#レシート",
            "tags": ["#領収書", "#出費記録", "#書類", "#メモ"],
            "caption": "大切なレシートや書類を記録として保存 🧾",
        },
        "sunset_and_nature": {
            "label": "夕暮れ＆夕焼け空",
            "primary_tag": "#夕焼け",
            "tags": ["#夕暮れ", "#空が好き", "#黄昏時", "#癒やし"],
            "caption": "一日の終わりに静かに広がる夕焼けの空 🌅",
        },
        "general_photo": {
            "label": "風景＆雰囲気",
            "primary_tag": "#風景",
            "tags": ["#PhotoOfTheDay", "#風景写真", "#癒やし"],
            "caption": "レンズ越しに切り取った穏やかな瞬間 📷",
        },
    },
    "ko": {
        "social_and_community": {
            "label": "모임 & 친구 / 커뮤니티",
            "primary_tag": "#모임",
            "tags": ["#친구들", "#우정", "#추억만들기"],
            "caption": "열정 넘치는 친구들과 함께한 최고의 추억! ✨🤝",
        },
        "lifestyle_portrait": {
            "label": "라이프스타일 & 일상 기록",
            "primary_tag": "#일상",
            "tags": ["#DailyLife", "#일상기록", "#소소한행복"],
            "caption": "오늘의 아름다운 추억 한 조각을 담아 ✨",
        },
        "signboard_and_commercial": {
            "label": "간판 & 랜드마크 기록",
            "primary_tag": "#간판",
            "tags": ["#간판스타그램", "#랜드마크", "#스팟", "#길거리"],
            "caption": "길에서 마주친 인상적인 간판과 랜드마크를 기록 📍",
        },
        "screenshot_and_app": {
            "label": "스크린샷 & 앱 화면",
            "primary_tag": "#스크린샷",
            "tags": ["#캡처", "#메모", "#기록", "#스마트폰"],
            "caption": "중요한 화면 캡처를 기록으로 저장 📱",
        },
        "document_and_receipt": {
            "label": "영수증 & 문서 기록",
            "primary_tag": "#영수증",
            "tags": ["#지출기록", "#가계부", "#문서", "#메모"],
            "caption": "기억해둘 영수증과 지출 내역을 기록 🧾",
        },
        "sunset_and_nature": {
            "label": "노을 & 일몰 하늘",
            "primary_tag": "#노을",
            "tags": ["#일몰", "#하늘스타그램", "#골든아워", "#힐링"],
            "caption": "하루의 끝자락을 물들이는 아름다운 노을 🌅",
        },
        "general_photo": {
            "label": "풍경 & 감성 분위기",
            "primary_tag": "#풍경",
            "tags": ["#PhotoOfTheDay", "#풍경스타그램", "#감성사진"],
            "caption": "렌즈를 통해 담아낸 평온한 순간 📷",
        },
    },
}

ENTITY_TAGS_I18N = {
    "vi": {
        "person": "#Nguoi", "pizza": "#Pizza", "sandwich": "#BanhMi", "cake": "#BanhKem",
        "donut": "#BanhDonut", "hot dog": "#HotDog", "apple": "#TraiCay", "banana": "#Chuoi",
        "orange": "#Cam", "bowl": "#ToBat", "cup": "#CaPhe", "bottle": "#DoUong",
        "wine glass": "#RuouVang", "dining table": "#BanAn", "laptop": "#Laptop",
        "keyboard": "#BanPhim", "mouse": "#ChuotMayTinh", "cell phone": "#DienThoai",
        "book": "#SachHay", "tv": "#XemTV", "remote": "#DieuKhien", "couch": "#Sofa",
        "bed": "#GiuongNgu", "airplane": "#MayBay", "bus": "#XeBus", "train": "#TauHoa",
        "boat": "#Thuyen", "suitcase": "#Vali", "backpack": "#BaLo", "car": "#XeHoi",
        "motorcycle": "#XeMay", "bicycle": "#XeDap", "dog": "#CunYeu", "cat": "#MeoMeo",
        "bird": "#ChimCanh", "sports ball": "#BongDa", "tennis racket": "#Tennis",
        "skateboard": "#TruotVan", "surfboard": "#LuotSong",
    },
    "en": {
        "person": "#People", "pizza": "#Pizza", "sandwich": "#Sandwich", "cake": "#Cake",
        "donut": "#Donut", "hot dog": "#HotDog", "apple": "#Fruit", "banana": "#Banana",
        "orange": "#Orange", "bowl": "#MealBowl", "cup": "#CoffeeTime", "bottle": "#Drink",
        "wine glass": "#WineTime", "dining table": "#DiningTable", "laptop": "#Laptop",
        "keyboard": "#Keyboard", "mouse": "#TechSetup", "cell phone": "#Mobile",
        "book": "#GoodRead", "tv": "#WatchTV", "remote": "#RemoteControl", "couch": "#CozySofa",
        "bed": "#BedTime", "airplane": "#Flight", "bus": "#BusTrip", "train": "#TrainRide",
        "boat": "#BoatTrip", "suitcase": "#Suitcase", "backpack": "#Backpack", "car": "#RoadTrip",
        "motorcycle": "#Motorcycle", "bicycle": "#Cycling", "dog": "#DogLover", "cat": "#CatLover",
        "bird": "#Birds", "sports ball": "#SportsBall", "tennis racket": "#Tennis",
        "skateboard": "#Skateboarding", "surfboard": "#Surfing",
    },
    "ja": {
        "person": "#人物", "pizza": "#ピザ", "sandwich": "#サンドイッチ", "cake": "#ケーキ",
        "donut": "#ドーナツ", "hot dog": "#ホットドッグ", "apple": "#りんご", "banana": "#バナナ",
        "orange": "#みかん", "bowl": "#丼", "cup": "#コーヒー", "bottle": "#ドリンク",
        "wine glass": "#ワイン", "dining table": "#食卓", "laptop": "#ノートPC",
        "keyboard": "#キーボード", "mouse": "#PCマウス", "cell phone": "#スマホ",
        "book": "#読書", "tv": "#テレビ", "remote": "#リモコン", "couch": "#ソファ",
        "bed": "#ベッド", "airplane": "#飛行機", "bus": "#バス", "train": "#電車",
        "boat": "#船", "suitcase": "#スーツケース", "backpack": "#リュック", "car": "#ドライブ",
        "motorcycle": "#バイク", "bicycle": "#自転車", "dog": "#愛犬", "cat": "#愛猫",
        "bird": "#小鳥", "sports ball": "#スポーツ", "tennis racket": "#テニス",
        "skateboard": "#スケボー", "surfboard": "#サーフィン",
    },
    "ko": {
        "person": "#사람", "pizza": "#피자", "sandwich": "#샌드위치", "cake": "#케이크",
        "donut": "#도넛", "hot dog": "#핫도그", "apple": "#사과", "banana": "#바나나",
        "orange": "#오렌지", "bowl": "#보울", "cup": "#커피타임", "bottle": "#음료",
        "wine glass": "#와인", "dining table": "#식탁", "laptop": "#노트북",
        "keyboard": "#키보드", "mouse": "#마우스", "cell phone": "#스마트폰",
        "book": "#독서", "tv": "#티비", "remote": "#리모컨", "couch": "#소파",
        "bed": "#침대", "airplane": "#비행기", "bus": "#버스", "train": "#기차",
        "boat": "#보트", "suitcase": "#캐리어", "backpack": "#백팩", "car": "#드라이브",
        "motorcycle": "#오토바이", "bicycle": "#자전거", "dog": "#댕댕이", "cat": "#냥이",
        "bird": "#새", "sports ball": "#공놀이", "tennis racket": "#테니스",
        "skateboard": "#스케이트보드", "surfboard": "#서핑",
    },
}

SOCIAL_CONTEXT_I18N = {
    "vi": {
        "no_people": {"tags": ["#PhongCanh", "#TinhVat"], "description": "Ảnh phong cảnh / Tĩnh vật / Không có người"},
        "solo": {"tags": ["#Solo", "#ChinhMinh"], "description": "Ảnh chân dung một mình / Cá nhân"},
        "duo": {"tags": ["#DoiBanThan", "#HenHo", "#CapDoi"], "description": "Cặp đôi / Đôi bạn thân"},
        "group": {"tags": ["#HoiBanThan", "#GiaDinh", "#TuTap"], "description_template": "Nhóm bạn bè / Gia đình ({count} người)"},
        "crowd": {"tags": ["#SuKien", "#DongNguoi", "#HoatDongTapThe"], "description_template": "Sự kiện / Hoạt động tập thể / Đám đông ({count} người)"},
    },
    "en": {
        "no_people": {"tags": ["#Scenery", "#StillLife"], "description": "Scenery / Still life / No people"},
        "solo": {"tags": ["#Solo", "#Myself"], "description": "Portrait / Solo moment"},
        "duo": {"tags": ["#Besties", "#Couple", "#Together"], "description": "Couple / Best friends duo"},
        "group": {"tags": ["#SquadGoals", "#Family", "#Friends"], "description_template": "Friends / Family group ({count} people)"},
        "crowd": {"tags": ["#Community", "#Event", "#Crowd"], "description_template": "Community event / Crowd gathering ({count} people)"},
    },
    "ja": {
        "no_people": {"tags": ["#風景写真", "#静物"], "description": "風景 / 静物 / 人物なし"},
        "solo": {"tags": ["#ソロ", "#自分時間"], "description": "ソロショット / 個人ポートレート"},
        "duo": {"tags": ["#親友", "#カップル", "#ふたり"], "description": "カップル / 親友ツーショット"},
        "group": {"tags": ["#仲間", "#家族", "#仲良し"], "description_template": "友人グループ / 家族 ({count}人)"},
        "crowd": {"tags": ["#イベント", "#集合写真", "#賑やか"], "description_template": "コミュニティイベント / 人混み ({count}人)"},
    },
    "ko": {
        "no_people": {"tags": ["#풍경스타그램", "#정물"], "description": "풍경 / 정물 / 사람 없음"},
        "solo": {"tags": ["#혼자서", "#나만의시간"], "description": "개인 프로필 / 솔로 샷"},
        "duo": {"tags": ["#절친", "#커플", "#우정"], "description": "커플 / 절친 투샷"},
        "group": {"tags": ["#친구들", "#가족", "#우정스타그램"], "description_template": "친구 모임 / 가족 ({count}명)"},
        "crowd": {"tags": ["#이벤트", "#단체사진", "#북적북적"], "description_template": "단체 행사 / 많은 사람들 ({count}명)"},
    },
}
