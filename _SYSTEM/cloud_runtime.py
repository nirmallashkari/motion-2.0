"""Registered GPU notebook worker: data-only plans, no scene code generation."""
import json,os,subprocess,sys,time
from pathlib import Path
from cloud_contract import REVISION,digest,strict_json,validate_choice


def run(request,output_dir):
    started=time.monotonic();root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    import torch
    if not torch.cuda.is_available():raise RuntimeError('A CUDA GPU is required; CPU substitution is disabled.')
    if request['model']!='Qwen/Qwen3-8B':raise ValueError('Unregistered cloud model.')
    from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
    tokenizer=AutoTokenizer.from_pretrained(request['model'],revision=request['model_revision'],trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(request['model'],revision=request['model_revision'],trust_remote_code=False,
        device_map='auto',quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_compute_dtype=torch.float16,bnb_4bit_quant_type='nf4'))
    results=[];calls=0;previous=[]
    for index,job in enumerate(request['jobs']):
        source=json.loads(job['messages'][1]['content']);source['previous_visuals']=previous
        messages=[job['messages'][0],dict(role='user',content=json.dumps(source,ensure_ascii=False)),
            dict(role='user',content='Return JSON matching this exact schema: '+json.dumps(job['schema']))]
        for attempt in range(1,3):
            text=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            inputs=tokenizer(text,return_tensors='pt').to(model.device)
            if inputs.input_ids.shape[-1]>12000:raise ValueError('Source batch exceeds cloud context allowance.')
            calls+=1
            with torch.inference_mode():
                generated=model.generate(**inputs,max_new_tokens=job['tokens'],do_sample=True,temperature=.7,top_p=.8,top_k=20,
                    pad_token_id=tokenizer.eos_token_id)
            ids=generated[0][inputs.input_ids.shape[-1]:]
            content=tokenizer.decode(ids,skip_special_tokens=True).strip()
            try:
                if len(ids)>=job['tokens']:raise ValueError('Cloud model output reached its token limit.')
                answer=validate_choice(job,strict_json(content))
                results.append(dict(output=answer,attempts=attempt,output_tokens=len(ids)))
                previous.extend(item['concept'] for item in answer['scenes'])
                break
            except Exception as exc:
                if attempt==2:raise ValueError(f'Batch {index+1} failed validated JSON generation: {type(exc).__name__}') from exc
                messages.extend([dict(role='assistant',content=content),dict(role='user',content='Repair the response. Preserve every source cue in order. Choose only that cue\'s allowed_choices and its registered three-stage capability; prioritize a requested action over the problem it solves. Copy a verbatim source anchor. Exact JSON only.')])
        print(f'CLOUD: planned batch {index+1}/{len(request["jobs"])}',flush=True)
    report=dict(revision=REVISION,request_id=digest(request),model=request['model'],status='completed',results=results,
        runtime_ai_calls=calls,gpu=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],elapsed_seconds=round(time.monotonic()-started,3))
    (root/'plan.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return report
