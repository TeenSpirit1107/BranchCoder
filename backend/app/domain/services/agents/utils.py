import json
from enum import Enum

def extract_message_field(data):
    """
    兼容字符串和dict两种情况，提取message字段
    """
    if isinstance(data, dict):
        return data.get("message", data)
    if isinstance(data, str):
        try:
            obj = json.loads(data)
            if isinstance(obj, dict):
                return obj.get("message", obj)
        except Exception:
            pass
        return data
    return data

def safe_json_dumps(obj, **kwargs):
    """
    支持Enum等特殊类型的json序列化
    """
    def default(o):
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, 'dict'):
            return o.dict()
        if hasattr(o, '__dict__'):
            return o.__dict__
        return str(o)
    if 'ensure_ascii' not in kwargs:
        kwargs['ensure_ascii'] = False
    return json.dumps(obj, default=default, **kwargs) 