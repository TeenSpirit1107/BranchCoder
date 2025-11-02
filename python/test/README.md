# RAG Concurrency Tests

这个测试套件用于验证 RAG 系统的并发功能是否正常工作。

## 测试文件

- `test_rag_concurrency.py`: 测试 RAG 索引服务的并发访问能力

## 运行测试

### 方式 1: 直接运行 Standalone 测试

```bash
cd python
python3 test/test_rag_concurrency.py
```

这个方式会运行基本的并发测试，不需要 pytest。

### 方式 2: 使用 pytest 运行

```bash
cd python
pytest test/test_rag_concurrency.py -v
```

## 测试内容

测试套件包含以下测试：

1. **test_concurrent_retrieval**: 测试多个不同查询的并发检索
2. **test_concurrent_retrieval_with_same_query**: 测试相同查询的多次并发调用
3. **test_build_and_retrieve_concurrent**: 测试构建和检索的并发执行
4. **test_concurrent_build_protection**: 测试并发构建的序列化保护
5. **test_retrieve_after_multiple_builds**: 测试多次构建后的检索
6. **test_stress_concurrent_retrieval**: 压力测试（20个并发请求）
7. **test_indexing_direct_concurrent_access**: 直接测试 Indexing 类的并发访问

## 测试原理

测试验证了以下并发安全特性：

1. **检索锁 (`_retrieve_lock`)**: 确保多个检索请求不会同时修改索引状态
2. **构建锁 (`_build_lock`)**: 确保构建操作是串行执行的
3. **异步方法**: 所有关键方法都是异步的，支持并发调用

## 注意事项

- 测试需要安装项目依赖（包括 `llama_index`）
- 测试需要 OpenAI API 密钥配置（用于 embedding）
- 如果没有配置 API 密钥，测试可能会失败
- 测试使用模拟数据，不会影响实际工作空间

### 安装依赖

```bash
# 确保已安装项目依赖
cd /home/yf/Workspace/branch_coder
# 根据项目配置安装依赖（如使用 pip、uv 等）
```

### 环境变量

确保设置了必要的环境变量：
```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="your-base-url"  # 如果需要
```

## 预期结果

如果所有测试通过，说明：
- ✅ 多个并发检索请求可以安全执行
- ✅ 锁机制正确保护了索引的构建和检索操作
- ✅ 系统支持高并发的访问模式

