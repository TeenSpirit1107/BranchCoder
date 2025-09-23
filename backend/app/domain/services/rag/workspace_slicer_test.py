# demo_slice_workspace.py
from workspace_slicer import slice_workspace

if __name__ == "__main__":
    res = slice_workspace("sample_workspace")

    # Pydantic v2
    print(res.model_dump_json(indent=2))

    # 也可以更友好地看一眼统计
    # print("\n=== STATS ===")
    # print("root:", res.root)
    # print("processed files:", res.num_files_processed)
    # print("functions:", res.num_functions, "classes:", res.num_classes)
    # print("errors:", len(res.errors))
