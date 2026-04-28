"""
╔══════════════════════════════════════════════════════════════════════╗
║           TABIB AI — CLAUDE-POWERED MEDICAL EXPERT SYSTEM           ║
║           AI Health Hackathon 2026  |  Production Ready             ║
║                                                                      ║
║  Run:  uvicorn main:app --reload --port 8000                         ║
║  Docs: http://localhost:8000/docs                                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, re, uuid, logging
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
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
# CONFIG
# ══════════════════════════════════════════════════════════════════════
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-sonnet-4-6"
MAX_HISTORY       = 30
MAX_MSG_LEN       = 5000

# ══════════════════════════════════════════════════════════════════════
# TIBBIY BILIMLAR BAZASI
# ══════════════════════════════════════════════════════════════════════
DISEASES = {
    "diabet": {
        "uz_names": ["diabet","qand kasalligi","shakar kasalligi","dm"],
        "ru_names": ["диабет","сахарный диабет"],
        "en_names": ["diabetes","type 1 diabetes","type 2 diabetes"],
        "description_uz": "Qand diabeti — qondagi shakar miqdori me'yoridan yuqori bo'lib qoladigan surunkali kasallik.",
        "symptoms_uz": ["Tez-tez siydik qilish","Ko'p suv ichish","Tez charchash","Ko'rish xiralashishi","Oyoq-qo'llarda uvishish","Yaralarning sekin bitishi"],
        "target_values_uz": {"Och qoringa":"3.9-7.0 mmol/L","HbA1c":"< 7%","Qon bosimi":"< 130/80 mmHg"},
        "medications_first_line": ["Metformin 500-2000mg/kun","Empagliflozin 10-25mg","Sitagliptin 100mg","Insulin (1-tur uchun majburiy)"],
        "emergency_signs_uz": ["Gipoglikemiya: titroq+ter+hushdan ketish -> DARHOL 15g glukoza","DKA: meva hidi+chuqur nafas -> TEZDA 103","HHS: juda yuqori shakar+chalkashlik -> TEZDA 103"],
        "monitoring_uz": "HbA1c 3 oyda bir, buyrak (kreatinin, GFR) yiliga bir, ko'z tekshiruvi yiliga bir",
        "complications_uz": ["Nefropatiya","Retinopatiya","Neyropatiya","Kardiovaskulyar kasalliklar","Diabetik oyoq"],
    },
    "gipertoniya": {
        "uz_names": ["gipertoniya","qon bosimi","arterial gipertoniya","bosim","giperton"],
        "ru_names": ["гипертония","артериальная гипертензия","давление"],
        "en_names": ["hypertension","high blood pressure","hbp"],
        "description_uz": "Arterial gipertoniya - qon bosimining 140/90 mmHg dan yuqori bo'lib qolishi.",
        "stages_uz": {"Normal":"<120/80","Yuqori normal":"130-139/85-89","1-daraja":"140-159/90-99","2-daraja":"160-179/100-109","3-daraja":">=180/>=110 — TEZDA shifokor"},
        "medications_first_line": ["ACE ingibitorlari: Enalapril 5-40mg, Lisinopril 10-40mg","ARB: Losartan 50-100mg","CCB: Amlodipine 5-10mg","Beta-blokator: Bisoprolol 2.5-10mg","Diuretik: Indapamid 1.5mg"],
        "emergency_signs_uz": ["Kriz: BP>180/120 + simptom -> TEZDA 103","Ko'krak ogrig'i + yuqori BP -> TEZDA 103","Nutq buzilishi + BP yuqori -> Insult xavfi, TEZDA 103"],
        "monitoring_uz": "Kuniga 2 marta o'lchash (ertalab va kechqurun)",
    },
    "yurak_kasalligi": {
        "uz_names": ["yurak kasalligi","yurak","ishemik yurak","stenokardiya","yurak yetishmovchiligi","yuk"],
        "ru_names": ["ибс","ишемическая болезнь сердца","стенокардия","сердечная недостаточность"],
        "en_names": ["coronary artery disease","heart disease","angina","heart failure","ihd"],
        "medications_first_line": ["Aspirin 75-100mg","Bisoprolol 2.5-10mg","Atorvastatin 20-80mg","ACE ingibitori","Nitrogliterin (og'riqda: 0.4mg til ostiga)"],
        "emergency_signs_uz": ["Ko'krak ogrig'i >20 daqiqa+ter -> DARHOL 103 (infarkt)","Nafas qisilishi+oyoq shishi -> TEZDA 103","Sinkopal holat -> TEZDA 103"],
        "monitoring_uz": "EKG, EXO-KG, lipid profili, BNP yurak yetishmovchiligida",
    },
    "astma": {
        "uz_names": ["astma","bronxial astma","xirillash","nafas yoli"],
        "ru_names": ["астма","бронхиальная астма"],
        "en_names": ["asthma","bronchial asthma","wheezing"],
        "medications_first_line": ["SABA: Salbutamol 100mcg (hujumda)","ICS: Budesonid 200-400mcg 2x/kun","ICS/LABA: Symbicort, Seretide","Montelukast 10mg (qo'shimcha)"],
        "emergency_signs_uz": ["Gapira olmaslik -> DARHOL 103","Lab ko'kimligi -> DARHOL 103","Salbutamol ishlamasa -> TEZDA 103"],
    },
    "copd": {
        "uz_names": ["sopk","surunkali bronxit","emfizema","copd"],
        "ru_names": ["хобл","хроническая обструктивная болезнь"],
        "en_names": ["copd","chronic obstructive pulmonary disease","emphysema"],
        "medications_first_line": ["LAMA: Tiotropium 18mcg 1x/kun","LABA: Formoterol, Salmeterol","ICS/LABA: Seretide, Symbicort","Ekzatserbatsiyada: Prednizolon 40mg x5 kun + antibiotik"],
        "emergency_signs_uz": ["SpO2 <88% -> TEZDA 103","Nafas ololmaslik -> TEZDA 103"],
    },
    "insult": {
        "uz_names": ["insult","miya qon aylanishi","falaj"],
        "ru_names": ["инсульт","кровоизлияние в мозг","ишемический инсульт"],
        "en_names": ["stroke","cva","brain attack"],
        "emergency_signs_uz": ["FAST: Yuz qiyshayishi+Qo'l kuchsizligi+Nutq buzilishi -> DARHOL 103","Ishemik insultda 4.5 soat ichida tPA mumkin - HAR DAQIQA MUHIM"],
        "prevention_uz": ["Qon bosimini nazorat","Fibrillatsiyada antikoagulyant","Statinlar","Antiplatelet"],
    },
    "buyrak_kasalligi": {
        "uz_names": ["buyrak kasalligi","buyrak","pielonefrit","buyrak yetishmovchiligi","ckd"],
        "ru_names": ["почечная болезнь","хроническая болезнь почек","пиелонефрит"],
        "en_names": ["kidney disease","ckd","chronic kidney disease","pyelonephritis"],
        "stages_uz": {"G1":"GFR>=90","G2":"GFR 60-89","G3a":"GFR 45-59","G3b":"GFR 30-44","G4":"GFR 15-29 - Dializ tayyorligi","G5":"GFR<15 - Dializ/Transplantatsiya"},
        "medications_first_line": ["ACE/ARB (proteinuriya uchun)","Diuretiklar","Bikarbonat (atsidozda)"],
        "monitoring_uz": "Kreatinin, eGFR, albuminuriya 3 oyda bir",
        "emergency_signs_uz": ["Anuriya (siydik yo'q) -> TEZDA 103","Giperkaliemiya >6.5 -> TEZDA 103"],
    },
    "qalqonsimon_bez": {
        "uz_names": ["qalqonsimon bez","gipertireoz","gipotireoz","tiroid","zob"],
        "ru_names": ["щитовидная железа","гипотиреоз","гипертиреоз"],
        "en_names": ["thyroid","hypothyroidism","hyperthyroidism","goiter"],
        "medications_first_line_uz": {"gipotireoz":"Levotiroksin 25-200mcg (och qoringa, 30-60 daqiqa oldin)","gipertireoz":"Tiamazol 10-40mg/kun, Propiltiourasil"},
        "monitoring_uz": "TSH 6-8 haftada bir (doza o'zgarganda), keyin 6 oyda bir",
        "important_uz": "Levotiroksin kalsiy, temir, antatsidlardan 4 soat oldin",
    },
    "depressiya": {
        "uz_names": ["depressiya","kayfiyat tushishi","ruhiy kasallik","tashvish"],
        "ru_names": ["депрессия","тревожность","психическое расстройство"],
        "en_names": ["depression","anxiety","mental health"],
        "medications_first_line": ["SSRI 1-qator: Sertralin 50-200mg, Escitalopram 10-20mg, Fluoksetin 20-60mg","SNRI: Venlafaksin 75-225mg","TCA: Amitriptilin (2-qator)"],
        "monitoring_uz": "PHQ-9 skalasi bilan monitoring; dori ta'siri 2-4 haftada boshlanadi",
        "emergency_signs_uz": ["O'z joniga qasd qilish fikri -> DARHOL krizis yordami, 103"],
    },
}

MEDICATIONS = {
    "metformin": {
        "brand_names": ["Metformin","Glucophage","Siofor","Glyukofaj"],
        "class_uz": "Biguanid - insulinga sezuvchanlikni oshiruvchi",
        "indications_uz": "2-tur DM, prediabet, PCOS",
        "dose_uz": "500mg 2x/kun ovqat bilan boshlash, maksimal 2000-2550mg/kun",
        "mechanism_uz": "Jigar glyukoneogenezini kamaytiradi, periferik insulinga sezuvchanlikni oshiradi, GLP-1 sekretsiyasini kuchaytiradi",
        "how_to_take_uz": "Ovqat bilan (ko'ngil aynishini kamaytiradi). Sekin doza oshirish kerak.",
        "common_side_effects_uz": ["Ko'ngil aynishi (vaqtincha, 2-4 haftada o'tadi)","Ich ketishi","B12 vitamini yetishmovchiligi (uzoq muddatda)"],
        "serious_side_effects_uz": ["Laktik atsidoz (GFR<30 da xavf) - zaiflik+nafas qisishi+qorin ogrig'i"],
        "contraindications_uz": ["eGFR<30","Kontrast olishdan 48 soat oldin to'xtatish","Og'ir jigar kasalligi","Spirt suiiste'moli"],
        "interactions_uz": ["Alkogol: laktik atsidoz xavfi","Kontrast: 48 soat to'xtatish"],
        "missed_dose_uz": "Ovqat vaqtida eslab qolsangiz oling. Keyingi ovqatga yaqin bo'lsa - o'tkazib yuboring. IKKI BARAVAR OLMANG.",
        "monitoring_uz": "eGFR va B12 yiliga bir",
    },
    "enalapril": {
        "brand_names": ["Enalapril","Enap","Renitek","Berlipril"],
        "class_uz": "ACE ingibitori",
        "indications_uz": "Gipertoniya, YuYe, Diabetik nefropatiya",
        "dose_uz": "Boshlash: 5mg 1-2x/kun. Maqsad: 10-40mg/kun",
        "mechanism_uz": "Angiotensin II hosil bo'lishini to'xtatadi - vazodilatasiya + aldosteron kamayishi",
        "how_to_take_uz": "Ovqatdan qat'i nazar, bir xil vaqtda",
        "common_side_effects_uz": ["Quruq yo'tal (10-15%: Bradikinin ortishi sabab)","Bosh aylanishi (birinchi dozada)","Holsizlik"],
        "serious_side_effects_uz": ["Angiooedem - DARHOL 103 (hayot uchun xavfli)","Giperkaliemiya","Qon bosimi keskin tushishi"],
        "contraindications_uz": ["Homiladorlik","Angiooedem tarixi","Bilateral renal artery stenosis"],
        "interactions_uz": ["NSAID: BP ta'siri kamayadi + buyrak xavfi","Kaliy preparatlari: giperkaliemiya","Litiy: toksiklik"],
        "missed_dose_uz": "Eslab qolsangiz oling. Keyingi doza yaqin bo'lsa - o'tkazib yuboring.",
        "monitoring_uz": "Kreatinin, kaliy, qon bosimi - dori boshlanishida va 1-2 haftada",
    },
    "amlodipine": {
        "brand_names": ["Amlodipine","Norvasc","Stamlo","Tenox"],
        "class_uz": "Dihidropiridin kalsiy kanal blokatori",
        "indications_uz": "Gipertoniya, Stenokardiya",
        "dose_uz": "2.5-10mg kuniga bir marta",
        "mechanism_uz": "L-tip kalsiy kanallarini bloklab silliq mushak relaksatsiyasi - periferik rezistentlik kamayishi",
        "how_to_take_uz": "Kuniga 1 marta, istalgan vaqtda. Greyfurt bilan OLMANG.",
        "common_side_effects_uz": ["Periferik odem (oyoq shishi)","Refleks taxikardiya","Yuz qizarishi","Bosh ogrig'i"],
        "interactions_uz": ["Greyfurt: CYP3A4 inhibitsiyasi - konsentratsiya 2x oshadi","Simvastatin>20mg: miopatiya xavfi"],
        "missed_dose_uz": "Eslab qolsangiz oling. Ikki baravar OLMANG.",
    },
    "atorvastatin": {
        "brand_names": ["Atorvastatin","Lipitor","Torvast","Atoris"],
        "class_uz": "Statin - HMG-CoA reduktaza inhibitori",
        "indications_uz": "Giperlipidemiya, KVK profilaktika",
        "dose_uz": "10-80mg kechqurun (jigar sintezi kechasi yuqori)",
        "mechanism_uz": "Jigar xolesterol sintezining asosiy fermenti HMG-CoA reduktazani bloklab LDL receptorlarni oshiradi",
        "how_to_take_uz": "Kechqurun, ovqatdan qat'i nazar. Greyfurt bilan OLMANG.",
        "common_side_effects_uz": ["Mialgiya (mushak ogrig'i)","ALT/AST oshishi","Bosh ogrig'i"],
        "serious_side_effects_uz": ["Rabdomioliz: kuchli mushak ogrig'i+qoramtir siydik -> TEZDA shifokor (CK >10x ULN)","Jigar zararlanishi (ALT>3x ULN)"],
        "interactions_uz": ["Greyfurt: CYP3A4 inhibitsiyasi","Gemfibrozil: rabdomioliz xavfi","Warfarin: INR oshadi"],
        "monitoring_uz": "ALT, AST boshlanganda va 3 oyda bir",
        "missed_dose_uz": "Eslab qolsangiz oling. Ikki baravar OLMANG.",
    },
    "warfarin": {
        "brand_names": ["Warfarin","Coumadin","Marevan"],
        "class_uz": "Vitamin K antagonisti - antikoagulyant",
        "indications_uz": "AF, DVT, PE, mexanik qopiq, tromboemboliya profilaktika",
        "dose_uz": "INR ga qarab individual (odatda 2-10mg/kun)",
        "mechanism_uz": "Vitamin K-dependent koagulyatsiya faktorlari (II, VII, IX, X) sintezini bloklab qon ivishini sekinlashtiradi",
        "how_to_take_uz": "Har kuni bir xil vaqtda (kechqurun). INR nazorati SHART.",
        "target_inr": {"Umumiy ko'rsatma":"2.0-3.0","Mexanik mitral qopiq":"2.5-3.5"},
        "serious_side_effects_uz": ["Qon ketish - qora najaslar, qon qusish, kuchli bosh ogrig'i -> TEZDA 103"],
        "food_interactions_uz": ["K vitamini (karam, qovoq): miqdorni DOIMIY saqlang","Greyfurt, mango: ta'sirni oshiradi","Spirt: ta'sirni o'zgartiradi"],
        "drug_interactions_uz": ["NSAID: qon ketish xavfi kuchayadi","Antibiotiklar (metronidazol, flukonazol): INR oshadi"],
        "missed_dose_uz": "O'sha kuni eslab qolsangiz oling. Ertasi kuni ikki baravar OLMANG. Shifokorga xabar bering.",
        "monitoring_uz": "INR: dastlab haftada bir, maqsad INR ga yetgach oyda bir",
        "reversal_uz": "Overdoz/qon ketish: K vitamini IV + 4-faktorli PCC",
    },
    "insulin": {
        "brand_names": ["Novorapid","Humalog","Lantus","Levemir","Tresiba","Actrapid","Protafan"],
        "class_uz": "Insulin preparatlari",
        "types_uz": {
            "Ultra-qisqa (Novorapid, Humalog)": "Ovqat oldidan 0-15 daqiqa. Ta'sir: 15min, cho'qqi 1-2h, davom 3-5h",
            "Qisqa (Actrapid, Regular)": "Ovqatdan 30 daqiqa oldin. Cho'qqi 2-4h, davom 5-8h",
            "O'rta (Protafan, NPH)": "1-2x/kun. Cho'qqi 4-8h, davom 12-18h",
            "Uzoq (Lantus/Glargin)": "Kuniga bir marta. Cho'qqi YO'Q, davom 20-24h",
            "Ultra-uzoq (Tresiba)": "Kuniga bir marta. Davom >42h",
        },
        "hypoglycemia_uz": {
            "Belgilar": "Titroq, ter bosish, yurak tez urishi, bosh aylanishi, chalkashlik",
            "Yengil (<70mg/dL)": "15g tez karbohidrat: 150ml sharbat YOKI 3-4 ta shakar YOKI glukoza tablet",
            "15-15 qoidasi": "15g glukoza -> 15 daqiqa kuting -> qayta o'lchang",
            "Og'ir (hushsiz)": "Glukagon 1mg IM/SC YOKI 40% glukoza 20-40ml IV -> TEZDA 103",
        },
        "storage_uz": "Ochilmagan: 2-8°C. Ochilgan: xona haroratida 28-30 kun",
        "injection_sites_uz": "Qorin (tez), son (o'rta), yelka (sekin). Joyni aylantirish SHART",
        "missed_dose_uz": "HECH QACHON o'z-o'zidan o'zgartirmang. Shifokorga darhol qo'ng'iroq qiling.",
    },
    "bisoprolol": {
        "brand_names": ["Bisoprolol","Concor","Biprol","Bisocard"],
        "class_uz": "Selektiv beta-1 blokator",
        "indications_uz": "Gipertoniya, Yurak yetishmovchiligi, Stenokardiya, Aritmiya (AF)",
        "dose_uz": "YuYe: 1.25mg dan boshlash, sekin titratsiya, maksimal 10mg/kun",
        "mechanism_uz": "Beta-1 adrenoreseptorlarni bloklab yurak urishi va kontraktillikni kamaytiradi",
        "how_to_take_uz": "Ertalab, ovqat bilan. KESKIN TO'XTATMANG.",
        "common_side_effects_uz": ["Bradikardiya","Charchash","Sovuqqa chidamaslik","Bronxospazm (astmada ehtiyot)"],
        "contraindications_uz": ["Bradikardiya <50/min","AV blok 2-3 daraja","Og'ir bronxial astma"],
        "important_uz": "TO'SATDAN TO'XTATMANG - rebound: taxikardiya, stenokardiya, infarkt xavfi. 2 hafta davomida doza kamaytiriladi.",
        "missed_dose_uz": "Eslab qolsangiz oling. Ikki baravar OLMANG.",
    },
    "levotiroksin": {
        "brand_names": ["Levotiroksin","Euthyrox","L-tiroksin","Eutiroks"],
        "class_uz": "Sintetik T4 gormoni",
        "indications_uz": "Gipotireoz, Tiroid saratoni, Eutiroid zob",
        "dose_uz": "25-50mcg dan boshlash. Maqsad: TSH normal diapazonda.",
        "how_to_take_uz": "Ertalab OVQATDAN 30-60 DAQIQA OLDIN, faqat suv bilan.",
        "interactions_uz": "Kalsiy, temir, magniy, antatsidlar: 4 soat keyin qabul qiling.",
        "missed_dose_uz": "Eslab qolsangiz oling. Ikki baravar OLMANG.",
        "monitoring_uz": "TSH: doza o'zgargandan 6-8 hafta keyin. Keyin 6-12 oyda bir.",
        "important_uz": "Umrbod qabul qilinadi. To'xtatilsa gipotireoz qaytadi.",
    },
    "omeprazol": {
        "brand_names": ["Omeprazol","Losek","Ultop","Omez","Gastrozol"],
        "class_uz": "Proton nasos inhibitori (PPI)",
        "indications_uz": "GERD, Peptik yara, H.pylori (kombinatsiyada), NSAIDdan himoya",
        "dose_uz": "20-40mg kuniga 1-2 marta",
        "mechanism_uz": "Parietal hujayralardagi H+/K+-ATPazani qaytmas inhibe qilib HCl sekretsiyasini kamaytiradi",
        "how_to_take_uz": "Ovqatdan 30-60 DAQIQA OLDIN. Kapsulani chaqmang.",
        "long_term_risks_uz": ["Magniy yetishmovchiligi (>1 yil)","B12 yetishmovchiligi","Suyak sinishi xavfi"],
        "missed_dose_uz": "Eslab qolsangiz oling. Ikki baravar OLMANG.",
        "hpylori_uz": "3 komponentli sxema: PPI + Klaritromitsin 500mg + Amoksitsillin 1000mg - 14 kun",
    },
    "aspirin": {
        "brand_names": ["Aspirin","Kardi ASK","Aspirin Cardio","Cardiomagnyl","Thrombass"],
        "class_uz": "Antiplatelet (past doza) / Analgetik-antipiretik (yuqori doza)",
        "indications_uz": "KVK ikkilamchi profilaktika, ACS, Insult profilaktika (TIA keyin)",
        "dose_uz": "Antiplatelet: 75-100mg/kun. ACS: 300mg yuk doza (chaynab)",
        "mechanism_uz": "COX-1 ni qaytmas atsetillab tromboksan A2 sintezini bloklab trombosit agregatsiyasini kamaytiradi",
        "how_to_take_uz": "Ovqat bilan (enterik qoplama - yutib yuboring).",
        "contraindications_uz": ["Faol peptik yara","Qon ketish buzilishlari","18 yoshgacha (Reye sindromi)"],
        "interactions_uz": ["Warfarin: qon ketish xavfi 2x","NSAID: GI qon ketish","Ibuprofen: aspirin ta'sirini bloklaydi"],
        "important_uz": "O'Z-O'ZIDAN TO'XTATMANG - ACS/stent bemorlarda tromboz xavfi.",
    },
    "sertralin": {
        "brand_names": ["Sertralin","Zoloft","Stimuloton","Serlift"],
        "class_uz": "SSRI antidepressant",
        "indications_uz": "Depressiya, Panik buzilish, OKB, PTSD, Ijtimoiy fobiya",
        "dose_uz": "50mg dan boshlash, 50-200mg/kun (4-8 haftada titratsiya)",
        "mechanism_uz": "Serotonin transporter (SERT) ni selektiv bloklab sinaptik serotoninni oshiradi",
        "how_to_take_uz": "Ertalab yoki kechqurun, ovqat bilan yoki ovqatsiz.",
        "onset_uz": "Ta'sirini bildirishi 4-8 hafta",
        "serious_side_effects_uz": ["Serotonin sindromi (MAOi bilan) - hayot uchun xavfli","Suitsidal fikrlar (ayniqsa 25 yoshgacha)"],
        "discontinuation_uz": "TO'XTATMANG o'z-o'zidan - diskontinuatsiya sindromi. 2-4 hafta sekin kamaytirish.",
        "missed_dose_uz": "Eslab qolsangiz oling. Ikki baravar OLMANG.",
    },
    "ibuprofen": {
        "brand_names": ["Ibuprofen","Nurofen","Advil","MIG"],
        "class_uz": "NSAID (nosteroid yallig'lanishga qarshi dori)",
        "indications_uz": "Ogrig'i, Isitma, Yallig'lanish, Artrit",
        "dose_uz": "200-800mg, har 6-8 soatda. OTC maks: 1200mg/kun",
        "mechanism_uz": "COX-1 va COX-2 ni inhibe qilib prostaglandinlar sintezini kamaytiradi",
        "how_to_take_uz": "Ovqat bilan. Eng past samarali dozada, qisqa muddatga.",
        "contraindications_uz": ["Peptik yara","Og'ir buyrak/jigar kasalligi","Homiladorlikning 3-trimestr","Yurak yetishmovchiligi"],
        "interactions_uz": ["Warfarin: qon ketish xavfi","ACE/ARB: buyrak perfuziyasi kamayadi","Aspirin: antiplatelet ta'sirini bloklaydi"],
        "serious_side_effects_uz": ["GI qon ketish: qora najaslar -> TEZDA shifokor"],
    },
    "paracetamol": {
        "brand_names": ["Paracetamol","Panadol","Efferalgan","Tylenol"],
        "class_uz": "Analgetik va antipiretik",
        "indications_uz": "Ogrig'i, Isitma",
        "dose_uz": "500-1000mg har 4-6 soatda. Kunlik MAKSIMAL: 4g (3g jigar kasalligi/spirt qabul qiluvchilarda)",
        "how_to_take_uz": "Ovqat bilan yoki ovqatsiz. Eng xavfsiz analgetik to'g'ri dozada.",
        "serious_side_effects_uz": ["JIGAR NEKROZI (overdoz) -> Acetilsistein antidot, TEZDA 103"],
        "important_uz": ["Spirt bilan birga OLMANG","Boshqa paracetamol tutgan dorilar (gripp dorisi) bilan dozani hisoblab qo'shing","4g/kun chegarasini OSHIRMANG"],
    },
}

LAB_REFERENCE = {
    "qon_shakar": {
        "uz_name": "Qon glyukozasi",
        "units": "mmol/L",
        "normal": {"Och qoringa":"3.9-5.5 mmol/L","Ovqatdan 2h keyin":"<7.8 mmol/L"},
        "prediabet": {"Och qoringa":"5.6-6.9 mmol/L","OGTT 2h":"7.8-11.0 mmol/L"},
        "diabet": {"Och qoringa":">=7.0 mmol/L (2 marta tasdiqlash)","OGTT 2h":">=11.1 mmol/L"},
        "hba1c": {"Normal":"<5.7%","Prediabet":"5.7-6.4%","Diabet":">=6.5%","DM maqsad":"<7%"},
        "critical": {"Gipoglikemiya":"<3.9 mmol/L","Og'ir gipo":"<2.8 mmol/L - shoshilinch","Giperglikemiya":">13.9 mmol/L - shifokorga"},
    },
    "qon_bosimi": {
        "uz_name": "Arterial qon bosimi",
        "units": "mmHg",
        "ESC_2018": {"Optimal":"<120/80","Normal":"120-129/80-84","Yuqori normal":"130-139/85-89","1-daraja":"140-159/90-99","2-daraja":"160-179/100-109","3-daraja":">=180/>=110"},
        "kriz": ">180/>120 -> SHOSHILINCH",
    },
    "lipidlar": {
        "uz_name": "Lipid profili",
        "units": "mmol/L",
        "total_cholesterol": {"Maqsad":"<5.2 mmol/L","Yuqori":"<6.2 mmol/L"},
        "ldl": {"Past xavf":"<3.0 mmol/L","Yuqori xavf (DM,YuYe)":"<1.8 mmol/L","Juda yuqori xavf (ACS)":"<1.4 mmol/L"},
        "hdl": {"Erkak":">1.0 mmol/L","Ayol":">1.2 mmol/L"},
        "trig": {"Normal":"<1.7 mmol/L","Og'ir":">5.6 mmol/L - pankreatit xavfi"},
    },
    "inr": {
        "uz_name": "INR (Warfarin nazorati)",
        "normal": "0.8-1.2",
        "warfarin_maqsad": {"Umumiy":"2.0-3.0","Mexanik mitral qopiq":"2.5-3.5"},
        "critical": {"INR>4":"Warfarin to'xtatish/kamaytirish","INR>5":"Vitamin K 1-2mg oral","INR>8 yoki qon ketish":"K vit IV + PCC -> TEZDA 103"},
    },
    "tsh": {
        "uz_name": "TSH (Tiroid stimulovchi gormon)",
        "units": "mIU/L",
        "normal": "0.4-4.0 mIU/L",
        "gipotireoz": ">4.0 mIU/L",
        "gipertireoz": "<0.4 mIU/L",
        "levotiroksin_maqsad": {"Umumiy":"0.5-2.5 mIU/L","Tiroid saratoni":"<0.1 mIU/L (supressiv)"},
    },
    "gemoglobin": {
        "uz_name": "Gemoglobin",
        "units": "g/L",
        "normal": {"Erkak (>18)":"135-175 g/L","Ayol (>18)":"120-155 g/L","Homilador":"110-140 g/L"},
        "anemiya": {"Yengil":"100-normal pastki","O'rta":"70-99 g/L","Og'ir":"<70 g/L - transfuziya ko'rib chiqish"},
    },
    "kreatinin_egfr": {
        "uz_name": "Kreatinin va eGFR",
        "kreatinin_normal": {"Erkak":"62-115 mkmol/L","Ayol":"44-97 mkmol/L"},
        "egfr_ckd": {"G1":">=90","G2":"60-89","G3a":"45-59","G3b":"30-44","G4":"15-29 - Dializ tayyorligi","G5":"<15"},
        "metformin": "eGFR<45: ehtiyotkorlik; eGFR<30: to'xtatish",
    },
    "umumiy_qon": {
        "uz_name": "Umumiy qon tahlili (CBC)",
        "eritrotsitlar": {"Erkak":"4.5-5.5 x10^12/L","Ayol":"3.8-4.8 x10^12/L"},
        "leykositlar": "4.0-9.0 x10^9/L (>11 infeksiya/yallig'lanish; <4 immunosupressiya)",
        "trombotsitlar": "150-400 x10^9/L (<100: qon ketish xavfi; >400: tromboz xavfi)",
    },
    "jigar_fermenlari": {
        "uz_name": "Jigar fermentlari (LFT)",
        "alt_asat": {"Normal":"ALT: 7-56 U/L, AST: 10-40 U/L",">3x ULN":"Dori to'xtatish ko'rib chiqiladi",">10x ULN":"Og'ir jigar zararlanishi - TEZDA shifokor"},
        "bilirubin": {"Normal":"Umumiy: <17 mkmol/L","Sarilik":">34 mkmol/L ko'rinadigan"},
    },
    "elektrolitlar": {
        "uz_name": "Elektrolitlar",
        "natriy": {"Normal":"136-145 mmol/L","Giponatriya":"<135","Gipernatriya":">145"},
        "kaliy": {"Normal":"3.5-5.0 mmol/L","Gipokaliya":"<3.5 (aritmiya xavfi <3.0)","Giperkaliemiya":">5.0 (kritik >6.5 - TEZDA 103)"},
        "magniy": {"Normal":"0.7-1.0 mmol/L"},
        "kalsiy": {"Normal":"2.2-2.6 mmol/L","Gipokalsemiya":"<2.2","Giperkalsemiya":">2.6"},
    },
}

DRUG_INTERACTIONS = {
    "warfarin_nsaid": {"drugs":["Warfarin","Ibuprofen","Aspirin","Diklofenak"],"severity":"YUQORI","effect_uz":"GI qon ketish xavfi 3-5x oshadi","recommendation_uz":"Birga OLMANG. Ogrig'i uchun Paracetamol xavfsizroq."},
    "statins_grapefruit": {"drugs":["Atorvastatin","Simvastatin","Lovastatin"],"severity":"O'RTA-YUQORI","effect_uz":"Statin konsentratsiyasi 2-3x oshadi - miopatiya/rabdomioliz","recommendation_uz":"Greyfurt butunlay tashlag."},
    "metformin_contrast": {"drugs":["Metformin"],"situation":"Yodli kontrast (KT, angiografiya)","severity":"YUQORI","effect_uz":"Kontrast nefropatiya -> Metformin to'planishi -> laktik atsidoz","recommendation_uz":"eGFR<60: tekshiruvdan 48 soat oldin to'xtatish va 48 soat keyin boshlash."},
    "ssri_maoi": {"drugs":["Sertralin","Fluoksetin","Escitalopram","MAO inhibitorlari"],"severity":"HAYOT UCHUN XAVFLI","effect_uz":"Serotonin sindromi: gipertermiya, qattiqlik, o'lim","recommendation_uz":"HECH QACHON birga OLMANG. MAOi to'xtatilgandan 14 kun keyin SSRI."},
    "levotiroksin_minerals": {"drugs":["Levotiroksin","Kalsiy","Temir","Antatsidlar"],"severity":"O'RTA","effect_uz":"So'rilishni 20-40% kamaytiradi","recommendation_uz":"Levotiroksindan kamida 4 soat keyin qabul qiling."},
    "aspirin_ibuprofen": {"drugs":["Aspirin (past doza)","Ibuprofen"],"severity":"O'RTA-YUQORI","effect_uz":"Ibuprofen aspirin kardioprotektiv ta'sirini yo'q qiladi","recommendation_uz":"Ibuprofen Aspirindan 30 daqiqa keyin yoki 8 soat oldin qabul qiling."},
    "bisoprolol_verapamil": {"drugs":["Bisoprolol","Verapamil","Diltiazem"],"severity":"YUQORI","effect_uz":"Additive bradikardiya + AV blok - hemodynamik beqarorlik","recommendation_uz":"Kardioldog nazoratisiz birga OLMANG."},
    "ace_potassium": {"drugs":["Enalapril","Lisinopril","Spironolakton","Kaliy preparatlari"],"severity":"O'RTA-YUQORI","effect_uz":"Giperkaliemiya xavfi - aritmiya, yurak to'xtashi","recommendation_uz":"Kaliy darajasini muntazam tekshirish."},
}

SYMPTOM_MAP = {
    "bosh_ogrik": {
        "uz_terms": ["bosh og'riq","bosh ogri","boshim ogri","migran","bosh og'riyapti","bosh ogrimoqda"],
        "possible_causes": ["Gipertoniya (ensa, ertalab)","Migran (bir tomonlama+ko'ngil aynish)","Gergin bosh og'rig'i","Ko'z muammolari","Insult (to'satdan, eng kuchli)","Meningit (+isitma+bo'yin qotishi)"],
        "red_flags_uz": ["THUNDERCLAP (to'satdan eng kuchli) -> SAK xavfi, DARHOL 103","Bosh ogrig'i+isitma+bo'yin qotishi -> meningit, TEZDA 103","Bosh ogrig'i+nutq buzilishi/yuz qiyshayishi -> insult, TEZDA 103"],
    },
    "kokrak_ogrik": {
        "uz_terms": ["ko'krak og'riq","yurak og'riyapti","ko'krakda og'riq","siqilish ko'krakda","ko'krak ogrimoqda"],
        "possible_causes": ["ACS/Infarkt (siquvchi, ter, chap qo'l tarqaladi)","Stenokardiya","GERD (yonish, ovqatdan keyin)","Plevrit","Mushabka"],
        "red_flags_uz": ["Ko'krak ogrig'i>20 daqiqa+ter+chap qo'l -> INFARKT, DARHOL 103","Ko'krak ogrig'i+nafas qisilishi -> DARHOL 103","To'satdan kuchli+orqaga tarqalishi -> aorta disseksiyasi, TEZDA 103"],
    },
    "nafas_qisilishi": {
        "uz_terms": ["nafas qisil","nafas olish qiyin","nafas ololmayapman","xirillash","entikish"],
        "possible_causes": ["Astma hujumi","COPD ekzatserbatsiyasi","Yurak yetishmovchiligi","Pnevmoniya","Anafilaksiya","PE"],
        "red_flags_uz": ["SpO2<90% -> DARHOL 103","Lab ko'kimligi -> DARHOL 103","Gapira olmaslik -> DARHOL 103"],
    },
    "qorin_ogrik": {
        "uz_terms": ["qorin og'riq","oshqozon og'ri","qornim og'riyapti"],
        "possible_causes": ["Gastrit/PUD","Appenditsit (o'ng pastki)","Xoletsistit (o'ng yuqori)","Pankreatit","Buyrak toshi"],
        "red_flags_uz": ["Qorin parda belgilari (taxtaday qattiq) -> TEZDA 103","O'ng pastki ogrig'i+isitma -> appenditsit, TEZDA 103","Qora najaslar/qon qusish -> TEZDA 103"],
    },
}


def search_knowledge(query: str, max_items: int = 4) -> str:
    query_lower = query.lower()
    found = []
    for key, data in DISEASES.items():
        all_names = data.get("uz_names",[]) + data.get("ru_names",[]) + data.get("en_names",[])
        if any(n in query_lower for n in all_names):
            s = f"[KASALLIK: {key.upper()}]\n{data.get('description_uz','')}\n"
            if isinstance(data.get("symptoms_uz"), list):
                s += "Belgilar: " + "; ".join(data["symptoms_uz"][:5]) + "\n"
            if data.get("medications_first_line"):
                meds = data["medications_first_line"]
                s += "1-qator dorilar: " + (", ".join(meds) if isinstance(meds, list) else str(meds)) + "\n"
            if data.get("emergency_signs_uz"):
                s += "SHOSHILINCH: " + "; ".join(data["emergency_signs_uz"][:3]) + "\n"
            if data.get("monitoring_uz"):
                s += "Monitoring: " + data["monitoring_uz"] + "\n"
            found.append(s)
            if len(found) >= max_items: break
    if len(found) < max_items:
        for key, data in MEDICATIONS.items():
            brands_low = [b.lower() for b in data.get("brand_names", [])]
            if key in query_lower or any(b in query_lower for b in brands_low):
                s = f"[DORI: {'/'.join(data['brand_names'])}]\n"
                s += f"Sinf: {data.get('class_uz','')}\nKo'rsatma: {data.get('indications_uz','')}\n"
                s += f"Doza: {data.get('dose_uz','')}\nQabul: {data.get('how_to_take_uz','')}\n"
                if data.get("mechanism_uz"): s += f"Mexanizm: {data['mechanism_uz']}\n"
                if data.get("common_side_effects_uz"):
                    s += "Yon ta'sirlar: " + "; ".join(data["common_side_effects_uz"][:3]) + "\n"
                if data.get("interactions_uz"):
                    inter = data["interactions_uz"]
                    s += "O'zaro ta'sirlar: " + (str(inter) if isinstance(inter, str) else "; ".join(inter) if isinstance(inter, list) else str(inter)) + "\n"
                if data.get("contraindications_uz"):
                    s += "Qarshi ko'rsatmalar: " + "; ".join(data["contraindications_uz"][:3]) + "\n"
                if data.get("monitoring_uz"): s += f"Monitoring: {data['monitoring_uz']}\n"
                found.append(s)
                if len(found) >= max_items: break
    if len(found) < max_items:
        for key, data in SYMPTOM_MAP.items():
            if any(t in query_lower for t in data.get("uz_terms",[])):
                s = f"[SIMPTOM: {key}]\nMumkin sabablar: {', '.join(data.get('possible_causes',[]))}\n"
                if data.get("red_flags_uz"):
                    s += "XAVFLI BELGILAR: " + "; ".join(data["red_flags_uz"][:2]) + "\n"
                found.append(s)
                if len(found) >= max_items: break
    if len(found) < max_items:
        for key, data in LAB_REFERENCE.items():
            uz_name = data.get("uz_name","").lower()
            if key in query_lower or uz_name in query_lower or any(k in query_lower for k in key.split("_")):
                s = f"[LAB: {data.get('uz_name',key)}]\n"
                for k, v in data.items():
                    if k not in ["uz_name","units"]:
                        s += f"  {k}: {v}\n"
                found.append(s)
                if len(found) >= max_items: break
    for key, data in DRUG_INTERACTIONS.items():
        drugs_low = [d.lower() for d in data.get("drugs",[])]
        if any(d in query_lower for d in drugs_low):
            s = f"[DORI TA'SIRI: {key}]\nJiddiylik: {data.get('severity','')}\n{data.get('effect_uz','')}\nTavsiya: {data.get('recommendation_uz','')}\n"
            if s not in found: found.append(s)
    return "\n---\n".join(found)


# ══════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """
Sen TABIB AI — O'zbekiston sog'liqni saqlash tizimi uchun yaratilgan klinik darajadagi tibbiy ekspert tizimisan.

═══════════════════════════════════════════════════════
ASOSIY ROL VA VAZIFALAR
═══════════════════════════════════════════════════════

Sen bir vaqtning o'zida 5 ta rolni bajarasan:

1. KLINIK EKSPERT: Dorilar (mexanizm, doza, yon ta'sir, o'zaro ta'sir), kasalliklar, laboratoriya ko'rsatkichlari bo'yicha chuqur klinik bilim egasi
2. BEMOR VOSITACHISI: Murakkab tibbiy ma'lumotni tushunarli tilda yetkazuvchi
3. ADHERENCE NAZORATCHI: Dori qabul qilishni kuzatib xavflarni erta aniqlovchi
4. SHIFOKOR YORDAMCHISI: Aniq, strukturlangan klinik ma'lumot yetkazuvchi
5. TIZIM TAHLILCHISI: Bemor ma'lumotlari, lab natijalari, dori ro'yxatini kompleks tahlil qiluvchi

═══════════════════════════════════════════════════════
ANIQ VA PROFESSIONAL JAVOB STANDARTI
═══════════════════════════════════════════════════════

HECH QACHON umumiy, noaniq javob berma. Har doim SPESIFIK, ANIQ, KLINIK bo'l.

YOMON MISOL: "Metformin oshqozon uchun yomon bo'lishi mumkin"
YAXSHI MISOL: "Metformin boshlanishida 20-30% bemorlarda ko'ngil aynish va ich ketishi chiqadi. Bu yon ta'sir odatda 2-4 haftada o'tadi. Oldini olish uchun: ovqat bilan birga oling, doza oshirishni sekin bajaring (haftada 500mg). Agar kuchli bo'lsa — Metformin XR (uzaytirilgan) formulasi yaxshiroq toleratsiya qilinadi."

YOMON MISOL: "Qon bosimi yuqori bo'lsa shifokorga boring"
YAXSHI MISOL: "160/100 mmHg — 2-daraja gipertoniya. Enalapril 10mg allaqachon belgilangan bo'lsa, ma'lumotlaringizga qarab: qo'shimcha doza titratsiyasi yoki 2-dori (CCB: Amlodipine 5mg) qo'shish ko'rib chiqilishi mumkin. Hozir: tuz <5g/kun, spirtdan voz kechish, muntazam monitorin."

═══════════════════════════════════════════════════════
BEMOR MA'LUMOTLARINI TAHLIL QILISH
═══════════════════════════════════════════════════════

Agar [BEMOR_PROFILI], [DORI_RO'YXATI], [LAB_NATIJALARI], [DIAGNOZ_TARIXI] berilgan bo'lsa:

1. Barcha ma'lumotlarni integratsiya qil
2. Potensial xavflarni aniqlash: dori-dori ta'sirlari, lab va dori muvofiqligi
3. Monitoring bo'shliqlari: qaysi tekshiruvlar yetishmayapti?
4. Adherence xavfi: qaysi dorilar kritik?
5. Berilgan ma'lumotlarni asosida ANIQ, PERSONALIZATSIYALANGAN javob ber

═══════════════════════════════════════════════════════
SHIFOKORGA HISOBOT
═══════════════════════════════════════════════════════

Shifokorga hisobot so'ralsa:

KLINIK HISOBOT — TABIB AI
Sana: [sana]
═══════════════════════════
BEMOR HOLATI XULOSASI:
FAOL DIAGNOZLAR:
DORI ADHERENCE:
LAB NATIJALARI TAHLILI:
DORI-DORI TA'SIRLARI:
XAVF OMILLARI:
TAVSIYALAR:
MONITORING REJASI:

═══════════════════════════════════════════════════════
QOIDALAR
═══════════════════════════════════════════════════════

BAJARA OLASAN:
- Aniq, spesifik tibbiy ma'lumot berish (doz, mexanizm, yon ta'sir, monitoring)
- Berilgan bemor ma'lumotlarini kompleks tahlil qilish
- Dori-dori ta'sirlarini aniqlash
- Lab natijalarini me'yor bilan solishtirish va interpretatsiya
- Shifokorga strukturlangan hisobot
- Adherence oshirish strategiyalari

BAJARA OLMAYSAN:
- Yangi diagnoz qo'yish
- Yangi dori buyurish
- Shifokor ko'rsatmasini bekor qilish

TIL: Berilgan tilda avtomatik javob ber (O'zbek/Rus/Ingliz)
TON: Bemor bilan iliq va tushunarli; shifokor uchun klinik va aniq

SHOSHILINCH: Ko'krak ogrig'i, nafas qisilishi, falaj belgilari, kuchli allergiya, hushdan ketish, suitsidal fikr -> DARHOL: "103 ga qo'ng'iroq qiling. Yonizda kimdir bormi?"
""".strip()


# ══════════════════════════════════════════════════════════════════════
# RISK ENGINE
# ══════════════════════════════════════════════════════════════════════
URGENT_PATTERNS = {
    "chest_pain": [r"ko['\u2019]?krak\s*og['\u2019]?ri", r"chest\s*pain", r"боль\s*в\s*груди"],
    "breathing": [r"nafas.*qiyin", r"nafas.*qis", r"nafas\s*ololmay", r"одышка"],
    "fainting": [r"hushdan\s*ket", r"hushsiz", r"faint", r"обморок"],
    "stroke": [r"yuz.*qiyshay", r"nutq.*buzil", r"gapira\s*olmay", r"перекос\s*лиц"],
    "severe_allergy": [r"tomoq.*shish", r"lab.*shish", r"til.*shish", r"swelling.*(throat|tongue|face)"],
    "seizure": [r"tutqanoq", r"seizure", r"судорог"],
    "suicidal": [r"o['\u2019]?zimni\s*o['\u2019]?ldir", r"jonimga\s*qasd", r"suicide"],
    "severe_bleeding": [r"kuchli\s*qon", r"qon\s*qus", r"qora\s*najaslar", r"vomiting\s*blood"],
}

_PATTERNS = {
    "missed": [r"unutdim", r"ichmadim", r"o['\u2019]?tkazib\s*yubordim", r"missed", r"forgot", r"забыл", r"пропустил"],
    "stop": [r"to['\u2019]?xtatdim", r"ichgim\s*kelmay", r"endi\s*ichmayman", r"stopped?", r"перестал"],
    "side_effect": [r"nojo['\u2019]?ya", r"ko['\u2019]?ngil\s*ayn", r"bosh\s*ayl", r"toshma", r"nausea", r"dizzy", r"побоч"],
    "cost": [r"qimmat", r"pulim\s*yetmay", r"sotib\s*ololmay", r"afford", r"дорого"],
    "confusion": [r"qachon\s*ich", r"qanday\s*ich", r"chalkash", r"confused", r"когда\s*принимать"],
    "critical_med": [r"insulin", r"tutqanoq", r"epilep", r"warfarin", r"tb", r"sil", r"hiv", r"nitrogliterin", r"prednizolon"],
    "double_dose": [r"ikki\s*baravar", r"2\s*ta\s*ichdim", r"double\s*dose", r"двойную\s*доз"],
    "pregnancy": [r"homilador", r"emiz", r"pregnan", r"беремен"],
}


def _match(text, key):
    return any(re.search(p, text, re.IGNORECASE) for p in _PATTERNS[key])


def _match_urgent(text):
    return [l for l, pats in URGENT_PATTERNS.items() if any(re.search(p, text, re.IGNORECASE) for p in pats)]


def detect_language(text):
    if re.search(r"[а-яё]", text, re.IGNORECASE): return "ru"
    if any(w in text.lower() for w in ["men","menga","dori","ichdim","qanday","nima","yaxshi","og'riq","shifokor"]): return "uz"
    return "en"


def analyze_risk(message):
    text = message.strip()
    urgent = _match_urgent(text)
    if urgent:
        return {"risk_level": "URGENT", "risk_flags": urgent, "detected_language": detect_language(text)}
    flags, risk = [], "LOW"
    if _match(text, "missed"):
        flags.append("missed_medication"); risk = "MODERATE"
        m = re.search(r"(\d+)\s*(kun|day|дн)", text, re.IGNORECASE)
        if m and int(m.group(1)) >= 2: flags.append("missed_2plus_days"); risk = "HIGH"
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


class Prescription(BaseModel):
    drug_name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    start_date: Optional[str] = None
    prescribed_by: Optional[str] = None
    indication: Optional[str] = None
    adherence_rate: Optional[float] = None  # 0.0 - 1.0


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
    status: Optional[str] = None  # active, resolved, chronic
    notes: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MSG_LEN)
    session_id: Optional[str] = None

    # Tizim ma'lumotlari (ixtiyoriy - integratsiya uchun)
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
    if payload.patient_profile:
        p = payload.patient_profile
        parts.append(f"""[BEMOR_PROFILI]
Ism: {p.name or "Noma'lum"} | Yosh: {p.age or "?"} | Jins: {p.gender or "?"} | Vazn: {p.weight_kg or "?"} kg | Bo'y: {p.height_cm or "?"} cm
Allergiyalar: {', '.join(p.allergies) if p.allergies else "Ko'rsatilmagan"} | Qon guruhi: {p.blood_type or "Noma'lum"}""")

    if payload.diagnoses:
        lines = []
        for d in payload.diagnoses:
            line = f"  - {d.name}"
            if d.icd_code: line += f" [{d.icd_code}]"
            if d.status: line += f" | {d.status}"
            if d.date_diagnosed: line += f" | {d.date_diagnosed}"
            if d.notes: line += f" | {d.notes}"
            lines.append(line)
        parts.append("[DIAGNOZ_TARIXI]\n" + "\n".join(lines))

    if payload.prescriptions:
        lines = []
        for rx in payload.prescriptions:
            line = f"  - {rx.drug_name}"
            if rx.dose: line += f" | {rx.dose}"
            if rx.frequency: line += f" | {rx.frequency}"
            if rx.indication: line += f" | Ko'rsatma: {rx.indication}"
            if rx.adherence_rate is not None:
                pct = int(rx.adherence_rate * 100)
                flag = " ⚠️ PAST" if pct < 70 else ""
                line += f" | Adherence: {pct}%{flag}"
            lines.append(line)
        parts.append("[DORI_RO'YXATI]\n" + "\n".join(lines))

    if payload.lab_results:
        lines = []
        for lab in payload.lab_results:
            line = f"  - {lab.test_name}: {lab.value}"
            if lab.unit: line += f" {lab.unit}"
            if lab.reference_range: line += f" (Me'yor: {lab.reference_range})"
            if lab.is_abnormal: line += " ⚠️ ANORMAL"
            if lab.date: line += f" | {lab.date}"
            lines.append(line)
        parts.append("[LAB_NATIJALARI]\n" + "\n".join(lines))

    if payload.context:
        lines = [f"  {k}: {v}" for k, v in payload.context.items()]
        parts.append("[QO'SHIMCHA_KONTEKST]\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else ""


# ══════════════════════════════════════════════════════════════════════
# CLAUDE CLIENT
# ══════════════════════════════════════════════════════════════════════
def get_client():
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not set in environment variables.")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def generate_reply(session_id: str, payload: ChatRequest, risk: dict):
    client = get_client()
    user_message = payload.message
    patient_ctx = build_patient_context(payload)
    knowledge = search_knowledge(user_message)

    system_parts = [SYSTEM_PROMPT]
    system_parts.append(f"\n[RISK_CONTEXT - ICHKI]\nRisk: {risk['risk_level']} | Flags: {risk['risk_flags']} | Til: {risk['detected_language']}")
    if patient_ctx:
        system_parts.append(f"\n[JORIY BEMOR MA'LUMOTLARI - TAHLIL QILIB JAVOB BER]\n{patient_ctx}")
    if knowledge:
        system_parts.append(f"\n[TASDIQLANGAN TIBBIY MA'LUMOTLAR - JAVOBDA ISHLATISH MAJBURIY]\n{knowledge}")

    full_system = "\n".join(system_parts)
    history = get_history(session_id)
    messages = history + [{"role": "user", "content": user_message}]

    response = get_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=full_system,
        messages=messages,
    )
    reply = response.content[0].text.strip()

    # Doctor report
    doctor_report = None
    if payload.generate_doctor_report and patient_ctx:
        report_prompt = f"""Quyidagi bemor ma'lumotlari asosida shifokor uchun strukturlangan klinik hisobot tayyorla:

{patient_ctx}

So'nggi savol: {user_message}
Javob: {reply}

Hisobot formati:
KLINIK HISOBOT — TABIB AI
Sana: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
═══════════════════════════════
BEMOR HOLATI XULOSASI:
FAOL DIAGNOZLAR:
DORI ADHERENCE HOLATI:
LAB NATIJALARI TAHLILI:
POTENSIAL XAVFLAR:
TAVSIYALAR:
MONITORING REJASI:"""

        report_resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": report_prompt}],
        )
        doctor_report = report_resp.content[0].text.strip()

    append_history(session_id, "user", user_message)
    append_history(session_id, "assistant", reply)
    log.info(f"[{session_id[:8]}] risk={risk['risk_level']} patient_ctx={bool(patient_ctx)} kb={bool(knowledge)}")
    return reply, doctor_report


# ══════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════════════
app = FastAPI(
    title="Tabib AI — Claude Medical Expert System",
    description="""
## Tabib AI v3.0 — Claude-Powered Medical Expert

### Endpointlar:
- `POST /chat` — Asosiy chat (bemor ma'lumotlari bilan yoki ularsiz)
- `POST /analyze` — Bemor ma'lumotlarini kompleks tahlil
- `POST /doctor-report` — Shifokorga hisobot generatsiyasi
- `GET /medications/{drug}` — Dori ma'lumotlari
- `GET /diseases/{disease}` — Kasallik ma'lumotlari
- `GET /lab-reference/{test}` — Lab me'yoriy qiymatlari
- `GET /sessions/{id}` — Sessiya tarixi

### Integratsiya:
`patient_profile`, `prescriptions`, `lab_results`, `diagnoses` fieldlarini request ga qo'shing.
    """,
    version="3.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Tabib AI",
        "model": CLAUDE_MODEL,
        "active_sessions": len(SESSIONS),
        "knowledge_base": {
            "diseases": len(DISEASES),
            "medications": len(MEDICATIONS),
            "lab_tests": len(LAB_REFERENCE),
            "drug_interactions": len(DRUG_INTERACTIONS),
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    session_id = payload.session_id or str(uuid.uuid4())
    risk = analyze_risk(payload.message)
    reply, doctor_report = generate_reply(session_id, payload, risk)
    SESSION_META.setdefault(session_id, {}).update({
        "last_risk_level": risk["risk_level"],
        "last_risk_flags": risk["risk_flags"],
        "last_seen": datetime.utcnow().isoformat(),
        "has_patient_data": bool(payload.patient_profile or payload.prescriptions),
    })
    return ChatResponse(
        session_id=session_id, reply=reply, risk_level=risk["risk_level"],
        risk_flags=risk["risk_flags"], detected_language=risk["detected_language"],
        doctor_report=doctor_report, timestamp=datetime.utcnow().isoformat()
    )


@app.post("/analyze")
def analyze_patient(payload: AnalyzeRequest):
    client = get_client()
    ctx_req = ChatRequest(
        message="",
        patient_profile=payload.patient_profile,
        prescriptions=payload.prescriptions,
        lab_results=payload.lab_results,
        diagnoses=payload.diagnoses,
    )
    patient_ctx = build_patient_context(ctx_req)
    if not patient_ctx:
        raise HTTPException(status_code=400, detail="Tahlil uchun ma'lumot berilmagan")

    prompts = {
        "full": "Barcha ma'lumotlarni kompleks tahlil qil: dori-dori ta'sirlari, lab interpretatsiyasi, adherence xavflari, monitoring bo'shliqlari, shifokorga tavsiyalar.",
        "adherence": "Faqat dori adherence tahlili: qaysi dorilar xavfli, strategiyalar.",
        "labs": "Lab natijalarini interpretatsiya qil: anormal ko'rsatkichlar, klinik ahamiyati, qo'shimcha tekshiruvlar.",
        "interactions": "Dori-dori va dori-kasallik o'zaro ta'sirlarini tekshir.",
        "risk": "Umumiy klinik xavf baholash: KVK xavfi, qon ketish xavfi, buyrak funksiyasi.",
    }

    prompt = f"{patient_ctx}\n\nVAZIFA: {prompts.get(payload.analysis_type, prompts['full'])}"
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT + "\n\nSen hozir klinik tahlil rejimida. Tizimli, professional, aniq bo'l.",
        messages=[{"role": "user", "content": prompt}],
    )
    return {"analysis_type": payload.analysis_type, "result": response.content[0].text.strip(), "timestamp": datetime.utcnow().isoformat()}


@app.post("/doctor-report")
def doctor_report_endpoint(payload: DoctorReportRequest):
    client = get_client()
    ctx_req = ChatRequest(
        message="",
        patient_profile=payload.patient_profile,
        prescriptions=payload.prescriptions,
        lab_results=payload.lab_results,
        diagnoses=payload.diagnoses,
    )
    patient_ctx = build_patient_context(ctx_req)

    prompt = f"""Quyidagi bemor ma'lumotlari asosida SHIFOKOR UCHUN to'liq klinik hisobot tayyorla:

{patient_ctx}
{f"Asosiy shikoyat: {payload.chief_complaint}" if payload.chief_complaint else ""}
{f"Qo'shimcha: {payload.additional_notes}" if payload.additional_notes else ""}

KLINIK HISOBOT — TABIB AI MONITORING TIZIMI
Sana: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BEMOR UMUMIY HOLATI:
FAOL DIAGNOZLAR:
DORI ADHERENCE HOLATI:
LAB NATIJALARI TAHLILI:
DORI-DORI / DORI-KASALLIK TA'SIRLARI:
ASOSIY XAVF OMILLARI:
SHIFOKORGA TAVSIYALAR:
MONITORING VA KUZATUV REJASI:
SHOSHILINCH HOLAT BELGILARI (Bemorga):"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"report": response.content[0].text.strip(), "generated_at": datetime.utcnow().isoformat()}


@app.get("/medications/{drug_name}")
def get_medication(drug_name: str):
    drug_lower = drug_name.lower()
    for key, data in MEDICATIONS.items():
        brands_low = [b.lower() for b in data.get("brand_names", [])]
        if key == drug_lower or drug_lower in brands_low or any(drug_lower in b for b in brands_low):
            return {"drug": key, "data": data}
    raise HTTPException(status_code=404, detail=f"'{drug_name}' topilmadi")


@app.get("/diseases/{disease_name}")
def get_disease(disease_name: str):
    name_lower = disease_name.lower()
    for key, data in DISEASES.items():
        all_names = data.get("uz_names",[]) + data.get("en_names",[]) + data.get("ru_names",[])
        if key == name_lower or name_lower in all_names:
            return {"disease": key, "data": data}
    raise HTTPException(status_code=404, detail=f"'{disease_name}' topilmadi")


@app.get("/lab-reference/{test_name}")
def get_lab(test_name: str):
    name_lower = test_name.lower()
    for key, data in LAB_REFERENCE.items():
        if key == name_lower or name_lower in data.get("uz_name","").lower():
            return {"test": key, "data": data}
    raise HTTPException(status_code=404, detail=f"'{test_name}' topilmadi")


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    return {"session_id": session_id, "meta": SESSION_META.get(session_id, {}), "messages": SESSIONS.get(session_id, [])}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    SESSIONS.pop(session_id, None); SESSION_META.pop(session_id, None)
    return {"status": "deleted", "session_id": session_id}


# ══════════════════════════════════════════════════════════════════════
# FRONTEND
# ══════════════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
def home():
    return """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8"><title>Tabib AI</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--g:#0d6e4f;--g2:#1a8a63;--gl:#e8f5f0;--text:#1a1a1a;--muted:#6b7280;--border:#e5e7eb;--bg:#f8faf9}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.launcher{position:fixed;right:22px;bottom:22px;width:60px;height:60px;border:none;border-radius:18px;background:var(--g);color:#fff;font-size:26px;cursor:pointer;box-shadow:0 8px 32px rgba(13,110,79,.35);z-index:100;transition:transform .15s}
.launcher:hover{transform:scale(1.07)}
.chat{position:fixed;right:22px;bottom:96px;width:420px;height:660px;max-width:calc(100vw - 28px);max-height:calc(100vh - 110px);background:#fff;border-radius:20px;box-shadow:0 20px 60px rgba(0,0,0,.18);display:none;flex-direction:column;z-index:99;overflow:hidden}
.chat.open{display:flex!important}
.hdr{padding:16px 18px;background:var(--g);color:#fff;border-radius:20px 20px 0 0;display:flex;justify-content:space-between;align-items:center}
.hdr-title{font-family:'DM Serif Display',serif;font-size:18px}
.hdr-sub{font-size:11px;opacity:.85;margin-top:2px}
.dot{display:inline-block;width:7px;height:7px;background:#4ade80;border-radius:50%;margin-right:5px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.close-btn{border:none;width:30px;height:30px;background:rgba(255,255,255,.2);color:#fff;border-radius:8px;font-size:16px;cursor:pointer}
.risk-bar{padding:7px 14px;font-size:12px;font-weight:600;display:none;border-bottom:1px solid var(--border)}
.risk-bar.LOW{display:block;background:#f0fdf4;color:#166534}
.risk-bar.MODERATE{display:block;background:#fffbeb;color:#92400e}
.risk-bar.HIGH{display:block;background:#fff7ed;color:#9a3412}
.risk-bar.URGENT{display:block;background:#fef2f2;color:#991b1b}
.msgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:12px;background:#f9fafb}
.msg{display:flex;gap:8px;align-items:flex-end}
.msg.user{flex-direction:row-reverse}
.bubble{max-width:82%;padding:11px 14px;border-radius:16px;font-size:13.5px;line-height:1.65;white-space:pre-wrap;word-wrap:break-word;animation:fadein .25s ease}
@keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.ai .bubble{background:#fff;border:1px solid var(--border);border-bottom-left-radius:4px}
.user .bubble{background:var(--g);color:#fff;border-bottom-right-radius:4px}
.av{width:28px;height:28px;border-radius:8px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600}
.av.ai-av{background:var(--g);color:#fff}
.av.user-av{background:#e5e7eb;color:#374151}
.typing{background:#fff;border:1px solid var(--border);border-radius:16px;border-bottom-left-radius:4px;padding:12px 16px;display:flex;gap:4px}
.typing span{width:6px;height:6px;background:#9ca3af;border-radius:50%;animation:bounce .9s infinite}
.typing span:nth-child(2){animation-delay:.15s}.typing span:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}
.chips{display:flex;gap:6px;overflow-x:auto;padding:8px 12px;border-top:1px solid var(--border);background:#fff}
.chips::-webkit-scrollbar{display:none}
.chip{white-space:nowrap;border:1px solid #d1fae5;background:#f0fdf4;color:#065f46;padding:5px 10px;border-radius:999px;cursor:pointer;font-size:11.5px;font-family:inherit;transition:background .15s}
.chip:hover{background:#d1fae5}
.form{display:flex;gap:8px;padding:10px 12px 14px;border-top:1px solid var(--border);background:#fff;border-radius:0 0 20px 20px}
textarea{flex:1;resize:none;border:1.5px solid var(--border);border-radius:12px;padding:10px 12px;min-height:40px;max-height:100px;outline:none;font-family:inherit;font-size:13.5px;background:#f9fafb;transition:border .2s}
textarea:focus{border-color:var(--g);background:#fff}
.send{width:40px;height:40px;border:none;border-radius:10px;background:var(--g);color:#fff;font-size:17px;cursor:pointer;flex-shrink:0;transition:background .15s}
.send:hover{background:var(--g2)}.send:disabled{opacity:.45;cursor:not-allowed}
.key-setup{padding:18px}
.key-card{background:#f9fafb;border:1px solid var(--border);border-radius:14px;padding:22px}
.key-card h3{font-family:'DM Serif Display',serif;margin-bottom:8px;font-size:18px}
.key-card p{font-size:13px;color:var(--muted);margin-bottom:16px;line-height:1.6}
.key-row{display:flex;gap:8px}
.key-input{flex:1;padding:9px 12px;border:1.5px solid var(--border);border-radius:10px;font-size:13px;font-family:inherit;outline:none;transition:border .2s}
.key-input:focus{border-color:var(--g)}
.key-btn{padding:9px 18px;background:var(--g);color:#fff;border:none;border-radius:10px;font-size:13px;font-family:inherit;cursor:pointer;font-weight:500}
.key-hint{font-size:11.5px;color:var(--muted);margin-top:10px}
.key-hint a{color:var(--g);text-decoration:none}
</style>
</head>
<body>
<button class="launcher" id="launcher">🩺</button>
<div class="chat" id="chat">
  <div class="hdr">
    <div>
      <div class="hdr-title">Tabib AI</div>
      <div class="hdr-sub"><span class="dot"></span>Klinik ekspert · 24/7</div>
    </div>
    <button class="close-btn" id="closeBtn">✕</button>
  </div>
  <div class="risk-bar" id="riskBar"></div>
  <div id="chatBody" style="display:flex;flex-direction:column;flex:1;overflow:hidden">
    <div id="keySetup" style="padding:18px">
      <div class="key-card">
        <h3>API kalitini kiriting</h3>
        <p>Anthropic API kalitingizni kiriting. Kalit faqat brauzeringizda saqlanadi va serverga yuborilmaydi.</p>
        <div class="key-row">
          <input class="key-input" type="password" id="apiKeyInput" placeholder="sk-ant-...">
          <button class="key-btn" onclick="startChat()">Boshlash</button>
        </div>
        <p class="key-hint">Kalit <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a> da</p>
      </div>
    </div>
    <div id="chatMain" style="display:none;flex-direction:column;flex:1;overflow:hidden">
      <div class="msgs" id="msgs">
        <div class="msg ai"><div class="av ai-av">AI</div><div class="bubble">Assalomu alaykum! Men Tabib AI — klinik darajadagi tibbiy ekspert tizimiman.

Quyidagilarda yordam bera olaman:
• Dorilar: mexanizm, doza, yon ta'sir, o'zaro ta'sirlar
• Kasalliklar: belgilar, davolash, monitoring
• Laboratoriya natijalari: interpretatsiya va me'yorlar
• Bemor ma'lumotlarini tahlil qilish
• Shifokorga klinik hisobot

Qanday savol bor?</div></div>
      </div>
      <div class="chips">
        <button class="chip" data-q="Metformin va Enalapril birga ichsa boladimi?">Dori ta'sirlari</button>
        <button class="chip" data-q="HbA1c 8.5% bolsa nima degani?">HbA1c tahlil</button>
        <button class="chip" data-q="Bisoprolol toxtatsa nima boladi?">Bisoprolol</button>
        <button class="chip" data-q="Atorvastatin ichgandan mushagim ogriypti">Statin yon ta'sir</button>
        <button class="chip" data-q="Warfarin INR 3.8 bolsa nima qilish kerak?">Warfarin INR</button>
      </div>
      <form id="chatForm" class="form">
        <textarea id="msgInput" rows="1" placeholder="Savol yozing... (dori, kasallik, lab natijasi)"></textarea>
        <button class="send" type="submit" id="sendBtn">➤</button>
      </form>
    </div>
  </div>
</div>
<script>
var apiKey = "";
var sessionId = localStorage.getItem("tabib_sid") || null;

document.getElementById("launcher").onclick = function() {
  var chat = document.getElementById("chat");
  if (chat.classList.contains("open")) {
    chat.classList.remove("open");
  } else {
    chat.classList.add("open");
    if (apiKey) document.getElementById("msgInput").focus();
  }
};

document.getElementById("closeBtn").onclick = function() {
  document.getElementById("chat").classList.remove("open");
};

document.querySelectorAll(".chip").forEach(function(b) {
  b.onclick = function() {
    document.getElementById("msgInput").value = b.dataset.q;
    document.getElementById("msgInput").focus();
  };
});

function startChat() {
  var k = document.getElementById("apiKeyInput").value.trim();
  if (!k.startsWith("sk-ant")) {
    alert("Notogri kalit! sk-ant- bilan boshlanishi kerak");
    return;
  }
  apiKey = k;
  document.getElementById("keySetup").style.display = "none";
  var cm = document.getElementById("chatMain");
  cm.style.display = "flex";
  cm.style.flexDirection = "column";
  cm.style.flex = "1";
  cm.style.overflow = "hidden";
  document.getElementById("msgInput").focus();
}

function escapeHtml(text) {
  var d = document.createElement("div");
  d.appendChild(document.createTextNode(text));
  return d.innerHTML;
}

function addMsg(text, role) {
  var msgs = document.getElementById("msgs");
  var row = document.createElement("div");
  row.className = "msg " + (role === "user" ? "user" : "ai");
  var av = document.createElement("div");
  av.className = "av " + (role === "user" ? "user-av" : "ai-av");
  av.textContent = role === "user" ? "Siz" : "AI";
  var bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = escapeHtml(text).split("\n").join("<br>");
  row.appendChild(av);
  row.appendChild(bubble);
  msgs.appendChild(row);
  msgs.scrollTop = 99999;
}

function showTyping() {
  var msgs = document.getElementById("msgs");
  var d = document.createElement("div");
  d.className = "msg ai";
  d.id = "typing";
  var av = document.createElement("div");
  av.className = "av ai-av";
  av.textContent = "AI";
  var typing = document.createElement("div");
  typing.className = "typing";
  typing.innerHTML = "<span></span><span></span><span></span>";
  d.appendChild(av);
  d.appendChild(typing);
  msgs.appendChild(d);
  msgs.scrollTop = 99999;
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 100) + "px";
}

document.getElementById("msgInput").addEventListener("input", function() {
  autoResize(this);
});

document.getElementById("msgInput").addEventListener("keydown", function(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    document.getElementById("chatForm").dispatchEvent(new Event("submit", {bubbles: true}));
  }
});

document.getElementById("chatForm").addEventListener("submit", async function(e) {
  e.preventDefault();
  var input = document.getElementById("msgInput");
  var text = input.value.trim();
  if (!text || !apiKey) return;
  addMsg(text, "user");
  input.value = "";
  autoResize(input);
  document.getElementById("sendBtn").disabled = true;
  showTyping();
  try {
    var res = await fetch("/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: text, session_id: sessionId})
    });
    var data = await res.json();
    var t = document.getElementById("typing");
    if (t) t.parentNode.removeChild(t);
    if (!res.ok) throw new Error(data.detail || "Server error");
    sessionId = data.session_id;
    localStorage.setItem("tabib_sid", sessionId);
    var rb = document.getElementById("riskBar");
    rb.className = "risk-bar " + data.risk_level;
    rb.textContent = "Risk: " + data.risk_level + (data.risk_flags.length ? " | " + data.risk_flags.join(", ") : "");
    addMsg(data.reply, "ai");
  } catch(err) {
    var t = document.getElementById("typing");
    if (t) t.parentNode.removeChild(t);
    addMsg("Xatolik: " + err.message, "ai");
  }
  document.getElementById("sendBtn").disabled = false;
  document.getElementById("msgInput").focus();
});
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 62)
    print("  TABIB AI — Claude-Powered Medical Expert System v3.0")
    print("=" * 62)
    print(f"  http://localhost:8000")
    print(f"  http://localhost:8000/docs  (API dokumentatsiya)")
    print(f"  Model: {CLAUDE_MODEL}")
    print("=" * 62 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
