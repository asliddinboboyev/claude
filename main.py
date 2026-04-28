"""
╔══════════════════════════════════════════════════════════════════════╗
║         TABIB AI — PROFESSIONAL MEDICAL EXPERT SYSTEM v4.0          ║
║         MedGuard AI | AI Health Hackathon 2026                       ║
║                                                                      ║
║  Run:   uvicorn main:app --reload --port 8000                        ║
║  Docs:  http://localhost:8000/docs                                   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, re, uuid, logging, httpx, json
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import anthropic

# ══════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("TabibAI")

# ══════════════════════════════════════════════════════════════════════
# CONFIG — barcha kalitlar serverda, frontendga chiqmaydi
# ══════════════════════════════════════════════════════════════════════
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY     = os.getenv("TAVILY_API_KEY", "")      # web search uchun
ALERT_WEBHOOK_URL  = os.getenv("ALERT_WEBHOOK_URL", "")   # shifokorga xabar uchun
CLAUDE_MODEL       = "claude-sonnet-4-6"
MAX_HISTORY        = 40
MAX_MSG_LEN        = 6000
MISSED_DOSE_ALERT_HOURS = 48   # 2 kun

# ══════════════════════════════════════════════════════════════════════
# TIBBIY BILIMLAR BAZASI
# ══════════════════════════════════════════════════════════════════════
DISEASES = {
    "diabet": {
        "uz_names": ["diabet","qand kasalligi","shakar kasalligi","dm","qand","shakar"],
        "ru_names": ["диабет","сахарный диабет","диабет 2"],
        "en_names": ["diabetes","type 1 diabetes","type 2 diabetes","dm","t2dm"],
        "description": "Qand diabeti — qondagi glyukoza darajasining surunkali oshishi. Insulin yetishmovchiligi (1-tur) yoki insulinga rezistentlik (2-tur) sabab.",
        "symptoms": ["Poliuriya (tez-tez siydik)","Polidipsiya (haddan ko'p suv ichish)","Polifagiya (ochlik)","Tez charchash","Ko'rish xiralashishi","Yaralarnining sekin bitishi","Oyoq-qo'llarda paresteziya"],
        "target_labs": {"HbA1c": "<7.0% (individuallashtirilgan: <6.5-8.0%)","Och qorin glyukoza": "3.9-7.2 mmol/L","Postprandial 2h": "<10.0 mmol/L","Qon bosimi": "<130/80 mmHg","LDL": "<2.6 mmol/L (yurak xavfi bo'lsa <1.8)"},
        "medications": ["Metformin 500-2000mg/kun (1-qator)","SGLT2i: Empagliflozin 10-25mg, Dapagliflozin 10mg","GLP-1: Semaglutide, Liraglutide","DPP-4i: Sitagliptin 100mg","Insulin (1-tur: majburiy; 2-tur: kerak bo'lsa)"],
        "complications": ["Mikrovaskulyar: nefropatiya, retinopatiya, neyropatiya","Makrovaskulyar: MI, insult, PAD","Diabetik oyoq","Giperglisemik kriz (DKA, HHS)"],
        "monitoring": "HbA1c 3 oyda bir | Kreatinin/GFR yiliga bir | Ko'z fundus yiliga bir | Oyoq ko'rik har vizitda",
        "emergency": ["DKA: meva hidi + chuqur nafas (Kussmaul) + giperglikemiya > 11mmol/L + ketonuriya → 103","HHS: ekstrem giperglikemiya >33mmol/L + dehidratatsiya + aql buzilishi → 103","Og'ir gipoglikemiya: hushsizlik → Glukagon 1mg IM + 103"],
    },
    "gipertoniya": {
        "uz_names": ["gipertoniya","qon bosimi","bosim","arterial gipertoniya","giperton","yuqori bosim"],
        "ru_names": ["гипертония","артериальная гипертензия","высокое давление","давление"],
        "en_names": ["hypertension","high blood pressure","hbp","arterial hypertension"],
        "description": "Arterial gipertoniya — sistol BP ≥130 yoki diastol ≥80 mmHg (ACC/AHA 2017). O'zbekistonda katta yoshlilarning 40%+ da mavjud.",
        "stages": {"Normal":"<120/<80","Yuqori normal":"120-129/<80","1-daraja HT":"130-139/80-89","2-daraja HT":"≥140/≥90","Kriz":">180/>120 + organik zararlanish → SHOSHILINCH"},
        "medications": ["ACEi: Enalapril 5-40mg, Lisinopril 10-40mg, Ramipril 2.5-10mg","ARB: Losartan 50-100mg, Valsartan 80-320mg, Telmisartan 40-80mg","CCB: Amlodipine 2.5-10mg, Lercanidipine 10-20mg","Beta-blokator: Bisoprolol 1.25-10mg, Nebivolol 2.5-10mg","Tiazid: Indapamid 1.5-2.5mg, Gidrokhlorotiazid 12.5-25mg","MRA: Spironolakton 25-50mg (rezistent HT)"],
        "monitoring": "Uyda kuniga 2x o'lchash (ertalab + kechqurun) | 24h ABPM yiliga bir | Kreatinin, kaliy 6 oyda bir",
        "emergency": ["Gipertonik kriz (BP>180/120 + bosh og'riq/ko'rish buzilishi/ko'krak og'rig'i) → 103","Ko'krak og'rig'i + yuqori BP → MI xavfi, DARHOL 103","Nutq buzilishi + yuz qiyshayishi + yuqori BP → Insult, DARHOL 103"],
    },
    "yurak": {
        "uz_names": ["yurak kasalligi","yurak","ishemik yurak","stenokardiya","yurak yetishmovchiligi","iyk","stent","shunt"],
        "ru_names": ["ибс","ишемическая болезнь сердца","стенокардия","сердечная недостаточность","инфаркт"],
        "en_names": ["coronary artery disease","cad","heart disease","angina","heart failure","ihd","mi","acs"],
        "medications": ["Antiplatelet: Aspirin 75-100mg + Klopidogrel 75mg (ACS/stentdan keyin 12 oy)","Statin: Atorvastatin 40-80mg (yuqori intensiv)","ACEi/ARB: post-MI va HF da majburiy","Beta-blokator: post-MI va HF da majburiy","MRA: Spironolakton/Eplerenon (HF EF≤35%)","SGLT2i: Empagliflozin (HF da kardioprotektiv)","Nitrogliterin 0.4mg til ostiga (og'riq hujumida)"],
        "monitoring": "EKG | EXO-KG 6-12 oyda | NT-proBNP (HF) | Lipidlar 3 oyda | Koronarografiya (ko'rsatma bo'yicha)",
        "emergency": ["STEMI: to'satdan ko'krak og'rig'i >20 min + ter + chap qo'l → DARHOL 103, Aspirin 300mg chaynab","NSTEMI/UA: ko'krak og'rig'i dam olganda ham → TEZDA 103","Akut HF: ortopnoe + ko'pikli balg'am + sianoz → DARHOL 103","VF/VT: hushsizlik + puls yo'q → CPR + DARHOL 103"],
    },
    "astma": {
        "uz_names": ["astma","bronxial astma","xirillash","astma hujumi"],
        "ru_names": ["астма","бронхиальная астма","приступ астмы"],
        "en_names": ["asthma","bronchial asthma","wheezing","bronchospasm"],
        "medications": ["Qisqa ta'sirli (Reliever): Salbutamol 100mcg x2 nafas (hujumda)","Nazorat (Controller): Budesonid 200-400mcg 2x/kun yoki Flutikazon","Kombinatsiya: Symbicort (Budesonid+Formoterol), Seretide (Flutikazon+Salmeterol)","Montelukast 10mg (qo'shimcha)","Og'ir: Omalizumab (anti-IgE biologik)"],
        "monitoring": "PEF monitoring | Spirometriya 1-2 yilda | Qo'zg'atuvchilardan qochish rejasi",
        "emergency": ["Og'ir hujum: gapira olmaslik + SpO2<92% + taxikardiya → DARHOL 103","Salbutamol 20 min ichida ishlamasa → TEZDA 103","Lab ko'kimligi (sianoz) → DARHOL 103"],
    },
    "copd": {
        "uz_names": ["sopk","surunkali bronxit","emfizema","copd","o'pka kasalligi"],
        "ru_names": ["хобл","хроническая обструктивная болезнь","эмфизема"],
        "en_names": ["copd","chronic obstructive pulmonary disease","emphysema","chronic bronchitis"],
        "medications": ["LAMA: Tiotropium 18mcg 1x/kun (asosiy)","LABA: Formoterol, Indakaterol","LAMA+LABA: Ultibro, Anoro (og'ir COPD)","ICS+LABA: Seretide, Symbicort (eosinofil >300)","Ekzatserbatsiya: Prednizolon 40mg x5 kun + Amoksitsillin/Azitromitsin"],
        "monitoring": "Spirometriya yiliga bir | SpO2 monitoring | CAT skalasi | Emlash (gripp, pnevmokok)",
        "emergency": ["SpO2<88% tinch holatda → O2 terapiya + TEZDA 103","Ekzatserbatsiya: balg'am ko'payishi + nafas qisilishi kuchayishi → TEZDA shifokor","Nafas mushaklari charchoq belgilari → TEZDA 103"],
    },
    "buyrak": {
        "uz_names": ["buyrak kasalligi","buyrak","ckd","surunkali buyrak","dializ","gfr"],
        "ru_names": ["почечная болезнь","хроническая болезнь почек","диализ"],
        "en_names": ["chronic kidney disease","ckd","renal failure","dialysis","egfr"],
        "stages": {"G1":"GFR≥90 (normal/yuqori)","G2":"GFR 60-89 (hafif)","G3a":"GFR 45-59 (o'rta-hafif)","G3b":"GFR 30-44 (o'rta-og'ir)","G4":"GFR 15-29 (og'ir, dializ tayyorligi)","G5":"GFR<15 (buyrak yetishmovchiligi)"},
        "medications": ["ACEi/ARB: proteinuriyani kamaytirish (GFR>30 da)","SGLT2i: Dapagliflozin (CKD progressiyasini sekinlashtiradi)","BP maqsad: <130/80 mmHg","Bikarbonat: atsidoz korreksiyasi","Fosfat boglash: Sevelamer, Kalsiy karbonat","ESA: Eritropoetin (Hb<100 g/L)","Kaliy nazorat: taomnoma, Patiromer (og'ir giperkaliemiya)"],
        "monitoring": "Kreatinin/eGFR 3-6 oyda | UACR 3-6 oyda | Kaliy, bikarbonat | PTH, fosfat (G3b+) | Gemoglobin",
        "emergency": ["Anuriya (siydik yo'q) →TEZDA 103","Giperkaliemiya K>6.5 + EKG o'zgarishi → DARHOL 103","Uremik ensefalopati (chalkashlik + tremor) → TEZDA 103","Akut buyrak zararlanishi (kreatinin tez oshishi) → TEZDA shifokor"],
    },
    "insult": {
        "uz_names": ["insult","miya qon aylanishi","falaj","tia","miya","insult"],
        "ru_names": ["инсульт","ишемический инсульт","геморрагический инсульт","тиа"],
        "en_names": ["stroke","ischemic stroke","hemorrhagic stroke","tia","cva"],
        "fast": "F — Face drooping (yuz qiyshayishi) | A — Arm weakness (qo'l kuchsizligi) | S — Speech difficulty (nutq buzilishi) | T — Time → DARHOL 103",
        "treatment": "Ishemik insult: 4.5 soat ichida tPA (alteplaz) yoki 24 soat ichida trombektomiya. HAR DAQIQA = 1.9 million neyron!",
        "prevention": ["Qon bosimi nazorat (eng muhim)","Antiplatelet: Aspirin+Dipiridamol yoki Klopidogrel","AF da antikoagulyant: Apixaban, Rivaroksaban, Dabigatran","Statin: Atorvastatin 40-80mg","Chekishni tashlash","Diabet nazorati"],
        "emergency": ["FAST belgilari → DARHOL 103, hech narsa yedirma/ichdirma","To'satdan kuchli bosh og'riq → SAK xavfi, DARHOL 103","TIA (o'tuvchi simptom) → ham TEZDA 103 (24 soat ichida insult xavfi yuqori)"],
    },
    "tiroid": {
        "uz_names": ["qalqonsimon bez","gipotireoz","gipertireoz","tiroid","zob","levotiroksin","tsh"],
        "ru_names": ["щитовидная железа","гипотиреоз","гипертиреоз","тиреоид"],
        "en_names": ["thyroid","hypothyroidism","hyperthyroidism","goiter","tsh","hashimoto"],
        "medications": {"gipotireoz": "Levotiroksin: 25-50mcg dan boshlash. 1.6 mcg/kg/kun maqsad doza. Ertalab och qoringa 30-60 min oldin.","gipertireoz": "Tiamazol 10-40mg/kun (PTU homiladorlikda). Propranolol simptomlar uchun. Radioaktiv yod yoki operatsiya."},
        "monitoring": "TSH 6-8 hafta (doza o'zgarishdan keyin) → 6 oyda bir. FT4 zarur bo'lsa. Levotiroksin: kalsiy, temir, soyadan 4 soat interval.",
        "emergency": ["Tireoid bo'ron: isitma>38.5 + taxikardiya + qaltirashlash + aql buzilishi → TEZDA 103","Miksedem koma: bradikardiya + gipotermiya + hushsizlik → DARHOL 103"],
    },
    "depressiya": {
        "uz_names": ["depressiya","ruhiy kasallik","kayfiyat tushishi","tashvish","asabiylashish","xavotir"],
        "ru_names": ["депрессия","тревожность","психическое расстройство","ВСД"],
        "en_names": ["depression","anxiety","mental health","panic disorder","ptsd"],
        "medications": ["SSRI (1-qator): Sertralin 50-200mg, Escitalopram 10-20mg, Fluoksetin 20-60mg","SNRI: Venlafaksin 75-225mg, Duloksetin 60-120mg","TCA (2-qator): Amitriptilin 25-150mg (uyqu, neyropatik og'riq uchun ham)","Atipik: Mirtazapin 15-45mg (ishtaha/uyqu muammosida)","Stabilizator: Litiy, Valproat (bipolyar)"],
        "monitoring": "PHQ-9 (depressiya), GAD-7 (tashvish) skalasi | Jigar fermentlari (TCA) | Litiy darajasi (0.6-1.2 mEq/L)",
        "emergency": ["Suitsidal fikr/reja → DARHOL 103 yoki 1448 (O'zbekiston ruhiy salomatlik xatti)","Psixoz belgilari (gallyutsinatsiya, paranoya) → TEZDA psixiatr","Serotonin sindromi (SSRI+MAOi): gipertermiya + qattiqlik + klonus → TEZDA 103"],
    },
}

MEDICATIONS = {
    "metformin": {
        "brands": ["Metformin","Glucophage","Siofor","Glyukofaj","Metfogamma"],
        "class": "Biguanid antidiabetik",
        "dose": "500mg 2x/kun (ovqat bilan) → 1000mg 2x/kun. Maksimal: 2550mg/kun. XR formulasi yaxshiroq toleratsiya.",
        "mechanism": "Jigar glyukoneogenezini inhibe qiladi (AMPK aktivatsiyasi). Insulinga sezuvchanlikni oshiradi. GLP-1 darajasini ko'taradi.",
        "side_effects": {"Tez-tez": "Ko'ngil aynish, ich ketish, qorin noqulayligi (vaqtincha, 2-4 haftada o'tadi)","Kam": "B12 vitamini yetishmovchiligi (uzoq muddatda — yiliga bir tekshiring)","Jiddiy": "Laktik atsidoz (GFR<30 da xavf — zaiflik+nafas qisishi → 103)"},
        "take_with": "Ovqat bilan birga yoki darhol keyin. Spirt iste'molini kamaytiring.",
        "contraindications": ["eGFR<30 (to'xtatish)","eGFR 30-45 (ehtiyotkorlik, doza kamaytirish)","Kontrast tekshiruvdan 48 soat oldin to'xtatish","Og'ir jigar kasalligi","Spirt suiiste'moli"],
        "missed": "Ovqat paytida eslab qolsangiz — oling. Keyingi ovqatga yaqin bo'lsa — o'tkazib yuboring. IKKI BARAVAR OLMANG.",
        "monitoring": "eGFR + B12 yiliga bir",
        "interactions": {"Kontrast modda": "48 soat oldin to'xtatish","Alkogol": "Laktik atsidoz xavfi","Simetidin": "Metformin darajasini oshiradi"},
    },
    "enalapril": {
        "brands": ["Enalapril","Enap","Renitek","Berlipril","Ednit"],
        "class": "ACE ingibitori",
        "dose": "2.5-5mg 2x/kun dan boshlash. Maqsad: 10-20mg 2x/kun (HF); 10-40mg/kun (HT).",
        "mechanism": "ACE fermentini inhibe qilib Ang I→Ang II konversiyasini bloklaydi → vazodilatasiya, aldosteron kamayishi, bradikinin oshishi.",
        "side_effects": {"Tez-tez": "Quruq yo'tal (10-15%, bradikinin oshishi sabab)","Kam": "Bosh aylanishi (1-doza effekti — gipotenziya)","Jiddiy": "Angioedema (0.1-0.5%) → DARHOL 103 | Giperkaliemiya | AKI (bilateral renal artery stenosis)"},
        "take_with": "Ovqatdan qat'i nazar, bir xil vaqtda. Birinchi doza kechqurun (gipotenziya xavfi).",
        "contraindications": ["Homiladorlik (teratogen — FDA X)","Angioedema tarixi (ACEi yoki hereditar)","Bilateral renal artery stenosis"],
        "missed": "Eslab qolsangiz — oling. Keyingi vaqtga yaqin bo'lsa — o'tkazib yuboring.",
        "monitoring": "Kreatinin, kaliy boshlanganda, 1 haftada, keyin 3-6 oyda",
        "interactions": {"NSAID": "BP ta'siri kamayadi + nefrotoksiklik","Kaliy tutuvchi diuretik": "Giperkaliemiya","Litiy": "Litiy toksiklik xavfi","Allopurinol": "Angioedema xavfi oshadi"},
    },
    "amlodipine": {
        "brands": ["Amlodipine","Norvasc","Stamlo","Tenox","Amlovas"],
        "class": "Dihidropiridin CCB (kalsiy kanal blokatori)",
        "dose": "2.5-5mg 1x/kun dan boshlash. Maksimal: 10mg/kun.",
        "mechanism": "Vaskulyar silliq mushaklardagi L-tip kalsiy kanallarini bloklaydi → periferik rezistentlik kamayishi → BP tushishi. Uzoq yarim yemirilish davri (30-50 soat) — bir marta qabul qilish yetarli.",
        "side_effects": {"Tez-tez": "Periferik odem (oyoq shishi — kapillyar o'tkazuvchanlik oshishi sabab, 10-15%)","Kam": "Yuz qizarishi, bosh og'riq","Kam uchraydi": "Gingival giperplaziya"},
        "take_with": "Kuniga 1 marta, istalgan vaqtda. Greyfurt bilan OLMANG.",
        "interactions": {"Greyfurt": "CYP3A4 inhibitsiyasi → konsentratsiya oshadi","Simvastatin": ">20mg bilan birga miopatiya xavfi → Atorvastatin ga o'ting","Siklosporin": "Siklosporin darajasi oshadi"},
        "missed": "Eslab qolsangiz — oling. Ikki baravar OLMANG.",
    },
    "bisoprolol": {
        "brands": ["Bisoprolol","Concor","Biprol","Bisocard","Bisogamma"],
        "class": "Selektiv beta-1 adrenoblokator",
        "dose": "HF: 1.25mg dan boshlash → sekin titratsiya → 10mg/kun. HT: 2.5-10mg/kun. AF: yurak urishi nazorati uchun.",
        "mechanism": "Beta-1 adrenoreseptorlarni selektiv bloklab HR va BP kamaytiradi. RAAS modulyatsiyasi. HF da kardioprotektiv ta'sir.",
        "side_effects": {"Tez-tez": "Bradikardiya, charchash, sovuqqa sezuvchanlik","Kam": "Bronxospazm (beta-2 spesifik emas, lekin og'ir astmada ehtiyot)","Muhim": "KESKIN TO'XTATMANG — rebound taxikardiya/angina"},
        "take_with": "Ertalab, ovqat bilan yoki ovqatsiz.",
        "contraindications": ["AV blok 2-3 daraja","Bradikardiya HR<50/min","Kardiogen shok","Og'ir bronxial astma (ehtiyotkorlik)"],
        "missed": "Eslab qolsangiz — oling. Ikki baravar OLMANG. TO'XTATMOQCHI BO'LSANGIZ — shifokor bilan 2-4 haftada sekin kamaytiring.",
        "interactions": {"Verapamil/Diltiazem": "Og'ir bradikardiya/AV blok xavfi","Klonidin": "Klonidinni to'xtatishda rebound HT xavfi","Insulin": "Gipoglikemiya simptomlarini yashiradi (titroq saqlanadi)"},
    },
    "atorvastatin": {
        "brands": ["Atorvastatin","Lipitor","Torvast","Atoris","Tulip"],
        "class": "Statin — HMG-CoA reduktaza inhibitori",
        "dose": "Kuchli intensiv: 40-80mg kechqurun. O'rtacha: 10-20mg. Yurak xavfi yuqori bo'lsa 40-80mg.",
        "mechanism": "Jigar HMG-CoA reduktazasini inhibe qilib xolesterol sintezini kamaytiradi → jigar LDL retseptorlarini oshiradi → qondagi LDL kamayadi. Anti-inflamatuar va endotelial ta'siri ham bor.",
        "side_effects": {"Tez-tez": "Mialgiya (5-10%, CK tekshiring)","Kam": "Transaminazlar oshishi (ALT>3x ULN — to'xtatish)","Jiddiy": "Rabdomioliz: kuchli mushak og'rig'i + qoramtir siydik → TEZDA shifokor"},
        "take_with": "Kechqurun, ovqatdan qat'i nazar. Greyfurt bilan OLMANG.",
        "interactions": {"Greyfurt": "CYP3A4 inhibitsiyasi → atorvastatin 2-3x oshadi","Gemfibrozil": "Rabdomioliz xavfi","Warfarin": "INR oshadi","Siklosporin": "Statin darajasi oshadi"},
        "monitoring": "ALT/AST boshlanganda, 3 oyda → yiliga bir. CK (mushak og'rig'ida).",
        "missed": "Eslab qolsangiz — oling. Ikki baravar OLMANG.",
    },
    "warfarin": {
        "brands": ["Warfarin","Coumadin","Marevan","Warcumin"],
        "class": "Vitamin K antagonisti antikoagulyant",
        "dose": "INR ga qarab individual titratsiya (odatda 2-8mg/kun).",
        "mechanism": "Vitamin K-dependent koagulyatsiya faktorlari (II, VII, IX, X) va protein C, S sintezini bloklab qon ivishini sekinlashtiradi.",
        "target_inr": {"AF/DVT/PE": "2.0-3.0","Mexanik mitral qopiq": "2.5-3.5","Bioprostetik qopiq": "2.0-3.0"},
        "side_effects": {"Asosiy": "Qon ketish (GI, intrakranial, yumshoq to'qima)"},
        "food_interactions": "K vitamini — karam, broccoli, spinach, o'simlik moylari. MIQDORNI DOIMIY saqlang (butunlay tashlamang). Greyfurt, mango — ta'sirni OSHIRADI.",
        "drug_interactions": "JUDA KO'P ta'sir: NSAID (qon ketish xavfi), antibiotiklar (ko'pchiligi INR o'zgartiradi), antifungallar, statin. Yangi dori boshlanishida DOIMO shifokorga ayting va INR ni 3-5 kun ichida tekshiring.",
        "reversal": "INR>5 (qon ketishsiz): Vitamin K 1-2.5mg oral. INR>10 yoki aktiv qon ketish: Vitamin K 5-10mg IV + 4-faktorli PCC yoki FFP → TEZDA 103.",
        "monitoring": "INR: dastlab haftada bir → maqsad INR da oyda bir.",
        "missed": "O'sha kuni eslab qolsangiz oling. Ertasi kuni 2x OLMANG. Shifokorga xabar bering + 3-5 kun ichida INR tekshiring.",
    },
    "insulin": {
        "brands": ["Novorapid","Humalog","Lantus","Glargin","Levemir","Tresiba","Actrapid","Protafan","Ryzodeg"],
        "class": "Insulin preparati",
        "types": {
            "Ultra-qisqa (NovoRapid/Humalog)": "Ovqatdan 0-15 daqiqa oldin. Cho'qqi: 1-2 soat. Davom: 3-5 soat.",
            "Qisqa (Actrapid)": "Ovqatdan 30 daqiqa oldin. Cho'qqi: 2-4 soat. Davom: 5-8 soat.",
            "O'rta (Protafan/NPH)": "1-2x/kun. Cho'qqi: 4-8 soat. Davom: 12-18 soat.",
            "Uzoq (Lantus/Glargin)": "Kuniga 1x, bir xil vaqtda. Cho'qqi YO'Q. Davom: 20-24 soat.",
            "Ultra-uzoq (Tresiba)": "Kuniga 1x. Davom: >42 soat. Eng barqaror bazal.",
        },
        "hypoglycemia": {
            "Belgilar": "Titroq, ter, yurak tez urishi, bosh aylanishi, o'tkir ochlik, chalkashlik, hushdan ketish",
            "Yengil-o'rta (glukoza 2.8-3.9)": "15g tez uglevod: 150ml sharbat YOKI 3-4 shakar YOKI 3-4 glukoza tablet → 15 daqiqa kut → qayta o'lcha → takrorla",
            "Og'ir (hushsiz)": "Glukagon 1mg IM/SC (avtoinjeksiya yoki kit) YOKI 40% glukoza 20-40ml IV → DARHOL 103",
        },
        "storage": "Ochilmagan: 2-8°C muzlatgichda (muzlatma). Ochilgan: xona haroratida 28-30 kun. Quyosh va issiqlikdan saqlang.",
        "injection": "Qorin (eng tez so'riladi), son (o'rta), yelka (sekin). Lipodistrofiyadan qochish uchun joyni AYLANTIRING (har safar 1-2 sm siljiting).",
        "missed": "HECH QACHON o'zingizcha o'zgartirmang. Shifokorga darhol qo'ng'iroq qiling.",
    },
    "levotiroksin": {
        "brands": ["Levotiroksin","Euthyrox","L-tiroksin","Eutiroks","Tirosint"],
        "class": "Sintetik tiroid gormoni (T4)",
        "dose": "Boshlash: keksa/yurak bemorlari 25-50mcg. Yosh/sog'lom: 50-100mcg. Maqsad doza: 1.6mcg/kg/kun.",
        "mechanism": "T4 periferik to'qimalarda T3 ga deiodinatsiya qilinadi. Metabolizm, o'sish, yurak, asab tizimini boshqaradi.",
        "take_with": "ERTALAB, OVQATDAN 30-60 DAQIQA OLDIN, FAQAT SUV BILAN. Har kuni bir xil vaqtda.",
        "interactions": "Kalsiy, temir, magniy, antatsidlar, soya, tolali ovqat — kamida 4 soat keyin.",
        "side_effects": "To'g'ri dozada minimal. Ortiqcha doza: yurak tez urishi, titroq, ter bosish, uyqusizlik, vazn yo'qotish.",
        "monitoring": "TSH doza o'zgargandan 6-8 hafta keyin. Keyin 6-12 oyda bir. Maqsad TSH: 0.5-2.5 mIU/L.",
        "missed": "Eslab qolsangiz — oling. Ikki baravar OLMANG.",
        "important": "Umrbod qabul qilinadi. To'xtatilsa gipotireoz qaytadi. Homiladorlikda doza ko'pincha oshiriladi.",
    },
    "aspirin": {
        "brands": ["Aspirin","Kardi ASK","Aspirin Cardio","Cardiomagnyl","Thrombass","Acecard"],
        "class": "COX-1 inhibitori antiplatelet (past doza)",
        "dose": "Antiplatelet: 75-100mg/kun. ACS yuk doza: 300mg chaynab. Analgetik: 300-1000mg.",
        "mechanism": "COX-1 ni qaytmas atsetillab tromboksan A2 sintezini bloklaydi → trombosit agregatsiyasi kamayadi (10 kun davom etadi — trombosit umri).",
        "contraindications": ["Faol peptik yara","Qon ketish buzilishlari","18 yoshgacha (Reye sindromi xavfi)","Aspirin-sezuvchan astma"],
        "interactions": {"Warfarin": "Qon ketish xavfi","Ibuprofen": "Aspirin antiplatelet ta'sirini bloklaydi (ibuprofen avval qabul qilinsa)","Metotreksat": "Toksiklik oshadi"},
        "missed": "O'z-o'zidan TO'XTATMANG — stent/ACS bemorlarda tromboz xavfi. Shifokorga maslahat.",
        "important": "ACS/stent bemorlarda Klopidogrel bilan birga DUAL antiplatelet terapiya (DAPT) — shifokor ko'rsatmasiz to'xtatmang.",
    },
    "sertralin": {
        "brands": ["Sertralin","Zoloft","Stimuloton","Serlift","Asentra"],
        "class": "SSRI (selektiv serotonin qayta qabul qilish inhibitori)",
        "dose": "25-50mg/kun dan boshlash. Maqsad: 50-200mg/kun. Asta-sekin oshirish.",
        "mechanism": "SERT (serotonin transporteri) ni selektiv bloklab presinaptik neyrondan serotonin qayta qabul qilinishini to'xtatadi → sinaptik serotonin oshadi.",
        "onset": "Tashvish/uyqu 1-2 haftada. To'liq antidepressant ta'sir 4-8 haftada. Sabr qiling.",
        "side_effects": {"Tez-tez (o'tuvchi)": "Ko'ngil aynish, bosh og'riq, uyqu buzilishi, ter bosish","Doimiy": "Jinsiy ta'sir (40-60%: orgazm kechikishi, libido kamayishi)","Jiddiy": "Suitsidal fikrlar (ayniqsa 25 yoshgacha — birinchi 2 haftada kuzatish)"},
        "discontinuation": "TO'XTATMOQCHI BO'LSANGIZ — shifokor bilan 4-8 haftada sekin kamaytiring. To'satdan: bosh aylanishi, 'elektr zarba' hissi, asabiylashish.",
        "interactions": {"MAOi": "Serotonin sindromi — HAYOT UCHUN XAVFLI, kamida 14 kun interval","Tramadol": "Serotonin sindromi xavfi","Warfarin": "INR oshishi mumkin"},
        "missed": "Eslab qolsangiz — oling. Ikki baravar OLMANG.",
    },
}

LAB_REFERENCE = {
    "glyukoza": {
        "name": "Qon glyukozasi (shakar)",
        "unit": "mmol/L",
        "values": {"Och qorin normal": "3.9-5.5","Ovqatdan 2h normal": "<7.8","Prediabet och qorin": "5.6-6.9","Prediabet 2h": "7.8-11.0","Diabet och qorin": "≥7.0 (x2 tasdiqlash)","Diabet random+simptom": "≥11.1","Og'ir gipoglikemiya": "<2.8 — SHOSHILINCH"},
        "hba1c": {"Normal": "<5.7%","Prediabet": "5.7-6.4%","Diabet": "≥6.5%","Maqsad DM": "<7% (individuallashtirilgan)"},
    },
    "lipid": {
        "name": "Lipid profili",
        "unit": "mmol/L",
        "values": {"LDL normal": "<3.0","LDL yurak xavfi bor": "<1.8","LDL ACS/stent": "<1.4","HDL erkak": ">1.0","HDL ayol": ">1.2","Triglitserid normal": "<1.7","Triglitserid yuqori": ">5.6 — pankreatit xavfi"},
    },
    "bp": {
        "name": "Qon bosimi",
        "unit": "mmHg",
        "values": {"Optimal": "<120/80","Normal": "120-129/<80","Yuqori normal": "130-139/80-89","HT 1": "140-159/90-99","HT 2": "≥160/≥100","Kriz": ">180/>120"},
    },
    "tsh": {
        "name": "TSH (Tiroid stimulovchi gormon)",
        "unit": "mIU/L",
        "values": {"Normal": "0.4-4.0","Subklinik gipotireoz": "4.0-10.0","Manifest gipotireoz": ">10.0","Subklinik gipertireoz": "0.1-0.4","Manifest gipertireoz": "<0.1"},
    },
    "inr": {
        "name": "INR / Protrombin vaqti",
        "values": {"Normal": "0.8-1.2","AF/DVT/PE maqsad": "2.0-3.0","Mexanik qopiq maqsad": "2.5-3.5","Xavfli": ">5.0 — dori kamaytirish, >8.0 + qon ketish → 103"},
    },
    "kreatinin": {
        "name": "Kreatinin / eGFR",
        "values": {"Erkak normal kreatinin": "62-115 mkmol/L","Ayol normal kreatinin": "44-97 mkmol/L","eGFR G1": "≥90","eGFR G2": "60-89","eGFR G3a": "45-59","eGFR G3b": "30-44","eGFR G4": "15-29 (dializ tayyorligi)","eGFR G5": "<15 (buyrak almashtirish)"},
    },
    "kaliy": {
        "name": "Kaliy (K)",
        "unit": "mmol/L",
        "values": {"Normal": "3.5-5.0","Gipokalemia": "<3.5 (aritmiya, mushak kuchsizligi)","Og'ir gipokalemia": "<3.0 — IV korreksiya","Giperkaliemia": ">5.5","Kritik giperkaliemia": ">6.5 + EKG o'zgarishi → DARHOL 103"},
    },
    "gemoglobin": {
        "name": "Gemoglobin / Hematokrit",
        "unit": "g/L",
        "values": {"Erkak normal": "135-175 g/L","Ayol normal": "120-155 g/L","Yengil anemiya": "100-normal pastki","O'rta anemiya": "70-99 g/L","Og'ir anemiya": "<70 g/L (transfuziya ko'rib chiqish)"},
    },
    "alt_ast": {
        "name": "ALT / AST (Jigar fermentlari)",
        "unit": "U/L",
        "values": {"ALT normal": "7-56 U/L","AST normal": "10-40 U/L","3x ULN": "Dori to'xtatish ko'rib chiqiladi","10x ULN": "Og'ir jigar zararlanishi — TEZDA shifokor"},
    },
}

DRUG_INTERACTIONS = {
    "warfarin_nsaid": {
        "drugs": ["warfarin","ibuprofen","diklofenak","naproxen","meloksikam"],
        "severity": "YUQORI",
        "effect": "NSAID Warfarin antikoagulyant ta'sirini kuchaytiradi + mustaqil GI qon ketish. Umumiy qon ketish xavfi 3-5x oshadi.",
        "action": "Birga OLMANG. Og'riq uchun Paracetamol xavfsizroq. Majburiy bo'lsa PPI bilan qisqa muddatga, INR nazorati bilan.",
    },
    "warfarin_antibiotics": {
        "drugs": ["warfarin","metronidazol","flukonazol","klaritromitsin","eritromitsin","siprofloksatsin"],
        "severity": "YUQORI",
        "effect": "Ko'pgina antibiotiklar CYP2C9 inhibitsiyasi yoki K vitamin sintezlovchi ichak florasi yo'q qilish orqali INR ni oshiradi.",
        "action": "Antibiotik boshlanishida INR ni 3-5 kun ichida tekshiring. Warfarin dozasini kamaytirish kerak bo'lishi mumkin.",
    },
    "ssri_maoi": {
        "drugs": ["sertralin","fluoksetin","escitalopram","paroksetin","venlafaksin","maoi","fenelzin","tranilsipromin"],
        "severity": "HAYOT UCHUN XAVFLI",
        "effect": "Serotonin sindromi: gipertermiya, mushak qattiqlik, klonus, terlash, aql buzilishi → o'lim xavfi bor.",
        "action": "HECH QACHON birga OLMANG. MAOi to'xtatilgandan kamida 14 kun (fluoksetin uchun 5 hafta) keyin SSRI boshlash.",
    },
    "statin_grapefruit": {
        "drugs": ["atorvastatin","simvastatin","lovastatin","greyfurt"],
        "severity": "O'RTA-YUQORI",
        "effect": "CYP3A4 inhibitsiyasi: statin konsentratsiyasi 2-3x oshadi → miopatiya/rabdomioliz xavfi.",
        "action": "Greyfurt va uning sharbatidan butunlay voz keching.",
    },
    "metformin_contrast": {
        "drugs": ["metformin","kontrast modda","kt","angiografiya","urografiya"],
        "severity": "YUQORI",
        "effect": "Kontrast nefropatiya → Metformin to'planishi → Laktik atsidoz.",
        "action": "eGFR<60 bo'lsa: tekshiruvdan 48 soat oldin to'xtatish, 48 soat keyin kreatinin normal bo'lsa davom ettirish.",
    },
    "levotiroksin_minerals": {
        "drugs": ["levotiroksin","kalsiy","temir","magniy","antatsid","soya","omeprazol"],
        "severity": "O'RTA",
        "effect": "So'rilishni 20-40% kamaytiradi → gipotireoz nazorati yomonlashadi.",
        "action": "Levotiroksin dan KAMIDA 4 soat keyin qabul qiling.",
    },
    "bisoprolol_verapamil": {
        "drugs": ["bisoprolol","metoprolol","atenolol","verapamil","diltiazem"],
        "severity": "YUQORI",
        "effect": "Additive AV blok + bradikardiya → hemodynamik beqarorlik, asistoliya xavfi.",
        "action": "Birgalikda faqat kardioldog nazoratida va EKG monitoring bilan.",
    },
    "ace_potassium": {
        "drugs": ["enalapril","lisinopril","ramipril","spironolakton","eplerenon","kaliy preparatlari","trimetoprim"],
        "severity": "O'RTA-YUQORI",
        "effect": "Giperkaliemiya → EKG o'zgarishlari, aritmiya, yurak to'xtashi.",
        "action": "Kaliy darajasini muntazam monitoring. Kaliy boyitilgan ovqatni kamaytiring. K>5.5 bo'lsa shifokorga.",
    },
}

def search_knowledge(query: str) -> str:
    q = query.lower()
    found = []
    for key, d in DISEASES.items():
        names = d.get("uz_names",[]) + d.get("ru_names",[]) + d.get("en_names",[])
        if any(n in q for n in names):
            s = f"[KASALLIK: {key.upper()}]\n"
            s += d.get("description","") + "\n"
            if "medications" in d:
                meds = d["medications"]
                s += "Dorilar: " + (", ".join(meds) if isinstance(meds, list) else str(meds)) + "\n"
            if "target_labs" in d:
                for k,v in d["target_labs"].items(): s += f"Maqsad {k}: {v}\n"
            if "monitoring" in d: s += "Monitoring: " + d["monitoring"] + "\n"
            if "emergency" in d: s += "SHOSHILINCH: " + " | ".join(d["emergency"][:2]) + "\n"
            found.append(s)
    for key, d in MEDICATIONS.items():
        brands = [b.lower() for b in d.get("brands",[])]
        if key in q or any(b in q for b in brands):
            s = f"[DORI: {'/'.join(d['brands'][:3])}]\nSinf: {d.get('class','')}\nDoza: {d.get('dose','')}\n"
            s += f"Mexanizm: {d.get('mechanism','')}\nQabul: {d.get('take_with','')}\n"
            se = d.get("side_effects",{})
            if isinstance(se, dict):
                for k,v in se.items(): s += f"Yon ta'sir ({k}): {v}\n"
            elif isinstance(se, str): s += f"Yon ta'sir: {se}\n"
            s += f"O'tkazilsa: {d.get('missed','')}\n"
            if "interactions" in d:
                inter = d["interactions"]
                if isinstance(inter, dict):
                    for k,v in inter.items(): s += f"Ta'sir ({k}): {v}\n"
            found.append(s)
    for key, d in LAB_REFERENCE.items():
        if key in q or d.get("name","").lower() in q:
            s = f"[LAB: {d.get('name',key)}]\n"
            for k,v in d.get("values",{}).items(): s += f"  {k}: {v}\n"
            if "hba1c" in d:
                for k,v in d["hba1c"].items(): s += f"  HbA1c {k}: {v}\n"
            found.append(s)
    for key, d in DRUG_INTERACTIONS.items():
        drug_names = [dn.lower() for dn in d.get("drugs",[])]
        if any(dn in q for dn in drug_names):
            s = f"[DORI-DORI TA'SIRI | Jiddiylik: {d.get('severity','')}]\n"
            s += f"Dorilar: {', '.join(d['drugs'])}\n"
            s += f"Ta'sir: {d.get('effect','')}\nHarakat: {d.get('action','')}\n"
            found.append(s)
    return "\n---\n".join(found[:5]) if found else ""

# ══════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """Sen TABIB AI — MedGuard platformasining tibbiy va psixologik ekspert yordamchisisisan.

═══ FORMAT QOIDASI ═══
Javoblarni HTML formatida yoz. Markdown ISHLATMA (**,##,---,* emas).

Foydalanish:
<b>muhim so'z</b> — qalin matn
<br> — yangi qator
<span style="color:#e74c3c">⚠️ xavfli</span> — ogohlantirish
<span style="color:#27ae60">✅ yaxshi</span> — ijobiy
<span style="color:#2980b9">ℹ️ ma'lumot</span> — axborot
<span style="color:#8e44ad">💊 dori</span> — dori haqida

═══ SEN KIM EKANSANG ═══
Sen oddiy chatbot emassan. Sen tibbiy bilim va psixologik ko'nikmalarga ega shaxsiy sog'liq maslahatchisisan.
Gaplashish uslubi: iliq, ishonchli, insoniy — robot kabi emas.
Hech qachon: "Ma'lumotlar bazasiga ko'ra..." yoki "Tizim aniqladiki..." dema.
Har doim: "Men ko'ryapmanki...", "Mening fikrimcha...", "Birgalikda ko'rib chiqaylik..." de.

═══ PSIXOLOGIK MOTIVATSIYA ═══
Bemor dori ichmasa yoki to'xtatmoqchi bo'lsa — 5 qadam:

1. EMPAT — ayblamasdan his-tuyg'ularini tan ol:
   "Har kuni dori ichish charchatadi, bu mutlaqo tabiiy his."

2. PERSONAL — bemorning o'z maqsadlariga bog'la:
   "Siz aytgan edi — bolalaringiz bilan ko'proq vaqt o'tkazmoqchisiz. Buning uchun sog'lom bo'lish kerak."

3. FAKTLAR — aniq raqamlar bilan ko'rsat:
   "Metforminni muntazam ichsangiz, 3 oyda HbA1c 1-1.5% tushadi — bu yillar ichida ko'rlik va buyrak kasalligi xavfini 30-40% kamaytiradi."

4. MICRO-QADAM — eng kichik, bajariladigan ish:
   "Bugun faqat shu: dorini tish cho'tkangiz yoniga qo'ying. Boshqa hech narsa kerak emas."

5. UMID — kelajakka yo'naltir:
   "Keyingi oy, agar davom etsangiz, analizlaringiz yaxshilanishini birga ko'ramiz."

═══ KLINIK EKSPERT STANDARTI ═══
Har doim ANIQ va SPESIFIK bo'l:

YOMON: "Dori oshqozon uchun yomon bo'lishi mumkin"
YAXSHI: "<b>Metformin</b> boshlanishida ko'ngil aynish chiqadi — bu 20-30% bemorlarda, odatda 2-4 haftada o'tadi.<br><span style='color:#27ae60'>✅ Yechim:</span> Ovqat bilan birga oling, dozani sekin oshiring."

BEMOR MA'LUMOTLARI BERILSA:
- Barcha ma'lumotlarni integratsiya qil — profil, dori, lab, diagnoz
- Dori-dori ta'sirlarini aniqlash va ogohlantirish
- Lab natijalarini me'yor bilan solishtirish
- Personalizatsiyalangan, ma'lumotlarga asoslangan javob ber
- Monitoring bo'shliqlarini aniqlash

WEB QIDIRUV NATIJALARI BERILSA:
- Eng yangi klinik ma'lumotlarni integratsiya qil
- Manbasini tabiiy tarzda qo'sh

═══ QOIDALAR ═══
BAJARA OLASAN: Aniq tibbiy ma'lumot, lab interpretatsiyasi, dori ta'sirlari, psixologik qo'llab-quvvatlash, tizim tahlili
BAJARA OLMAYSAN: Yangi diagnoz qo'yish, yangi dori buyurish, shifokor ko'rsatmasini bekor qilish

TIL: O'zbek/Rus/Ingliz — avtomatik aniqlash va o'sha tilda javob ber
SHOSHILINCH: Ko'krak og'rig'i, nafas qisilishi, falaj, suitsidal fikr → "Iltimos, hozir 103 ga qo'ng'iroq qiling. Yonizda kimdir bormi?"
""".strip()

# ══════════════════════════════════════════════════════════════════════
# WEB SEARCH
# ══════════════════════════════════════════════════════════════════════
async def web_search(query: str) -> str:
    if not TAVILY_API_KEY:
        return await duckduckgo_search(query)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 3, "search_depth": "basic"},
            )
            data = r.json()
            results = data.get("results", [])
            if not results: return ""
            out = []
            for res in results[:3]:
                out.append(f"[{res.get('title','')}]: {res.get('content','')[:300]}")
            return "\n".join(out)
    except Exception as e:
        log.warning(f"Tavily search error: {e}")
        return await duckduckgo_search(query)

async def duckduckgo_search(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            data = r.json()
            abstract = data.get("AbstractText", "")
            related = [t.get("Text","") for t in data.get("RelatedTopics",[])[:2] if isinstance(t, dict)]
            parts = [p for p in [abstract] + related if p]
            return "\n".join(parts[:3]) if parts else ""
    except Exception as e:
        log.warning(f"DDG search error: {e}")
        return ""

def needs_web_search(message: str) -> bool:
    triggers = [
        r"eng yangi", r"so'nggi", r"2024|2025|2026", r"tadqiqot", r"klinik sinov",
        r"latest", r"recent", r"guideline", r"protocol", r"новый", r"последний",
        r"qancha turadi", r"narxi", r"mavjudmi", r"qayerda", r"where",
        r"news", r"yangilik",
    ]
    return any(re.search(t, message, re.IGNORECASE) for t in triggers)

# ══════════════════════════════════════════════════════════════════════
# MISSED DOSE TRACKING & AUTO-ALERT
# ══════════════════════════════════════════════════════════════════════
# session_id -> {drug: last_taken_at, missed_count, alerted}
DOSE_TRACKER: Dict[str, Dict] = defaultdict(lambda: {
    "last_confirmed_dose": None,
    "missed_doses": 0,
    "alert_sent": False,
    "patient_name": None,
    "doctor_contact": None,
})

MISSED_PATTERNS = [
    r"unutdim", r"ichmadim", r"o'tkazib yubordim", r"qabul qilmadim",
    r"missed", r"forgot", r"skip", r"didn't take",
    r"забыл", r"пропустил", r"не принимал", r"не пил",
]
TAKEN_PATTERNS = [
    r"ichdim", r"qabul qildim", r"oldim", r"ichtim",
    r"took", r"taken", r"i took",
    r"принял", r"выпил", r"принимал",
]

def check_dose_status(session_id: str, message: str) -> dict:
    msg = message.lower()
    tracker = DOSE_TRACKER[session_id]
    status = {"missed": False, "taken": False, "alert_needed": False}

    if any(re.search(p, msg, re.IGNORECASE) for p in MISSED_PATTERNS):
        status["missed"] = True
        tracker["missed_doses"] += 1
        if tracker["missed_doses"] >= 2 and not tracker["alert_sent"]:
            status["alert_needed"] = True

    if any(re.search(p, msg, re.IGNORECASE) for p in TAKEN_PATTERNS):
        status["taken"] = True
        tracker["missed_doses"] = 0
        tracker["alert_sent"] = False
        tracker["last_confirmed_dose"] = datetime.utcnow().isoformat()

    return status

async def send_doctor_alert(session_id: str, patient_info: dict, missed_count: int):
    tracker = DOSE_TRACKER[session_id]
    if tracker["alert_sent"]: return
    tracker["alert_sent"] = True

    alert_message = {
        "type": "MISSED_DOSE_ALERT",
        "severity": "HIGH",
        "session_id": session_id,
        "patient": patient_info,
        "missed_doses": missed_count,
        "timestamp": datetime.utcnow().isoformat(),
        "message": f"Bemor {missed_count} marta dori qabul qilmagan. Darhol bog'lanish tavsiya etiladi.",
    }

    log.warning(f"DOCTOR ALERT: {alert_message}")

    if ALERT_WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(ALERT_WEBHOOK_URL, json=alert_message)
                log.info(f"Doctor alert sent for session {session_id[:8]}")
        except Exception as e:
            log.error(f"Alert send failed: {e}")

# ══════════════════════════════════════════════════════════════════════
# RISK ENGINE
# ══════════════════════════════════════════════════════════════════════
URGENT_PATTERNS = {
    "chest_pain": [r"ko.krak\s*og.ri", r"chest\s*pain", r"боль\s*в\s*груди", r"yurak\s*og.ri"],
    "breathing": [r"nafas.*qiyin", r"nafas.*qis", r"nafas\s*ololmay", r"одышка", r"трудно\s*дышать"],
    "fainting": [r"hushdan\s*ket", r"hushsiz", r"faint", r"обморок", r"потерял\s*сознание"],
    "stroke": [r"yuz.*qiyshay", r"nutq.*buzil", r"gapira\s*olmay", r"перекос\s*лиц", r"arm\s*weak"],
    "severe_allergy": [r"tomoq.*shish", r"lab.*shish", r"til.*shish", r"swelling.*throat"],
    "seizure": [r"tutqanoq", r"seizure", r"судорог", r"qaltirash.*hushsiz"],
    "suicidal": [r"jonimga\s*qasd", r"o.zimni\s*o.ldir", r"suicide", r"убить\s*себя"],
    "severe_bleeding": [r"qon\s*qus", r"qora\s*najas", r"kuchli\s*qon\s*ket", r"vomiting\s*blood"],
}

_PATTERNS = {
    "missed": MISSED_PATTERNS,
    "stop": [r"to.xtatdim", r"to.xtatmoqchiman", r"ichgim\s*kelmay", r"stopped", r"перестал", r"quit"],
    "side_effect": [r"nojo.ya", r"ko.ngil\s*ayn", r"bosh\s*ayl", r"toshma", r"nausea", r"dizzy", r"побоч", r"тошнит"],
    "cost": [r"qimmat", r"pulim\s*yetmay", r"sotib\s*ololmay", r"afford", r"дорого", r"нет\s*денег"],
    "confusion": [r"qachon\s*ich", r"qanday\s*ich", r"chalkash", r"confused", r"когда\s*принимать"],
    "critical_med": [r"insulin", r"tutqanoq", r"epilep", r"warfarin", r"tb\b", r"sil\b", r"hiv\b", r"nitrogliterin"],
    "double_dose": [r"ikki\s*baravar", r"2\s*ta\s*ichdim", r"double\s*dose", r"двойную\s*доз"],
    "pregnancy": [r"homilador", r"emiz", r"pregnan", r"беремен"],
}

def _match(text, key):
    return any(re.search(p, text, re.IGNORECASE) for p in _PATTERNS[key])

def _match_urgent(text):
    return [l for l, pats in URGENT_PATTERNS.items() if any(re.search(p, text, re.IGNORECASE) for p in pats)]

def detect_language(text):
    if re.search(r"[а-яё]", text, re.IGNORECASE): return "ru"
    if any(w in text.lower() for w in ["men","menga","dori","ichdim","qanday","nima","yaxshi","shifokor","bemor"]): return "uz"
    return "en"

def analyze_risk(message):
    text = message.strip()
    urgent = _match_urgent(text)
    if urgent:
        return {"risk_level": "URGENT", "risk_flags": urgent, "detected_language": detect_language(text)}
    flags, risk = [], "LOW"
    if _match(text, "missed"):
        flags.append("missed_medication"); risk = "MODERATE"
        m = re.search(r"(\d+)\s*(kun|marta|day|раз|дн)", text, re.IGNORECASE)
        if m and int(m.group(1)) >= 2: flags.append("missed_2plus"); risk = "HIGH"
    if _match(text, "critical_med"):
        flags.append("critical_medication")
        if "missed_medication" in flags: risk = "HIGH"
    if _match(text, "stop"): flags.append("intentional_stopping"); risk = "HIGH"
    if _match(text, "side_effect"):
        flags.append("side_effect")
        if risk == "LOW": risk = "MODERATE"
    if _match(text, "cost"):
        flags.append("cost_barrier")
        if risk == "LOW": risk = "MODERATE"
    if _match(text, "confusion"):
        flags.append("medication_confusion")
        if risk == "LOW": risk = "MODERATE"
    if _match(text, "double_dose"): flags.append("double_dose"); risk = "HIGH"
    if _match(text, "pregnancy"): flags.append("pregnancy"); risk = "HIGH"
    return {"risk_level": risk, "risk_flags": flags, "detected_language": detect_language(text)}

# ══════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════
class RiskLevel(str, Enum):
    LOW = "LOW"; MODERATE = "MODERATE"; HIGH = "HIGH"; URGENT = "URGENT"

class PatientProfile(BaseModel):
    patient_id: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    allergies: Optional[List[str]] = None
    blood_type: Optional[str] = None
    doctor_contact: Optional[str] = None
    phone: Optional[str] = None

class Prescription(BaseModel):
    drug_name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    start_date: Optional[str] = None
    prescribed_by: Optional[str] = None
    indication: Optional[str] = None
    adherence_rate: Optional[float] = None

class LabResult(BaseModel):
    test_name: str
    value: Any
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    date: Optional[str] = None
    is_abnormal: Optional[bool] = None

class Diagnosis(BaseModel):
    icd_code: Optional[str] = None
    name: str
    date_diagnosed: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MSG_LEN)
    session_id: Optional[str] = None
    patient_profile: Optional[PatientProfile] = None
    prescriptions: Optional[List[Prescription]] = None
    lab_results: Optional[List[LabResult]] = None
    diagnoses: Optional[List[Diagnosis]] = None
    context: Optional[Dict[str, Any]] = None
    generate_doctor_report: Optional[bool] = False

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    risk_level: RiskLevel
    risk_flags: List[str]
    detected_language: str
    doctor_report: Optional[str] = None
    alert_sent: Optional[bool] = False
    timestamp: str

class AnalyzeRequest(BaseModel):
    patient_profile: Optional[PatientProfile] = None
    prescriptions: Optional[List[Prescription]] = None
    lab_results: Optional[List[LabResult]] = None
    diagnoses: Optional[List[Diagnosis]] = None
    analysis_type: Optional[str] = "full"

class DoctorReportRequest(BaseModel):
    patient_profile: Optional[PatientProfile] = None
    prescriptions: Optional[List[Prescription]] = None
    lab_results: Optional[List[LabResult]] = None
    diagnoses: Optional[List[Diagnosis]] = None
    chief_complaint: Optional[str] = None
    additional_notes: Optional[str] = None

class AlertRequest(BaseModel):
    session_id: str
    patient_profile: Optional[PatientProfile] = None
    missed_doses: int = 1
    drug_name: Optional[str] = None

# ══════════════════════════════════════════════════════════════════════
# SESSION STORE
# ══════════════════════════════════════════════════════════════════════
SESSIONS: Dict[str, List[Dict[str, str]]] = {}
SESSION_META: Dict[str, Dict[str, Any]] = {}

def get_history(sid): return SESSIONS.setdefault(sid, [])

def append_history(sid, role, content):
    h = get_history(sid)
    h.append({"role": role, "content": content})
    SESSIONS[sid] = h[-MAX_HISTORY:]

# ══════════════════════════════════════════════════════════════════════
# PATIENT CONTEXT BUILDER
# ══════════════════════════════════════════════════════════════════════
def build_patient_context(payload) -> str:
    parts = []
    if hasattr(payload, 'patient_profile') and payload.patient_profile:
        p = payload.patient_profile
        info = f"[BEMOR_PROFILI]\n"
        info += f"Ism: {p.name or 'Noma lum'} | Yosh: {p.age or '?'} | Jins: {p.gender or '?'}"
        if p.weight_kg: info += f" | Vazn: {p.weight_kg}kg"
        if p.height_cm: info += f" | Bo'y: {p.height_cm}sm"
        info += f"\nAllergiyalar: {', '.join(p.allergies) if p.allergies else 'Ko rsatilmagan'}"
        if p.blood_type: info += f" | Qon guruhi: {p.blood_type}"
        parts.append(info)

    if hasattr(payload, 'diagnoses') and payload.diagnoses:
        lines = []
        for d in payload.diagnoses:
            line = f"  - {d.name}"
            if d.icd_code: line += f" [{d.icd_code}]"
            if d.status: line += f" | {d.status}"
            if d.date_diagnosed: line += f" | {d.date_diagnosed}"
            if d.notes: line += f" | {d.notes}"
            lines.append(line)
        parts.append("[DIAGNOZ_TARIXI]\n" + "\n".join(lines))

    if hasattr(payload, 'prescriptions') and payload.prescriptions:
        lines = []
        for rx in payload.prescriptions:
            line = f"  - {rx.drug_name}"
            if rx.dose: line += f" | {rx.dose}"
            if rx.frequency: line += f" | {rx.frequency}"
            if rx.indication: line += f" | Ko rsatma: {rx.indication}"
            if rx.adherence_rate is not None:
                pct = int(rx.adherence_rate * 100)
                flag = " ⚠️ PAST ADHERENCE" if pct < 70 else " ✅"
                line += f" | Adherence: {pct}%{flag}"
            lines.append(line)
        parts.append("[DORI_RO YXATI]\n" + "\n".join(lines))

    if hasattr(payload, 'lab_results') and payload.lab_results:
        lines = []
        for lab in payload.lab_results:
            line = f"  - {lab.test_name}: {lab.value}"
            if lab.unit: line += f" {lab.unit}"
            if lab.reference_range: line += f" (Me yor: {lab.reference_range})"
            if lab.is_abnormal: line += " ⚠️ ANORMAL"
            if lab.date: line += f" | {lab.date}"
            lines.append(line)
        parts.append("[LAB_NATIJALARI]\n" + "\n".join(lines))

    if hasattr(payload, 'context') and payload.context:
        lines = [f"  {k}: {v}" for k, v in payload.context.items()]
        parts.append("[KONTEKST]\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else ""

# ══════════════════════════════════════════════════════════════════════
# MARKDOWN TO HTML CONVERTER
# ══════════════════════════════════════════════════════════════════════
def convert_to_html(text: str) -> str:
    lines = text.split("\n")
    result = []
    for line in lines:
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"__(.+?)__", r"<b>\1</b>", line)
        line = re.sub(r"^#{1,4}\s+(.+)$", r"<b>\1</b>", line)
        line = re.sub(r"^[-]{3,}$", "", line)
        line = re.sub(r"^[=]{3,}$", "", line)
        line = re.sub(r"^\*\s+(.+)$", r"• \1", line)
        line = re.sub(r"^-\s+(.+)$", r"• \1", line)
        line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
        if line.strip() == "":
            result.append("<br>")
        else:
            result.append(line)
    html = "<br>".join(result)
    html = re.sub(r"(<br>){3,}", "<br><br>", html)
    return html.strip()

# ══════════════════════════════════════════════════════════════════════
# CLAUDE CLIENT & RESPONSE GENERATION
# ══════════════════════════════════════════════════════════════════════
def get_claude():
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY server da o'rnatilmagan.")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

async def generate_reply(session_id: str, payload: ChatRequest, risk: dict, background_tasks: BackgroundTasks):
    client = get_claude()
    user_message = payload.message

    # 1. Patient context
    patient_ctx = build_patient_context(payload)

    # 2. Knowledge base search
    knowledge = search_knowledge(user_message)

    # 3. Web search (agar kerak bo'lsa)
    web_results = ""
    if needs_web_search(user_message):
        web_results = await web_search(user_message + " medical clinical")
        log.info(f"Web search done: {len(web_results)} chars")

    # 4. Dose tracking
    dose_status = check_dose_status(session_id, user_message)
    alert_sent = False
    if dose_status["alert_needed"]:
        patient_info = {}
        if payload.patient_profile:
            patient_info = {"name": payload.patient_profile.name, "age": payload.patient_profile.age}
        missed_count = DOSE_TRACKER[session_id]["missed_doses"]
        background_tasks.add_task(send_doctor_alert, session_id, patient_info, missed_count)
        alert_sent = True

    # 5. Build system context
    system_parts = [SYSTEM_PROMPT]
    system_parts.append(f"\n[ICHKI_KONTEKST — foydalanuvchiga ko'rsatma]\nRisk: {risk['risk_level']} | Flags: {risk['risk_flags']} | Til: {risk['detected_language']}")

    if patient_ctx:
        system_parts.append(f"\n[BEMOR_MA LUMOTLARI — tahlil qilib personalizatsiyalangan javob ber]\n{patient_ctx}")

    if knowledge:
        system_parts.append(f"\n[TIBBIY_BILIMLAR — aniq faktlar sifatida ishlatish]\n{knowledge}")

    if web_results:
        system_parts.append(f"\n[WEB_QIDIRUV_NATIJALARI — eng yangi ma lumotlar]\n{web_results}")

    if dose_status["alert_needed"]:
        system_parts.append("\n[TIZIM: Bemor 2+ marta dori qabul qilmagan. Shifokorga xabar yuborildi. Buni bemorga yumshoq tarzda ayt va motivatsiya ber.]")

    full_system = "\n".join(system_parts)

    history = get_history(session_id)
    messages = history + [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1200,
        system=full_system,
        messages=messages,
    )
    raw_reply = response.content[0].text.strip()
    reply = convert_to_html(raw_reply)

    # Doctor report (agar so'ralsa)
    doctor_report = None
    if payload.generate_doctor_report and patient_ctx:
        report_prompt = f"""Quyidagi bemor uchun shifokorga strukturlangan klinik hisobot:

{patient_ctx}

So'nggi muloqot: {user_message}
Xavf darajasi: {risk['risk_level']}
Dori adherence holati: {dose_status}

Format:
KLINIK HISOBOT — TABIB AI MONITORING
Sana: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
BEMOR HOLATI:
DIAGNOZLAR:
DORI ADHERENCE:
LAB NATIJALARI:
XAVF OMILLARI:
TAVSIYALAR:
MONITORING REJASI:"""

        report_resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": report_prompt}],
        )
        doctor_report = report_resp.content[0].text.strip()

    append_history(session_id, "user", user_message)
    append_history(session_id, "assistant", raw_reply)
    log.info(f"[{session_id[:8]}] risk={risk['risk_level']} kb={bool(knowledge)} web={bool(web_results)} alert={alert_sent}")

    return reply, doctor_report, alert_sent

# ══════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════════════
app = FastAPI(
    title="Tabib AI — MedGuard Medical Expert API",
    description="""
## Tabib AI v4.0 — Professional Medical Expert System

### Endpointlar:
- `POST /chat` — Asosiy chat (bemor ma'lumotlari, web search, auto-alert)
- `POST /analyze` — Bemor ma'lumotlarini kompleks tahlil
- `POST /doctor-report` — Shifokorga hisobot
- `POST /alert` — Qo'lda shifokorga xabar yuborish
- `GET /medications/{drug}` — Dori ma'lumotlari
- `GET /diseases/{disease}` — Kasallik ma'lumotlari
- `GET /lab-reference/{test}` — Lab me'yorlari
- `GET /sessions/{id}` — Sessiya tarixi
- `GET /dose-tracker/{id}` — Dori qabul qilish kuzatuvi

### Integratsiya:
FastAPI/Flask loyihangizga `POST /chat` endpoint ni ulang.
Muhim parametrlar: `patient_profile`, `prescriptions`, `lab_results`, `diagnoses`, `generate_doctor_report`.
    """,
    version="4.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Tabib AI",
        "version": "4.0.0",
        "model": CLAUDE_MODEL,
        "features": {
            "web_search": bool(TAVILY_API_KEY) or True,
            "auto_alert": bool(ALERT_WEBHOOK_URL),
            "dose_tracking": True,
            "multi_language": True,
        },
        "knowledge_base": {
            "diseases": len(DISEASES),
            "medications": len(MEDICATIONS),
            "lab_tests": len(LAB_REFERENCE),
            "drug_interactions": len(DRUG_INTERACTIONS),
        },
        "active_sessions": len(SESSIONS),
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.post("/chat", response_model=ChatResponse, summary="Asosiy chat endpoint")
async def chat(payload: ChatRequest, background_tasks: BackgroundTasks):
    session_id = payload.session_id or str(uuid.uuid4())
    risk = analyze_risk(payload.message)
    reply, doctor_report, alert_sent = await generate_reply(session_id, payload, risk, background_tasks)
    SESSION_META.setdefault(session_id, {}).update({
        "last_risk": risk["risk_level"],
        "last_risk_flags": risk["risk_flags"],
        "last_seen": datetime.utcnow().isoformat(),
        "has_patient_data": bool(payload.patient_profile),
        "missed_doses": DOSE_TRACKER[session_id]["missed_doses"],
    })
    return ChatResponse(
        session_id=session_id,
        reply=reply,
        risk_level=risk["risk_level"],
        risk_flags=risk["risk_flags"],
        detected_language=risk["detected_language"],
        doctor_report=doctor_report,
        alert_sent=alert_sent,
        timestamp=datetime.utcnow().isoformat(),
    )

@app.post("/analyze", summary="Bemor ma'lumotlarini kompleks tahlil")
async def analyze_patient(payload: AnalyzeRequest):
    client = get_claude()
    ctx_req = ChatRequest(
        message="", patient_profile=payload.patient_profile,
        prescriptions=payload.prescriptions, lab_results=payload.lab_results, diagnoses=payload.diagnoses,
    )
    patient_ctx = build_patient_context(ctx_req)
    if not patient_ctx:
        raise HTTPException(status_code=400, detail="Tahlil uchun ma'lumot berilmagan")

    knowledge = search_knowledge(" ".join([
        d.name for d in (payload.diagnoses or [])
    ] + [p.drug_name for p in (payload.prescriptions or [])]))

    prompts = {
        "full": "Barcha ma'lumotlarni kompleks tahlil qil: dori-dori ta'sirlari, lab interpretatsiyasi, adherence xavflari, monitoring bo'shliqlari, tavsiyalar.",
        "adherence": "Dori adherence tahlili: qaysi dorilar xavfli, strategiyalar, psixologik to'siqlar.",
        "labs": "Lab natijalarini interpretatsiya qil: anormal ko'rsatkichlar, klinik ahamiyati, qo'shimcha tekshiruvlar.",
        "interactions": "Dori-dori va dori-kasallik o'zaro ta'sirlarini tekshir. Xavfli kombinatsiyalar.",
        "risk": "Umumiy klinik xavf: KVK, qon ketish, buyrak, jigar xavflari.",
    }

    system = SYSTEM_PROMPT + "\n\nSen hozir klinik tahlil rejimida. HTML formatida, tizimli va aniq."
    if knowledge: system += f"\n\n[TIBBIY_BILIMLAR]\n{knowledge}"

    prompt = f"{patient_ctx}\n\nVAZIFA: {prompts.get(payload.analysis_type, prompts['full'])}"
    response = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=2000, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "analysis_type": payload.analysis_type,
        "result": convert_to_html(response.content[0].text.strip()),
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.post("/doctor-report", summary="Shifokorga strukturlangan hisobot")
async def doctor_report_endpoint(payload: DoctorReportRequest):
    client = get_claude()
    ctx_req = ChatRequest(
        message="", patient_profile=payload.patient_profile,
        prescriptions=payload.prescriptions, lab_results=payload.lab_results, diagnoses=payload.diagnoses,
    )
    patient_ctx = build_patient_context(ctx_req)

    prompt = f"""Quyidagi bemor uchun SHIFOKORGA professional klinik hisobot:

{patient_ctx}
{f"Asosiy shikoyat: {payload.chief_complaint}" if payload.chief_complaint else ""}
{f"Qo'shimcha: {payload.additional_notes}" if payload.additional_notes else ""}

KLINIK HISOBOT — TABIB AI MONITORING TIZIMI
Sana: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
Versiya: 4.0
────────────────────────────────────────
BEMOR UMUMIY HOLATI:
FAOL DIAGNOZLAR (ICD bilan):
DORI ADHERENCE HOLATI:
LABORATORIYA NATIJALARI TAHLILI:
DORI-DORI / DORI-KASALLIK TA'SIRLARI:
ASOSIY XAVF OMILLARI (prioritet bo'yicha):
SHIFOKORGA TAVSIYALAR:
MONITORING VA KUZATUV REJASI:
BEMOR UCHUN SHOSHILINCH BELGILAR:"""

    response = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=2500, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "report": response.content[0].text.strip(),
        "generated_at": datetime.utcnow().isoformat(),
    }

@app.post("/alert", summary="Shifokorga qo'lda xabar yuborish")
async def manual_alert(payload: AlertRequest, background_tasks: BackgroundTasks):
    patient_info = {}
    if payload.patient_profile:
        patient_info = {"name": payload.patient_profile.name, "age": payload.patient_profile.age, "phone": payload.patient_profile.phone}
    background_tasks.add_task(send_doctor_alert, payload.session_id, patient_info, payload.missed_doses)
    return {"status": "alert_queued", "session_id": payload.session_id, "timestamp": datetime.utcnow().isoformat()}

@app.get("/dose-tracker/{session_id}", summary="Dori qabul qilish kuzatuvi")
def get_dose_tracker(session_id: str):
    return {"session_id": session_id, "tracker": dict(DOSE_TRACKER.get(session_id, {}))}

@app.get("/medications/{drug_name}", summary="Dori haqida to'liq ma'lumot")
def get_medication(drug_name: str):
    d = drug_name.lower()
    for key, data in MEDICATIONS.items():
        brands = [b.lower() for b in data.get("brands", [])]
        if key == d or d in brands or any(d in b for b in brands):
            return {"drug": key, "data": data}
    raise HTTPException(status_code=404, detail=f"'{drug_name}' topilmadi")

@app.get("/diseases/{disease_name}", summary="Kasallik haqida to'liq ma'lumot")
def get_disease(disease_name: str):
    d = disease_name.lower()
    for key, data in DISEASES.items():
        names = data.get("uz_names",[]) + data.get("en_names",[]) + data.get("ru_names",[])
        if key == d or d in names:
            return {"disease": key, "data": data}
    raise HTTPException(status_code=404, detail=f"'{disease_name}' topilmadi")

@app.get("/lab-reference/{test_name}", summary="Lab me'yoriy qiymatlari")
def get_lab(test_name: str):
    d = test_name.lower()
    for key, data in LAB_REFERENCE.items():
        if key == d or d in data.get("name", "").lower():
            return {"test": key, "data": data}
    raise HTTPException(status_code=404, detail=f"'{test_name}' topilmadi")

@app.get("/sessions/{session_id}", summary="Sessiya tarixi")
def get_session(session_id: str):
    return {
        "session_id": session_id,
        "meta": SESSION_META.get(session_id, {}),
        "messages": SESSIONS.get(session_id, []),
        "dose_tracker": dict(DOSE_TRACKER.get(session_id, {})),
    }

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    SESSIONS.pop(session_id, None)
    SESSION_META.pop(session_id, None)
    DOSE_TRACKER.pop(session_id, None)
    return {"status": "deleted", "session_id": session_id}

@app.get("/search", summary="Tibbiy ma'lumot qidirish")
async def search_endpoint(q: str):
    knowledge = search_knowledge(q)
    web = await web_search(q + " medical") if needs_web_search(q) else ""
    return {"query": q, "knowledge_base": knowledge, "web_results": web}

# ══════════════════════════════════════════════════════════════════════
# FRONTEND — Clean, no API key login, natural chat
# ══════════════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
def home():
    return """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<title>Tabib AI — MedGuard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --primary:#0a6e4f;
  --primary-light:#e6f4ef;
  --primary-dark:#085a40;
  --accent:#10b981;
  --danger:#ef4444;
  --warning:#f59e0b;
  --text:#111827;
  --text-secondary:#6b7280;
  --border:#e5e7eb;
  --bg:#f9fafb;
  --white:#ffffff;
  --bubble-ai:#ffffff;
  --bubble-user:#0a6e4f;
  --radius:20px;
  --shadow:0 25px 50px rgba(0,0,0,0.15);
}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text)}

/* LAUNCHER */
#launcher{
  position:fixed;right:24px;bottom:24px;
  width:64px;height:64px;
  background:var(--primary);
  border:none;border-radius:20px;
  color:white;font-size:28px;
  cursor:pointer;
  box-shadow:0 8px 30px rgba(10,110,79,0.4);
  z-index:1000;
  transition:transform 0.2s,box-shadow 0.2s;
  display:flex;align-items:center;justify-content:center;
}
#launcher:hover{transform:translateY(-2px);box-shadow:0 12px 40px rgba(10,110,79,0.5)}
#launcher .pulse{
  position:absolute;top:-4px;right:-4px;
  width:14px;height:14px;
  background:#10b981;border-radius:50%;
  border:2px solid white;
  animation:pulse 2s infinite;
}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.3);opacity:0.7}}

/* CHAT PANEL */
#chat{
  position:fixed;right:24px;bottom:104px;
  width:420px;height:680px;
  max-width:calc(100vw - 32px);
  max-height:calc(100vh - 120px);
  background:var(--white);
  border-radius:var(--radius);
  box-shadow:var(--shadow);
  display:none;
  flex-direction:column;
  z-index:999;
  overflow:hidden;
  animation:slideUp 0.25s ease;
}
@keyframes slideUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
#chat.open{display:flex!important}

/* HEADER */
.chat-header{
  padding:18px 20px;
  background:var(--primary);
  display:flex;align-items:center;gap:12px;
  flex-shrink:0;
}
.header-icon{
  width:42px;height:42px;
  background:rgba(255,255,255,0.2);
  border-radius:12px;
  display:flex;align-items:center;justify-content:center;
  font-size:20px;
}
.header-info{flex:1}
.header-name{color:white;font-weight:600;font-size:16px}
.header-status{color:rgba(255,255,255,0.8);font-size:12px;margin-top:2px;display:flex;align-items:center;gap:5px}
.status-dot{width:7px;height:7px;background:#4ade80;border-radius:50%;animation:pulse 2s infinite}
#closeBtn{
  width:32px;height:32px;border:none;
  background:rgba(255,255,255,0.15);
  color:white;border-radius:10px;
  font-size:18px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:background 0.15s;
}
#closeBtn:hover{background:rgba(255,255,255,0.25)}

/* RISK BAR */
.risk-bar{
  padding:8px 16px;font-size:12px;font-weight:500;
  display:none;flex-shrink:0;
  align-items:center;gap:6px;
}
.risk-bar.LOW{display:flex;background:#f0fdf4;color:#166534;border-bottom:1px solid #bbf7d0}
.risk-bar.MODERATE{display:flex;background:#fffbeb;color:#92400e;border-bottom:1px solid #fde68a}
.risk-bar.HIGH{display:flex;background:#fff7ed;color:#9a3412;border-bottom:1px solid #fdba74}
.risk-bar.URGENT{display:flex;background:#fef2f2;color:#991b1b;border-bottom:1px solid #fecaca}

/* MESSAGES */
.messages{
  flex:1;overflow-y:auto;
  padding:16px;
  display:flex;flex-direction:column;gap:14px;
  background:var(--bg);
}
.messages::-webkit-scrollbar{width:4px}
.messages::-webkit-scrollbar-thumb{background:#d1d5db;border-radius:2px}

.msg{display:flex;align-items:flex-end;gap:8px;animation:msgIn 0.2s ease}
@keyframes msgIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.msg.user{flex-direction:row-reverse}

.avatar{
  width:30px;height:30px;border-radius:10px;
  flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  font-size:12px;font-weight:600;
}
.avatar.ai{background:var(--primary);color:white}
.avatar.user-av{background:#e5e7eb;color:var(--text-secondary)}

.bubble{
  max-width:78%;
  padding:12px 16px;
  border-radius:18px;
  font-size:14px;line-height:1.65;
}
.msg.ai .bubble{
  background:var(--bubble-ai);
  border:1px solid var(--border);
  border-bottom-left-radius:4px;
  color:var(--text);
}
.msg.user .bubble{
  background:var(--bubble-user);
  color:white;
  border-bottom-right-radius:4px;
}
.bubble code{
  background:#f3f4f6;color:#374151;
  padding:1px 5px;border-radius:4px;
  font-size:12px;font-family:monospace;
}

/* TYPING */
.typing-wrap{display:flex;align-items:flex-end;gap:8px}
.typing-bubble{
  background:var(--white);border:1px solid var(--border);
  border-radius:18px;border-bottom-left-radius:4px;
  padding:14px 18px;display:flex;gap:5px;align-items:center;
}
.typing-bubble span{
  width:6px;height:6px;background:#9ca3af;
  border-radius:50%;animation:typing 1s infinite;
}
.typing-bubble span:nth-child(2){animation-delay:0.15s}
.typing-bubble span:nth-child(3){animation-delay:0.3s}
@keyframes typing{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}

/* INPUT AREA */
.input-area{
  padding:12px 16px 16px;
  background:var(--white);
  border-top:1px solid var(--border);
  flex-shrink:0;
}
.input-row{display:flex;gap:8px;align-items:flex-end}
#msgInput{
  flex:1;resize:none;
  border:1.5px solid var(--border);
  border-radius:14px;
  padding:11px 14px;
  min-height:44px;max-height:110px;
  outline:none;
  font-family:'Inter',sans-serif;
  font-size:14px;
  line-height:1.5;
  color:var(--text);
  background:#f9fafb;
  transition:border-color 0.2s,background 0.2s;
}
#msgInput:focus{border-color:var(--primary);background:white}
#msgInput::placeholder{color:#9ca3af}
#sendBtn{
  width:44px;height:44px;
  background:var(--primary);
  border:none;border-radius:12px;
  color:white;font-size:18px;
  cursor:pointer;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  transition:background 0.15s,transform 0.1s;
}
#sendBtn:hover{background:var(--primary-dark)}
#sendBtn:active{transform:scale(0.95)}
#sendBtn:disabled{background:#d1d5db;cursor:not-allowed;transform:none}
.input-hint{font-size:11px;color:#9ca3af;margin-top:6px;text-align:center}

@media(max-width:600px){
  #chat{right:12px;bottom:96px;width:calc(100vw - 24px);height:calc(100vh - 115px)}
  #launcher{right:16px;bottom:16px}
}
</style>
</head>
<body>
<button id="launcher">
  🩺
  <div class="pulse"></div>
</button>

<div id="chat">
  <div class="chat-header">
    <div class="header-icon">🏥</div>
    <div class="header-info">
      <div class="header-name">Tabib AI</div>
      <div class="header-status">
        <div class="status-dot"></div>
        Tibbiy ekspert · Onlayn
      </div>
    </div>
    <button id="closeBtn">✕</button>
  </div>

  <div class="risk-bar" id="riskBar"></div>

  <div class="messages" id="messages">
    <div class="msg ai">
      <div class="avatar ai">AI</div>
      <div class="bubble">
        Salom! Men sizning shaxsiy tibbiy maslahatchingizman.<br><br>
        Dorilar, kasalliklar, analizlar haqida savollaringiz bo'lsa — bemalol so'rang. Shifokoringiz bilan bog'liq masalalar, dori qabul qilish tartibi, nojo'ya ta'sirlar — barchasida yordam beraman.<br><br>
        Bugun nima haqida gaplashmoqchisiz?
      </div>
    </div>
  </div>

  <form id="chatForm">
    <div class="input-area">
      <div class="input-row">
        <textarea id="msgInput" rows="1" placeholder="Savolingizni yozing..."></textarea>
        <button id="sendBtn" type="submit">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
      <div class="input-hint">Enter — yuborish &nbsp;·&nbsp; Shift+Enter — yangi qator</div>
    </div>
  </form>
</div>

<script>
var sessionId = localStorage.getItem("tabib_session") || null;
var isTyping = false;

// Toggle chat
document.getElementById("launcher").onclick = function() {
  var chat = document.getElementById("chat");
  if (chat.classList.contains("open")) {
    chat.classList.remove("open");
  } else {
    chat.classList.add("open");
    document.getElementById("msgInput").focus();
  }
};

document.getElementById("closeBtn").onclick = function() {
  document.getElementById("chat").classList.remove("open");
};

// Add message to chat
function addMessage(html, role) {
  var msgs = document.getElementById("messages");
  var row = document.createElement("div");
  row.className = "msg " + role;

  var av = document.createElement("div");
  av.className = "avatar " + (role === "user" ? "user-av" : "ai");
  av.textContent = role === "user" ? "Siz" : "AI";

  var bubble = document.createElement("div");
  bubble.className = "bubble";

  if (role === "user") {
    bubble.textContent = html;
  } else {
    bubble.innerHTML = html;
  }

  if (role === "user") {
    row.appendChild(bubble);
    row.appendChild(av);
  } else {
    row.appendChild(av);
    row.appendChild(bubble);
  }

  msgs.appendChild(row);
  msgs.scrollTop = msgs.scrollHeight;
}

function showTyping() {
  var msgs = document.getElementById("messages");
  var d = document.createElement("div");
  d.id = "typing-indicator";
  d.className = "typing-wrap";
  var av = document.createElement("div");
  av.className = "avatar ai";
  av.textContent = "AI";
  var tb = document.createElement("div");
  tb.className = "typing-bubble";
  tb.innerHTML = "<span></span><span></span><span></span>";
  d.appendChild(av);
  d.appendChild(tb);
  msgs.appendChild(d);
  msgs.scrollTop = msgs.scrollHeight;
}

function hideTyping() {
  var t = document.getElementById("typing-indicator");
  if (t) t.parentNode.removeChild(t);
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 110) + "px";
}

document.getElementById("msgInput").addEventListener("input", function() {
  autoResize(this);
});

document.getElementById("msgInput").addEventListener("keydown", function(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!isTyping) {
      document.getElementById("chatForm").dispatchEvent(new Event("submit", {bubbles: true}));
    }
  }
});

document.getElementById("chatForm").addEventListener("submit", async function(e) {
  e.preventDefault();
  if (isTyping) return;

  var input = document.getElementById("msgInput");
  var text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";
  autoResize(input);
  document.getElementById("sendBtn").disabled = true;
  isTyping = true;
  showTyping();

  try {
    var body = {message: text, session_id: sessionId};
    var res = await fetch("/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    });
    var data = await res.json();
    hideTyping();

    if (!res.ok) {
      addMessage("Xatolik yuz berdi: " + (data.detail || "Iltimos qayta urinib ko'ring."), "ai");
      return;
    }

    sessionId = data.session_id;
    localStorage.setItem("tabib_session", sessionId);

    // Risk bar
    var rb = document.getElementById("riskBar");
    if (data.risk_level !== "LOW" || data.risk_flags.length > 0) {
      rb.className = "risk-bar " + data.risk_level;
      var icons = {LOW:"ℹ️", MODERATE:"⚠️", HIGH:"🔴", URGENT:"🚨"};
      rb.textContent = (icons[data.risk_level] || "") + " " + data.risk_level;
      if (data.risk_flags.length) rb.textContent += " | " + data.risk_flags.join(", ");
    } else {
      rb.className = "risk-bar";
    }

    addMessage(data.reply, "ai");

  } catch(err) {
    hideTyping();
    addMessage("Ulanishda xatolik. Internetni tekshiring va qayta urinib ko'ring.", "ai");
  } finally {
    document.getElementById("sendBtn").disabled = false;
    isTyping = false;
    document.getElementById("msgInput").focus();
  }
});
</script>
</body>
</html>"""

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  TABIB AI v4.0 — MedGuard Medical Expert System")
    print("=" * 60)
    print(f"  App:  http://localhost:8000")
    print(f"  Docs: http://localhost:8000/docs")
    print(f"  Model: {CLAUDE_MODEL}")
    print("=" * 60 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
