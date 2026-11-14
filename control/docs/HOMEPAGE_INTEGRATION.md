# 首页风格融合（2026-11-15）

交接包 Control-homepage-frontend-changes.zip 含 frontend/app.js、frontend/style.css 和一份合并说明。仅采用 showProjectHome 的首页布局与样式增量，没有覆盖交接包旧业务代码。

首页采用星空视差、Control 控制舱开场、最近项目、搜索/阶段分类、项目卡片及分段进度；支持减少动画偏好。当前顶部按钮保持原样，首页增加经验库入口。卡片更多菜单保留重命名和查看教学记录，以现有共享经验库替代旧的手工选择教法入口。

仅修改 frontend/app.js 的 showProjectHome，frontend/style.css 追加首页作用域样式，frontend/index.html 更新资源缓存版本。非首页 JavaScript 与操作前备份逐字一致；后端、执行流程、模型配置和用户数据未修改。样式仅匹配 #project-home 或 body.home-open。

操作前备份：`C:\Users\十三月\Desktop\coding agent\00-Control-最新版本\control\tmp\homepage-20261115-033122/backup`。

验证：node --check frontend/app.js；python -X utf8 scripts/verify_homepage.py。后者复用共享经验库隔离测试，使用临时 SQLite、真实 Chromium、模拟模型，不产生账户调用。覆盖命名/空名连续编号、首页搜索、重命名、教学记录、继续学习、经验矩阵折叠/排序/来源改名同步/评分证据/撤销；桌面 1440×1000 三列及 390×844 单列、无横向溢出。截图及 JSON 在 tmp/homepage-verification。

本地服务继续使用 http://127.0.0.1:8772 ，未重启。刷新页面即可加载新前端。

全量 unittest：285 项，2 failures、5 errors、1 skipped，未全绿。失败涉及后端旧 settings 测试被当前主机配置策略返回 403、教学工具请求形状、后台经验及知识设置；本次未更改后端。首页专项 32 项全部通过、无浏览器运行异常。

## 飞船卡片与新建窗口复位
所有项目（含新建入口）统一 376px 高、等宽网格；固定两行标题区域，使用同尺寸飞船船体、舷窗、翼板及推进光。新建仓库成功进入后调用当前 Coding 窗口复位按钮，恢复默认位置/尺寸及展开状态；现有项目的自由拖动保留。专项浏览器 35 项通过，包含移动并收起后新建复位、桌面及窄屏所有卡片等尺寸。

## 圆润探索飞船（替代多边形裁切版）
重新绘制原生 SVG：连续曲线船体、玻璃驾驶舱、后掠侧翼、双引擎及尾焰，实际 HTML 标题/状态/进度/菜单置于中央舱内。所有历史卡片等宽、420px 高。上方长条改为开启新项目，下方移除新建卡片，最近打开项目置顶并标记，其余按更新时间排序。桌面及390px窄屏截图已检查；新建后 Coding 默认位置复位保留。造型参考：https://www.czepeku.com/store/product/rapid-deployment-fighter ，页面使用自行绘制的矢量造型，不依赖远程图片。

## 恢复方框卡片（当前最终样式）
按用户要求撤除飞船 SVG 和相关样式，恢复统一326px高的矩形项目卡片；保留顶部开启新项目、下方历史项目及最近项目置顶。移除代码工具栏版本与回退按钮及对应绑定；版本数据和后端保留。新建时Coding复位保持。专项浏览器检查通过。
