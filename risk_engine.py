import re
from typing import Dict, List, Optional, Any

from models import RiskLevel


URGENT_PATTERNS = {
    "chest_pain": [
        r"ko[‘']?krak og[‘']?rig", r"chest pain", r"боль в груди",
    ],
    "breathing_difficulty": [
        r"nafas.*qiyin", r"nafas.*qis", r"breath.*difficult", r"shortness of breath",
        r"трудно дышать", r"одышка",
    ],
    "fainting": [
        r"hushdan ket", r"faint", r"passed out", r"обморок", r"потерял сознание",
    ],
    "severe_allergy": [
        r"lab.*shish", r"til.*shish", r"tomoq.*shish", r"yuz.*shish",
        r"swelling.*lip", r"swelling.*tongue", r"swelling.*throat",
        r"отек.*губ", r"отек.*язык", r"отек.*горл",
    ],
    "seizure": [
        r"tutqanoq", r"seizure", r"convulsion", r"судорог", r"приступ",
    ],
    "stroke_signs": [
        r"yuz.*qiyshay", r"qo[‘']?l.*kuchsiz", r"gapira olmay",
        r"face droop", r"arm weakness", r"speech difficulty",
        r"перекос.*лиц", r"слабость.*рук", r"нарушение речи",
    ],
    "severe_bleeding": [
        r"kuchli qon", r"qon ket", r"severe bleeding", r"сильное кровотечение",
        r"vomiting blood", r"qon qus", r"рвота кровью",
    ],
    "suicidal": [
        r"o[‘']?zimni o[‘']?ldir", r"jonimga qasd", r"suicide", r"kill myself",
        r"самоубий", r"убить себя",
    ],
    "loss_of_consciousness": [
        r"loss of consciousness", r"без сознания", r"hushsiz",
    ],
    "severe_rash": [
        r"kuchli toshma", r"teri ko[‘']?ch", r"rash.*fever", r"skin peeling",
        r"сильная сыпь", r"кожа.*слез",
    ],
}

MISSED_PATTERNS = [
    r"unutdim", r"ichmadim", r"o[‘']?tkazib yubordim", r"qabul qilmadim",
    r"missed", r"forgot", r"skip", r"skipped",
    r"забыл", r"пропустил", r"не пил", r"не принимал",
]

STOP_PATTERNS = [
    r"to[‘']?xtatdim", r"to[‘']?xtatmoqchiman", r"ichgim kelmayapti", r"endi ichmayman",
    r"stopped", r"stop taking", r"quit", r"don[’']?t want to take",
    r"перестал", r"бросил", r"не хочу принимать",
]

SIDE_EFFECT_PATTERNS = [
    r"nojo[‘']?ya", r"ko[‘']?ngil ayn", r"bosh ayl", r"bosh og[‘']?ri", r"toshma",
    r"nausea", r"dizzy", r"headache", r"rash", r"side effect", r"stomach pain",
    r"тошнит", r"головокруж", r"головная боль", r"сыпь", r"побоч",
]

COST_PATTERNS = [
    r"qimmat", r"pulim yetmay", r"sotib ololmay", r"tejay", r"yarimta ich",
    r"expensive", r"can[’']?t afford", r"cost", r"ration",
    r"дорого", r"не могу купить", r"нет денег",
]

CONFUSION_PATTERNS = [
    r"qachon ich", r"qanday ich", r"oldinmi", r"keyinmi", r"chalkash", r"tushunmadim",
    r"when should", r"how should", r"before food", r"after food", r"confused",
    r"когда принимать", r"как принимать", r"до еды", r"после еды", r"не понимаю",
]

SWALLOW_PATTERNS = [
    r"yuta olmay", r"yutish qiyin", r"tabletka katta", r"kapsula katta",
    r"can[’']?t swallow", r"hard to swallow", r"pill too big",
    r"не могу глотать", r"трудно глотать", r"таблетка большая",
]

CRITICAL_MED_PATTERNS = [
    r"insulin", r"инсулин",
    r"tutqanoq", r"epilep", r"seizure", r"судорог", r"эпилеп",
    r"warfarin", r"варфарин", r"blood thinner", r"anticoagulant", r"qon suyult",
    r"\btb\b", r"sil", r"tuberculosis", r"туберкул",
    r"\bhiv\b", r"vih", r"вич",
    r"transplant", r"anti-rejection",
    r"nitroglycerin", r"yurak", r"heart failure",
    r"prednisolone", r"hydrocortisone", r"steroid",
]

DOUBLE_DOSE_PATTERNS = [
    r"ikki baravar", r"2 ta ichdim", r"double dose", r"took two", r"двойную доз",
]

PREGNANCY_PATTERNS = [
    r"homilador", r"emiz", r"pregnan", r"breastfeed", r"беремен", r"кормлю груд",
]


def match_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def detect_language(text: str) -> str:
    lower = text.lower()

    if re.search(r"[а-яё]", lower):
        return "ru"

    uz_words = [
        "men", "menga", "dori", "ichdim", "ichmadim", "qanday", "nima",
        "yaxshi", "og‘riq", "og'riq", "bosh", "ko‘ngil", "ko'ngil",
        "shifokor", "farmatsevt", "qimmat", "unutdim", "qabul",
    ]

    if any(word in lower for word in uz_words):
        return "uz"

    return "en"


def extract_missed_days(text: str) -> Optional[int]:
    lower = text.lower()

    digit_match = re.search(r"(\d+)\s*(kun|kunda|kundan|day|days|день|дня|дней)", lower)
    if digit_match:
        return int(digit_match.group(1))

    word_numbers = {
        "bir": 1,
        "bitta": 1,
        "one": 1,
        "один": 1,
        "одна": 1,
        "ikki": 2,
        "two": 2,
        "два": 2,
        "две": 2,
        "uch": 3,
        "three": 3,
        "три": 3,
        "to‘rt": 4,
        "to'rt": 4,
        "tort": 4,
        "four": 4,
        "четыре": 4,
        "besh": 5,
        "five": 5,
        "пять": 5,
    }

    for word, number in word_numbers.items():
        if re.search(rf"\b{re.escape(word)}\b.*(kun|day|дн)", lower):
            return number

    if any(x in lower for x in ["kecha", "yesterday", "вчера"]):
        return 1

    return None


def analyze_risk(message: str) -> Dict[str, Any]:
    text = message.strip().lower()
    flags: List[str] = []

    urgent_found = []
    for flag, patterns in URGENT_PATTERNS.items():
        if match_any(text, patterns):
            urgent_found.append(flag)

    if urgent_found:
        return {
            "risk_level": RiskLevel.URGENT,
            "risk_flags": urgent_found,
            "detected_language": detect_language(message),
        }

    risk = RiskLevel.LOW

    if match_any(text, MISSED_PATTERNS):
        flags.append("missed_medication")
        risk = RiskLevel.MODERATE

        missed_days = extract_missed_days(text)
        if missed_days and missed_days >= 2:
            flags.append("missed_2_plus_days")
            risk = RiskLevel.HIGH

    if match_any(text, CRITICAL_MED_PATTERNS):
        flags.append("critical_medication_possible")
        if "missed_medication" in flags:
            flags.append("critical_medication_missed")
            risk = RiskLevel.HIGH

    if match_any(text, STOP_PATTERNS):
        flags.append("intentional_stopping")
        risk = RiskLevel.HIGH

    if match_any(text, SIDE_EFFECT_PATTERNS):
        flags.append("side_effect")
        if risk == RiskLevel.LOW:
            risk = RiskLevel.MODERATE

    if match_any(text, COST_PATTERNS):
        flags.append("cost_barrier")
        if any(x in text for x in ["yarimta", "ration", "tejay", "half"]):
            risk = RiskLevel.HIGH
        elif risk == RiskLevel.LOW:
            risk = RiskLevel.MODERATE

    if match_any(text, CONFUSION_PATTERNS):
        flags.append("medication_confusion")
        if risk == RiskLevel.LOW:
            risk = RiskLevel.MODERATE

    if match_any(text, SWALLOW_PATTERNS):
        flags.append("swallowing_difficulty")
        if risk == RiskLevel.LOW:
            risk = RiskLevel.MODERATE

    if match_any(text, DOUBLE_DOSE_PATTERNS):
        flags.append("possible_double_dose")
        risk = RiskLevel.HIGH

    if match_any(text, PREGNANCY_PATTERNS):
        flags.append("pregnancy_or_breastfeeding")
        if risk in [RiskLevel.LOW, RiskLevel.MODERATE]:
            risk = RiskLevel.HIGH

    return {
        "risk_level": risk,
        "risk_flags": flags,
        "detected_language": detect_language(message),
    }