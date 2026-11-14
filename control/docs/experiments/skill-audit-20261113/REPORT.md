# 桌面Skill清单：Coding优先接入检查（2026-11-13）

结论：**65项不能全部原样、全局启用。64项的Skill入口在真实OpenCode中加载成功；1项没有标准入口。加载成功不证明方法完整可执行或能改善Coding。真实效果对照尚无有效样本。**

## 已完成的验证

- 读取桌面的3份清单，对65个候选定位来源、固定仓库commit、缓存正文并记录内容哈希。原桌面文档未改动。
- 在独立临时目录调用项目实际OpenCode 1.18.34，以本机合成服务强制发出skill工具调用：64项均返回completed。只允许读取/加载，没有执行Skill脚本、Shell、发布或安装动作。
- S08原链接是套件，补充定位到`skills/zettelkasten-socratic-tutor/SKILL.md`；它不是原清单中的同名独立目录。
- S09当前固定版本未找到SKILL.md，是Python教学项目/课程材料；不能算成第65个可直接加载的Skill。
- S12/S13虽然入口可加载，但正文是转调grilling、domain-modeling的包装；没有补依赖，不代表功能可用。
- 原生加载实验只验证入口与协议。引用文件、脚本、其他Skill、MCP和宿主hooks不是全部验证通过；优先候选的附属资料也仅部分缓存。
- 当前工作台的默认Skill注册/解锁状态没有改变，没有把65项设成已验证或自动启用，也没有修改现有模型连接配置。

## 当前模型阻塞与效果边界

- 原先工作台Qwen服务的22个已创建实验任务均未形成有效对照；返回Access denied并指向账户状态/欠费说明。实验任务与失败记录保留，不改学生项目。
- 用户指定改用SiliconFlow中国站`https://api.siliconflow.cn/v1`与`Qwen/Qwen2.5-7B-Instruct`。一次最小认证调用返回HTTP401、code=30014、Token is invalid；站点已由用户确认。
- **有效效果样本数=0。不能给出“提升多少”“哪些实测无效”等结论。** 失败请求和未修改的缺陷教材已从所有效果统计中排除。
- 基线/单Skill比较脚本已加入认证熔断；没有成功模型输出时不对种子代码计分、不转sample。旧失败数据只作为故障记录。

## Coding优先的适配建议（不是效果排名）

| 第一批候选 | 适用阶段 | 必须保留的边界 |
|---|---|---|
| S32 systematic-debugging | 真实问题定位与修复 | 先根因；无执行工具就标明复现/测试待做 |
| S33 verification-before-completion | 宣布完成之前 | 用真实证据；当前不能伪称运行测试 |
| S38 qa-test-planner | 设计正常/边界/回归验收 | 测试计划和实际结果分开 |
| S56 frontend-design | 新界面和视觉实现 | 保留用户确认的风格；还需浏览器/视觉检查 |

S11适合规划阶段；S10/S16需避免额外审批/评分门槛阻塞已授权任务。S58/S59仅在React/Next场景采用。S34/S39/S57等完整工作流依赖尚未开放的执行/浏览器/构建能力。S01—S08多数应留Teaching侧，不能让Coding变成持续测验。

## 后续可复现对照

准备了4个固定案例：精确金额/非法输入修复、待办存储ID与隔离性、计数器DOM/持久化、购物MVP阶段计划。预设24轮，每个基线/单Skill单元2次，最多2个并发；不在学生项目上实验。

- Native对照每轮最多指定一个原始Skill，正文不改写；宿主仅在隔离实验中允许skill工具。额外审批/外部发布不覆盖任务授权，脚本不运行。
- 金额与存储运行合成JS行为检查；计数器使用模拟DOM和静态可访问性检查，不等于浏览器验收；规划检查结构、依赖与范围，不认证教学或长期工程质量。
- Node测试进程不继承API密钥，限制文件读取、禁止子进程授权，并在禁止字符串/WASM动态代码生成的独立VM中运行合成产物。
- 模型工具调用能力先做单独探测；如果模型未调用工具，结果标为能力未证实，不归咎于Skill。
- 保留模型名、固定源码版本/哈希、输入、输出、加载工具事件、耗时和行为结果。2次重复仍只是小样本，不支持稳定能力提升结论。

在control根目录运行，密钥由终端隐藏输入，只进入进程内存，不必再贴到聊天：

```powershell
# 先只验证认证，不跑整组：
python docs/experiments/skill-audit-20261113/skill_lab_direct.py
# 确认可调用后显式开始24轮（产生模型调用费用）：
python docs/experiments/skill-audit-20261113/skill_lab_direct.py --run
```

默认保持用户指定模型`Qwen/Qwen2.5-7B-Instruct`及中国站，不偷偷更换模型。当前执行超时仍为900秒；本轮不改变工作台权限或服务配置。

## 全部65项适配表

| ID | Skill | 原生入口 | Coding适配判断 | 原因 |
|---|---|---|---|---|
| S01 | [socratic-tutor](https://github.com/janestreet/agent_skills/blob/7c6715c29548a3b39d4a9545c698ee4fd17a7213/socratic-tutor/SKILL.md) | 加载成功 | 适合教学侧 | 苏格拉底式课程会改变Coding交互目标；应放Teaching，不让已授权开发变成测验。 |
| S02 | [learn-codebase](https://github.com/ktaletsk/learn-codebase/blob/06534bcba81ad14159b372cf4f636abc04d2fe66/SKILL.md) | 加载成功 | 适合教学侧 | 预测、主动回忆与学习日志适合代码理解；日志需映射现有课程记录，不能另立学习事实源。 |
| S03 | [teach](https://github.com/baney75/myelinate/blob/682f3c91c205dd30574be1389f30f0c213fc99c9/skills/teach/SKILL.md) | 加载成功 | 适合教学侧 | 围绕课程和课时，不是工程实现能力；保留到Teaching实验。 |
| S04 | [tutor](https://github.com/baney75/myelinate/blob/682f3c91c205dd30574be1389f30f0c213fc99c9/skills/tutor/SKILL.md) | 加载成功 | 适合教学侧 | 课程辅导方法，正文较长；不应作为Coding常驻提示。 |
| S05 | [assignment](https://github.com/baney75/myelinate/blob/682f3c91c205dd30574be1389f30f0c213fc99c9/skills/assignment/SKILL.md) | 加载成功 | 适合教学侧 | 作业辅导需保留学生思考，和Coding直接交付代码的职责不同。 |
| S06 | [generating-technical-quiz](https://github.com/gkuchar/educational-agent-skills/blob/afbf3aeba794423c7b9ea91d774011284b23d2cf/generating-technical-quiz/SKILL.md) | 加载成功 | 适合教学侧 | 技术测验生成属于教学评价材料，不直接提高代码实现能力。 |
| S07 | [leetcode-debrief](https://github.com/gkuchar/educational-agent-skills/blob/afbf3aeba794423c7b9ea91d774011284b23d2cf/leetcode-debrief/SKILL.md) | 加载成功 | 适合教学侧 | 算法题复盘，适合相应教学情境，不适合作为电商开发默认能力。 |
| S08 | [socratic-coding-tutor](https://github.com/faramirezs/socratic-coding-tutor/blob/2ab16fac5ee73bc0c40e1879626647049531e1fe/skills/zettelkasten-socratic-tutor/SKILL.md) | 加载成功 | 改入口后可加载 | 原仓库是套件；定位到zettelkasten-socratic-tutor，依赖其知识/记忆工作流，优先Teaching而非Coding。 |
| S09 | [python-tutor-skill](https://github.com/Mainloop-AI/python-tutor-skill) | 无标准入口 | 需要重新封装 | 当前固定版本没有SKILL.md；是Python教学课程/系统资料，不能当成已可独立安装的Skill。 |
| S10 | [brainstorming](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/brainstorming/SKILL.md) | 加载成功 | 规划阶段试用 | 保留需求澄清和方案比较；额外设计审批及writing-plans依赖需适配，不能覆盖已明确的学生授权。 |
| S11 | [writing-plans](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/writing-plans/SKILL.md) | 加载成功 | 规划阶段试用 | 任务、文件与验收拆分有参考价值；Git、子代理及后续执行Skill流程不能直接照搬。 |
| S12 | [grill-me](https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/productivity/grill-me/SKILL.md) | 加载成功 | 依赖未补齐 | 正文仅转调用grilling，是包装入口；加载它不等于加载了真正的访谈方法。 |
| S13 | [grill-with-docs](https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/engineering/grill-with-docs/SKILL.md) | 加载成功 | 依赖未补齐 | 正文要求调用grilling和domain-modeling；需补对应依赖或直接选实际方法。 |
| S14 | [to-spec](https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/engineering/to-spec/SKILL.md) | 加载成功 | 需适配发布动作 | 会把规格发布到项目工单系统；可取本地规格整理，不能默认发布或要求安装作者整套工作流。 |
| S15 | [to-tickets](https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/engineering/to-tickets/SKILL.md) | 加载成功 | 拆任务时试用 | 纵向切片、依赖与验收有价值；创建外部工单动作应改成本地计划，再由学生决定。 |
| S16 | [requirements-clarity](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/requirements-clarity/SKILL.md) | 加载成功 | 需去除硬性门槛 | 需求评分到90分才继续的循环与当前自然开发容易冲突；可借鉴Why/Simpler，不能当学生分数或发送门槛。 |
| S17 | [gepetto](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/gepetto/SKILL.md) | 加载成功 | 完整流程暂不适合 | 多LLM审查、访谈和编排较重，当前没有所需工具；先取局部规划方法，不启用整套流程。 |
| S18 | [Feature Forge](https://github.com/Jeffallan/claude-skills/blob/078a25cc5bfd8011459be7b91d004e900c1d02d3/skills/feature-forge/SKILL.md) | 加载成功 | 功能规划时试用 | 适合明确功能、规格和验收；只在需要设计功能时触发，先核对其额外代理约定。 |
| S19 | [The Fool](https://github.com/Jeffallan/claude-skills/blob/078a25cc5bfd8011459be7b91d004e900c1d02d3/skills/the-fool/SKILL.md) | 加载成功 | 方案审查时试用 | 反向质疑和挑战假设适合设计评审，不宜让每次小修改都进入辩论。 |
| S20 | [Product Manager Toolkit](https://github.com/alirezarezvani/claude-skills/blob/08cd8a9fc86cc370e2c0d448e8171fbcfdbc5a30/product-team/skills/product-manager-toolkit/SKILL.md) | 加载成功 | 产品工作储备 | 偏产品分析与优先级，工具脚本需单独验证；不作为Coding实现基线。 |
| S21 | [doc-coauthoring](https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/doc-coauthoring/SKILL.md) | 加载成功 | 写文档时试用 | 适合共写需求/设计文档；文档协作流程不能阻塞普通代码执行。 |
| S22 | [mermaid-diagrams](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/mermaid-diagrams/SKILL.md) | 加载成功 | 需适配展示 | 能指导Mermaid文本，但当前教学导图是受限结构；需要单独渲染/校验，不能宣称页面已支持其所有图形。 |
| S23 | [c4-architecture](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/c4-architecture/SKILL.md) | 加载成功 | 架构文档时试用 | C4适合较大项目关系说明；图形查看和架构事实需核验，不强加给小改动。 |
| S24 | [draw-io](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/draw-io/SKILL.md) | 加载成功 | 需图形工具适配 | draw.io编辑/导出涉及工具链；当前可以保存文件，不等于具备图形渲染与验收。 |
| S25 | [excalidraw](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/excalidraw/SKILL.md) | 加载成功 | 需图形工具适配 | Excalidraw流程及其专用工具需核对；先限制为文档方法，不默认引入MCP/子代理。 |
| S26 | [database-schema-designer](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/database-schema-designer/SKILL.md) | 加载成功 | 数据库设计时试用 | 适合DDL、索引和模型讨论；没有数据库执行工具，不能把设计建议当成迁移成功或性能已验证。 |
| S27 | [frontend-to-backend-requirements](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/frontend-to-backend-requirements/SKILL.md) | 加载成功 | 接口交接时试用 | 前端给后端的需求交接可用于新检查点协议；应映射现有字段，避免另起接口。 |
| S28 | [backend-to-frontend-handoff-docs](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/backend-to-frontend-handoff-docs/SKILL.md) | 加载成功 | 接口交接时试用 | 后端给前端的契约材料有针对性；需要绑定当前代码/接口版本。 |
| S29 | [Architecture Designer](https://github.com/Jeffallan/claude-skills/blob/078a25cc5bfd8011459be7b91d004e900c1d02d3/skills/architecture-designer/SKILL.md) | 加载成功 | 架构阶段试用 | 适合大项目架构设计，不适合作为三行修复的固定前置流程。 |
| S30 | [API Designer](https://github.com/Jeffallan/claude-skills/blob/078a25cc5bfd8011459be7b91d004e900c1d02d3/skills/api-designer/SKILL.md) | 加载成功 | API设计时试用 | 适合接口约束和文档设计；运行校验、契约测试仍需真实工具证据。 |
| S31 | [improve-codebase-architecture](https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/engineering/improve-codebase-architecture/SKILL.md) | 加载成功 | 重构任务时试用 | 架构改进要有明确授权与行为回归，不能凭Skill自动扩大到整个项目重写。 |
| S32 | [systematic-debugging](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging/SKILL.md) | 加载成功 | 优先小范围试用 | 先根因再修复符合当前问题；复现/验证依赖执行证据，文件模式下只能诚实给出待执行检查。 |
| S33 | [verification-before-completion](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/verification-before-completion/SKILL.md) | 加载成功 | 优先小范围试用 | 有助于区分完成说明和验证证据；当前不能运行命令，必须标注未验证，不能假装完整执行此方法。 |
| S34 | [test-driven-development](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/test-driven-development/SKILL.md) | 加载成功 | 补执行工具后再测 | 真正TDD需要实际红灯→绿灯→回归；只读写代码不能证明TDD流程完成。 |
| S35 | [requesting-code-review](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/requesting-code-review/SKILL.md) | 加载成功 | 需审查代理适配 | 原方法涉及独立审查代理及Git信息，当前工具未提供；可映射现有Teaching审查，但不是原样即用。 |
| S36 | [receiving-code-review](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/receiving-code-review/SKILL.md) | 加载成功 | 收到审查意见时试用 | 先核验意见再修改有针对性；仍需确认当前代码和回归证据。 |
| S37 | [diagnosing-bugs](https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/engineering/diagnosing-bugs/SKILL.md) | 加载成功 | 需调试工具适配 | 适合复杂诊断，但命令、浏览器或外部工作流能力不能由Skill文字自行获得。 |
| S38 | [qa-test-planner](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/qa-test-planner/SKILL.md) | 加载成功 | 优先小范围试用 | 正常、边界、回归及预期/实际记录适配当前工作台；Figma等专项集成只在工具可用时采用。 |
| S39 | [webapp-testing](https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/webapp-testing/SKILL.md) | 加载成功 | 补浏览器/执行后再测 | 依赖Playwright、服务启动和实际浏览器操作；当前不能完成完整行为验收。 |
| S40 | [Test Master](https://github.com/Jeffallan/claude-skills/blob/078a25cc5bfd8011459be7b91d004e900c1d02d3/skills/test-master/SKILL.md) | 加载成功 | 补测试执行后再测 | 测试设计部分可借鉴，完整测试工作流需要运行器、环境和真实结果。 |
| S41 | [Code Reviewer](https://github.com/Jeffallan/claude-skills/blob/078a25cc5bfd8011459be7b91d004e900c1d02d3/skills/code-reviewer/SKILL.md) | 加载成功 | 代码审查时试用 | 源码审查适合只读任务；问题需有对应代码依据，不把静态审查当行为通过。 |
| S42 | [audit-context-building](https://github.com/trailofbits/skills/blob/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/audit-context-building/skills/audit-context-building/SKILL.md) | 加载成功 | 安全审查专用 | 偏深入上下文收集/安全审计，成本与目标不同，不作为每轮教学或普通开发前置。 |
| S43 | [differential-review](https://github.com/trailofbits/skills/blob/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/differential-review/skills/differential-review/SKILL.md) | 加载成功 | 需差异/历史适配 | 差异审查依赖Git历史及上下文；当前隔离目录不是原仓库，要显式提供版本化diff而非假装有Git历史。 |
| S44 | [requirement-elicitation](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/requirement-elicitation/SKILL.md) | 加载成功 | 需求不明确时试用 | 和S10/S16重叠；只在关键需求缺失时触发，不重复问已提供信息。 |
| S45 | [context-aware-questions](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/context-aware-questions/SKILL.md) | 加载成功 | 上下文缺口时试用 | 先利用已有材料再追问可减少摩擦；读取范围仍是当前项目。 |
| S46 | [idea-to-design](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/idea-to-design/SKILL.md) | 加载成功 | 从想法到设计时试用 | 适合早期设计说明；可写本地文档，不能自动扩展为发布或执行整个项目。 |
| S47 | [writing-product-specs](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/writing-product-specs/SKILL.md) | 加载成功 | 规格文档时试用 | 适合用户/约束/验收整理；不是直接的代码实现增强。 |
| S48 | [writing-user-stories](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/writing-user-stories/SKILL.md) | 加载成功 | 验收场景时试用 | 用户故事和Given–When–Then可帮助写验收条件，不代表已执行测试。 |
| S49 | [project-planning](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/project-planning/SKILL.md) | 加载成功 | 大任务规划时试用 | 流程较全面，和其他规划Skill重叠；先选一项对照，避免叠加成复杂工作流。 |
| S50 | [issue-decomposition](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/issue-decomposition/SKILL.md) | 加载成功 | 拆任务时试用 | 带工单及估点语义，建议映射本地阶段/依赖；外部发布需另行授权。 |
| S51 | [dependency-mapping](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/dependency-mapping/SKILL.md) | 加载成功 | 依赖复杂时试用 | 可用于解释开发顺序和关键依赖，简单任务不必额外画依赖图。 |
| S52 | [timeline-planning](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/timeline-planning/SKILL.md) | 加载成功 | 时间规划时试用 | 甘特图和估时应标假设与不确定性，不把模型估时当承诺。 |
| S53 | [architecture-diagramming](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/architecture-diagramming/SKILL.md) | 加载成功 | 架构图时试用 | 组件和数据流图适合较大项目，图形渲染及代码一致性需额外验证。 |
| S54 | [writing-verification-plans](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/writing-verification-plans/SKILL.md) | 加载成功 | 验收规划时试用 | 可对接人工操作/预期/实际/版本记录；编写计划不等于测试通过。 |
| S55 | [project-analysis](https://github.com/britt/agent-skills/blob/a048db47b7c92d921e4f3ab7583eca530d645e3a/skills/project-analysis/SKILL.md) | 加载成功 | 接手代码时试用 | 项目结构、入口和依赖分析适合接续；引用应以实际读取的当前文件为准。 |
| S56 | [frontend-design](https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/frontend-design/SKILL.md) | 加载成功 | 优先小范围试用 | 适合生成界面及视觉层级；已有主题和用户风格优先，不能自行整站换皮；视觉收益仍需真实浏览器检查。 |
| S57 | [web-artifacts-builder](https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/web-artifacts-builder/SKILL.md) | 加载成功 | 补构建链后再测 | 初始化和打包脚本依赖Shell/依赖安装，当前完整产物流程不能直接运行。 |
| S58 | [vercel-react-best-practices](https://github.com/vercel-labs/agent-skills/blob/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/react-best-practices/SKILL.md) | 加载成功 | React/Next项目再启用 | 技术栈专用规则；不是原生JS通用优化，需按具体版本/规则资源加载。 |
| S59 | [vercel-composition-patterns](https://github.com/vercel-labs/agent-skills/blob/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/composition-patterns/SKILL.md) | 加载成功 | React组件项目再启用 | 组件组合方法依赖React场景，不应用于所有原生DOM代码。 |
| S60 | [web-design-guidelines](https://github.com/vercel-labs/agent-skills/blob/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/web-design-guidelines/SKILL.md) | 加载成功 | 需联网规则适配 | 原文要求每轮WebFetch最新规则；当前无此工具，可改为固定版本规则快照，但不是原流程全量可用。 |
| S61 | [planning-with-files](https://github.com/OthmanAdi/planning-with-files/blob/51bf62def62d1cb317d37936929b4ef97cf862c3/skills/planning-with-files/SKILL.md) | 加载成功 | 需记忆与宿主适配 | 包含Claude Code hooks、loop/goal、脚本与文件状态；不能直接替代SQLite和teaching.course。 |
| S62 | [lesson-learned](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/lesson-learned/SKILL.md) | 加载成功 | 复盘时适配 | 需要Git历史/diff，当前应注入任务changes等版本化证据；生成经验仍须审核。 |
| S63 | [session-handoff](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/session-handoff/SKILL.md) | 加载成功 | 交接时适配 | 交接摘要需映射已有课程接续，不新建冲突状态源、不改写原始学生证据。 |
| S64 | [ship-learn-next](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/ship-learn-next/SKILL.md) | 加载成功 | 练习迁移时适配 | 下一轮练习适合教学或学习规划，不能自动当掌握证明、安装能力或触发发布。 |
| S65 | [skill-judge](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/skill-judge/SKILL.md) | 加载成功 | 维护者评审工具 | 用于审查Skill结构与触发，不是Coding能力本身；结构得分不能替代真实A/B效果。 |

## 版本、资源与授权记录

[catalog.json](catalog.json)给出逐项commit、入口、原始SHA256、适配判断；[native-load-results.json](native-load-results.json)给出加载回执；[live-status.json](live-status.json)记录脱敏的认证阻塞。完整源码/附属资料和原始工具事件只保存在本机`data/skill-lab/20261113`，不混入学生学习证据，不随源码包发布。
许可证按具体文件核对。例如S56正文指向的LICENSE.txt为Apache-2.0，不能按旧清单的整库概括处理；未核完的授权不视为可以公开分发。当前只做本机实验和来源引用。

参考：[OpenCode Skill机制](https://opencode.ai/docs/skills/)、[SiliconFlow Chat接口](https://docs.siliconflow.cn/docs/api/chat-completions-post)、[阿里云错误说明](https://help.aliyun.com/zh/model-studio/error-code)。
