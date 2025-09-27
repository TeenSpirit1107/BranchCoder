# Branch Coder

## Pre-requirement
1. docker
2. conda or uv
3. brain (no need)

## Setup
1. change the `UPLOAD_HOST_ABS_PATH` in `.env` to your own ABS path. It should be in the **backend folder** and should be an **ABS path** (**important!**)
2. setup conda environment
    ```bash
    conda create -n branch_coder python=3.13
    conda activate branch_coder
    pip install -r requirements.txt
    ```
3. compose up the project (it takes a few minutes for the first time)
    ```bash
    sudo systemctl start docker
    docker compose up
    ```
4. access the frontend by `localhost:5173` in your browser

## Shutdown
1. shutdown in one commend
    ```bash
    docker compose down
    ```
    - You can press `Ctrl+C` twice to force shutdown. It is much quicker and has no known effect yet. Otherwise, it will shut down gracefully (gracefully slow)

## Restart
1. restart in one commend (should be fast)
    ```bash
    docker compose up
    ```
   
## Remind
1. `temperature` and `max_token` is not used in the openai api call yet since the interface of gpt-5 api is different from the legacy. Most importantly, I am lazy to change it.
2. You can use any email address and password to access the frontend.
3. When you restart the project, remember to close the legacy taps in your browser, otherwise there will be an error.

## Label
1. **[dev]** Only for development. This version may not run successfully
2. **[feature]** This version should run successfully.
3. **[milestone]** Big version update that can be used directly for any potential rollback.
4. Any other labels you want like `bug` `doc` etc.

## Technical Detail
### File Upload
- When you upload a file, it is uploaded to `/home/ubuntu/upload` in `sandbox` container
- I mount the `/home/ubuntu/upload` in `sandbox` container to `UPLOAD_HOST_ABS_PATH` in the backend folder of the host.
- I also mount the `./backend` folder to the `/app` folder in the `backend` container.
- As a result, `./backend/upload` in the host is synced to the `sandbox` and `backend` container.
- host: `./backend/upload` == backend: `/app/upload` == sandbox: `/home/ubuntu/upload`
### Rag Service
- By default, `Rag Service` run in the `backend` container and treat `/app/upload` as the workspace
- Indexing Pipeline
  1. Slice all the python file in the workspace to functions and classes, and build the caller-callee graph 
  2. Generate descriptions about the functions and classes and store them into the `./backend/app/domain/services/rag/describe_output.json`
  3. Generate index and store in `./backend/app/domain/services/rag/.rag_store`. There are three rag databases, each for `function`, `class`, and `file`.
- Retrival Pipeline
  1. Vector Similarity: Parameter: `initial_candidates`
  2. Rerank: Parameter: `enable_rerank` `rerank_top_n`
  - Three databases return `3*rerank_top_n` records together.
- Interface `/backend/app/domain/services/rag/rag_service.py`
- Parameters:
- `initial_candidates`: how many records per database is returned after `Vector Similarity` retrival.
- `enable_rerank`: whether enable `Rerank`. By default, enabled.
- `rerank_top_n`: how many records per database after `Rerank` retrival.

懒得写了，就这样吧 ：）
