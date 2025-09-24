from ..class_slicer import slice_classes_in_workspace

if __name__ == "__main__":
    res = slice_classes_in_workspace("sample_workspace")

    # Pydantic v2
    print(res.model_dump_json(indent=2))