"""Host-enforced hybrid routing: humans use Blender; Python uses reviewed graphics."""
from character_catalog import candidates

REVISION = 'human-blender-1.0'
# Only reviewed object assets may enter the human-free Python route. Unknown
# pictograms (including silhouettes and emoji people) are not implicitly safe.
OBJECTS = set('train plane car bus ship rocket building-store carrot umbrella brain book device-mobile device-laptop currency-rupee currency-dollar cash pig-money wallet chart-line coin clock calendar heart stethoscope pill barbell bike headphones cup burger droplet plant leaf world moon sun bolt bulb flask atom robot shield lock building home school briefcase target trophy mountain volcano camera movie cloud shopping-cart basket planet dna magnet microscope tree fish paw flower lungs eye'.split())


def human_free(item):
    if item['kind']=='narrative':
        from narrative_catalog import PYTHON_CONCEPTS
        return item.get('theme') in PYTHON_CONCEPTS
    return item['kind'] == 'abstract' or (item['kind'] == 'asset' and
        item.get('icon') in OBJECTS and (not item.get('secondary') or item['secondary'] in OBJECTS))


def enforce(cues, selected, choices):
    """Override model routing where a Python preset could draw a person."""
    decisions = {item['cue_id']: dict(item) for item in choices}
    safe = []; changes = []
    for cue, preset in zip(cues, selected):
        item = decisions[cue['id']]
        adjusted = dict(preset)
        if item['action'] == 'python' and not human_free(adjusted):
            supported = candidates(cue, adjusted)
            if supported:
                item['action'] = supported[0]
                reason = 'Human-containing preset replaced by a source-supported Blender action.'
            else:
                adjusted = dict(kind='abstract', domain='neutral', action='journey',
                    origin='human_free_fallback', shot_variant=adjusted.get('shot_variant',0),
                    limitation='Unsupported interaction replaced by a nonhuman abstract transition.')
                reason = 'Unsupported human preset replaced by a human-free Python transition.'
            changes.append(dict(cue_id=cue['id'], action=item['action'], reason=reason))
        safe.append(adjusted)
        decisions[cue['id']] = item
    return safe, [decisions[cue['id']] for cue in cues], dict(revision=REVISION,
        status='enforced', humans_engine='blender', graphics_engine='python', changes=changes)


def validate(cues, selected, choices):
    """Fail before rendering if a human preset leaks into the Python branch."""
    indexed = {choice['cue_id']:choice for choice in choices}
    for cue, item in zip(cues, selected):
        if indexed[cue['id']]['action'] == 'python' and not human_free(item):
            raise ValueError(f"Human routing violation at cue {cue['id']}: Python preset is not human-free.")
