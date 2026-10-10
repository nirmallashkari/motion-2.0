"""Grounded, reusable character actions; no model-authored animation code."""
import re

REVISION = "character-2.1"
ACTIONS = {
    "walk": dict(environment="outdoor", objects=["person", "path"],
        pattern=r"\bwalk(?:ing|s)?\b|टहल|पैदल|चलते|चलना|चल रहा"),
    "read": dict(environment="study", objects=["person", "book", "desk", "chair"],
        pattern=r"\bread(?:ing|s)?\b|\bstudy\b|पढ़|किताब|पुस्तक"),
    "phone": dict(environment="living", objects=["person", "phone", "sofa"],
        pattern=r"\bphone\b|\bmobile\b|मोबाइल|फोन|फ़ोन"),
    "lift": dict(environment="gym", objects=["person", "dumbbell"],
        pattern=r"\bexercise\b|\bdumbbell\b|\bworkout\b|व्यायाम|डम्बल|डंबल|कसरत|एक्सरसाइज"),
    "run": dict(environment="gym", objects=["person", "treadmill", "headphones"],
        pattern=r"\brun(?:ning|s)?\b|\btreadmill\b|दौड़|ट्रेडमिल"),
    "meditate": dict(environment="living", objects=["person", "mat"],
        pattern=r"\bmeditat(?:es?|ion|ing)\b|मेडिटेशन|ध्यान करता|ध्यान लग|ध्यान में|ध्यान के लिए"),
    "sleep": dict(environment="bedroom", objects=["person", "bed", "clock"],
        pattern=r"\bsleep(?:ing|s)?\b|सोते|सोना|सो रहा|नींद"),
    "carry_phone": dict(environment="study", objects=["person", "phone", "door"],
        pattern=r"(?:phone|mobile).*?(?:another room|away)|(?:मोबाइल|फोन|फ़ोन).*?(?:दूसरे कमरे|दूर)"),
    "write": dict(environment="study", objects=["person","notebook","pen","desk"],
        pattern=r"\bwrit(?:e|es|ing)\b|लिख रहा|लिखती|लिखता|लिखना|नोट्स लिख"),
    "type": dict(environment="study", objects=["person","laptop","desk"],
        pattern=r"\btyp(?:e|es|ing)\b|टाइप|लैपटॉप पर काम|कंप्यूटर पर काम"),
    "drink": dict(environment="living", objects=["person","cup"],
        pattern=r"\bdrink(?:s|ing)?\b|चाय पी|पानी पी|कॉफी पी|पी रहा"),
    "eat": dict(environment="living", objects=["person","bowl","spoon"],
        pattern=r"\beat(?:s|ing)?\b|खाना खा|भोजन कर|खा रहा"),
    "explain": dict(environment="living", objects=["person","presentation board"],
        pattern=r"\bexplain(?:s|ing)?\b|समझा रहा|समझाती|समझाता|समझाना"),
    "point": dict(environment="living", objects=["person","target board"],
        pattern=r"\bpoint(?:s|ing)? (?:at|to)\b|इशारा करता|इशारा कर|उंगली से"),
    "wave": dict(environment="outdoor", objects=["person"],
        pattern=r"\bwav(?:e|es|ing) (?:hello|goodbye|to)\b|हाथ हिलाकर|हाथ हिला|अलविदा"),
    "celebrate": dict(environment="living", objects=["person","trophy"],
        pattern=r"\bcelebrat(?:e|es|ing)\b|जश्न|खुशी से उछल|जीत का"),
    "think": dict(environment="living", objects=["person"],
        pattern=r"\bthink(?:s|ing)?\b|सोच रहा|सोचती|सोचता|सोच में"),
    "sad": dict(environment="living", objects=["person"],
        pattern=r"\bsad\b|\bdisappointed\b|उदास|निराश"),
    "stretch": dict(environment="gym", objects=["person","mat"],
        pattern=r"\bstretch(?:es|ing)?\b|स्ट्रेच|अंगड़ाई"),
    "pushup": dict(environment="gym", objects=["person","mat"],
        pattern=r"\bpush[ -]?ups?\b|पुशअप|पुश अप"),
    "squat": dict(environment="gym", objects=["person","mat"],
        pattern=r"\bsquat(?:s|ting)?\b|स्क्वाट|उठक बैठक"),
    "jump": dict(environment="outdoor", objects=["person","path"],
        pattern=r"\bjump(?:s|ing)?\b|कूद रहा|कूदती|कूदना|छलांग"),
    "listen": dict(environment="living", objects=["person","headphones"],
        pattern=r"\blisten(?:s|ing)?\b|संगीत सुन|गाना सुन|ऑडियो सुन"),
    "stand": dict(environment="living", objects=["person"],
        pattern=r"\bstand(?:s|ing)?\b|खड़ा है|खड़े हैं|खड़ी है"),
    "sit": dict(environment="living", objects=["person","sofa"],
        pattern=r"\bsit(?:s|ting)?\b|बैठ रहा|बैठती|बैठता|बैठा है"),
    "carry_box": dict(environment="outdoor", objects=["person","box","path"],
        pattern=r"\bcarr(?:y|ies|ying) (?:a |the )?box\b|डिब्बा ले|बॉक्स ले|डिब्बा उठा"),
    "shop": dict(environment="market", objects=["person","basket","produce stall"],
        pattern=r"\bshop(?:s|ping)?\b|खरीदारी|सब्जी खरीद|सब्जियां खरीद|सामान खरीद"),
    "cook": dict(environment="kitchen", objects=["person","pan","stove"],
        pattern=r"\bcook(?:s|ing)?\b|खाना बना|भोजन बना|पकाता|पका रहा"),
    "water_plant": dict(environment="outdoor", objects=["person","watering can","plant"],
        pattern=r"\bwater(?:s|ing)? (?:a |the )?plant\b|पौध.*पानी|पानी.*पौध"),
    "paint": dict(environment="studio", objects=["person","brush","canvas","easel"],
        pattern=r"\bpaint(?:s|ing)?\b|पेंटिंग बना|चित्र बना|रंग भर"),
    "cycle": dict(environment="outdoor", objects=["person","bicycle","path"],
        pattern=r"\bcycl(?:e|es|ing)\b|\brides? (?:a |the )?bicycle\b|साइकिल चला|साइकिल चल"),
    "talk": dict(environment="living", objects=["person"],
        pattern=r"\btalk(?:s|ing)?\b|\bspeak(?:s|ing)?\b|बात कर|बोल रहा|बोलती|बोलता"),
}
FAMILIES = {"night_plan":"sleep", "small_start":"read", "two_lines":"read",
            "convenience":"phone", "gym":"lift", "treadmill":"run",
            "phone_away":"carry_phone", "fixed_anchor":"read"}
PRIORITY = ["carry_phone","carry_box","water_plant","pushup","squat","stretch","cycle",
            "write","type","cook","paint","shop","drink","eat","celebrate","wave",
            "listen","point","explain","sad","think","sleep","meditate","run","lift",
            "read","phone","walk","sit","stand","talk","jump"]
NEGATION = re.compile(r"\b(?:not|never|don't|doesn't|cannot|can't|nahi|mat)\b|नहीं|मत\s",re.I)
METAPHOR = re.compile(r"\brun (?:a |the )?(?:business|company|program)\b|\bjump to conclusions\b|ध्यान देना|ध्यान दें",re.I)
ROMAN = {
    'walk':r'paidal|chal raha|chal rahi|tehal|tahal',
    'read':r'padh raha|padh rahi|kitab padh|padhna',
    'write':r'likh raha|likh rahi|notes likh|likhna',
    'type':r'type kar|typing|laptop par kaam',
    'drink':r'pani pi|chai pi|coffee pi|pee raha',
    'eat':r'khana kha|kha raha|kha rahi',
    'cook':r'khana bana|paka raha|paka rahi',
    'shop':r'kharidari|sabzi kharid|saman kharid',
    'sleep':r'so raha|so rahi|sona|neend|bistar par lete|bistar pe lete',
    'carry_phone':r'(?:phone|mobile).*(?:dusre kamre|doosre kamre|door rakh)',
    'carry_box':r'(?:dabba|box).*(?:le ja|utha)',
    'water_plant':r'paudh.*pani|pani.*paudh',
    'meditate':r'dhyan laga|dhyan kar|meditation',
    'run':r'daud raha|daud rahi|daudna|treadmill',
    'lift':r'vyayam|kasrat|dumbbell',
    'think':r'soch raha|soch rahi|sochta|socha tha|khud se darr|aaina dekha|khud par yakeen',
    'sad':r'udaas|udas|nirash|nazron mein gir|taane sun|waqt kharab',
    'stand':r'\butho\b|uth jao|khade ho|khada hai',
    'celebrate':r'jashn|khushi se',
    'talk':r'baat kar|bol raha|bol rahi',
    'listen':r'gana sun|sangeet sun|audio sun',
    'cycle':r'cycle chala|cycle chal|saikil chala',
}
NONHUMAN = re.compile(r'\b(?:dog|cat|bird|robot|planet)\b|कुत्ता|बिल्ली|पक्षी|रोबोट|ग्रह',re.I)


def physical_matches(text, pattern):
    """Reject negated clauses and familiar nonphysical verb usages."""
    for match in re.finditer(pattern,text,re.I):
        left=max(text.rfind(mark,0,match.start()) for mark in ('.','!','?','।',';'))+1
        right=min([pos for mark in ('.','!','?','।',';') if (pos:=text.find(mark,match.end()))>=0] or [len(text)])
        clause=text[left:right]
        if not NEGATION.search(clause) and not METAPHOR.search(clause):
            return True
    return False


def candidates(cue, chosen):
    if NONHUMAN.search(cue['text']):return []
    found = [name for name in PRIORITY if physical_matches(cue["text"],ACTIONS[name]["pattern"]+'|'+ROMAN[name] if name in ROMAN else ACTIONS[name]["pattern"])]
    # Habit templates may encode supported context, but never replace a metaphor
    # with an unrelated literal exercise scene merely because it mentions a brain.
    family = chosen.get("family")
    if family in FAMILIES and not found and not NEGATION.search(cue["text"]):
        preferred = FAMILIES[family]
        found = [preferred] + [name for name in found if name != preferred]
    if "carry_phone" in found:
        found = ["carry_phone"] + [name for name in found if name not in {"phone","carry_phone"}]
    if "run" in found:
        found = ["run"] + [name for name in found if name not in {"run","walk"}]
    # Technical or scientific comparisons that merely mention reading/phones
    # retain the source-related 2D route if no physical scene is supported.
    return found[:5]


def decisions(cues, selected):
    return [dict(cue_id=cue["id"], choices=candidates(cue,chosen))
            for cue,chosen in zip(cues,selected)]
