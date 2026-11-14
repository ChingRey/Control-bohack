"""Coding -> Teaching checkpoint contract. Project events are not mastery evidence."""
import copy
import difflib
import time
import re
from . import code_refs, knowledge, memory, project_files

DIFF_CHARS = 12000
SOURCE_CHARS = 16000


def record(task, checkpoint_id, instruction, agent_output, before, after, stage_index, kind='development', tool_events=None, before_assets=None, after_assets=None):
    events = task.setdefault('coding_checkpoints', [])
    if any(e['checkpoint_id'] == checkpoint_id for e in events):
        return next(e for e in events if e['checkpoint_id'] == checkpoint_id)
    before_assets=before_assets or {};after_assets=after_assets or {}
    old_assets=project_files.asset_metadata(before_assets);new_assets=project_files.asset_metadata(after_assets)
    binary_changes=[{'file':n,'before':old_assets.get(n),'after':new_assets.get(n)} for n in sorted(set(old_assets)|set(new_assets)) if old_assets.get(n)!=new_assets.get(n)]
    changes = []
    remaining = DIFF_CHARS
    for name in sorted(set(before) | set(after)):
        if before.get(name) == after.get(name):
            continue
        diff = '\n'.join(difflib.unified_diff(before.get(name, '').splitlines(), after.get(name, '').splitlines(),
                                             fromfile='before/' + name, tofile='after/' + name, lineterm=''))
        excerpt = diff[:remaining]
        remaining -= len(excerpt)
        changes.append({'file': name, 'before_hash': code_refs.digest(before[name]) if name in before else None,
                        'after_hash': code_refs.digest(after[name]) if name in after else None,
                        'diff': excerpt, 'diff_truncated': len(excerpt) != len(diff)})
    executions=[]
    for item in tool_events or []:
        part=item.get('part',{});state=part.get('state',{})
        if part.get('tool') in ('bash','shell') and state.get('status') in ('completed','error'):
            command=str(state.get('input',{}).get('command',''))[:2000]
            executions.append({'tool':part['tool'],'command':command,'status':state['status'],
                               'output':str(state.get('output') or state.get('error') or '')[:2000],
                               'source':'coding_tool_event_not_independent_verification',
                               'version_notice':'工具执行后源码可能继续变化，需核对最终版本'})
    tests=[row for row in executions if re.search(r'pytest|unittest|--test|npm\s+(?:run\s+)?test|bun\s+test|cargo\s+test|go\s+test',row['command'])]
    requirement = next((m['content'] for m in task.get('messages', [])
                        if m.get('channel') == 'coding' and m.get('role') == 'user'), instruction)
    plan = task.get('plan', [])
    event = {'schema_version': 1, 'event_type': 'coding.paused', 'session_id': task['id'],
             'checkpoint_id': checkpoint_id, 'stage': plan[stage_index] if stage_index < len(plan) else 'planning',
             'stage_index': stage_index, 'kind': kind, 'task_description': instruction,
             'user_requirement': requirement, 'agent_output': agent_output, 'created_at': time.time(),
             'project_evidence': {'base_code_hash': knowledge.code_hash(before), 'code_hash': knowledge.code_hash(after),
                                  'changes': changes,'binary_changes':binary_changes,'asset_hash':project_files.asset_hash(after_assets),
                                  'runtime_observations': copy.deepcopy(task.get('runtime_observations', [])[-20:]),
                                  'runtime_notice': 'Browser reports are unverified and not bound to this checkpoint code version.',
                                  'execution_records':executions[-10:], 'test_records':tests[-10:],
                                  'test_status':'tool_reported_unverified' if tests else 'not_run',
                                  'read_file_tool': 'read_project_file'},
             'delivery': {'status': 'pending'}}
    if events and kind=='development' and events[-1]['kind']=='development' and events[-1]['stage_index']==stage_index:
        parent=events[-1]
        root_id=parent.get('root_checkpoint_id',parent['checkpoint_id'])
        root_event=next(e for e in events if e['checkpoint_id']==root_id)
        if not root_event.get('resume_request_id'):
            event['root_checkpoint_id']=root_id;event['previous_checkpoint_id']=parent['checkpoint_id']
    event['material_revision']=task.get('workflow',{}).get('revision',0)
    events.append(event)
    return event


def view(task, files):
    """Bound the model-facing event; the stored event retains original text and file references."""
    events = task.get('coding_checkpoints', [])
    if not events:
        return None
    event = copy.deepcopy(events[-1])
    event['operation_count']=len(event.pop('operations',[]))
    for key in ('task_description', 'user_requirement', 'agent_output'):
        value = event[key]
        event[key] = value[:4000]
        event[key + '_truncated'] = len(value) > 4000
    evidence = event['project_evidence']
    evidence['stale_for_code'] = evidence['code_hash'] != knowledge.code_hash(files)
    binary_changes=evidence.get('binary_changes',[])
    evidence['binary_change_count']=len(binary_changes);evidence['binary_changes']=binary_changes[:40]
    evidence['stale_for_assets']=evidence.get('asset_hash',project_files.asset_hash({}))!=project_files.metadata_hash(task.get('binary_files',{}))
    changes = evidence['changes']
    evidence['change_count'] = len(changes)
    evidence['changes'] = changes[:40]
    evidence['omitted_change_count'] = max(0, len(changes) - 40)
    for key in ('execution_records','test_records'):
        records=evidence.get(key,[])
        evidence[key]=[{**row,'output':row['output'][:1000]} for row in records[-3:]]
        evidence[key+'_omitted_count']=max(0,len(records)-3)
    # Browser messages can be large in old tasks; never infer a test result from them.
    evidence['runtime_observations'] = [
        {'type': row.get('type'), 'message': str(row.get('message', ''))[:500],
         'line': row.get('line'), 'source': 'browser_report_not_verified_test'}
        for row in evidence['runtime_observations'][-5:]]
    return event


def source_context(task, files):
    """Prefer changed files, with bounded complete lines; omitted source stays tool-readable."""
    events = task.get('coding_checkpoints', [])
    preferred = [c['file'] for c in events[-1]['project_evidence']['changes']] if events else []
    names = list(dict.fromkeys([*preferred, *files]))
    selected = {}
    for name in names:
        if name not in files:
            continue
        lines = []
        for i, line in enumerate(files[name].splitlines()[:120], 1):
            row = {'line': i, 'text': line}
            candidate = {**selected, name: [*lines, row]}
            if memory.size(candidate) > SOURCE_CHARS:
                break
            lines.append(row)
        if lines:
            selected[name] = lines
        if memory.size(selected) >= SOURCE_CHARS - 100:
            break
    index = [{'path': name, 'line_count': len(files[name].splitlines()), 'hash': code_refs.digest(files[name])}
             for name in names[:100] if name in files]
    return selected, {'files': index, 'total_file_count': len(files), 'omitted_file_count': max(0, len(files) - 100),
                      'source_budget_characters': SOURCE_CHARS, 'read_tool': 'read_project_file',
                      'notice': 'Initial source excerpts are incomplete. Read required lines before citing. Tool reads use this teaching run snapshot.'}
