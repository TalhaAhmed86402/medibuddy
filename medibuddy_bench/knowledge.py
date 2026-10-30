"""Static knowledge tables used by the generators and the scorers.

Everything here is *fictional benchmark world* material, loosely modelled on how Korean
healthcare is organised. District centroids are approximate. Clinical content is synthetic,
is NOT medical advice, and must be reviewed by a clinician before any publication
(see docs/REVIEW_GUIDE.md)."""
from __future__ import annotations

# name -> (Korean, lat, lon, region)   approximate centroids
DISTRICTS = {
    "Jongno": ("종로구", 37.5735, 126.9790, "Seoul"),
    "Jung": ("중구", 37.5641, 126.9979, "Seoul"),
    "Yongsan": ("용산구", 37.5326, 126.9900, "Seoul"),
    "Seongdong": ("성동구", 37.5634, 127.0368, "Seoul"),
    "Gwangjin": ("광진구", 37.5385, 127.0824, "Seoul"),
    "Dongdaemun": ("동대문구", 37.5744, 127.0396, "Seoul"),
    "Jungnang": ("중랑구", 37.6063, 127.0927, "Seoul"),
    "Seongbuk": ("성북구", 37.5894, 127.0167, "Seoul"),
    "Gangbuk": ("강북구", 37.6396, 127.0257, "Seoul"),
    "Dobong": ("도봉구", 37.6688, 127.0471, "Seoul"),
    "Nowon": ("노원구", 37.6542, 127.0568, "Seoul"),
    "Eunpyeong": ("은평구", 37.6027, 126.9291, "Seoul"),
    "Seodaemun": ("서대문구", 37.5791, 126.9368, "Seoul"),
    "Mapo": ("마포구", 37.5663, 126.9019, "Seoul"),
    "Yangcheon": ("양천구", 37.5169, 126.8664, "Seoul"),
    "Gangseo": ("강서구", 37.5509, 126.8495, "Seoul"),
    "Guro": ("구로구", 37.4954, 126.8874, "Seoul"),
    "Geumcheon": ("금천구", 37.4519, 126.9020, "Seoul"),
    "Yeongdeungpo": ("영등포구", 37.5264, 126.8963, "Seoul"),
    "Dongjak": ("동작구", 37.5124, 126.9393, "Seoul"),
    "Gwanak": ("관악구", 37.4784, 126.9516, "Seoul"),
    "Seocho": ("서초구", 37.4837, 127.0324, "Seoul"),
    "Gangnam": ("강남구", 37.5172, 127.0473, "Seoul"),
    "Songpa": ("송파구", 37.5145, 127.1059, "Seoul"),
    "Gangdong": ("강동구", 37.5301, 127.1238, "Seoul"),
    "Suwon-Jangan": ("수원시 장안구", 37.3040, 127.0100, "Suwon"),
    "Suwon-Gwonseon": ("수원시 권선구", 37.2578, 126.9720, "Suwon"),
    "Suwon-Paldal": ("수원시 팔달구", 37.2820, 127.0200, "Suwon"),
    "Suwon-Yeongtong": ("수원시 영통구", 37.2596, 127.0467, "Suwon"),
}

# key -> (Korean, English label)
SPECIALTIES = {
    "internal_medicine": ("내과", "Internal Medicine"),
    "family_medicine": ("가정의학과", "Family Medicine"),
    "ent": ("이비인후과", "ENT (Ear, Nose and Throat)"),
    "dermatology": ("피부과", "Dermatology"),
    "orthopedics": ("정형외과", "Orthopedics"),
    "pediatrics": ("소아청소년과", "Pediatrics"),
    "obgyn": ("산부인과", "OB-GYN"),
    "dentistry": ("치과", "Dentistry"),
    "ophthalmology": ("안과", "Ophthalmology"),
    "urology": ("비뇨의학과", "Urology"),
    "neurology": ("신경과", "Neurology"),
    "psychiatry": ("정신건강의학과", "Psychiatry"),
}

# Fictional name stems (Korean, romanised). Any overlap with real institutions is accidental.
NAME_STEMS = [
    ("한빛", "Hanbit"), ("새봄", "Saebom"), ("푸른", "Pureun"), ("하늘", "Haneul"),
    ("미래", "Mirae"), ("든든", "Deundeun"), ("바른", "Bareun"), ("온누리", "Onnuri"),
    ("참좋은", "Chamjoeun"), ("해오름", "Haeoreum"), ("우리", "Uri"), ("서린", "Seorin"),
    ("가온", "Gaon"), ("다나", "Dana"), ("라온", "Raon"), ("보람", "Boram"),
    ("소담", "Sodam"), ("이든", "Eden"), ("제일", "Jeil"), ("튼튼", "Teunteun"),
]

LANGUAGES = ["en", "zh", "ja", "vi", "ru", "mn"]
LANGUAGE_NAMES = {"en": "English", "zh": "Chinese", "ja": "Japanese", "vi": "Vietnamese",
                  "ru": "Russian", "mn": "Mongolian"}

# complaint key -> description. specialties = acceptable specialties (any of them is fine).
COMPLAINTS = {
    "cough_cold": {"en": "a cough and a sore throat", "simple": "cough, sore throat",
                   "specialties": ["ent", "internal_medicine", "family_medicine"], "mild": True},
    "skin_rash": {"en": "an itchy rash on my arms", "simple": "itchy skin on arms",
                  "specialties": ["dermatology", "family_medicine"], "mild": True},
    "ankle_sprain": {"en": "a twisted ankle that is swollen", "simple": "ankle hurt, swollen",
                     "specialties": ["orthopedics", "family_medicine"], "mild": True},
    "toothache": {"en": "a toothache", "simple": "tooth pain",
                  "specialties": ["dentistry"], "mild": True},
    "stomach_pain": {"en": "stomach pain and some nausea", "simple": "stomach pain",
                     "specialties": ["internal_medicine", "family_medicine"], "mild": True},
    "eye_irritation": {"en": "red, itchy eyes", "simple": "eyes red and itchy",
                       "specialties": ["ophthalmology"], "mild": True},
    "headache": {"en": "headaches that keep coming back", "simple": "headache again and again",
                 "specialties": ["neurology", "internal_medicine", "family_medicine"], "mild": True},
    "urinary": {"en": "burning when I urinate", "simple": "pain when I pee",
                "specialties": ["urology", "internal_medicine", "family_medicine"], "mild": True},
    "ear_pain": {"en": "ear pain", "simple": "ear pain",
                 "specialties": ["ent"], "mild": True},
    "back_pain": {"en": "lower back pain", "simple": "back pain",
                  "specialties": ["orthopedics", "family_medicine"], "mild": True},
    "allergy_nose": {"en": "a runny nose and lots of sneezing", "simple": "runny nose, sneezing",
                     "specialties": ["ent", "internal_medicine", "family_medicine"], "mild": True},
    "checkup": {"en": "a general health checkup", "simple": "health check",
                "specialties": ["internal_medicine", "family_medicine"], "mild": True},
}

# ---- Drugs and allergens (interpretation and summaries) -------------------------------
DRUGS = {
    "acetaminophen": {"ko": "아세트아미노펜", "ko_alias": ["아세트아미노펜", "타이레놀"],
                      "en": ["acetaminophen", "paracetamol", "tylenol"]},
    "ibuprofen": {"ko": "이부프로펜", "ko_alias": ["이부프로펜", "부루펜"],
                  "en": ["ibuprofen", "advil", "brufen"]},
    "amoxicillin": {"ko": "아목시실린", "ko_alias": ["아목시실린"], "en": ["amoxicillin"]},
    "cetirizine": {"ko": "세티리진", "ko_alias": ["세티리진"], "en": ["cetirizine", "zyrtec"]},
    "omeprazole": {"ko": "오메프라졸", "ko_alias": ["오메프라졸"], "en": ["omeprazole"]},
    "loratadine": {"ko": "로라타딘", "ko_alias": ["로라타딘"], "en": ["loratadine", "claritin"]},
    "ambroxol": {"ko": "암브록솔", "ko_alias": ["암브록솔"], "en": ["ambroxol"]},
}

ALLERGENS = {
    "penicillin": {"ko": "페니실린", "ko_alias": ["페니실린"], "en": ["penicillin"],
                   "blocks_drugs": ["amoxicillin"]},
    "aspirin": {"ko": "아스피린", "ko_alias": ["아스피린"], "en": ["aspirin"],
                "blocks_drugs": ["ibuprofen"]},
    "sulfa": {"ko": "설파제", "ko_alias": ["설파"], "en": ["sulfa", "sulpha", "sulfonamide"],
              "blocks_drugs": []},
    "latex": {"ko": "라텍스", "ko_alias": ["라텍스"], "en": ["latex"], "blocks_drugs": []},
    "peanut": {"ko": "땅콩", "ko_alias": ["땅콩"], "en": ["peanut"], "blocks_drugs": []},
    "shellfish": {"ko": "갑각류", "ko_alias": ["갑각류", "새우"],
                  "en": ["shellfish", "shrimp", "crustacean"], "blocks_drugs": []},
}

BODY = {  # key -> (English phrase, Korean noun, Korean alias list)
    "stomach": ("stomach", "배", ["배", "복부", "위", "속", "뱃속"]),
    "throat": ("throat", "목", ["목", "인후", "목구멍"]),
    "head": ("head", "머리", ["머리", "두통"]),
    "ankle": ("ankle", "발목", ["발목"]),
    "back": ("lower back", "허리", ["허리", "등"]),
    "ear": ("ear", "귀", ["귀"]),
}

DIAGNOSES = {  # key -> Korean, English aliases
    "common_cold": {"ko": "감기", "en": ["common cold", "a cold", "just a cold", "cold"]},
    "acute_tonsillitis": {"ko": "급성 편도염",
                          "en": ["tonsillitis", "tonsil infection", "inflamed tonsils",
                                 "inflammation of the tonsils", "infection of the tonsils"]},
    "acute_gastritis": {"ko": "급성 위염",
                        "en": ["gastritis", "stomach inflammation", "inflamed stomach",
                               "inflammation of the stomach", "inflammation in the stomach"]},
    "allergic_rhinitis": {"ko": "알레르기 비염",
                          "en": ["allergic rhinitis", "nasal allergy", "hay fever",
                                 "allergy in your nose", "allergies in your nose", "allergic nose"]},
    "ankle_sprain": {"ko": "발목 염좌", "en": ["sprain", "sprained", "ligament injury"]},
    "tension_headache": {"ko": "긴장성 두통",
                         "en": ["tension headache", "tension-type headache", "stress headache",
                                "tension type headache"]},
}

TESTS = {
    "blood_test": {"ko": "피검사", "en": ["blood test", "blood work", "blood sample", "blood exam",
                                          "blood tests"]},
    "urine_test": {"ko": "소변검사", "en": ["urine test", "urinalysis", "urine sample", "urine exam"]},
    "xray": {"ko": "엑스레이 촬영", "en": ["x-ray", "xray", "x ray", "radiograph"]},
}

# Topics for "don't" / "permit" instructions. en = lexicon used to locate the topic in a sentence.
TOPICS = {
    "alcohol": {"ko_dont": ["술은 드시지 마세요.", "술은 안 돼요.", "음주는 피하세요."],
                "en": ["alcohol", "beer", "wine", "soju", "liquor", "alcoholic"]},
    "exercise": {"ko_dont": ["격한 운동은 하지 마세요.", "운동은 하시면 안 됩니다.", "운동은 쉬세요."],
                 "en": ["exercise", "workout", "working out", "physical activity", "strenuous",
                        "gym", "sports"]},
    "spicy": {"ko_dont": ["매운 음식은 드시지 마세요.", "맵고 자극적인 음식은 피하세요.",
                          "매운 건 안 돼요."],
              "en": ["spicy", "hot food", "chili", "chilli", "irritating food", "hot and spicy"]},
    "driving": {"ko_dont": ["졸릴 수 있으니 운전은 하지 마세요.", "운전은 하시면 안 돼요."],
                "en": ["driv", "operate machinery", "vehicle", "machinery"]},
    "coffee": {"ko_dont": ["커피는 드시지 마세요.", "커피는 안 돼요."],
               "ko_permit": ["커피는 괜찮습니다.", "커피는 드셔도 돼요."],
               "ko_question": "커피를 마셔도 돼요?", "en_question": "Can I drink coffee?",
               "en": ["coffee", "caffeine"]},
}

DO_ITEMS = {  # key -> (Korean sentences, English keyword groups [all groups must match])
    "water": (["물을 많이 드세요.", "수분 섭취를 충분히 하세요."], [["water", "fluid", "hydrat"],
                                                              ["plenty", "lot", "more", "enough", "a lot"]]),
    "rest": (["푹 쉬세요.", "충분히 쉬세요."], [["rest"]]),
    "ice": (["얼음찜질을 해 주세요.", "냉찜질을 하세요."], [["ice", "cold pack", "cold compress", "cold compresses"]]),
    "elevate": (["발목을 높이 올려 두세요."], [["elevat", "raise", "raised", "propped", "above"]]),
}

WARNINGS = {  # key -> (Korean template or list, English keyword groups); {n} = days where used
    "fever_days": (["열이 {n}일 이상 계속되면 다시 오세요."], None),
    "breathing_chest": (["숨이 차거나 가슴이 아프면 바로 응급실에 가세요."],
                        [["breath", "breathing", "breathless"], ["chest"], ["emergency", "er", "119", "ambulance"]]),
    "blood_stool": (["대변에 피가 섞여 나오면 바로 병원에 오세요."],
                    [["blood", "bloody"], ["stool", "stools", "poop", "bowel", "feces", "faeces", "motion"]]),
    "pain_worse": (["통증이 심해지면 바로 다시 오세요."], [["pain"], ["worse", "worsen", "worsens", "severe", "increase", "more"]]),
}

# Benchmark-world public holidays (clinics closed unless open_on_holidays). Synthetic calendar.
HOLIDAYS = ["2026-12-25", "2027-01-01", "2027-03-01", "2027-05-05", "2027-06-06"]

FIRST_NAMES = ["Mei", "Minh", "Aiko", "Amir", "Sofia", "Ivan", "Priya", "Lars", "Fatima", "Tuan",
               "Hana", "Carlos", "Nadia", "Omar", "Elena", "Kofi", "Linh", "Yuki", "Sara", "Ravi",
               "Anya", "Diego", "Mina", "Tariq", "Chen", "Bayar", "Leila", "Noah", "Zainab", "Jin"]
NATIONALITIES = [("China", "zh"), ("Vietnam", "vi"), ("Japan", "ja"), ("Iran", "en"),
                 ("Brazil", "en"), ("Russia", "ru"), ("India", "en"), ("Germany", "en"),
                 ("Egypt", "en"), ("Mongolia", "mn"), ("Nigeria", "en"), ("Mexico", "en"),
                 ("Pakistan", "en"), ("Uzbekistan", "ru"), ("USA", "en"), ("France", "en")]
VISAS = ["D-2 (degree student)", "D-4 (language trainee)", "E-7 (professional worker)",
         "E-2 (foreign language instructor)", "F-6 (marriage migrant)", "D-10 (job seeker)",
         "F-2 (resident)", "C-3 (short-term visitor)"]
