# 检索平台参考

本文档列出支付公司 MCP/Skill 的所有检索平台、检索方法和验证标准。

## 平台总览

| 平台 | 检索方式 | 公开 API | 需要登录 | 备注 |
|------|---------|---------|----------|------|
| npm | 脚本 `search_registries.py` | ✅ | 否 | registry API |
| PyPI | 脚本 `search_registries.py` | ✅ | 否 | 无搜索 API，用候选包名逐个查询 |
| GitHub | 脚本 `search_registries.py` | ✅ | 需 Token | 支持 gh CLI / .github_token 文件 / 环境变量 |
| 魔搭 MCP 广场 | 脚本 `search_registries.py` | ✅ | 否 | OpenAPI，SPA 页面搜索引擎不可见 |
| mcp-cn.com | 脚本 `search_registries.py` | ✅ | 否 | `GET /api/servers?search=` |
| ClawHub | 脚本 `search_registries.py` | ✅ | 否 | `GET /api/v1/packages?q=`，返回 isOfficial 信号 |
| 扣子 (Coze) | WebSearch | ❌ | — | 无公开 Skill 搜索 API |
| 腾讯元器 | WebSearch | ❌ | — | Cookie 认证不可持久化，无公开 MCP 搜索 API |
| 公司自有平台 | 主动探查 | ❌ | 因公司而异 | 见第四节已知入口，WebSearch + WebFetch 直接访问 |
| 通用搜索引擎 | WebSearch | — | — | 新闻、博客、官方公告 |

---

## 一、代码仓库与包管理器（脚本检索）

这些平台有公开 API，使用 `scripts/search_registries.py` + `scripts/merge_results.py` 脚本完成。

### npm (registry.npmjs.org)

- **API**: `https://registry.npmjs.org/-/v1/search?text=<keyword>&size=10`
- **搜索策略**: 包名、描述、keywords 字段全覆盖
- **归属验证信号**:
  - `publisher.email` 域名是否匹配公司域名（如 @huifu.com、@yeepay.com）
  - 包名是否包含公司英文名/品牌名
  - `repository_url` 是否指向公司官方 GitHub 组织
  - `description` 中是否出现公司全称

### PyPI (pypi.org)

- **API**: `https://pypi.org/pypi/<package_name>/json`
- **搜索策略**: PyPI 无公开搜索 API，需用候选包名逐个尝试精准查询。候选名从关键词自动生成（连字符化、下划线化、添加 -mcp/-server 前后缀）
- **归属验证信号**:
  - `author_email` / `maintainer_email` 域名是否匹配
  - `home_page` / `project_urls` 是否指向公司官方域
  - `classifiers` 中是否包含公司相关标识

### GitHub (github.com)

- **命令**: `gh search repos "mcp OR skill <keyword> in:name,description" --limit 10 --json ...`
- **前置条件**: 需要 `gh auth login` 完成认证
- **搜索策略**: 搜索仓库名和描述中包含 mcp/skill + 关键词的仓库
- **归属验证信号**:
  - 仓库所属组织（owner）是否为公司官方 GitHub 组织
  - 仓库描述是否声明"官方"
  - topics 标签中是否包含公司名
  - README 中是否出现公司域名

### 魔搭 MCP 广场 (modelscope.cn) — API 检索

- **API**: `PUT https://www.modelscope.cn/openapi/v1/mcp/servers`
- **认证**: 搜索**无需 Token**，公开可用
- **参数**: `search`（匹配中文名/英文名/作者）, `page_number`, `page_size`（最大 100）
- **注意**: 魔搭是 SPA 应用，MCP 详情页**无法被通用搜索引擎索引**。必须通过 OpenAPI 直接查询，不能依赖 WebSearch `site:modelscope.cn`。
- **归属验证信号**:
  - `publisher` / `id`（格式 `@org/name`）是否为官方账号
  - `description` 中是否声明官方身份
  - `categories` 是否包含 `finance`（作为辅助信号）
  - 同一条目是否在公司官网/新闻中被提及（交叉验证）

### mcp-cn.com — API 检索

- **API**: `GET https://mcp-cn.com/api/servers?search=<keyword>`
- **认证**: 搜索**无需 Token**，公开可用
- **返回格式**: `{"code": 0, "data": [...]}`，每个条目含 `qualified_name`、`display_name`、`description`、`creator`、`package_url`、`use_count`、`tag`、`is_domestic`
- **搜索策略**: 模糊匹配，可能返回不相关内容；需在归属验证阶段通过 `creator`、`package_url` 等字段过滤
- **归属验证信号**:
  - `creator` 是否使用公司官方账号名
  - `package_url` 是否指向公司官方 npm 包或 GitHub 仓库
  - `description` 是否明确提及公司名称

### ClawHub — API 检索

- **API**: `GET https://clawhub.ai/api/v1/packages?q=<keyword>&limit=<N>`
- **认证**: 搜索**无需 Token**，公开可用
- **返回格式**: `{"items": [...], "nextCursor": "..."}`，每个条目含 `name`、`displayName`、`summary`、`family`（skill/plugin）、`ownerHandle`、`isOfficial`、`stats.downloads`
- **搜索策略**: 模糊匹配；**关键信号** `isOfficial` 字段可直接判定官方身份
- **归属验证信号**:
  - `isOfficial` — 最可靠的直接信号，TRUE 即官方发布
  - `ownerHandle` 是否为公司官方账号
  - `channel` 是否为 `official`（官方渠道）
  - `verificationTier` 验证等级

---

## 二、无公开 API 的垂直平台（WebSearch 检索）

以下平台没有公开的搜索 API，使用 WebSearch 工具检索。

### 扣子 (Coze)

- **搜索方式**: WebSearch `"公司名 skill" site:coze.cn` 或 `"公司名 扣子"`
- **判断标准**: Skill 发布者是否为公司官方账号，skill 名称/描述是否对应

### 腾讯元器

- **搜索方式**: WebSearch `"公司名 腾讯元器 MCP"`
- **判断标准**: 是否在腾讯元器平台内可搜索到；注意该平台仅限平台内使用

---

## 三、搜索引擎（WebSearch 检索）

### 通用搜索引擎

- **搜索关键词策略**（动态生成，不做硬编码）:
  1. `"公司全称 MCP"` — 基础搜索
  2. `"公司品牌名/产品名 MCP server"` — 产品维度
  3. `"公司全称 Agent Skill"` 或 `"公司全称 智能体"` — 覆盖不同术语
  4. `"公司英文名 MCP model context protocol"` — 英文源
  5. `"公司全名 AI agent 开放平台"` — 覆盖开放平台入口

- **结果判断**:
  - 官方新闻稿/博客 → 记录为"已发布"的证据
  - 第三方报道 → 记录为参考信息，需交叉验证
  - 技术社区讨论 → 参考但不作为直接证据

---

## 四、公司自有平台

部分支付公司通过自己的开放平台/开发者站点提供 MCP/Skill，不会被通用平台（npm/PyPI/GitHub 等）覆盖。**由 SKILL.md 阶段 3 负责主动探查。**

- **检查方式**: 先查本节已知入口 → WebSearch 搜索 `"公司名 开发者中心"` / `"公司名 开放平台"` → WebFetch 读取找到的页面
- **已知有明确入口的**:
  - 易宝支付: open.yeepay.com/ai-connect
  - 银联: mcp.yun.unionpay.com
- 发现新的公司自有入口后，更新本节列表
- 记录 MCP/Skill 获取方式（公开 / 需注册 / 需签约），供梯队分类使用

---

## 五、归属验证的总原则

对每个搜到的结果，依次验证：

1. **域名验证**（最可靠）: 发布者邮箱域名 / 项目主页 URL / 组织域名 是否匹配公司官方域名
2. **命名验证**: 包名/仓库名是否包含公司英文名或已知品牌名
3. **内容验证**: 描述/README 中是否出现公司全称并声明"官方"身份
4. **交叉验证**: 公司官方新闻/博客中是否提及该 MCP/Skill 发布

**最低通过标准**: 满足第 1 条（域名验证）或同时满足第 2+3 条，方可认定为官方发布。
