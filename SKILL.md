---
name: search-payment-mcp
description: 检索指定支付公司（国内/国际，如汇付天下、易宝支付、Stripe、Adyen 等）发布的 MCP Server 或 Agent Skill。当用户询问某支付公司是否发布了 MCP/Skill 工具、或想调研某支付公司的 AI 智能体生态时触发。输出包含梯队分类的飞书云文档报告（第一梯队：公开可获取；第二梯队：仅限特定渠道；第三梯队：仅演示/概念）。
agent_created: true
---

# 检索支付公司 MCP/Skill

单公司调研工具：输入一家支付公司名称（国内或国际均可），检索该公司在所有相关平台上发布的 MCP Server 或 Agent Skill。

## 触发条件

当用户做出以下请求时使用本 skill：

- "XX支付公司有没有发布MCP/Skill？"
- "查一下XX公司的MCP/Skill情况"
- 给出一家公司名称，意图是了解其 MCP/Skill 生态

## 输入

唯一必填输入：**公司名称**（中文全称如"汇付天下"，或英文名如"Stripe"、"Adyen"）。可选附带品牌名、产品名或缩写以辅助关键词生成。

## 前置条件（一次性设置）

### GitHub Token（推荐）

GitHub 搜索需要认证。首次使用前，请告知用户完成以下设置：

1. 访问 https://github.com/settings/tokens 创建一个 Personal Access Token（仅需「公开仓库只读」权限，其他权限全部关闭）
2. 将 token 写入 skill 目录下的 `.github_token` 文件：

```bash
echo "ghp_xxxxxxxxxxxxxxxxxxxx" > ~/.workbuddy/skills/search-payment-mcp/.github_token
chmod 600 ~/.workbuddy/skills/search-payment-mcp/.github_token
```

设置一次后所有后续调用自动生效。脚本按以下顺序查找 token：
- 环境变量 `GITHUB_TOKEN` / `GH_TOKEN`
- Skill 目录下的 `.github_token` 文件
- 以上都没有 → 脚本返回认证错误

### PulseMCP API Key（可选）

PulseMCP 需要 API Key + Tenant ID。不配置则脚本自动跳过 PulseMCP。

1. 发送邮件至 `hello@pulsemcp.com` 申请 API Key 和 Tenant ID
2. 将凭证写入 skill 目录：

```bash
echo "<api_key>" > ~/.workbuddy/skills/search-payment-mcp/.pulsemcp_api_key
echo "<tenant_id>" > ~/.workbuddy/skills/search-payment-mcp/.pulsemcp_tenant_id
```

## 工作流

按顺序执行以下阶段，在阶段 10 完成时输出最终报告。

---

### 阶段 1：了解公司背景（按需）

如果对该公司不熟悉，或其产品/品牌名不确定，先做一轮快速搜索：

```
搜索: "公司全名 支付 业务 产品"
```

从搜索结果中提取：
- 中文全称和英文名
- 品牌名 / 产品名 / 平台名（如汇付天下的"斗拱"）
- 官方域名（如 huifu.com、yeepay.com）
- 常用缩写

对于知名公司（支付宝、微信支付、银联等），跳过此阶段。

---

### 阶段 2：动态生成搜索关键词

**不硬编码关键词**，每次根据策略动态生成：

| # | 生成策略 | 以汇付天下为例 |
|---|---------|---------------|
| 1 | 公司中文全名 + "MCP" | "汇付天下 MCP" |
| 2 | 公司品牌/产品名 + "MCP" | "斗拱 MCP" |
| 3 | 公司英文名 + "MCP server" | "huifu MCP server" |
| 4 | 公司名 + "skill" / "Agent Skill" / "智能体" | "汇付天下 skill" |
| 5 | 公司名 + "AI 开放平台" / "开放平台" | "汇付天下 AI 开放平台" |

总共生成 **3-5 组关键词**，覆盖最重要的名称变体。

关键规则：
- 中英文名称变体都要覆盖
- 如果公司有已知产品/平台品牌，必须纳入
- 如果对任何名称变体不确定，先执行阶段 1

---

### 阶段 3：检查公司自有开放平台

部分支付公司除了在第三方平台上发布外，还通过**自己的开放平台/开发者站点**提供 MCP/Skill 下载或文档入口。这些自有站点不会被 npm/PyPI/GitHub 等通用平台覆盖，必须主动探查。

**步骤 3a — 查阅已知入口：**

首先检查 `references/platforms.md` 第四节「官方开放平台」中是否已记录该公司的自有入口（如易宝 `open.yeepay.com/ai-connect`、银联 `mcp.yun.unionpay.com`）。如果有，直接用 WebFetch 读取页面内容，查找 MCP/Skill 下载链接、文档、接入指南等。

**步骤 3b — 搜索未知入口：**

如果 `references/platforms.md` 中没有该公司的记录，用 WebSearch 尝试发现：

```
搜索: "公司全名 开发者中心" OR "公司全名 开放平台" OR "公司英文名 developer platform" OR "公司英文名 open api"
```

或更直接的探索式搜索：
```
搜索: "公司全名 MCP server" OR "公司英文名 MCP"
```

**关注内容**：搜索结果中是否有指向该公司官方域名（通过阶段 1 确定的域名）下的页面，标题或描述中包含"MCP"、"Skill"、"Agent"、"开发者工具"等关键词。

**步骤 4c — 验证发现：**

对每个可能命中自有平台入口的页面：
1. 用 WebFetch 直接读取页面内容
2. 确认是否存在明确的 MCP Server 或 Agent Skill 下载/配置说明
3. 判断获取难度：是否公开可下载？需要注册登录？还是需要商务签约？

**输出**：记录公司自有平台 URL、发现的所有 MCP/Skill 名称、获取方式（公开/需注册/需签约），供阶段 7 梯队分类和阶段 10 报告使用。

---

### 阶段 4：检索代码仓库与 MCP 注册表（脚本）

使用内置脚本一次性搜索 npm、PyPI、GitHub、魔搭、mcp-cn.com、ClawHub、Smithery、Glama、PulseMCP。**不分国内外**，所有平台统一检索。

**步骤 4a — 执行搜索：**

将关键词 JSON 通过管道传入 `scripts/search_registries.py`：

```bash
echo '{"company":"公司全名","keywords":["关键词1","关键词2","关键词3"],"platforms":["npm","pypi","github","modelscope","mcpcn","clawhub","smithery","glama","pulsemcp"]}' \
  | python3 scripts/search_registries.py > /tmp/payment_mcp_raw.json
```

**PulseMCP 前置条件**（可选）：PulseMCP 需要 API Key + Tenant ID。如果未配置，脚本跳过 PulseMCP 并返回提示。配置方式见「前置条件」节。


**步骤 4b — 去重合并：**

```bash
cat /tmp/payment_mcp_raw.json | python3 scripts/merge_results.py > /tmp/payment_mcp_merged.json
```

**步骤 4c — 读取结果并提取关键字段：** 用 Read 工具读取 `/tmp/payment_mcp_merged.json`，提取每个候选项的：`name`（名称）、`url`（访问地址，已自动聚合为最优链接）、`description`（描述）、`source`（来源平台）、`platforms`（所有出现平台列表）。这些字段将用于阶段 7 归属验证和阶段 10 报告生成。

**步骤 4d — GitHub 认证检查：**

如果步骤 4c 的 GitHub 结果中包含认证错误（关键词：`not authenticated`、`未设置 GITHUB_TOKEN`），说明 token 尚未配置。**停止当前工作流**，引导用户完成一次性设置：

```
GitHub 搜索需要认证。请按以下步骤完成一次性设置：

1. 访问 https://github.com/settings/tokens 创建 Personal Access Token（仅需公开仓库只读权限）
2. 终端执行：
   echo "ghp_xxxxxxxxxxxxxxxxxxxx" > ~/.workbuddy/skills/search-payment-mcp/.github_token
   chmod 600 ~/.workbuddy/skills/search-payment-mcp/.github_token

设置完成后回复"好了"，我将继续检索。
```

token 文件是持久化的——设置一次后所有后续调用自动生效，不会再提示。

---

### 阶段 5：检索无 API 的垂直平台（WebSearch）

mcp-cn.com、ClawHub、Smithery、Glama、PulseMCP 已在阶段 4 通过脚本覆盖。以下平台无公开搜索 API，用 WebSearch 检索。

| 平台 | 搜索模式 |
|------|---------|
| 扣子 (Coze) | `"公司名 skill" OR "公司名 扣子"` |
| 腾讯元器 | `"公司名 腾讯元器" OR "公司名 MCP 元器"` |

对每个命中的结果，记录：平台名称、Skill/MCP 名称、发布者身份、**可访问 URL**、**描述/摘要**（用于阶段 10 简介生成）。

---

### 阶段 6：通用搜索引擎检索（WebSearch）

搜索新闻、官方公告和博客：

```
搜索: "公司全名 MCP" OR "公司全名 Agent Skill" OR "公司全名 AI agent 发布"
```

同时搜索英文变体：

```
搜索: "CompanyEnglishName MCP" OR "CompanyEnglishName model context protocol"
```

**止损条件**：本阶段最多搜索 3 组不同关键词。3 组无结果则标记"搜索引擎已穷尽"并继续。

---

### 阶段 7：归属验证

对阶段 3-6 找到的每个候选项，按以下优先级验证是否为**公司官方发布**：

1. **域名验证**（最强信号）：发布者邮箱域名 / 维护者邮箱 / 项目主页 URL / 仓库 URL 是否使用公司官方域名？
2. **命名验证**：包名/仓库名/Skill 名是否包含公司已知英文名或品牌名？
3. **内容验证**：描述/README/公告中是否明确出现"官方"字样并指明公司名称？
4. **交叉验证**：公司自己的新闻/博客中是否提到了该 MCP/Skill？

**"官方"的最低通过标准**：通过第 1 条（域名验证），或同时通过第 2+3 条。

全部不通过则为**第三方/社区**贡献，单独备注但不计入公司官方 MCP/Skill。

**步骤 7e — 穷举官方渠道（防漏）**：

关键词匹配可能遗漏用内部代号、缩写或非标准名称命名的 MCP/Skill。一旦确认某个渠道为官方，**不再依赖关键词，直接穷举该渠道全部内容**：

| 渠道类型 | 穷举方法 |
|---------|---------|
| GitHub 官方 org | `gh search repos --owner=<org> --limit=100 mcp` 列出 org 下所有相关仓库；再用 `gh repo list <org> --limit=200` 列出全部仓库，对每个仓库检查 README/description |
| npm scope（如 `@yeepay`） | `npm search @<scope>/ --json` 或访问 `https://registry.npmjs.org/-/v1/search?text=scope:<scope>` |
| PyPI maintainer | 访问 `https://pypi.org/user/<maintainer>/` 查看该用户所有包 |
| 魔搭 publisher | 搜索 publisher 名称的所有 MCP 条目 |
| mcp-cn.com creator | 搜索该 creator 的所有 MCP 条目 |
| ClawHub author | 搜索该 author 的所有 package |
| Smithery namespace | `GET /api.smithery.ai/servers?namespace=<namespace>` 列出该 org 所有服务器 |
| Glama namespace | 用 `query=<namespace>` 搜索同一 namespace 的全部 MCP 条目 |
| PulseMCP | 如果已配置 Key，搜索公司名全量拉取 |
| 官方自有平台 | 遍历平台页面上的全部 MCP/Skill 列表项 |

**穷举 vs 关键词的差异处理**：穷举可能发现新的 MCP/Skill（关键词没命中但确实存在）。如果穷举发现了**关键词阶段未命中的条目**，在输出报告中备注「通过穷举补漏发现」，并更新发现总数和置信度。

---

### 阶段 8：梯队分类

根据所有已验证发现，将公司归入唯一梯队：

| 梯队 | 标签 | 判据 |
|------|------|------|
| 🥇 第一梯队 | 已在公开平台发布 | 至少有一个 MCP Server 或 Skill 可在公开平台**无需登录/签约直接安装或下载**（npm install、pip install、git clone、扣子/魔搭可直接搜索到等） |
| 🥈 第二梯队 | 有提供但仅限特定渠道 | 有文档或公告说明 MCP/Skill 已提供，但只能通过**特定封闭平台**（如腾讯元器、阿里云点金）或**签约后**获取 |
| 🥉 第三梯队 | 仅演示或概念 | 仅有**新闻/演示/演讲/战略发布**中提及，未找到实际可下载或可获取的 MCP/Skill |

**边界情况**：如果公司官网提供 MCP 下载但需注册登录，归入第二梯队（封闭获取），因为"公开平台"标准要求无需注册即可访问。

---

### 阶段 9：置信度评估

标注本次检索的置信度：

| 级别 | 条件 |
|------|------|
| 高 | 所有平台搜索完成 + 至少对一个官方渠道完成穷举验证（GitHub org 或 npm scope 或官方平台） + 结果明确 |
| 中 | GitHub Token 未配置或少数非关键平台不可用，或穷举验证未能执行，但其余核心平台已覆盖，结论仍有充分依据 |
| 低 | 多个核心平台大面积不可用，或该公司网络信息极少，结论存在较大不确定性 |

列出各平台的实际搜索状态（完成/跳过/不可用），以及穷举验证是否已执行。

---

### 阶段 10：输出报告（飞书云文档）

将检索结果创建为飞书云文档，而非在对话中输出 Markdown。步骤如下。

**步骤 10a — 加载 lark-doc skill**：先调用 `Skill` 工具加载 `lark-doc` skill 及 `lark-shared`。创建文档时使用 `--as user` 身份。

**步骤 10b — 生成 XML 内容并创���文档**：

执行命令（参考 `lark-doc-xml.md` 的标签语法）：

```bash
lark-cli docs +create --as user --content '<xml-content>'
```

**步骤 10c — 输出链接**：创建成功后输出飞书文档 URL 作为唯一交付物（一句即可），不附加 Markdown 报告。

**XML 内容模板**（`{...}` 为占位符，替换为实际数据）：

```xml
<title>MCP/Skill 检索报告 - {公司名称}</title>

<h1>概览</h1>
<table>
  <colgroup><col span="2" width="120"/></colgroup>
  <thead><tr><th background-color="light-gray">项目</th><th background-color="light-gray">内容</th></tr></thead>
  <tbody>
    <tr><td><b>公司</b></td><td>{公司名称}</td></tr>
    <tr><td><b>搜索日期</b></td><td>{YYYY-MM-DD}</td></tr>
    <tr><td><b>梯队</b></td><td>{emoji} {梯队标签}</td></tr>
    <tr><td><b>置信度</b></td><td>{高/中/低}</td></tr>
  </tbody>
</table>

<h1>官方自有平台入口</h1>
<callout emoji="🔗" background-color="light-blue" border-color="blue">
  <p><b>官方自有平台</b>：{URL 或 "未找到"}</p>
  <p><b>入口说明</b>：{提供内容说明}</p>
</callout>
<p><em>如未找到，写：未检索到公司官方 MCP/Skill 专属入口。</em></p>

<h1>已发现的 MCP/Skill</h1>
<p>以下按同一能力聚合展示。</p>

<table>
  <colgroup>
    <col span="1" width="140"/><col span="1" width="80"/>
    <col span="1" width="60"/><col span="1" width="120"/>
    <col span="1" width="200"/><col span="1" width="250"/>
  </colgroup>
  <thead><tr>
    <th background-color="light-gray">名称</th>
    <th background-color="light-gray">类型</th>
    <th background-color="light-gray">归属</th>
    <th background-color="light-gray">所在平台</th>
    <th background-color="light-gray">访问地址</th>
    <th background-color="light-gray">简介</th>
  </tr></thead>
  <tbody>
    <tr><td>{名称}</td><td>{MCP Server / Agent Skill}</td><td>{官方 / 第三方}</td><td>{平台1 / 平台2}</td><td>{URL}</td><td>{1-2句中文简介}</td></tr>
  </tbody>
</table>

<callout emoji="📌" background-color="light-gray" border-color="gray">
  <p><b>平台优先级</b>：官方自有平台 &gt; GitHub &gt; npm/PyPI &gt; Smithery &gt; Glama &gt; PulseMCP &gt; 魔搭 &gt; mcp-cn.com &gt; ClawHub &gt; 扣子 &gt; 腾讯元器。</p>
  <p><b>访问地址</b>：从合并结果 url 字段取值（自动选最优链接）。</p>
</callout>

<h1>梯队判据</h1>
<p>{简要说明归入该梯队的原因，列出关键证据和来源}</p>

<h1>检索覆盖</h1>
<ul>
  <li><b>代码仓库与注册表</b>：npm {✅/❌} | PyPI {✅/❌} | GitHub {✅/❌} | 魔搭 {✅/❌} | mcp-cn.com {✅/❌} | ClawHub {✅/❌} | Smithery {✅/❌} | Glama {✅/❌} | PulseMCP {✅/❌}</li>
  <li><b>公司自有平台</b>：{✅/❌}（URL：{链接}）</li>
  <li><b>垂直平台</b>：扣子 {✅/❌} | 腾讯元器 {✅/❌}</li>
  <li><b>通用搜索</b>：{✅/❌}（关键词：{列出}）</li>
  <li><b>穷举补漏</b>：{✅/❌}（已穷举渠道：{...}，新发现 {N} 条）</li>
</ul>

<h1>备注</h1>
<p>{第三方贡献、相关新闻、可疑但无法确认的条目等}</p>
```

**XML 转义规则**：仅转义文本内容中的 `&` → `&amp;`、`<` → `&lt;`、`>` → `&gt;`，标签本身不转义。

**第三方条目**：在"已发现的 MCP/Skill"的主表格后，另加一个 `<callout emoji="ℹ️" background-color="light-gray" border-color="gray">` 列出社区/第三方 MCP/Skill 供参考。

**简介要求**：每条控制在 1-2 句中文，从 description/README 摘要提取或精简概括；无描述时写"暂无描述"。

---

## 止损条件

- **单平台止损**：在同一平台上搜索 3 组关键词无相关结果后，停止搜索该平台。
- **通用搜索止损**：相同关键词+平台组合绝不重复搜索。
- **整体止损**：整个工作流控制在 10-15 次工具调用内。接近 18 次时，输出已有发现的报告，在置信度评估中注明未完成的搜索项。
