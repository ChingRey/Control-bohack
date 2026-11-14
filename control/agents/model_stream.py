"""Read provider SSE incrementally; never publish reasoning or tool arguments."""
import json
import re
import time


def visible_text(text):
    marker = '<continuity_memory>'
    index = text.find('<continuity_memory')
    if index >= 0:
        text = text[:index]
    else:
        # A marker may be split between arbitrary network chunks.
        for count in range(min(len(text), len(marker) - 1), 0, -1):
            if text.endswith(marker[:count]):
                text = text[:-count]
                break
    # Hold an unfinished ASCII word (including a possible credential) until its
    # boundary arrives, so redaction happens before any part is published.
    return re.sub(r'[A-Za-z0-9_+/=:.@-]+$', '', text).rstrip()


def read(response, budget, emit):
    """Return the same completed wire object as a non-streaming request."""
    headers = getattr(response, 'headers', {})
    content_type = headers.get('Content-Type', '') if headers else ''
    if 'text/event-stream' not in content_type.lower():
        return json.load(response)  # Compatible servers may return ordinary JSON.
    text = ''
    calls = {}
    usage = {}
    finish = None
    data = []
    frame_bytes = 0
    last_publish = 0.0
    reasoning_seen = False

    def check():
        if budget.get('cancelled', lambda: False)():
            raise ValueError('本轮教学已因开发继续而中止')
        remaining = budget['deadline'] - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('模型流式回复超过本轮总时限')
        # urllib's timeout normally applies to each read; also enforce the round
        # deadline while a server keeps sending heartbeats or reasoning tokens.
        sock = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
        if sock is not None:
            sock.settimeout(min(budget.get('request_timeout', 60), remaining))

    def publish(force=False):
        nonlocal last_publish
        now = time.monotonic()
        if force or now - last_publish >= .35:
            emit('streaming', visible_text(text))
            last_publish = now

    def event(raw):
        nonlocal text, usage, finish, reasoning_seen
        if raw == '[DONE]':
            if finish not in ('stop', 'tool_calls', 'function_call'):
                raise ValueError('模型流式回复未完整结束，已生成片段保留，可重试')
            publish(True)
            message = {'role': 'assistant', 'content': text}
            if calls:
                message['tool_calls'] = [calls[i] for i in sorted(calls)]
            return {'choices': [{'message': message}], 'usage': usage}
        item = json.loads(raw)
        kind = item.get('type', '')
        if item.get('error') or kind in ('error', 'response.failed', 'response.incomplete'):
            # Provider messages may echo input. Keep errors fixed and secret-free.
            raise ValueError('模型流式回复未完成，已生成片段保留，可重试')
        if kind == 'response.output_text.delta':
            text += item.get('delta', '')
            publish()
        elif kind == 'response.completed':
            value = item.get('response', {})
            if value.get('status') != 'completed':
                raise ValueError('模型流式回复未完整结束，可重试')
            publish(True)
            # Includes function calls and encrypted reasoning items required for
            # the next tool round. They stay in memory, outside the live preview.
            return value
        elif kind.startswith('response.reasoning') and not reasoning_seen:
            reasoning_seen = True
            emit('reasoning', None)
        if item.get('usage'):
            usage = item['usage']
        for choice in item.get('choices', []):
            if choice.get('index', 0) != 0:
                continue
            delta = choice.get('delta', {})
            if delta.get('reasoning_content') and not reasoning_seen:
                reasoning_seen = True
                emit('reasoning', None)
            if delta.get('content'):
                text += delta['content']
                publish()
            for part in delta.get('tool_calls', []):
                index = part['index']
                call = calls.setdefault(index, {'id': '', 'type': 'function',
                                                'function': {'name': '', 'arguments': ''}})
                if part.get('id'):
                    call['id'] = part['id']
                for field in ('name', 'arguments'):
                    call['function'][field] += part.get('function', {}).get(field, '')
            if choice.get('finish_reason'):
                finish = choice['finish_reason']
        if len(text) > 200000 or sum(len(c['function']['arguments']) for c in calls.values()) > 200000:
            raise ValueError('模型回复过长，未采用未完成内容')
        return None

    while True:
        check()
        line = response.readline(1048577)
        check()
        if not line:
            raise ValueError('模型流式连接提前结束，已生成片段保留，可重试')
        frame_bytes += len(line)
        if frame_bytes > 1048576:
            raise ValueError('模型流式事件过大，未采用未完成内容')
        line = line.decode('utf-8').rstrip('\r\n')
        if not line:
            if data:
                result = event('\n'.join(data))
                if result is not None:
                    return result
            data = []
            frame_bytes = 0
        elif line.startswith('data:'):
            data.append(line[5:].lstrip(' '))
