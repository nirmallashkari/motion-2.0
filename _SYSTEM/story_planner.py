"""Reusable offline narration planner. Rules produce data, never new scene code."""
import re

DOMAINS = {
    'transport': {'train','plane','car','bus','ship','rocket','bike','walk','run'},
    'market': {'building-store','carrot','umbrella','burger','shopping-cart','basket'},
    'finance': {'currency-rupee','currency-dollar','chart-line','coin','cash','pig-money','wallet'},
    'science': {'world','moon','sun','planet','flask','atom','robot','dna','magnet','microscope'},
    'nature': {'plant','leaf','droplet','mountain','volcano','cloud','tree','fish','paw','flower'},
    'health': {'heart','stethoscope','pill','lungs','eye','brain','barbell'},
    'work': {'book','device-mobile','device-laptop','clock','calendar','bulb','briefcase','school','home','target','trophy','camera','movie','shield','lock'},
}
EXTRA_SUBJECTS = [
    ('currency-dollar',r'\bdollar\b|डॉलर','build'),
    ('cash',r'\bcash\b|नकद','build'),
    ('pig-money',r'\bsavings\b|गुल्लक','build'),
    ('wallet',r'\bwallet\b|बटुआ','cutaway'),
    ('shopping-cart',r'\bcart\b|खरीदारी','travel'),
    ('basket',r'\bbasket\b|टोकरी','cutaway'),
    ('planet',r'\bplanet\b|ग्रह','orbit'),
    ('dna',r'\bdna\b|जीन|डीएनए','cutaway'),
    ('magnet',r'\bmagnet\b|चुंबक','pair'),
    ('microscope',r'\bmicroscope\b|सूक्ष्मदर्शी','cutaway'),
    ('tree',r'\btree\b|वृक्ष','build'),
    ('fish',r'\bfish\b|मछली','travel'),
    ('paw',r'\banimal\b|जानवर|पशु','travel'),
    ('flower',r'\bflower\b|फूल','build'),
    ('lungs',r'\blungs?\b|फेफड़','cutaway'),
    ('eye',r'\beye\b|आंख|आँख','cutaway'),
]
HABIT_TOPIC = re.compile(r'\bhabit\b|\bdiscipline\b|\bsnooze\b|\btreadmill\b|\bmeditation\b|आदत|डिसिप्लिन|अनुशासन|स्नूज़|ट्रेडमिल|मेडिटेशन',re.I)
CONTINUATION = re.compile(r'^(और|लेकिन|फिर|ये|यह|इस|वह|वो|इसके|उसके|इसे|उसे|and\b|but\b|then\b|it\b|this\b|these\b|they\b|that\b)',re.I)


def domain_for(icon):
    return next((name for name,icons in DOMAINS.items() if icon in icons),'work')


def plan_story(cues,store,selector,choices=None,unmatched_policy='abstract'):
    """Resolve a complete timeline while keeping unsupported meaning visible."""
    if unmatched_policy not in {'abstract','ask','stop'}:
        raise ValueError('Unsupported unmatched-passage policy')
    use_habits=bool(HABIT_TOPIC.search(' '.join(c['text'] for c in cues)))
    selected,missing=selector(cues,store,choices,allow_habits=use_habits)
    # Resolve explicit pronouns using the closest earlier selected source subject.
    previous=None
    for index,(cue,chosen) in enumerate(zip(cues,selected)):
        if chosen is None and previous is not None and CONTINUATION.search(cue['text'].strip()):
            chosen=dict(previous,origin='context_rule',context_cue=previous.get('context_cue',cues[index-1]['id']))
            selected[index]=chosen
        if chosen is not None:
            chosen.setdefault('domain',domain_for(chosen.get('icon','book')))
            if chosen.get('domain')=='transport' and chosen.get('secondary') in DOMAINS['market']:
                chosen['domain']='market'
            chosen['shot_variant']=index%3
            previous=chosen
    missing=[entry for entry in missing if selected[next(i for i,c in enumerate(cues) if c['id']==entry['cue_id'])] is None]
    if unmatched_policy=='abstract':
        for index,(cue,chosen) in enumerate(zip(cues,selected)):
            if chosen is None:
                # No random icon or fabricated subject is assigned to unknown text.
                selected[index]=dict(kind='abstract',domain='neutral',action='journey',
                    origin='abstract_fallback',shot_variant=index%3,
                    limitation='No literal subject was recognized. This is an abstract visual transition, not verified interpretation.')
        missing=[]
    return selected,missing
