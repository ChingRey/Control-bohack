# 队友分支评估

分支codex/project-knowledge-retrieval，ae0ba86；基于6700f65。独立拉取目录：../control-teammate-review。不合并、不改运行数据。

增加：Teaching最多2条带学生原话证据的候选知识；人工审核通过后同任务检索；SQLite事务内索引同步；中文二元组/英文词匹配top3；传给Coding并记录版本、源代码hash、过期标志；安装脚本、多Windows可执行文件路径与可选显式代理。

实测：73项测试中72通过、1错误。test_learning_read_and_markdown_export_preserve_records访问Markdown导出返回404。backend.py的learning路由把Markdown return缩进放进了已return的分支，导致不可达。知识API专测4项通过。不是实际模型收益测试。

不能整支覆盖当前control：它保留旧的自动step推进、旧任务清单覆盖模式、旧20步提示词，缺少当前code_refs及前端行高亮等后续补丁。start_coding聊天分支重建packet，合并时必须保留knowledge上下文及锁定阶段信息，两者不可相互覆盖。

建议选择性接入knowledge.py、learning候选校验、数据库事务索引、审核/检索接口及测试；沿用当前执行器/前端，手动添加knowledge输入。保留双提升通道：此项属于小经验/项目上下文，不是Skill安装或学生已掌握认证。现有经验与知识可能重复，需要去重/共同停用开关。stale仅标记仍会召回，初版建议过期只作历史线索，不自动当当前事实。前端只有列表展示，无审核按钮，需要补。安装脚本先单独采用，代理可选不默认开启；不得照搬会把Coding定义为教师的system prompt。

下一步：在新的集成分支合入上述模块，先修Markdown导出，再跑双方回归及新旧阶段控制测试；最后做固定模型、知识启停、未见任务配对，才能评价提升。当前没有更改或推送任何集成结果。
