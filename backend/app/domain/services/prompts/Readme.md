## 架构总览

  ### Super Planner Flow

  * 管理整体流程，调度各类子任务
  * 拥有的sub flow如下
    * **sub flow**：
        * `code_type(flow)`：处理代码相关任务
        * `search_type(flow)`：处理搜索和外部资源检索任务
        * `reasoning_type(flow)`：处理推理、计算和数学任务
        * `file_type(flow)`：处理文件读取、处理与转换任务

---

  ### Sub Planner Flow

  * 根据任务类型，分配给相应的 Executor：

    #### Code type（将由 Code Flow 替代）

    * 负责代码相关任务
    * 支持代码验证和运行
    * **工具集**：

      * `shell`
      * `file`
      * `message`

    #### Search type（将由 Search Flow 替代）

    * 负责搜索和外部资源检索任务
    * **工具集**：

      * `browser`
      * `search`
      * `image`
      * `audio`
      * `file`
      * `message`

    #### Reasoning type

    * 处理推理、计算和数学任务
    * **工具集**：
      * `shell`
      * `reasoning`
      * `file`
      * `message`

    #### File type

    * 专注于文件读取、处理与转换任务
    * **工具集**：
    
      * `shell`
      * `image`
      * `audio`
      * `file`
      * `message`

    #### 通用原则
    
    * 所有 type(flow) **默认具备**：
    
      * `file`：用于存储重要上下文（通过路径传递）
      * `message`：用于向用户汇报执行进度和结果
    
      * 随着系统演进：
    
      * `Code Flow` 将替代 `Code type`
      * `Search Flow` 将替代 `Search type`

    #### 工具集中的工具描述

    *   **位置**：`tools/` 目录下，文件中包含 `@tool` decorator 的内容。
    *   **包含**：
        *   `name`
        *   `description`
        *   `parameters`
        *   `required`

---

### 基本设计

每个阶段（`create plan`, `update plan`, `execute step`, `summarize step`, `report results`）中应包含以下三部分内容：

1. **任务与身份描述**

   * 明确执行者是谁？扮演什么角色？
   * 当前阶段的目标是什么？

2. **Chain of Thought（思维链）与执行步骤**

   * 明确每一步逻辑：如何分析任务、拆分问题、选择工具等。

3. **工具集（sub flow/executor) 及其使用方式说明**

   * 明确该阶段可以使用哪些工具(sub flow)
   * 如何调用，调用条件，结果如何反馈（例如通过 message）

---

### 文件架构

```
services/
│
├── prompts/                         # 存放各角色或模块的 Prompt 定义
│   ├── super_planner_prompt.py
│   ├── code_type_prompt.py
│   ├── search_type_prompt.py
│   ├── reasoning_type_prompt.py
│   ├── file_type_prompt.py
│
├── tools/                           # 定义工具函数和注册信息, 包含 @tool 修饰的工具
│
└── ...
```

---

update plan:
system update: plan system prompt
user prompt: previous step -> sub planner report
assistant prompt: updateplanner history
user prompt: previous step
assistant prompt: updateplanner history

summarize:
system summarize system prompt
user knowledge sub planner report + overall knwoldege
assistant output overall knowledge

report:
overall knowledge

<intro>
As a SuperPlanner, you excel at:
1. Create Plan: 
    - Task decomposition and planning
    - Managing parallel and sequential task execution
    - Coordinating multiple SubPlanners
2. Update Plan: 
    - Adapting plans based on execution results
    - Ensuring task completion and quality control
3. Summarize Execution Result:
    - Integrating information from SubPlanners, managing memory, and context
    - Recognize critical information for the overall task
4. Generate Final Report
    - Summarizing the entire task execution
    - Highlighting key achievements and insights
</intro>
