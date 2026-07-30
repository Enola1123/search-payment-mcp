#!/usr/bin/env python3
"""
跨平台搜索 MCP/Skill 包：npm、PyPI、GitHub、魔搭、mcp-cn.com、ClawHub。

输入（stdin JSON）:
  - "keywords": 搜索关键词列表
  - "company": 公司名称（上下文用）
  - "platforms": 要搜索的平台列表（默认: ["npm", "pypi", "github", "modelscope", "mcpcn", "clawhub"]）

输出（stdout JSON）: 每个关键词在每个平台上的结构化结果。
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import time
from pathlib import Path


def search_npm(keyword, max_results=10):
    """Search npm registry for packages matching keyword."""
    url = (
        "https://registry.npmjs.org/-/v1/search?"
        f"text={urllib.parse.quote(keyword)}&size={max_results}"
    )
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "search-payment-mcp/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            results = []
            for obj in data.get("objects", []):
                pkg = obj.get("package", {})
                publisher = pkg.get("publisher", {}) or {}
                links = pkg.get("links", {}) or {}
                npm_url = links.get("npm", "")
                results.append(
                    {
                        "name": pkg.get("name"),
                        "version": pkg.get("version"),
                        "description": pkg.get("description"),
                        "publisher": publisher.get("username"),
                        "publisher_email": publisher.get("email"),
                        "date": pkg.get("date"),
                        "npm_url": npm_url,
                        "repository_url": links.get("repository"),
                        "keywords": pkg.get("keywords", []),
                    }
                )
            return results
    except Exception as e:
        return [{"error": str(e)}]


def search_pypi(keyword):
    """Search PyPI for packages matching keyword.

    PyPI has no good public search API, so try exact-name lookups
    against common naming conventions derived from the keyword.
    """
    results = []
    base = keyword.lower().strip()

    # Generate candidate package names
    candidates = [
        base.replace(" ", "-"),
        base.replace(" ", "_"),
        base.replace(" ", ""),
    ]
    # Also try with common prefix/suffix variants
    extra = []
    for c in candidates:
        extra.append(f"{c}-mcp")
        extra.append(f"{c}-server")
        extra.append(f"mcp-{c}")
    candidates = list(dict.fromkeys(candidates + extra))  # deduplicate

    for name in candidates:
        try:
            pkg_url = (
                f"https://pypi.org/pypi/{urllib.parse.quote(name, safe='')}/json"
            )
            req = urllib.request.Request(
                pkg_url, headers={"User-Agent": "search-payment-mcp/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                info = data.get("info", {})
                results.append(
                    {
                        "name": info.get("name"),
                        "version": info.get("version"),
                        "summary": info.get("summary"),
                        "description": (info.get("description") or "")[:500],
                        "author": info.get("author"),
                        "author_email": info.get("author_email"),
                        "maintainer": info.get("maintainer"),
                        "maintainer_email": info.get("maintainer_email"),
                        "home_page": info.get("home_page"),
                        "project_urls": info.get("project_urls", {}),
                        "pypi_url": info.get("package_url"),
                        "keywords": info.get("keywords", ""),
                        "classifiers": info.get("classifiers", []),
                    }
                )
        except urllib.error.HTTPError as e:
            if e.code != 404:
                results.append(
                    {"name": name, "error": f"HTTP {e.code}"}
                )
        except Exception as e:
            results.append({"name": name, "error": str(e)})

    return results


def _parse_github_repos(raw_items):
    """将 GitHub API / gh CLI 返回的仓库列表统一为内部格式。"""
    parsed = []
    for r in raw_items:
        owner_login = r.get("owner", {}).get("login", "") if isinstance(r.get("owner"), dict) else r.get("owner", "")
        parsed.append({
            "name": r.get("name"),
            "full_name": f"{owner_login}/{r.get('name', '')}" if owner_login else r.get("name"),
            "owner": owner_login,
            "description": r.get("description"),
            "url": r.get("url") or r.get("html_url"),
            "stars": r.get("stargazersCount") or r.get("stargazers_count"),
            "updated": r.get("updatedAt") or r.get("updated_at"),
            "language": r.get("language"),
            "topics": r.get("topics", []),
        })
    return parsed


def _github_api_search(keyword, token, max_results=10):
    """通过 GitHub REST API 搜索仓库（需要 token）。"""
    query = urllib.parse.quote(f"mcp OR skill {keyword} in:name,description")
    url = f"https://api.github.com/search/repositories?q={query}&per_page={max_results}&sort=updated"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "search-payment-mcp/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return _parse_github_repos(data.get("items", []))
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        return [{"error": f"GitHub API HTTP {e.code}: {body}"}]
    except Exception as e:
        return [{"error": str(e)}]


def search_github(keyword, max_results=10):
    """搜索 GitHub 仓库。
    
    认证优先级:
    1. gh CLI 已登录 → 用 gh search repos（最快）
    2. gh 未登录但有 GITHUB_TOKEN/GH_TOKEN 环境变量 → REST API
    3. 都没有但 skill 目录下有 .github_token 文件 → 读取后走 REST API
    4. 全部没有 → 返回错误
    """
    def _resolve_token():
        """按优先级解析 GitHub token。"""
        # 环境变量
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            return token
        # skill 目录下的 token 文件（持久化，一次配置长期有效）
        token_file = Path(__file__).resolve().parent.parent / ".github_token"
        try:
            if token_file.is_file():
                token = token_file.read_text().strip()
                if token:
                    return token
        except Exception:
            pass
        return None

    token = _resolve_token()
    # 先尝试 gh CLI
    try:
        query = f"mcp OR skill {keyword} in:name,description"
        result = subprocess.run(
            [
                "gh", "search", "repos", query,
                "--limit", str(max_results),
                "--json",
                "name,owner,description,url,stargazersCount,updatedAt,language,topics",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={**__import__("os").environ, "NO_COLOR": "1"},
        )
        if result.returncode == 0:
            repos = json.loads(result.stdout)
            return _parse_github_repos(repos)

        # gh CLI 失败了，看是不是认证问题
        stderr = result.stderr.strip()
        is_auth_error = any(kw in stderr.lower() for kw in ["auth", "login", "unauthorized", "credentials"])

        if is_auth_error:
            if token:
                return _github_api_search(keyword, token, max_results)
            else:
                return [{"error": (
                    "GitHub 搜索需要认证。请通过以下任一方式设置（推荐方式2，一次配置长期有效）：\n"
                    "  方式1: gh auth login（交互式登录）\n"
                    "  方式2: 将 GitHub Personal Access Token 写入 skill 目录下的 .github_token 文件\n"
                    "  方式3: export GITHUB_TOKEN=<token>\n"
                    "获取 Token: https://github.com/settings/tokens（无需任何权限即可搜索公共仓库）"
                )}]
        return [{"error": stderr}]

    except FileNotFoundError:
        if token:
            return _github_api_search(keyword, token, max_results)
        return [{"error": (
            "gh CLI 未安装且未设置 GitHub Token。请通过以下任一方式设置（推荐方式2）：\n"
            "  方式1: brew install gh && gh auth login\n"
            "  方式2: 将 GitHub Personal Access Token 写入 skill 目录下的 .github_token 文件\n"
            "  方式3: export GITHUB_TOKEN=<token>\n"
            "获取 Token: https://github.com/settings/tokens（无需任何权限即可搜索公共仓库）"
        )}]
    except Exception as e:
        return [{"error": str(e)}]


def search_modelscope(keyword, max_results=20):
    """搜索魔搭 MCP 广场，无需登录。

    API: PUT https://www.modelscope.cn/openapi/v1/mcp/servers
    匹配中文名、英文名和发布者。
    """
    url = "https://www.modelscope.cn/openapi/v1/mcp/servers"
    try:
        body = json.dumps({
            "search": keyword,
            "page_number": 1,
            "page_size": max_results,
        }).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "search-payment-mcp/1.0",
            },
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if not result.get("success"):
                return [{"error": f"API 返回异常: {result}"}]
            servers = result.get("data", {}).get("mcp_server_list", [])
            return [
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "chinese_name": s.get("chinese_name"),
                    "description": (s.get("description") or "")[:500],
                    "publisher": s.get("publisher"),
                    "categories": s.get("categories", []),
                    "view_count": s.get("view_count"),
                    "logo_url": s.get("logo_url"),
                }
                for s in servers
            ]
    except Exception as e:
        return [{"error": str(e)}]


def search_mcpcn(keyword, max_results=20):
    """搜索 mcp-cn.com 注册表，无需登录。

    API: GET https://mcp-cn.com/api/servers?search=<keyword>
    返回 MCP Server 列表，按使用量降序排列。
    """
    url = f"https://mcp-cn.com/api/servers?search={urllib.parse.quote(keyword)}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "search-payment-mcp/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if result.get("code") != 0:
                return [{"error": f"API 返回异常: {result.get('message', 'unknown')}"}]
            servers = result.get("data", [])[:max_results]
            return [
                {
                    "server_id": s.get("server_id"),
                    "qualified_name": s.get("qualified_name"),
                    "display_name": s.get("display_name"),
                    "description": (s.get("description") or "")[:500],
                    "creator": s.get("creator"),
                    "package_url": s.get("package_url"),
                    "use_count": s.get("use_count"),
                    "tag": s.get("tag"),
                    "is_domestic": s.get("is_domestic"),
                }
                for s in servers
            ]
    except Exception as e:
        return [{"error": str(e)}]


def search_clawhub(keyword, max_results=20):
    """搜索 ClawHub Skill 市场，无需登录。

    API: GET https://clawhub.ai/api/v1/packages?q=<keyword>&limit=<N>
    返回 skills 和 plugins 列表，包含 isOfficial 归属信号。
    """
    url = (
        "https://clawhub.ai/api/v1/packages?"
        f"q={urllib.parse.quote(keyword)}&limit={max_results}"
    )
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "search-payment-mcp/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            items = result.get("items", [])
            return [
                {
                    "name": s.get("name"),
                    "display_name": s.get("displayName"),
                    "family": s.get("family"),
                    "summary": (s.get("summary") or "")[:500],
                    "owner_handle": s.get("ownerHandle"),
                    "is_official": s.get("isOfficial"),
                    "channel": s.get("channel"),
                    "categories": s.get("categories", []),
                    "topics": s.get("topics", []),
                    "downloads": s.get("stats", {}).get("downloads"),
                    "stars": s.get("stats", {}).get("stars"),
                    "verification_tier": s.get("verificationTier"),
                }
                for s in items
            ]
    except Exception as e:
        return [{"error": str(e)}]


def main():
    input_data = json.loads(sys.stdin.read())
    keywords = input_data.get("keywords", [])
    company = input_data.get("company", "")
    platforms = input_data.get("platforms", ["npm", "pypi", "github", "modelscope", "mcpcn", "clawhub"])

    all_results = {
        "company": company,
        "searched_keywords": keywords,
        "platforms": {},
    }

    for keyword in keywords:
        platform_results = {}

        if "npm" in platforms:
            platform_results["npm"] = search_npm(keyword)
            time.sleep(0.5)

        if "pypi" in platforms:
            platform_results["pypi"] = search_pypi(keyword)
            time.sleep(0.5)

        if "github" in platforms:
            platform_results["github"] = search_github(keyword)
            time.sleep(1.0)

        if "modelscope" in platforms:
            platform_results["modelscope"] = search_modelscope(keyword)
            time.sleep(0.5)

        if "mcpcn" in platforms:
            platform_results["mcpcn"] = search_mcpcn(keyword)
            time.sleep(0.5)

        if "clawhub" in platforms:
            platform_results["clawhub"] = search_clawhub(keyword)
            time.sleep(0.5)

        all_results["platforms"][keyword] = platform_results

    print(json.dumps(all_results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
