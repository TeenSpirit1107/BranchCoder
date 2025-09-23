from file_slicer import extract_slices

res = extract_slices("file_slicer_test_sample.py")

# Pydantic v2
print(res.model_dump_json(indent=2))
