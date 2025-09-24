# Flow 系统说明文档✨

## 一、系统架构概览

### 1. BaseSubFlow（子流程基类）

* 所有子流程需继承此类
* 核心方法：`run()`

---

## 二、流程注册机制

### SubFlowFactory（流程工厂）

* 所有子流程需在 `factory.py` 的 `SubFlowFactory` 中注册
* 注册方式：在 `_register_default_flows()` 方法中添加子流程类
* 当前已注册流程：

  * `code_flow`: 代码相关操作（⚠️ 仅重定向，功能未实现）
  * `search_flow`: 搜索相关操作（⚠️ 仅重定向，功能未实现）
* 注意事项：

  * 除 `search_flow` 外，其余流程均直接重定向至 `sub planner flow`
  * `search_flow` 会先执行搜索逻辑，再重定向至 `sub planner flow`

---

## 三、流程类型支持

### Super Planner Agent 支持流程类型

* `file`: 文件操作
* `search`: 搜索操作（重定向至 Sub Planner Flow）
* `shell`: 命令行操作
* `message`: 消息处理

### Sub Planner Flow 支持流程类型

* `file`: 文件操作
* `search`: 搜索操作
* `shell`: 命令行操作
* `message`: 消息处理

---

## 四、记忆管理机制 🧠

### 1. 抽象结构

#### ① 计划记忆（Plan Memory）

* **Super Planner Memory**

  * 由 Super Planner 独立维护
  * 确保整体流程的上下文连贯性和一致性
* **Sub Planner Memory**

  * 每个子流程独立维护自身的规划逻辑和数据上下文

#### ② 执行记忆（Execution Memory）

* 每个 Sub Planner 独立维护，用于记录执行结果

---

### 2. 实现细节

#### Super Planner Flow 的记忆处理

* **memory**：记录整个工作流程的上下文
* **execution\_memory**：用于接收并存储子流程的执行结果

**流程传递逻辑：**

1. **执行（executing）**

   * 调用子流程时，Super Planner 将自身 `memory` 传递给 Sub Planner
   * 子流程执行后，其 `execution_memory` 会传回 Super Planner

2. **更新（updating）**

   * Super Planner 调用 `summarize agent`，将 `execution_memory` 进行总结，合并到全局 `memory`

3. **汇报（reporting）**

   * Super Planner 基于合并后的 `memory` 生成流程报告

#### Sub Planner Flow 的记忆处理（以 `plan_act` 为例）

* **计划、执行、更新** 阶段：可访问 Super Planner 提供的 `memory`
* **汇报阶段**：通过 `execution_memory` 向 Super Planner 返回结果

#### 从记忆视角看流程：

* `memory`：所有子流程报告经 `summarize agent` 汇总生成的全局记忆
* `execution_memory`：某次子流程执行后所生成的阶段性结果

#### Summarize Agent 的作用

* 接收当前子流程的 `execution_memory` 和全局 `memory`
* 输出更新后的新 `memory`

---

## 五、重要说明 ⚠️

1. 所有非 `search` 类型的流程，都会在工厂中直接重定向至 `sub planner flow`
2. `search` 类型流程会先执行 `search flow`，再重定向至 `sub planner flow`
3. 当前 `code_flow` 和 `search_flow` 均未实现具体功能，仅作重定向使用
