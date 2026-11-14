"""Small validated runtime limits; no model secrets or student state."""
import threading
_LOCK=threading.RLock()
DEFAULTS={'teacher_request_seconds':60,'teacher_total_seconds':120,
          'background_request_seconds':60,'background_total_seconds':180}
_VALUES=dict(DEFAULTS)


def settings():
    with _LOCK:return dict(_VALUES)


def validate(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULTS):raise ValueError('请提供完整的前台与后台超时设置')
    for name,number in value.items():
        maximum=300 if 'request' in name else 900
        if type(number) is not int or not 5<=number<=maximum:raise ValueError('单次超时范围5—300秒，整轮范围5—900秒')
    for prefix in ('teacher','background'):
        if value[prefix+'_request_seconds']>value[prefix+'_total_seconds']:raise ValueError('单次请求超时不能大于整轮超时')
    return dict(value)


def configure(value):
    clean=validate(value)
    with _LOCK:_VALUES.update(clean)
    return settings()


def budget(kind):
    import time
    s=settings();prefix='teacher' if kind=='teacher' else 'background'
    return {'attempts':0,'deadline':time.monotonic()+s[prefix+'_total_seconds'],
            'request_timeout':s[prefix+'_request_seconds'],'total_timeout':s[prefix+'_total_seconds']}
