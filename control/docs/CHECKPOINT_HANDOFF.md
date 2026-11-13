# Coding / Teaching 双向检查点接口

本协议使用现有任务锁、后台 Coding 和任务 JSON。当前一个任务 UUID 就是一个 `session_id`。它不是多用户鉴权服务；`confirmed` 和 `teaching_completed` 是本机调用方的明确声明，不是已认证的学生身份或能力证明。

## 开发端暂停与教学端接收

Coding 成功保存本阶段或显式计划生成的结果后登记唯一检查点；失败、超时、过期候选和普通聊天不登记。事件至少包含 `session_id/checkpoint_id/stage/task_description/user_requirement/agent_output/project_evidence`，详见 [API](API.md#coding--teaching-检查点契约)。自动模式调用现有 Teaching 选择教学目标，后者失败不回滚已完成开发。

为了不连接 Teaching Agent 也能联调，新建任务时指定：

```json
{"coding_mode":"opencode", "checkpoint_delivery":"manual"}
```

默认是 `automatic`。manual 模式在每轮暂停后将事件标为 `delivery.status=available`，不调用 Teaching Agent；教学端通过下列只读 API 接收事件：

| 方法 | 路径 | 返回 |
|---|---|---|
| GET | `/api/tasks/:session_id/checkpoints` | 最近50个事件及总数 |
| GET | `/api/tasks/:session_id/checkpoints/:checkpoint_id` | 事件、其操作回执及关联的新检查点ID |
| GET | `/api/tasks/:session_id/project-file?path=src/main.js&start_line=1&limit=80&checkpoint_id=...` | 当前项目对应文件行、代码哈希及是否相对该检查点过期 |

代码由 Coding 产生候选、后端校验并写入学生项目。预览由后端独立来源提供，地址取任务快照 `preview_url`。浏览器负责上报观察；Teaching 只读材料，不执行项目代码。差异和源码片段有长度预算，完整修改前后文本仍在原始任务记录。`project-file` 每次最多120行、12000字符，路径必须属于当前任务已保存文件，不能读本机其他目录。

## 操作一：学生确认的修改要求

`POST /api/tasks/:session_id/checkpoints/:checkpoint_id/revise`

```json
{
  "session_id":"当前任务UUID",
  "request_id":"stable-revision-1",
  "confirmed":true,
  "expected_code_hash":"最新相关检查点的project_evidence.code_hash",
  "instruction":"学生已经确认的修改原话"
}
```

返回202及 `{operation, task}`。原话先保存，Coding 只修改当前阶段，不推进 `step`。完成后产生新的 `checkpoint_id`，通过 `root_checkpoint_id/previous_checkpoint_id` 与原检查点关联；回执的 `result_checkpoint_id` 指向本轮检查结果。

同一个根检查点可以多次 revise，每轮使用新 `request_id` 和最新代码哈希，等待上一轮结束。同一根或其任一修改结果检查点均可作为后续接口路径；最终恢复互斥状态共享。最终恢复后不再接受该阶段的新修改要求。

## 操作二：教学结束后允许继续

`POST /api/tasks/:session_id/checkpoints/:checkpoint_id/resume`

```json
{
  "session_id":"当前任务UUID",
  "request_id":"stable-resume-1",
  "confirmed":true,
  "teaching_completed":true,
  "expected_code_hash":"最新相关检查点代码哈希",
  "instruction":"可选：学生确认的下一阶段补充要求",
  "skill_unlocks":[
    {"skill_id":"systematic-debugging", "assessment_id":"assessment-result-1", "unlocked":true}
  ]
}
```

服务端在任务锁内接受当前阶段一次，并保存 `resume_request_id`，随后仅执行已确认计划的下一阶段；完成后再次暂停并产生新检查点。最后一个阶段恢复时返回200、`outcome=development_finished`，不启动多余 Coding。其他情况首次接受返回202。

同一检查点族的最终恢复只生效一次。相同 `request_id` 与相同内容的重复请求返回200和原回执（即使原任务仍运行），不再执行；复用ID但更换内容或换新ID再次恢复返回400。

## 暂停、错误和重试约定

| 问题 | 当前约定 |
|---|---|
| Coding 是否有进程一直等待？ | 没有。CLI 轮次结束退出，任务和文件持久化为暂停状态；恢复会启动新的隔离调用。 |
| 修改次数与反馈？ | 一个根检查点可有多轮 revise；每轮成功都返回新检查点和版本证据。 |
| Teaching 失败？ | 保存事件、学生原话和 Coding 成果，独立记录 `teaching_run` 及 `delivery` 失败；自动模式可主动审查重试。manual 模式由外部教学端决定何时继续。 |
| HTTP 超时但未收到回执？ | 用同一ID和同一内容重发，返回已有回执。不要随意生成新ID重复执行。 |
| Coding 失败或服务重启？ | 操作记为 failed，不自动重放；同请求增加 `retry:true` 显式重试。resume 只重试原目标阶段，不再次接受或推进原阶段。 |
| 重试前代码或阶段变了？ | 拒绝重试，要求核对当前源码；不把旧指令直接用于新版本。 |
| 文件和数据库一致性？ | 文件写入失败尝试恢复本轮文件；仍没有跨文件与SQLite事务，强制退出需核对。 |

## Skill 通知、启用与使用回执

通知只接受登记的 `skill_id` 和考核结果ID，不接受客户端直接设置 `enabled/installed`。通知会传给 Coding 输入，并在操作及 `coding_run.skill_results` 中保存真实回执。

**当前尚无经审核 Skill 安装、绑定和实际加载确认通道。** 因此回执为 `notification_status=received`、`activation_status=unsupported`、`enabled=false`、`used=false`。它只表示收到了教学端报告，不认证通过考核，不改变学生分数或现有解锁申请。已启用/已使用记录必须来自未来实际加载器和工具证据，不能由模型文本或调用方字段伪造。本次实现没有假装安装候选 Skill。

## 文件操作与执行权限

明确的“创建 src/main.js”“写入JS文件”“按计划创建文件”等请求进入可写执行，而不会因为包含“计划”或未命中旧关键词而悄悄进入只读讨论。有已确认计划时限制在当前阶段；明确的独立代码文件命令本身登记为学生提供并授权的单步任务。普通产品需求和“如何创建”“先讨论”“不要写”等仍按讨论处理。

执行阶段显式允许项目文件读取、创建、编辑、补丁、重命名和删除。新增常用脚本、SQL、前端组件及项目配置文件类型；依赖目录、凭据文件及工作区外路径不进入项目材料。仍只提交受支持的UTF-8文本文件，不声称支持二进制资源管理。计划和讨论保持只读，执行器也核对只读轮次前后文件必须相同。

执行默认上限从180秒调整为900秒，讨论/计划仍为180秒；可用 `CONTROL_CODING_TIMEOUT_SECONDS` 在30–3600秒内配置。超时仍不自动提交候选修改；检查点操作保留失败及重试状态。

Shell、外部联网和全部工具通配放开的方案被自动审批拒绝，未应用。后续如获得明确授权，可单独开放当前项目的依赖安装、构建/测试命令与依赖下载/文档访问；不需要同时开放系统目录、账户凭据或自动安装未验证 Skill。

权限行为参考已锁定 [OpenCode 1.18.34 CLI](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/cli/cmd/run.ts) 和 [官方工具文档](https://opencode.ai/docs/tools/)。已用项目实际CLI的 `debug config --pure` 在全新临时配置中核对配置加载，不使用用户全局配置。

## 本阶段验收

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node --check frontend/app.js
# 可选：需要已安装项目自带OpenCode；不需要真实模型或密钥
python scripts/verify_opencode_write.py
```

`test_http_pause_receive_resume_continue_without_teaching` 使用真实本机HTTP、Handler、SQLite、项目文件和后台线程，模拟 Coding transport，完全不调用 Teaching Agent，验证暂停 → 教学端读取事件 → 恢复 → 下一阶段暂停，以及重复恢复不再执行。其他用例覆盖多次修改、失败重试、并发重复、版本/会话隔离和Skill未启用回执。

`verify_opencode_write.py` 使用真实 OpenCode 1.18.34 和本机模拟 Chat Completions 服务，验证真实 write 工具创建 `src/main.js` 并返回文件。不调用收费模型，不读取现有模型密钥，不修改学生项目。这些验证不代替真实模型质量、浏览器行为或完整依赖构建验收。
