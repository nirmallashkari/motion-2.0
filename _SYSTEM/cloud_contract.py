"""Strict cloud data contract shared by host and the registered GPU worker."""
import hashlib,json
from jsonschema import Draft202012Validator

REVISION='motion-cloud-planner-2.0'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def strict_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key in cloud output.')
            result[key]=value
        return result
    def bad(value):raise ValueError('Non-finite cloud JSON number.')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=bad)


def validate_choice(job,output):
    Draft202012Validator(job['schema']).validate(output)
    source=json.loads(job['messages'][1]['content'])
    if [s['cue_id'] for s in output['scenes']]!=[c['id'] for c in source['source']]:
        raise ValueError('Cloud changed source line order or repeated a cue ID.')
    for choice,cue,allowed in zip(output['scenes'],source['source'],source['allowed_choices']):
        if choice['concept'] not in allowed or choice['evidence'] not in cue['text'] or len(choice['evidence'].strip())<3:
            raise ValueError('Cloud visual lacks a permitted concept and verbatim source anchor.')
    return output


def validate_return(request,response):
    if set(response)!={'revision','request_id','model','status','results','runtime_ai_calls','gpu','elapsed_seconds'}:
        raise ValueError('Cloud return has missing or unexpected fields.')
    if response['revision']!=REVISION or response['request_id']!=digest(request) or response['model']!=request['model'] or response['status']!='completed':
        raise ValueError('Cloud return is stale, failed or bound to another request/model.')
    if type(response['runtime_ai_calls']) is not int or not len(request['jobs'])<=response['runtime_ai_calls']<=len(request['jobs'])*2:
        raise ValueError('Invalid cloud model call accounting.')
    if len(response['results'])!=len(request['jobs']):raise ValueError('Incomplete cloud return.')
    for job,result in zip(request['jobs'],response['results']):
        if set(result)!={'output','attempts','output_tokens'} or type(result['attempts']) is not int or result['attempts'] not in (1,2) or type(result['output_tokens']) is not int or not 1<=result['output_tokens']<=job['tokens']:
            raise ValueError('Invalid cloud result metadata.')
        validate_choice(job,result['output'])
    if sum(result['attempts'] for result in response['results'])!=response['runtime_ai_calls']:
        raise ValueError('Cloud call counts do not match completed results.')
    if not isinstance(response['gpu'],list) or not response['gpu'] or any(not isinstance(item,str) or not item.strip() for item in response['gpu']):
        raise ValueError('Cloud GPU evidence is missing.')
    if type(response['elapsed_seconds']) not in (int,float) or not 0<=response['elapsed_seconds']<=7200:
        raise ValueError('Invalid cloud elapsed time.')
    return response
