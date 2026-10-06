# 智能发票报销审核系统

以 **OCR 自动识别**替代手工录入、以 **规则化预审**统一审核口径的报销审核系统，构建"机器预审 + 人工终审"的人机协同流程。

**本期核心目标**

1. **自动填单** —— 批量上传发票影像 → OCR 提取字段 → 自动填入报销单，人工只做确认与修正
2. **规则拦截** —— 提交时硬拦截重复报销与金额不符，预警抬头错误与预算超标
3. **全程留痕** —— 字段修改痕迹与审核决策轨迹全程可追溯

---

## 技术栈

| 层 | 技术 |
| :--- | :--- |
| 前端 | Vue 3 + Element Plus + Pinia + Vue Router + Vite |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 + PyMySQL |
| 鉴权 | PyJWT 双令牌（HttpOnly Cookie）+ CSRF 双提交 + BCrypt |
| OCR | provider 开关：`mock`（默认）/ `paddle`（**真实本地引擎，已接入**，CPU 推理） |
| 数据库 | MySQL 8.0（utf8mb4，12 张表） |

---

## 快速开始

### 1. 环境要求

Python 3.10+、Node.js 18+、MySQL 8.0

### 2. 建库与配置

```sql
CREATE DATABASE IF NOT EXISTS invoice_system
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

复制 `backend/.env.example` 为 `backend/.env`，修改数据库账号密码（该文件不会入库）。

### 3. 安装依赖

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

cd ..\frontend
npm install
```

### 4. 建表并写入种子数据

```bash
cd backend
.venv\Scripts\python.exe scripts\init_db.py
```

### 5. 启动（两个终端）

```bash
# 终端 A：后端
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 B：前端
cd frontend
npx vite --port 5173 --strictPort
```

浏览器访问 **<http://localhost:5173>**（Vite 只监听 localhost）。

接口文档：<http://127.0.0.1:8000/docs> ｜ 健康检查：<http://127.0.0.1:8000/api/v1/health>

---

## 演示账号

密码统一 **`123456`**（仅本地演示用）

| 账号 | 角色 | 部门 |
| :--- | :--- | :--- |
| `employee` | 普通员工 | 研发部（单笔 5000 / 月度 50000） |
| `employee2` | 普通员工 | 研发部 |
| `finance` | 财务人员 | 财务部 |
| `admin` | 管理员 | 财务部 |

---

## 功能一览

**普通员工**：登录登出、批量上传发票（JPG/PNG，≤10MB）、OCR 自动填单、人工确认与修正（费用类别手选）、提交报销单（含预审拦截）、我的报销单（含驳回原因与重新提交）

**财务人员**：待办列表（按提交时间/金额/风险排序）、单据详情（影像 + OCR 字段与置信度）、通过/驳回（驳回必填原因）、审核轨迹查询

**管理员**：用户管理（含停用、重置密码、解锁）、部门维护（单笔/月度预算上限）、基础数据（角色权限码与菜单）

### 提交预审规则

| 规则 | 触发条件 | 处置 |
| :--- | :--- | :--- |
| 重复报销 | 同一发票已存在于审核中/已通过单据 | **硬拦截**，提示原单据号 |
| 红字发票 | 发票类型红字或金额为负 | 单独放行，不参与查重 |
| 金额勾稽 | \|不含税 + 税额 − 价税合计\| > 0.01 | **硬拦截**，给出算式 |
| 抬头核验 | 购买方名称/税号 ≠ 公司主体 | 预警（可提交） |
| 部门预算 | 月度累计将达 80% / 超 100% | 预警 / **硬拦截** |
| 部门预算 | 单笔超上限 | **硬拦截** |

### 报销单状态机

```
DRAFT（草稿/驳回后修改中） ──提交──> PENDING（待审核，发票进入占用态）
                                        │
                       财务通过 ────────┴──────── 财务驳回
                          │                          │
                    APPROVED（终态）          REJECTED ──重新提交──> 版本号 +1
```

---

## 验收与自测

```bash
cd backend

# 端到端验收：43 条断言，覆盖需求第六章 10 项验收标准（非幂等，先清库）
.venv\Scripts\python.exe scripts\init_db.py --drop
.venv\Scripts\python.exe scripts\e2e_check.py

# 一键演示：15 步 / 32 项校验，打印每步服务端返回，--reset 可先清库
.venv\Scripts\python.exe scripts\demo_flow.py

# 真实 OCR 相关（不需要真发票，脚本会自己合成票样）
.venv\Scripts\python.exe scripts\check_ocr_fields.py       # 字段提取层，50 条断言，秒级，无需装 paddleocr
.venv\Scripts\python.exe scripts\check_paddle_provider.py  # 真机识别（需装 paddleocr）
.venv\Scripts\python.exe scripts\check_paddle_provider.py --via-api  # 走上传接口（后端需在跑且 OCR_PROVIDER=paddle）

# 结构校验 / 清库重建
.venv\Scripts\python.exe scripts\check_db.py
.venv\Scripts\python.exe scripts\init_db.py --drop
```

前端：

```bash
cd frontend
npm run check     # SFC 静态校验（模板/脚本语法）
npm run build     # 生产构建 → dist/
npm run preview   # 生产预览（注意：未配 /api 代理，页面能开但接口不通）
```

> 后端验收脚本都要求后端已启动（默认 `127.0.0.1:8000`）。执行记录见 `验收记录.md`。

---

## 目录结构

```
发票系统/
├─ backend/                  # FastAPI 后端
│  ├─ .env.example           # 环境变量模板（复制为 .env）
│  ├─ app/
│  │  ├─ main.py             # 应用入口
│  │  ├─ api/deps.py         # 登录态 / CSRF / 权限码依赖
│  │  ├─ api/v1/             # auth, upload, invoices, reimb, review, admin, meta（34 条路径）
│  │  ├─ core/               # config, database, security, permissions
│  │  ├─ models/             # user, rbac, document（12 张表）
│  │  └─ services/           # auth, storage, preaudit, reimbursement, ocr（provider + 字段提取层）
│  ├─ scripts/               # init_db / check_db / e2e_check / demo_flow / check_ocr_fields / check_paddle_provider
│  └─ storage/uploads/       # 发票影像落盘（不入库）
└─ frontend/                 # Vue 3 前端
   ├─ vite.config.js         # 5173 dev 代理 /api 到 8000
   └─ src/
      ├─ api/index.js        # 统一请求层（自动注入 CSRF、透传拦截原因）
      ├─ router/index.js     # 路由与角色守卫
      ├─ stores/auth.js      # 登录态与菜单
      ├─ layout/             # 侧边菜单布局
      └─ views/              # 登录 / 员工 2 / 财务 2 / 管理员 3
```

---

## 文档索引

| 文档 | 作用 | 说明 |
| :--- | :--- | :--- |
| `提示词.md` | **需求规格基线** | 第三章角色功能、第四章数据模型、第五章非功能需求、第六章验收标准、第七章二期清单；只读 |
| `README.md` | 启动与功能总览（本文件） | 面向开发者与验收人 |
| `启动与使用文档.md` | 首次部署、日常启动、常见问题排查 | 含环境实测版本号 |
| `功能测试流程.md` | 人工回归清单 | 4 个演示账号逐页点击的核验步骤 |
| `项目报告.md` | **当前阶段报告** | 交付情况 + 未闭环项 + 后续排期，取代 `项目进度汇报.md` |
| `项目进度汇报.md` | 历史留档（S1 汇报） | 保留用于过程追溯 |
| `验收记录.md` | 自动化验收执行记录 | e2e / 演示 / 真实 OCR / 失败模式 的具体命令与结果 |

---

## 说明与限制

- **费用类别目前仅界面提示必填**：后端预审不校验类别，留空也能提交，与需求 3.1 第 4 项「费用类别必填」的字面要求
  仍有偏差（属未闭环项，见 `项目报告.md` §3.2）。
- **写接口未限流**：需求 5.2 要求写接口限流，当前未实现，只有登录「5 次错误锁定 15 分钟」。
- **OCR 有两种 provider，默认仍是 mock**：
  - `mock`（默认）：识别结果由图片哈希派生，稳定可复现，供联调与自动化验收使用，**不是真实识别**；
  - `paddle`：**真实本地 PaddleOCR**（CPU 推理），把 `.env` 的 `OCR_PROVIDER` 改为 `paddle` 即可启用。
    识别 10 个字段并各带置信度：`app/services/ocr/provider.py`（引擎）+ `app/services/ocr/invoice_fields.py`（关键词 + 正则提取层）。
    首次识别会自动下载检测/识别/方向分类三个中文模型（约 17 MB）到 `~/.paddleocr`，之后完全离线；
    离线部署可把现成模型目录填入 `PADDLE_OCR_DET_MODEL_DIR` / `PADDLE_OCR_REC_MODEL_DIR` / `PADDLE_OCR_CLS_MODEL_DIR`。
    实测（合成票样）：冷启动约 3.7 秒（含模型加载）、热态约 0.5 秒/张；**100 张真实票样的 P95 尚未测**。
    提取层是启发式的，正则未命中的字段会留空并标记「待人工确认」，绝不抛异常中断上传。
- **OCR 目前同步执行**：识别在请求线程内完成（引擎调用已加锁串行化），`ocr_task` 表与状态流转已就绪；
  生产部署应改为后台 Worker 进程池消费（需求 5.1）。
- **性能指标尚未全部实测**：真实引擎单张热态约 0.5 秒（合成票样），但需求 5.1 的「100 张样本 P95 ≤3 秒」
  与「批量 5 张 ≤30 秒」仍缺真实票样数据。
- **公司主体与部门预算为占位值**：需按实际业务写入 `COMPANY_NAME` / `COMPANY_TAX_NO` 与各部门上限。
- **本期仅支持 JPG/PNG**；PDF 发票、数据看板、消息通知、规则配置界面等属二期范围
  （`frontend` 已装 `echarts` 但暂无代码引用，二期做看板时可直接用）。
- **已知偏差**：`/auth/logout`、`/auth/refresh` 未做 CSRF 双提交校验（登录接口豁免是设计如此）。
  `SameSite=Lax` 已阻断跨站 POST 携带 Cookie，故本轮未加严；如需补齐请先评估老会话刷新失败的影响。
- **验收脚本需在清库后执行**：`scripts/e2e_check.py` 非幂等（固定发票号），请先 `scripts/init_db.py --drop`；
  执行记录见 `验收记录.md`。
- **安全提示**：演示密码与 `.env` 中的 `JWT_SECRET` 仅供开发使用，正式部署前必须更换；`.env` 与 `backend/storage/` 不应提交到仓库。
