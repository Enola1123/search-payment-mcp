#!/usr/bin/env python3
"""
Merge and deduplicate search results from multiple registries.

Input: JSON via stdin (output of search_registries.py)
Output: Deduplicated, grouped JSON to stdout.

Deduplication logic:
- npm packages linking to the same GitHub repo are merged into one item.
- PyPI packages with same home_page repo are merged.
- GitHub repos discovered directly are kept only if not already captured
  via npm/PyPI links.
"""

import json
import re
import sys


def extract_repo(url):
    """Extract owner/repo from a GitHub URL.

    Handles: github.com/owner/repo, github.com/owner/repo.git,
             github.com/owner/repo/tree/..., etc.
    """
    if not url:
        return None
    m = re.search(r"github\.com[/:]([^/]+/[^/]+?)(?:\.git)?(?:/|$)", url)
    return m.group(1).rstrip("/") if m else None


def normalize(s):
    """Normalize a name for fuzzy matching."""
    if not s:
        return ""
    return s.lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")


class ResultMerger:
    def __init__(self, data):
        self.data = data
        self.items = {}       # normalized_key -> item dict
        self.seen_repos = set()  # set of owner/repo strings

    def add_npm(self, pkg, keyword):
        if "error" in pkg:
            return
        key = normalize(pkg.get("name", ""))
        if not key:
            return

        repo = extract_repo(pkg.get("repository_url", "") or "")

        if key in self.items:
            self.items[key]["platforms"].add("npm")
            if keyword not in self.items[key]["matched_keywords"]:
                self.items[key]["matched_keywords"].append(keyword)
            if repo:
                self.items[key]["repo"] = self.items[key].get("repo") or repo
                self.seen_repos.add(repo)
            return

        self.items[key] = {
            "source": "npm",
            "name": pkg.get("name"),
            "version": pkg.get("version"),
            "description": pkg.get("description"),
            "platforms": {"npm"},
            "publisher": pkg.get("publisher"),
            "publisher_email": pkg.get("publisher_email"),
            "date": pkg.get("date"),
            "npm_url": pkg.get("npm_url"),
            "repo": repo,
            "matched_keywords": [keyword],
        }
        if repo:
            self.seen_repos.add(repo)

    def add_pypi(self, pkg, keyword):
        if "error" in pkg:
            return
        key = normalize(pkg.get("name", ""))
        if not key:
            return

        repo = extract_repo(pkg.get("home_page", "") or "")

        if key in self.items:
            self.items[key]["platforms"].add("pypi")
            if keyword not in self.items[key]["matched_keywords"]:
                self.items[key]["matched_keywords"].append(keyword)
            if repo:
                self.items[key]["repo"] = self.items[key].get("repo") or repo
                self.seen_repos.add(repo)
            return

        self.items[key] = {
            "source": "pypi",
            "name": pkg.get("name"),
            "version": pkg.get("version"),
            "description": pkg.get("summary") or pkg.get("description"),
            "platforms": {"pypi"},
            "publisher": pkg.get("author") or pkg.get("maintainer"),
            "publisher_email": pkg.get("author_email") or pkg.get("maintainer_email"),
            "date": None,
            "pypi_url": pkg.get("pypi_url"),
            "repo": repo,
            "matched_keywords": [keyword],
        }
        if repo:
            self.seen_repos.add(repo)

    def add_github(self, repo_obj, keyword):
        if "error" in repo_obj:
            return
        full_name = repo_obj.get("full_name", "")
        if not full_name:
            return

        # Skip if already captured via npm/PyPI cross-reference
        if full_name in self.seen_repos:
            return
        self.seen_repos.add(full_name)

        # Also check if any existing item already points to this repo
        for existing in self.items.values():
            if existing.get("repo") == full_name:
                if "github" not in existing["platforms"]:
                    existing["platforms"].add("github")
                if keyword not in existing["matched_keywords"]:
                    existing["matched_keywords"].append(keyword)
                if "stars" not in existing:
                    existing["stars"] = repo_obj.get("stars")
                if "topics" not in existing:
                    existing["topics"] = repo_obj.get("topics", [])
                return

        key = normalize(full_name)
        self.items[key] = {
            "source": "github",
            "name": repo_obj.get("name"),
            "full_name": full_name,
            "description": repo_obj.get("description"),
            "platforms": {"github"},
            "publisher": repo_obj.get("owner"),
            "date": repo_obj.get("updated"),
            "stars": repo_obj.get("stars"),
            "language": repo_obj.get("language"),
            "topics": repo_obj.get("topics", []),
            "github_url": repo_obj.get("url"),
            "repo": full_name,
            "matched_keywords": [keyword],
        }

    def add_modelscope(self, entry, keyword):
        if "error" in entry:
            return
        mcp_id = entry.get("id", "")
        if not mcp_id:
            return
        key = normalize(mcp_id)
        name = entry.get("chinese_name") or entry.get("name", "")

        if key in self.items:
            self.items[key]["platforms"].add("modelscope")
            if keyword not in self.items[key]["matched_keywords"]:
                self.items[key]["matched_keywords"].append(keyword)
            return

        self.items[key] = {
            "source": "modelscope",
            "name": name,
            "mcp_id": mcp_id,
            "description": entry.get("description"),
            "platforms": {"modelscope"},
            "publisher": entry.get("publisher"),
            "categories": entry.get("categories", []),
            "view_count": entry.get("view_count"),
            "logo_url": entry.get("logo_url"),
            "modelscope_url": f"https://modelscope.cn/mcp/{mcp_id}",
            "repo": None,
            "matched_keywords": [keyword],
        }

    def add_mcpcn(self, entry, keyword):
        if "error" in entry:
            return
        qualified = entry.get("qualified_name", "")
        if not qualified:
            return
        key = normalize(qualified)
        name = entry.get("display_name") or qualified

        if key in self.items:
            self.items[key]["platforms"].add("mcpcn")
            if keyword not in self.items[key]["matched_keywords"]:
                self.items[key]["matched_keywords"].append(keyword)
            return

        self.items[key] = {
            "source": "mcpcn",
            "name": name,
            "qualified_name": qualified,
            "description": entry.get("description"),
            "platforms": {"mcpcn"},
            "publisher": entry.get("creator"),
            "use_count": entry.get("use_count"),
            "tag": entry.get("tag"),
            "is_domestic": entry.get("is_domestic"),
            "package_url": entry.get("package_url"),
            "mcpcn_url": f"https://mcp-cn.com/server/{entry.get('server_id')}",
            "repo": None,
            "matched_keywords": [keyword],
        }

    def add_clawhub(self, entry, keyword):
        if "error" in entry:
            return
        name = entry.get("name", "")
        if not name:
            return
        key = normalize(name)
        display = entry.get("display_name") or name

        if key in self.items:
            self.items[key]["platforms"].add("clawhub")
            if keyword not in self.items[key]["matched_keywords"]:
                self.items[key]["matched_keywords"].append(keyword)
            return

        self.items[key] = {
            "source": "clawhub",
            "name": display,
            "package_name": name,
            "family": entry.get("family"),
            "description": entry.get("summary"),
            "platforms": {"clawhub"},
            "publisher": entry.get("owner_handle"),
            "is_official": entry.get("is_official"),
            "channel": entry.get("channel"),
            "categories": entry.get("categories", []),
            "topics": entry.get("topics", []),
            "downloads": entry.get("downloads"),
            "stars": entry.get("stars"),
            "verification_tier": entry.get("verification_tier"),
            "clawhub_url": f"https://clawhub.ai/{entry.get('owner_handle', '')}/{'skills' if entry.get('family') == 'skill' else 'plugins'}/{name}",
            "repo": None,
            "matched_keywords": [keyword],
        }

    def add_glama(self, entry, keyword):
        if "error" in entry:
            return
        glama_id = entry.get("id", "")
        if not glama_id:
            return
        key = normalize(f"{entry.get('namespace','')}/{entry.get('name','')}")

        repo_url = entry.get("repository_url")
        repo = extract_repo(repo_url) if repo_url else None

        if key in self.items:
            self.items[key]["platforms"].add("glama")
            if keyword not in self.items[key]["matched_keywords"]:
                self.items[key]["matched_keywords"].append(keyword)
            if repo and not self.items[key].get("repo"):
                self.items[key]["repo"] = repo
                self.seen_repos.add(repo)
            return

        self.items[key] = {
            "source": "glama",
            "name": entry.get("name"),
            "namespace": entry.get("namespace"),
            "description": entry.get("description"),
            "platforms": {"glama"},
            "publisher": entry.get("namespace"),
            "repo": repo,
            "attributes": entry.get("attributes", []),
            "tools_count": entry.get("tools_count"),
            "glama_url": entry.get("url"),
            "matched_keywords": [keyword],
        }
        if repo:
            self.seen_repos.add(repo)

    def add_smithery(self, entry, keyword):
        if "error" in entry:
            return
        qualified = entry.get("qualified_name", "")
        if not qualified:
            return
        key = normalize(qualified)

        if key in self.items:
            self.items[key]["platforms"].add("smithery")
            if keyword not in self.items[key]["matched_keywords"]:
                self.items[key]["matched_keywords"].append(keyword)
            return

        self.items[key] = {
            "source": "smithery",
            "name": entry.get("display_name") or qualified,
            "qualified_name": qualified,
            "namespace": entry.get("namespace"),
            "description": entry.get("description"),
            "platforms": {"smithery"},
            "publisher": entry.get("namespace"),
            "verified": entry.get("verified"),
            "use_count": entry.get("use_count"),
            "homepage": entry.get("homepage"),
            "created_at": entry.get("created_at"),
            "by_smithery": entry.get("by_smithery"),
            "score": entry.get("score"),
            "smithery_url": f"https://smithery.ai/servers/{qualified}",
            "repo": None,
            "matched_keywords": [keyword],
        }

    def add_pulsemcp(self, entry, keyword):
        if "error" in entry:
            return
        name = entry.get("name", "")
        if not name:
            return
        key = normalize(name)

        repo_url = entry.get("repository_url")
        repo = extract_repo(repo_url) if repo_url else None

        if key in self.items:
            self.items[key]["platforms"].add("pulsemcp")
            if keyword not in self.items[key]["matched_keywords"]:
                self.items[key]["matched_keywords"].append(keyword)
            if repo and not self.items[key].get("repo"):
                self.items[key]["repo"] = repo
                self.seen_repos.add(repo)
            return

        self.items[key] = {
            "source": "pulsemcp",
            "name": entry.get("title") or name,
            "mcp_name": name,
            "description": entry.get("description"),
            "version": entry.get("version"),
            "platforms": {"pulsemcp"},
            "publisher": None,
            "is_official": entry.get("is_official"),
            "visitors_weekly": entry.get("visitors_weekly"),
            "status": entry.get("status"),
            "website_url": entry.get("website_url"),
            "pulsemcp_url": entry.get("website_url"),
            "repo": repo,
            "matched_keywords": [keyword],
        }
        if repo:
            self.seen_repos.add(repo)

    def merge(self):
        platforms_data = self.data.get("platforms", {})
        for keyword, pf in platforms_data.items():
            for pkg in pf.get("npm", []):
                self.add_npm(pkg, keyword)
            for pkg in pf.get("pypi", []):
                self.add_pypi(pkg, keyword)
            for repo in pf.get("github", []):
                self.add_github(repo, keyword)
            for entry in pf.get("modelscope", []):
                self.add_modelscope(entry, keyword)
            for entry in pf.get("mcpcn", []):
                self.add_mcpcn(entry, keyword)
            for entry in pf.get("clawhub", []):
                self.add_clawhub(entry, keyword)
            for entry in pf.get("glama", []):
                self.add_glama(entry, keyword)
            for entry in pf.get("smithery", []):
                self.add_smithery(entry, keyword)
            for entry in pf.get("pulsemcp", []):
                self.add_pulsemcp(entry, keyword)

    # URL 优先级：GitHub > npm > PyPI > smithery > glama > pulsemcp > 魔搭 > mcp-cn.com > ClawHub（公开可访问优先）
    _URL_PRIORITY = [
        "github_url", "npm_url", "pypi_url",
        "smithery_url", "glama_url", "pulsemcp_url",
        "modelscope_url", "mcpcn_url", "clawhub_url",
    ]

    def summary(self):
        items = list(self.items.values())
        # Convert set fields to list for JSON serialization
        for item in items:
            if "platforms" in item and isinstance(item["platforms"], set):
                item["platforms"] = sorted(item["platforms"])
            # Unify URL: pick the best available platform URL
            for url_key in self._URL_PRIORITY:
                if item.get(url_key):
                    item["url"] = item[url_key]
                    break
        return {
            "company": self.data.get("company", ""),
            "searched_keywords": self.data.get("searched_keywords", []),
            "total_found": len(items),
            "by_platform": {
                "npm": sum(1 for i in items if "npm" in i.get("platforms", set())),
                "pypi": sum(1 for i in items if "pypi" in i.get("platforms", set())),
                "github": sum(1 for i in items if "github" in i.get("platforms", set())),
                "modelscope": sum(1 for i in items if "modelscope" in i.get("platforms", set())),
                "mcpcn": sum(1 for i in items if "mcpcn" in i.get("platforms", set())),
                "clawhub": sum(1 for i in items if "clawhub" in i.get("platforms", set())),
                "glama": sum(1 for i in items if "glama" in i.get("platforms", set())),
                "smithery": sum(1 for i in items if "smithery" in i.get("platforms", set())),
                "pulsemcp": sum(1 for i in items if "pulsemcp" in i.get("platforms", set())),
            },
            "items": items,
        }


def main():
    input_data = json.loads(sys.stdin.read())
    merger = ResultMerger(input_data)
    merger.merge()
    output = merger.summary()
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
