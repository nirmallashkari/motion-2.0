"""Separate network-capable DeepSeek process; validates data before host replay."""
import json
from pathlib import Path
import sys
import time

import contract
from cloud_contract import digest, validate_choice
from deepseek_client import DeepSeekClient, DeepSeekError
from deepseek_planner import REVISION, validate_return


def run(folder):
    request = contract.read_json(folder/'request.json')
    key_file = contract.no_links(contract.SYSTEM/'secrets/deepseek_api_key.txt', contract.SYSTEM)
    client = DeepSeekClient(key_file, model=request['model'], timeout=request['timeout_seconds'],
        reasoning_effort=request['reasoning_effort'], max_tokens=request['max_output_tokens'])
    started = time.monotonic()
    client.inventory()
    results, calls, previous = [], 0, []
    for index, job in enumerate(request['jobs']):
        body = json.loads(job['messages'][1]['content'])
        body['previous_visuals'] = previous
        messages = [job['messages'][0], dict(role='user', content=json.dumps(body, ensure_ascii=False))]
        for attempt in (1, 2):
            contract.write_json(folder/'status.json', dict(status='planning', batch=index+1, total_batches=len(request['jobs']), attempt=attempt))
            calls += 1
            try:
                output, evidence = client.generate(messages, job['schema'])
                validate_choice(job, output)
                results.append(dict(output=output, attempts=attempt, evidence=evidence))
                previous.extend(scene['concept'] for scene in output['scenes'])
                break
            except DeepSeekError:
                # Network, key, balance and truncated-output errors are not approval.
                raise
            except Exception:
                if attempt == 2:
                    raise DeepSeekError('DeepSeek batch failed source/schema validation after two attempts.') from None
                messages.append(dict(role='user', content='Previous JSON failed host validation. Return exactly the schema, cue order and allowed choices, with a verbatim source anchor. No extra fields.'))
        print(f'API: planned batch {index+1}/{len(request["jobs"])}', flush=True)
    response = dict(revision=REVISION, provider='deepseek', model=request['model'], request_id=digest(request),
        status='completed', results=results, runtime_ai_calls=calls, elapsed_seconds=round(time.monotonic()-started, 3))
    validate_return(request, response)
    contract.write_json(folder/'validated_plan.json', response)
    contract.write_json(folder/'status.json', dict(status='completed', runtime_ai_calls=calls))
    return response


if __name__ == '__main__':
    folder = Path(sys.argv[1]).resolve()
    try:
        run(folder)
    except DeepSeekError as error:
        # These messages contain only fixed diagnostics, never provider bodies/key.
        contract.write_json(folder/'status.json', dict(status='failed', reason=str(error)))
        print('ERROR: '+str(error), flush=True)
        sys.exit(1)
    except Exception:
        contract.write_json(folder/'status.json', dict(status='failed', reason='DeepSeek broker validation/execution failed.'))
        print('ERROR: DeepSeek broker validation/execution failed.', flush=True)
        sys.exit(1)
