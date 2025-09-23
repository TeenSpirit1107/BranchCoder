import json
from rag import extract_slices

if __name__ == "__main__":
    res = extract_slices("sample.py")

    # 转 dict，然后用 ensure_ascii=False 输出
    payload = res.model_dump()  # Pydantic v2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
