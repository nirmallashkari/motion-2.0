"""Registered three-stage action plans and meaning-level repetition checks.

Models select capabilities; the host owns timing, motion, paths and geometry.
These source rules are conservative illustrations, not arbitrary comprehension.
"""
import json
import re

REVISION = 'action-director-1.0'
STAGES = ('setup', 'action', 'result')
BOUNDARIES = (0., .20, .78, 1.)
# A second recipe must change props/actions, never just the camera or its ID.
VARIANTS = {
    'criticism': ('incoming_arrows', 'closed_gate'),
    'reflection': ('mirror_consideration',),
    'fear': ('hesitation', 'protective_shadow'),
    'night_reflection': ('awake_clock',),
    'exhaustion': ('heavy_shoulders',),
    'selfworth': ('fragmented_mirror',),
    'struggle': ('broken_path',),
    'resolve': ('clenched_hand',),
    'destiny': ('notebook_line',),
    'effort': ('work_progress',),
    'confidence': ('chest_to_open_hand',),
    'victory': ('raised_trophy',),
}
ARCS = {
    'reflection': ('Face the mirror and notice the reflected person.', 'Bring a hand to the chin and examine the reflection.', 'Hold eye contact with the reflection; no automatic success is implied.'),
    'fear': ('Notice a shifting shadow in a confined light.', 'Hesitate and draw a hand toward the face.', 'Remain alert as the shadow settles; fear is not silently converted into victory.'),
    'night_reflection': ('Establish an awake person, bed and clock.', 'Move the eyes and clock while the person remains awake.', 'Hold the sleepless expression as time advances.'),
    'criticism': ('Establish a person and the source-related judgment metaphor.', 'Converging arrows or a closing gate provoke a protective reaction.', 'The judgment props settle while the person lowers their hands.'),
    'exhaustion': ('Establish a tired person under a cold light.', 'Lower the head and shoulders and bring a hand toward the forehead.', 'Hold a fatigued posture; no recovery is claimed.'),
    'selfworth': ('Establish a person beside a visibly fractured mirror.', 'Lower the gaze and reach toward the face.', 'Keep the person and damaged reflection visible.'),
    'struggle': ('Reveal a broken path and obstacles ahead.', 'Advance along the path with articulated steps.', 'Reach a further paving segment; obstacles remain visible.'),
    'resolve': ('Start with lowered head and relaxed hands.', 'Raise the head and bring a clenched hand forward.', 'Hold a deliberate ready stance.'),
    'destiny': ('Show a notebook, pen and prepared desk.', 'Write a visible new line with the pen.', 'Reveal the completed line and lift the writing hand.'),
    'effort': ('Show a worker and an incomplete task on a laptop.', 'Type while visible task blocks accumulate.', 'Reveal the completed illustrative task and pause the typing hands.'),
    'confidence': ('Place a hand on the chest and establish eye contact.', 'Open the hand toward the viewer while lifting the head.', 'Hold an open confident stance; no trophy or win is added.'),
    'victory': ('Establish the character beside an illustrative trophy.', 'Raise both arms in celebration.', 'Hold the celebration beside the visible trophy.'),
    'time_loss': ('Show a clock and an intact stack of calendar leaves.', 'Advance the clock and release calendar leaves.', 'Show fewer calendar leaves and the advanced clock.'),
    'separation': ('Show two linked rings joined by a bridge.', 'Pull the rings apart until the bridge breaks.', 'Hold two separated rings as fragments disperse.'),
    'turning_point': ('Show a dark barrier with a narrow closed seam.', 'Separate the barrier panels and let light enter.', 'Reveal a lit passage between the open panels.'),
    'fire': ('Show a small ember above a dark base.', 'Grow and flicker a layered flame with rising sparks.', 'Hold a stronger flame with continued purposeful flicker.'),
    'resilience': ('Show raw heated metal on an anvil and a raised hammer.', 'Strike the metal and progressively flatten it; emit impact sparks.', 'Show a shaped glowing bar while the hammer rests above it.'),
    'pressure': ('Show rough coal between separated press plates.', 'Close the plates and transform the rough silhouette into facets.', 'Release the plates slightly and reveal a bright faceted diamond.'),
    'inner_power': ('Establish a recognizable lion face with closed eyes.', 'Open the eyes and expand the surrounding mane rays.', 'Hold the awakened gaze with a subtle mane pulse.'),
    'strategy': ('Show a chess piece at its starting square.', 'Move it along a route and then change direction.', 'Hold the piece at a new square with the route visible.'),
}


def capabilities(concepts):
    return {name: dict(engine=item['engine'], objects=item['objects'],
        phases=list(ARCS.get(name, ('Establish the source subject.', 'Perform its registered action.', 'Show the resulting source-related state.'))),
        action=item.get('action', 'python'), generated_code_allowed=False)
        for name, item in concepts.items()}


def supported_concepts(text, concepts):
    return [name for name, item in concepts.items() if re.search(item['pattern'], text, re.I)]


def phase_actions(family, variant):
    if family=='criticism' and variant==1:
        return ('Establish a person in front of an open physical gate.', 'Close the gate panels as the person brings their hands inward.', 'Hold the closed gate and a guarded posture; no arrows are present.')
    if family=='fear' and variant==1:
        return ('Establish a worried person beside a tall dark barrier.', 'The person draws a hand inward beside the shadow barrier.', 'Hold the alert expression and barrier; no success is added.')
    return ARCS.get(family, ('Establish the source-mentioned subject and relevant props.',
        'Perform the registered source-supported object or character action.',
        'Show the resulting pose or object state without adding a factual claim.'))


def compile_direction(cues, selected, choices):
    """Bind an actual motion recipe; reject exhaustion rather than recycle."""
    seen = {}; output = []; records = []
    for cue, preset, choice in zip(cues, selected, choices):
        item = dict(choice); theme = item.get('theme')
        if theme:
            family = theme; variants = VARIANTS.get(theme, (theme,))
            stages = ARCS[theme]
        else:
            family = ('physical:' + item['action'] if item['action'] != 'python' else
                json.dumps({k: preset.get(k) for k in ('kind', 'icon', 'secondary', 'action', 'domain')}, sort_keys=True))
            variants = ('source_action',)
            stages = ('Establish the source-mentioned subject and relevant props.',
                'Perform the registered source-supported object or character action.',
                'Show the resulting pose or object state without adding a factual claim.')
        count = seen.get(family, 0)
        if count >= len(variants):
            raise ValueError(f"Meaningful visual alternatives exhausted at source line {cue['id']} ({family}). Camera changes do not count as a new idea.")
        seen[family] = count + 1
        stages=phase_actions(family,count)
        plan = dict(revision=REVISION, motion_family=family, plan_id=family + '/' + variants[count], variant=count,
            phases=[dict(stage=stage, start=BOUNDARIES[i], end=BOUNDARIES[i+1], action=stages[i]) for i, stage in enumerate(STAGES)])
        item['action_plan'] = plan; output.append(item)
        records.append(dict(cue_id=cue['id'], source=cue['text'], engine='python' if item['action']=='python' else 'blender',
            source_evidence=item.get('source_evidence', cue['text']), **plan))
    return output, dict(revision=REVISION, status='plan_passed', scenes=records,
        meaning_repeat_policy='Registered prop/action recipe uniqueness; camera and scene ID are ignored.',
        limitations=['Keyword-supported source matching is not unrestricted language understanding.',
            'Unsupported repeated actions stop before rendering; the host never invents an animation.'])


def inspect(project, cues):
    failures=[]; seen=set()
    if len(project['scenes']) != len(cues): failures.append('Action plans must preserve one shot per source line.')
    for scene in project['scenes']:
        plan=scene['params'].get('action_plan')
        if not plan: failures.append(scene['id']+': registered action plan is missing.'); continue
        if set(plan)!={'revision','motion_family','plan_id','variant','phases'} or plan['revision'] != REVISION or [p['stage'] for p in plan['phases']] != list(STAGES):
            failures.append(scene['id']+': action phases were changed.')
        family=plan.get('motion_family');variants=VARIANTS.get(family,(family,)) if family in ARCS else ('source_action',)
        variant=plan.get('variant')
        if type(variant) is not int or not 0<=variant<len(variants) or plan['plan_id']!=family+'/'+variants[variant]:
            failures.append(scene['id']+': unregistered action recipe.');continue
        if family in ARCS and scene['params'].get('theme')!=family:
            failures.append(scene['id']+': motion recipe does not match the rendered theme.')
        if family.startswith('physical:') and family!='physical:'+scene['params'].get('action',''):
            failures.append(scene['id']+': motion recipe does not match the rendered action.')
        expected=[dict(stage=stage,start=BOUNDARIES[i],end=BOUNDARIES[i+1],action=action) for i,(stage,action) in enumerate(zip(STAGES,phase_actions(family,variant)))]
        if plan['phases']!=expected:failures.append(scene['id']+': unregistered action phase content or timing.')
        if family not in ARCS and not family.startswith('physical:'):
            try:
                decoded=json.loads(family);content=json.loads(scene['params']['content_key'])
                if not isinstance(decoded,dict) or decoded.get('kind') not in {'asset','abstract','habit'}:raise ValueError('Unknown family')
                if decoded.get('kind')=='asset' and any(decoded.get(k)!=content.get(k) for k in ('kind','icon','secondary','action','domain')):raise ValueError('Changed renderer')
            except (ValueError,KeyError,TypeError):failures.append(scene['id']+': object action plan is not bound to its rendered content.')
        if plan['plan_id'] in seen: failures.append(scene['id']+': repeated action idea, regardless of camera.')
        seen.add(plan['plan_id'])
    return dict(revision=REVISION, status='failed' if failures else 'plan_passed', failures=failures)


def enforce(project, cues):
    report=inspect(project,cues)
    if report['failures']: raise ValueError('Action direction gate failed: '+'; '.join(report['failures']))
    return report
