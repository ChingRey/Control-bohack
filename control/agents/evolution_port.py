"""Replacement seam only. No strategy optimization or automatic prompt changes."""
import copy
import hashlib
import json
import uuid

class MockEvolution:
    def evolve(self, packet):
        return {'mode':'mock','status':'placeholder','candidate_id':str(uuid.uuid4()),
                'parent_version':packet.get('strategy_version'),'strategy':None,
                'applied':False,'note':'Awaiting the new teaching strategy implementation'}

ADAPTER=MockEvolution()

def evolve(task, body):
    request_id=body.get('request_id')
    if not isinstance(request_id,str) or not 1<=len(request_id)<=120:raise ValueError('request_id required')
    packet={'session_id':task['id'],'teaching_session_id':body.get('teaching_session_id'),
        'strategy_version':body.get('strategy_version'),
        'completed_sessions':copy.deepcopy(task.get('teaching_sessions',[]))}
    fingerprint=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    records=task.setdefault('teaching_evolution_requests',{})
    if request_id in records:
        if records[request_id]['fingerprint']!=fingerprint:raise ValueError('request_id conflict')
        return copy.deepcopy(records[request_id]['result'])
    result=ADAPTER.evolve(packet)
    if not isinstance(result,dict) or result.get('applied') is not False:
        raise ValueError('Evolution interface cannot apply strategy changes')
    records[request_id]={'fingerprint':fingerprint,'result':copy.deepcopy(result)}
    return result
