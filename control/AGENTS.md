# 接手开发说明

## 先确认当前做到哪一步

这是可运行的本地教学原型，不是已经完成的双 Agent 自进化系统。

- **Teaching 已有真实模型适配器**：DeepSeek Chat Completions与OpenAI Responses API、工具调用、JSON 输出校验；是否真实调用由 `teaching_provider.mode` 判断。
- **Coding 是示例**：`agents/coding.py` 按步骤写固定待办代码；需求草稿也来自固定 `PLAN`。用户任意修改计划不会让它理解新计划。
- **进化有基础接口，未证明效果**：已接五项能力观察、个人经验草稿/确认/停用、候选Skill映射与申请。没有Skill安装、自动加分或Coding能力对照。固定Coding仅记录经验输入，不能宣称它已学会。
- 已有 53 项自动测试，使用临时数据和模拟响应；没有证明长期教学有效或模型能力稳定提升。

先读 README 和 docs/API.md，再改代码；不要参考已移除旧版的接口设想。不要把未实现功能写成已实现。

## 代码职责与真实调用链

| 位置 | 负责什么 | 输入 → 输出 |
|---|---|---|
| `frontend/app.js` | 发动作请求、展示状态、轮询教师任务 | 用户操作 → API；任务快照 → 页面 |
| `backend.py` 的 Handler | 校验确认、串行更新同一任务、调用两类 Agent | JSON 请求 → 任务快照或错误 |
| `agents/coding.py` 的 SampleCodingAgent.step | 按示例步骤写文件，追加 changes | 任务字典、确认指令 → 回复字符串；会修改项目与 changes |
| `backend.py` 的 start_teaching | 保存学生消息后的后台教学任务 | 任务、动作 → 后台线程；立即由接口返回 202 |
| `agents/teaching.py` 的 context / TeachingAgent.respond / validate / run | 组织材料、调用模型、检查结果、更新教学记录 | 任务和动作 → 回复文本；在工作副本中更新 teaching |
| `backend.py` 的 save / load | 当前任务 JSON 与教学历史归档 | 任务字典 ↔ SQLite |
| `backend.py` 的 PreviewHandler | 独立来源的静态项目预览 | 三个允许文件 → 浏览器 HTML/CSS/JS |

教师调用链：接口先保存学生原话 → `start_teaching` 拷贝上下文 → 后台读源码 → `context` → 模型及只读工具 → `validate` → 更新课程记录 → 重新读取最新任务并合并结果。前端约每 900ms GET 一次任务，完成后展示回复。当前没有 SSE 或逐字流式输出。

执行链：学生确认 → `expected_step` 必须为当前整数步骤 → `CODING.step` → 写文件并记录前后代码 → 步骤加一 → 自动发起教师审查 → 停下等待下次确认。暂停是每次请求只执行一步，不是暂停一个持续运行的自治 Agent。

## 教师如何保持一整门教程

提示词在 `agents/teaching_assets/system.md`；5份教学方法在同目录的 `skills/*/SKILL.md`。这是应用材料，不是给当前 Codex 安装的技能；修改时无需安装。

`teaching.course` 保存总体目标、目标证据、接续摘要、下一次接着做什么、检查点和技术选学偏好。每轮结合选中的近期两侧原话、当前Coding提示词、分段旧摘要、计划、带行号源码、最近改动摘要和运行观察，自选追问、提示、讲解、总结、迁移或评价；关注点标签不是强制关卡。

常用 Skill 正文预载，其他方法由工具读取。工具仅能读取登记的教学方法、当前三个文件、已整理参考资料和任务记录。教师不能执行代码、改文件、调用 Coding 或安装能力。

`LESSON`、`KNOWLEDGE`、`COURSE_OBJECTIVES` 仍在 `agents/teaching.py`，与待办示例绑定；扩展第二个项目时应先抽出案例配置，再统一调整前端主题、文件白名单和验证规则。当前引用资料是整理后的 MDN 摘要，不是联网检索系统。

## 不能破坏的规则

1. 学生原话先保存；不因模型失败丢作答，也不在真实模型失败后偷偷切 sample。
2. 计划和代码执行需要学生明确确认；教师不能自行代替学生确认。
3. 当前同任务修改串行；不要移除 `task_lock` 或运行中检查来“支持并发”。要改并发，先设计冲突处理。
4. 后台不能 `save(work)` 整块覆盖旧快照。进度只更新运行字段；结束核对任务编号、记录和源码，过期则拒绝采用。
5. 源码引用必须是对应行的完整代码行。无效学生引用保留普通教学回复，降级掌握建议并记录警告；不要改成所有回复都丢弃。
6. 普通聊天不能自动当迁移作答；candidate 只是待复核，不是学会证明。不自动加分或升级。
7. 密钥只放进进程环境；不入库、日志、前端持久化或压缩包。不要扫描本机其他软件凭据。
8. 静态标记检查、学生自述、浏览器 ready/error 都不是通过行为测试；教师没有运行工具，不得声称运行过。
9. 模型文本不作为 HTML 执行；思维导图只用受限结构渲染。保持预览独立来源与 iframe 约束。

## 数据和故障处理

- `data/workbench/records.sqlite3`：tasks 表保存任务 JSON；teaching_history 表保留较早教学轮次、检查点和目标观察。
- `data/workbench/<UUID>/project/`：真实项目文件，不是数据库内虚拟代码。不要删除组员本机 data 来修功能。
- 任务内保留最近20轮教学、40个检查点、每目标20条观察；模型上下文进一步缩短。完整聊天与代码改动仍在任务 JSON，长期规模扩展尚未解决。新增learning_versions表保存记忆和学习记录的不可覆盖版本；消息独立表和分页尚未迁移。
- 同一进程每任务独立锁，不是支持多进程的数据库并发设计；文件和 SQLite 也没有跨资源事务。
- 模型一轮最多5次请求，工具/格式修正/429与5xx重试共用预算。每次调用最多重试2次，30秒单次超时，120秒整轮预算；连接失败不会全部自动重试。
- 文件先临时写入再替换；异常返回 JSON。服务重启把遗留 queued/running 标为 failed；不自动续跑。
- 主端口默认8772；预览优先8773，被占用则选空闲端口，使用快照的 preview_url，前端不要写死。

## 建议怎么分工接下去

| 同学 | 优先工作 | 与谁先对齐 |
|---|---|---|
| A：Coding 接入 | 用真实模型/现成 Agent 替换示例；先实现一次计划、一次代码修改、完成即停 | D 确认异步执行结果和错误格式；C 确认教学拿到哪些材料 |
| B：案例与能力改进 | 整理可查证的错误案例、验证办法；设计经验或 Skill 的启用/禁用、版本与撤回 | A 确认加载和测试方式；C 确认证据与升级申请结构 |
| C：Teaching | 优化已有提示词、Skill、资料和真实模型实验；检查是否讲清原理、是否泄露答案、是否过早判断掌握 | A 看真实代码与日志；B 对齐案例来源；D 对齐展示字段 |
| D：页面与整合 | 保持接口与任务流程一致，先提供可替换适配器入口，再接 A/B/C | 先让各方用同一快照与请求字段，避免各写一套 |

这些是扩展建议，不是已完成承诺。不要直接将系统改造成复杂工作流平台；先跑通真实 Coding 的一个步骤，再扩展多案例和可撤回能力改进。

## 修改后怎么验证

在 control 根目录：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node --check frontend/app.js
python -X utf8 backend.py --port 8772
```

Node 只用于可选语法检查，运行不依赖 Node。至少手动检查：空白计划起点、确认后执行一步、保存并刷新恢复、网页预览、教师正常/失败回复、跳过技术选学。真实教学质量需要本机配置密钥后人工核对，不能用 mock 测试通过代替。

打包运行 `python scripts/package.py`。只发送源码压缩包，保留 data 在本机。

## 已接入的记忆与两条成长路线

先读docs/MEMORY_IMPLEMENTATION.md，再看原始设计docs/MEMORY_DESIGN.md。主程序使用agents/memory.py与learning.py，不依赖LangMem；SDK装在.venv-memory中，仅作对照实验，不随源码包发送。

- memory.prepare把较旧消息按连续区间分批交给真实模型整理，一次最多两批；摘要、源区间和摘要前原文哈希都保留。成功批次即使后面的教学回复失败也可以保存；过期任务仍不得合并。
- context保留当前Coding提示词和学生问题原文，额外原话有字符预算，不再重复塞80条学生发言；初始context上限80000 JSON字符，不是token上限。工具追加内容另受读取预算约束。较旧摘要每轮最多4段，其余需回查原话；未整理且未加载的数量明确提供。
- learning_update可产生observations、experiences、prompt_review。无效学习引用只丢本轮学习更新并记录warning，保留普通教学回复。观察一律model_suggestion，不认证独立掌握。
- experiences先draft；学生确认后按当前指令的标签匹配，最多3条进入Coding输入；可停用/重新启用，保留前一版本。当前仅同任务，不是跨项目学生账户画像。
- catalog.json列5项能力、3个Superpowers候选及所需能力。学生多条独立/迁移表现可形成复核申请，但候选都not_evaluated，没有安装通道。真实Agent对照实验报告的导入和有效性审核尚未实现，不能手改字段伪装完成验证。
- learning_versions与tasks在同一事务提交；同一个记忆revision:学习revision不能换内容。改memory或learning必须推进相应revision。普通学生消息、代码改动、错误状态不属于这份记忆版本，仍由原任务记录保存。
- 不删除或重排messages。当前证据ID仍为原数组下标，不要为迁移存储改掉旧证据。
- 没有通用记忆纠错/恢复接口、观察人工审核界面或跨项目检索；经验停用不等于完整记忆回滚。

本轮实验：docs/experiments/memory-offline.json、langmem-sdk.json、memory-live-recovery.json及memory-live-learning.json。含真实模型的小样本实验只使用合成对话，不代表真实学生评估。

复现离线流程：python scripts/verify_memory.py。真实实验：先在工作台连接模型，再运行python scripts/verify_memory_live.py；该脚本会新建测试项目和合成聊天，也会产生模型费用，不要在批量自动测试中默认执行。

可选SDK实验：python -m venv .venv-memory；使用uv pip install --python .venv-memory/Scripts/python.exe -r scripts/requirements-memory-experiment.txt安装已验证锁定版本；然后运行.venv-memory/Scripts/python.exe scripts/verify_langmem.py。该脚本使用固定模型回复，只验证SDK数据处理，不评价摘要质量。

## OpenAI提供商适配

agents/providers.py集中管理所选提供商的URL、密钥、请求格式和响应归一化。配置provider=openai，模型ID可填账户可用的值；UI地址固定到api.openai.com/v1/responses。DeepSeek地址独立，不能把OpenAI密钥发给DeepSeek。每个TeachingAgent在构造时固定配置快照，避免摘要和回复在中途切换提供商。

OpenAI使用store=false；函数调用和reasoning响应项在同轮后续请求中保留，工具结果按call_id关联。加密reasoning项只在当前模型工具循环的内存中使用，不放进学生记录、长期记忆或前端。JSON mode只约束JSON合法性，教学字段仍由validate检查。

OPENAI_API_KEY与TEACHING_MODEL可通过环境配置，或页面选择OpenAI；有多个服务商时显式设置TEACHING_PROVIDER。显式官方provider始终使用固定官方URL，不接受前端传入base_url。旧TEACHING_ENDPOINT用于未显式指定provider的兼容测试配置。

53项测试包含Responses格式、工具/推理项续传、摘要、密钥不落库、不串提供商和旧DeepSeek接口兼容。真实OpenAI账户API尚需用户配置后验证；不要将mock通过写成真实模型成功。
## 双向检查点接续

先读docs/CHECKPOINT_HANDOFF.md。agents/checkpoints.py登记coding.paused事件，agents/checkpoint_control.py处理学生确认的revise/resume、版本校验和幂等。checkpoint_id默认取Coding运行ID；多次修改通过root_checkpoint_id归属同一检查点族。最终恢复只接受一次；失败重试沿用原request_id和target_step，不能再次推进原阶段。

manual delivery可完全不调用Teaching Agent。Skill通知为教学端报告；实际启用和使用回执目前必须为false，不接受客户端传enabled/installed。Teaching失败不得改写已完成Coding状态。事件、操作、学生原话保存在任务JSON，启动恢复要同步标记操作失败，不能自动重放。

明确项目文件命令支持直接执行和后续返工；普通讨论仍只读。OpenCode配置只显式允许项目文件工具，Shell和外部网络仍被拒绝；不得把本次文件修复描述为已开放全部执行权限。文件写入失败尝试回滚，本地data不清理。verify_opencode_write.py使用真实CLI及本机模拟服务，不是实际模型质量验收。

通用项目文件接续：已移除扩展名/文件名白名单，任意项目内文件路径均可创建写入；文本与二进制分别保存和传输，binary_files快照只含元数据。明确开发授权在未确认计划时也进入可写执行，不将“执行/继续”静默降为只读。执行超时保持900秒；health.coding公开file_access=project_all_types、permission_revision=2和execution_timeout_seconds以核对运行版本。Shell和外部联网权限未改变。
