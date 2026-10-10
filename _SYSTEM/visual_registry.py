"""Expandable data-only visual recipes backed by installed registered renderers."""
import hashlib
import json
from pathlib import Path
import re

REVISION='visual-registry-1.0'
MOTIONS=('cutaway','travel','transfer','pair','compare','build','orbit')


def recipes(store, base, root=None):
    """Discover all supported recipes; the planner has no twenty-concept ceiling."""
    from human_policy import OBJECTS
    result={name:dict(item,kind='narrative',theme=name) for name,item in base.items()}
    for icon in sorted(OBJECTS & set(store.names())):
        for motion in MOTIONS:
            name=f'object:{icon}:{motion}'
            result[name]=dict(kind='asset',engine='python',icon=icon,action=motion,
                objects=[icon.replace('-',' ')],goal=f'Animate the {icon.replace("-"," ")} with a {motion} composition.',
                keywords=[icon.replace('-',' ')])
    root=Path(root) if root is not None else Path(__file__).parent/'visual_library'
    files=[]
    if root.exists():
        from contract import no_links
        no_links(root,root)
        for path in sorted(root.glob('*.json')):
            no_links(path,root)
            if path.is_symlink() or path.stat().st_size>1024*1024:
                raise ValueError('Invalid visual recipe file.')
            from contract import read_json
            content=read_json(path)
            if set(content)!={'revision','recipes'} or content['revision']!=REVISION or not isinstance(content['recipes'],list):
                raise ValueError('Invalid data-only visual library format.')
            for item in content['recipes']:
                if not isinstance(item,dict) or set(item)!={'id','keywords','icon','secondary','motion','goal'}:
                    raise ValueError('Recipe fields may contain data only, never code or paths.')
                name=item['id']
                if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,79}',name) or name in result:
                    raise ValueError('Invalid or duplicate visual recipe identity.')
                if not isinstance(item['icon'],str) or item['icon'] not in OBJECTS or item['secondary'] is not None and (not isinstance(item['secondary'],str) or item['secondary'] not in OBJECTS):
                    raise ValueError('Recipe assets must be reviewed nonhuman objects.')
                store.resolve(item['icon'])
                if item['secondary']:store.resolve(item['secondary'])
                if not isinstance(item['motion'],str) or item['motion'] not in MOTIONS:raise ValueError('Unregistered object animation.')
                if not isinstance(item['keywords'],list) or not item['keywords'] or any(
                    not isinstance(word,str) or not 2<=len(word)<=120 for word in item['keywords']):
                    raise ValueError('Recipe keywords must be literal source phrases.')
                if not isinstance(item['goal'],str) or not 20<=len(item['goal'])<=400:
                    raise ValueError('Invalid recipe visual goal.')
                result[name]=dict(kind='asset',engine='python',icon=item['icon'],secondary=item['secondary'],
                    action=item['motion'],goal=item['goal'],keywords=item['keywords'],
                    objects=[value.replace('-',' ') for value in (item['icon'],item['secondary']) if value])
            files.append(dict(name=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    identity=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return result,dict(revision=REVISION,recipes=len(result),fixed_concept_ceiling=False,
        installed_objects=len(OBJECTS & set(store.names())),motions=len(MOTIONS),library_hash=identity,files=files,
        limitations=['The library is extensible, not an infinite supply of assets or animations.',
                    'Registered compositions do not guarantee narrative or artistic quality.'])


def relevant(cue,preset,catalog,context=()):
    """Retrieve source-related recipes without sending the complete library to AI."""
    source=cue['text'].casefold()
    names=[]
    for name,item in catalog.items():
        if item['kind']=='narrative':continue
        literal=any(re.search(r'(?<!\w)'+re.escape(word.casefold())+r'(?!\w)',source) for word in item.get('keywords',[]))
        seeded=preset.get('kind')=='asset' and item.get('icon')==preset.get('icon')
        if literal or seeded:names.append(name)
    # A matching recipe is retrieved by source words or an existing subject rule.
    # Neighboring prose remains context for the model, not an asset whitelist.
    return names


def preset_for(name,catalog,evidence,index):
    item=catalog[name]
    if item['kind']=='narrative':
        return dict(kind='narrative',theme=name,domain='neutral',shot_variant=index%3,
            origin='source_anchored_concept',source_evidence=evidence)
    from story_planner import domain_for
    return dict(kind='asset',icon=item['icon'],secondary=item.get('secondary'),action=item['action'],
        domain=domain_for(item['icon']),shot_variant=index%3,origin='source_anchored_recipe',
        source_evidence=evidence,visual_goal=item['goal'],recipe_id=name)
