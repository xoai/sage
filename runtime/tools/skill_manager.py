#!/usr/bin/env python3
"""
skill_manager.py — Skill manager for Sage framework.
Zero pip dependencies — Python 3.8+ stdlib only.
Powered by skills.sh for community skill discovery.

Usage:
    python skill_manager.py find <keyword>                    # search skills.sh
    python skill_manager.py find <keyword> --json             # machine-readable
    python skill_manager.py add <source>                      # discover + pick skills
    python skill_manager.py add <source> --skill <name>       # install specific skill
    python skill_manager.py add <source> --all                # install all skills
    python skill_manager.py add <source> --audit              # security check first
    python skill_manager.py remove <skill>                    # uninstall skill
    python skill_manager.py list                              # show installed skills
    python skill_manager.py update [target]                   # update community skills
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Constants ──
SKILLSSH_API = "https://skills.sh/api/search"
AUDIT_API = "https://add-skill.vercel.sh/audit"
GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"
SAGE_SKILLS_DIR = "sage/skills"
SKILLS_JSON = "sage/skills/skills.json"

# Known SKILL.md locations in repos (priority order)
SKILL_PATTERNS = [
    re.compile(r"^skills/([^/]+)/SKILL\.md$"),
    re.compile(r"^\.agents/skills/([^/]+)/SKILL\.md$"),
    re.compile(r"^\.claude/skills/([^/]+)/SKILL\.md$"),
    re.compile(r"^([^/]+)/SKILL\.md$"),
]

# ── UI ──
class UI:
    C = {"reset":"\033[0m","bold":"\033[1m","red":"\033[31m","green":"\033[32m",
         "yellow":"\033[33m","blue":"\033[34m","cyan":"\033[36m","dim":"\033[2m"}
    def __init__(self): self.ok = hasattr(sys.stdout,"isatty") and sys.stdout.isatty()
    def _c(self,c,t): return f"{self.C.get(c,'')}{t}{self.C['reset']}" if self.ok else t
    def info(self,m): print(self._c("blue",f"  ℹ {m}"))
    def success(self,m): print(self._c("green",f"  ✓ {m}"))
    def warning(self,m): print(self._c("yellow",f"  ⚠ {m}"))
    def error(self,m): print(self._c("red",f"  ✗ {m}"),file=sys.stderr)
    def text(self,m): print(f"  {m}")
    def dim(self,m): print(self._c("dim",f"    {m}"))
    def bold(self,m): print(self._c("bold",f"  {m}"))
ui = UI()

# ── HTTP ──
def http_get(url, *, accept="application/json", timeout=15):
    from urllib.request import Request, urlopen
    r = Request(url, headers={"Accept": accept, "User-Agent": "sage/1.1"})
    with urlopen(r, timeout=timeout) as resp:
        return resp.read()

def http_json(url, **kw):
    return json.loads(http_get(url, **kw))

def http_text(url, **kw):
    return http_get(url, accept="text/plain", **kw).decode("utf-8", errors="replace")

# ── Git (fallback) ──
def has_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def git_clone(dest, url):
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
        capture_output=True, check=True, timeout=120
    )

# ── Frontmatter Parser ──
def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from SKILL.md. Pure Python, no yaml library."""
    lines = content.strip().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result = {}
    in_desc = False
    desc_lines = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if in_desc:
            stripped = line.strip()
            if stripped and not re.match(r"^\w+:", stripped):
                desc_lines.append(stripped)
                continue
            else:
                result["description"] = " ".join(desc_lines)
                in_desc = False
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if key == "description" and val in (">", ">-", "|", "|-", ""):
                in_desc = True
                desc_lines = []
                continue
            if val and val[0] in ('"', "'") and val[-1] == val[0]:
                val = val[1:-1]
            result[key] = val
        m2 = re.match(r"^\s+internal:\s*(true|false)", line)
        if m2:
            result["internal"] = m2.group(1) == "true"
    if in_desc and desc_lines:
        result["description"] = " ".join(desc_lines)
    return result

# ── Source Parser ──
class SourceInfo:
    def __init__(self, stype, owner="", repo="", path="", branch="", url=""):
        self.type = stype
        self.owner = owner
        self.repo = repo
        self.path = path
        self.branch = branch
        self.url = url

def parse_source(source):
    # Local path
    if source.startswith("./") or source.startswith("/") or os.path.isdir(source):
        return SourceInfo("local", url=os.path.abspath(source))
    # GitHub deep link
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)", source)
    if m:
        return SourceInfo("github", owner=m.group(1), repo=m.group(2),
                          branch=m.group(3), path=m.group(4))
    # GitHub URL
    m = re.match(r"https?://github\.com/([^/]+)/([^/.]+)/?$", source)
    if m:
        return SourceInfo("github", owner=m.group(1), repo=m.group(2))
    # GitHub shorthand
    m = re.match(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$", source)
    if m:
        return SourceInfo("github", owner=m.group(1), repo=m.group(2))
    # Well-known URL
    if source.startswith("http://") or source.startswith("https://"):
        return SourceInfo("wellknown", url=source.rstrip("/"))
    raise ValueError(f'Cannot parse source: "{source}"')

# ── GitHub Skill Discovery ──
def gh_tree(owner, repo):
    data = http_json(f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1")
    return data.get("tree", [])

def discover_skills_github(owner, repo, path_filter=""):
    tree = gh_tree(owner, repo)
    skills = []
    seen = set()
    for item in tree:
        if item.get("type") != "blob":
            continue
        fpath = item.get("path", "")
        if not fpath.endswith("/SKILL.md"):
            continue
        if path_filter and not fpath.startswith(path_filter.rstrip("/") + "/"):
            continue
        name = None
        for pattern in SKILL_PATTERNS:
            pm = pattern.match(fpath)
            if pm:
                name = pm.group(1)
                break
        if not name or name in seen:
            continue
        seen.add(name)
        skill_dir = str(Path(fpath).parent)
        files = [f["path"] for f in tree
                 if f.get("type") == "blob" and f["path"].startswith(skill_dir + "/")]
        skills.append({"name": name, "path": skill_dir, "files": files, "description": ""})
    return skills

def enrich_skill_meta(owner, repo, skills, branch=""):
    for skill in skills:
        content = gh_download_file(owner, repo, f"{skill['path']}/SKILL.md", branch)
        if content:
            fm = parse_frontmatter(content)
            skill["description"] = fm.get("description", "")
            if fm.get("internal"):
                skill["internal"] = True
    return [s for s in skills if not s.get("internal")]

def gh_download_file(owner, repo, path, branch=""):
    branches = [branch] if branch else ["main", "master", "HEAD"]
    for b in branches:
        try:
            data = http_get(f"{GITHUB_RAW}/{owner}/{repo}/{b}/{path}",
                            accept="application/octet-stream")
            return data.decode("utf-8", errors="replace")
        except Exception:
            continue
    return None

def gh_download_skill(owner, repo, skill, dest, branch=""):
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    base = skill["path"]
    for fpath in skill["files"]:
        content = gh_download_file(owner, repo, fpath, branch)
        if content is None:
            continue
        rel = fpath[len(base) + 1:]
        local = dest / rel
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(content, encoding="utf-8")
        n += 1
    if n == 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError(f"Download failed for {skill['name']}")
    return n

# ── Well-Known Protocol ──
def discover_skills_wellknown(base_url):
    for path in ["/.well-known/agent-skills/index.json",
                 "/.well-known/skills/index.json"]:
        try:
            data = http_json(f"{base_url}{path}")
            skills = []
            for s in data.get("skills", []):
                skills.append({
                    "name": s.get("name", ""),
                    "description": s.get("description", ""),
                    "files": s.get("files", ["SKILL.md"]),
                    "base_url": f"{base_url}/.well-known/agent-skills",
                    "path": s.get("name", ""),
                })
            return skills
        except Exception:
            continue
    raise RuntimeError(f"No well-known skills endpoint at {base_url}")

def download_skill_wellknown(skill, dest):
    dest.mkdir(parents=True, exist_ok=True)
    base = f"{skill['base_url']}/{skill['name']}"
    n = 0
    for fname in skill["files"]:
        try:
            content = http_text(f"{base}/{fname}")
            (dest / fname).write_text(content, encoding="utf-8")
            n += 1
        except Exception:
            continue
    if n == 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError(f"Download failed for {skill['name']}")
    return n

# ── Local Path Discovery ──
def discover_skills_local(local_path):
    root = Path(local_path)
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {local_path}")
    skills = []
    for skill_md in root.rglob("SKILL.md"):
        skill_dir = skill_md.parent
        name = skill_dir.name
        fm = parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
        if fm.get("internal"):
            continue
        files = [str(f.relative_to(skill_dir)) for f in skill_dir.rglob("*") if f.is_file()]
        skills.append({
            "name": name, "path": str(skill_dir),
            "description": fm.get("description", ""),
            "files": files, "local": True,
        })
    return skills

def install_skill_local(skill, dest):
    src = Path(skill["path"])
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return len(skill["files"])

# ── skills.sh Search ──
def skillssh_search(query, limit=10):
    from urllib.parse import quote
    try:
        data = http_json(f"{SKILLSSH_API}?q={quote(query)}&limit={limit}")
        return data.get("skills", [])
    except Exception as e:
        ui.warning(f"skills.sh search failed: {e}")
        return []

# ── Audit API ──
def audit_skills(source, slugs):
    from urllib.parse import quote
    try:
        return http_json(f"{AUDIT_API}?source={quote(source)}&skills={quote(','.join(slugs))}")
    except Exception as e:
        ui.warning(f"Audit failed: {e}")
        return {}

# ── Config ──
class SkillsConfig:
    def __init__(self, project_dir=None):
        self.project_dir = project_dir or Path.cwd()
        self.config_path = self.project_dir / SKILLS_JSON
        self.skills_dir = self.project_dir / SAGE_SKILLS_DIR
    def exists(self): return self.config_path.is_file()
    def read(self):
        if not self.exists(): return {"skills": {}}
        with open(self.config_path) as f: return json.load(f)
    def write(self, cfg):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.config_path.with_suffix(".tmp")
        with open(tmp, "w") as f: json.dump(cfg, f, indent=2)
        tmp.replace(self.config_path)
    def add_skill(self, name, source, path="", installs=0):
        c = self.read()
        c.setdefault("skills", {})[name] = {
            "source": source, "path": path,
            "added": time.strftime("%Y-%m-%d"), "installs": installs,
        }
        self.write(c)
    def remove_skill(self, name):
        c = self.read(); c.get("skills", {}).pop(name, None); self.write(c)
    def get_source(self, name):
        e = self.read().get("skills", {}).get(name)
        return e.get("source") if e else None
    def get_skill_info(self, name):
        return self.read().get("skills", {}).get(name)
    def community_skills(self):
        return {k: v for k, v in self.read().get("skills", {}).items()
                if v.get("source") != "built-in"}

# ── Platform Deploy/Undeploy ──
def deploy_to_platform(name, source_dir, project_dir):
    deployed = False
    # Claude Code: create loader stub
    claude_dir = project_dir / ".claude" / "skills"
    if claude_dir.parent.is_dir():
        dest = claude_dir / name
        dest.mkdir(parents=True, exist_ok=True)
        skill_md = source_dir / "SKILL.md"
        desc = ""
        if skill_md.is_file():
            fm = parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
            desc = fm.get("description", "")
            if desc and len(desc) > 120:
                desc = desc[:117] + "..."
        (dest / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {desc}\n---\n"
            f"Read and follow the full skill at sage/skills/{name}/SKILL.md\n",
            encoding="utf-8"
        )
        ui.success(f"Deployed loader to .claude/skills/{name}/")
        deployed = True
    # Antigravity: copy full skill
    agent_skills = project_dir / ".agent" / "skills"
    if agent_skills.is_dir():
        dest = agent_skills / name
        if dest.exists(): shutil.rmtree(dest)
        shutil.copytree(source_dir, dest)
        for cf in (list(source_dir.glob("constitution/*.md")) +
                   list(source_dir.glob("*constitution*.md"))):
            rules = project_dir / ".agent" / "rules"
            if rules.is_dir():
                shutil.copy2(cf, rules / f"skill-{name}-constitution.md")
        ui.success(f"Deployed to .agent/skills/{name}/")
        deployed = True
    if not deployed:
        ui.dim(f"Available at sage/skills/{name}/. Run sage init to deploy.")

def undeploy_from_platform(name, project_dir):
    # Claude Code
    p = project_dir / ".claude" / "skills" / name
    if p.exists():
        shutil.rmtree(p)
        ui.success(f"Removed from .claude/skills/{name}/")
    # Antigravity
    p = project_dir / ".agent" / "skills" / name
    if p.exists():
        shutil.rmtree(p)
        ui.success(f"Removed from .agent/skills/{name}/")
    r = project_dir / ".agent" / "rules" / f"skill-{name}-constitution.md"
    if r.exists():
        r.unlink()

# ── Display ──
def fmt_installs(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(n)

def print_search_results(results, *, as_json=False):
    if as_json:
        print(json.dumps(results, indent=2)); return
    if not results:
        ui.text("No results found."); return
    print(); ui.bold(f"Found {len(results)} skill(s):"); print()
    for i, s in enumerate(results, 1):
        name = s.get("name", s.get("id", "?"))
        source = s.get("source", "unknown")
        installs = s.get("installs", 0)
        inst = f"({fmt_installs(installs)} installs)" if installs else ""
        num = ui._c("dim", f"  {i:>3} ")
        nm = ui._c("bold", f" {name}")
        src = ui._c("dim", f" ·· {source}  {inst}")
        print(f"{num}{nm}{src}")
    print()

def print_discovered(skills):
    print(); ui.bold(f"Found {len(skills)} skill(s):"); print()
    mx = min(max((len(s["name"]) for s in skills), default=10), 30)
    for i, s in enumerate(skills, 1):
        name = s["name"]
        desc = s.get("description", "")
        if len(desc) > 60: desc = desc[:57] + "..."
        pad = mx - len(name) + 2
        num = ui._c("dim", f"  {i:>3} ")
        nm = ui._c("bold", f" {name}")
        ds = ui._c("dim", f"{'·' * pad} {desc}") if desc else ""
        print(f"{num}{nm}{ds}")
    print()

# ── Skill Operations ──
def handle_conflict(skill_name, source, cfg):
    existing_src = cfg.get_source(skill_name) or "unknown"
    print(); ui.warning(f"Skill '{skill_name}' already exists")
    ui.dim(f"From: {existing_src}"); print()
    alt = f"{skill_name}-{source.split('/')[0]}" if "/" in source else f"{skill_name}-new"
    print(f"    1) Skip — keep existing")
    print(f"    2) Replace — overwrite with {source}")
    print(f"    3) Install as '{alt}' — keep both"); print()
    try: ch = input("    Choice [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt): print(); return None
    if ch == "1": return None
    elif ch == "2":
        t = cfg.skills_dir / skill_name
        if t.exists(): shutil.rmtree(t)
        undeploy_from_platform(skill_name, cfg.project_dir)
        return skill_name
    elif ch == "3": return alt
    return None

def install_one(skill, install_name, src, source_str, cfg, branch=""):
    target = cfg.skills_dir / install_name
    if target.exists():
        resolved = handle_conflict(install_name, source_str, cfg)
        if resolved is None:
            ui.info("Skipped."); return False
        install_name = resolved
        target = cfg.skills_dir / install_name

    ui.dim(f"Downloading {install_name}...")
    try:
        if skill.get("local"):
            n = install_skill_local(skill, target)
        elif src.type == "wellknown":
            n = download_skill_wellknown(skill, target)
        elif src.type == "github":
            n = gh_download_skill(src.owner, src.repo, skill, target, branch)
        else:
            raise RuntimeError(f"Unknown source type: {src.type}")
        ui.success(f"Downloaded {n} files to sage/skills/{install_name}/")
    except Exception as e:
        if src.type == "github" and has_git():
            ui.dim("API failed, trying git clone...")
            cache = Path.home() / ".sage" / "cache" / f"{src.owner}-{src.repo}"
            if not cache.is_dir():
                git_clone(cache, f"https://github.com/{src.owner}/{src.repo}.git")
            local_src = cache / skill["path"]
            if not local_src.is_dir():
                ui.error(f"'{install_name}' not found in cloned repo"); return False
            if target.exists(): shutil.rmtree(target)
            shutil.copytree(local_src, target)
            ui.success(f"Copied to sage/skills/{install_name}/")
        else:
            ui.error(f"Download failed: {e}"); return False

    cfg.add_skill(install_name, source_str, path=skill.get("path", ""),
                  installs=skill.get("installs", 0))
    deploy_to_platform(install_name, target, cfg.project_dir)
    return True

# ── Commands ──
def cmd_find(query, limit=10, as_json=False):
    cfg = SkillsConfig()
    results = skillssh_search(query, limit)
    print_search_results(results, as_json=as_json)
    if as_json or not results or not sys.stdout.isatty(): return
    installed = 0
    while True:
        try: choice = input(f"  [1-{len(results)}] Install  |  [Enter] Done: ").strip()
        except (EOFError, KeyboardInterrupt): print(); break
        if not choice: break
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                s = results[idx]
                source = s.get("source", s.get("id", ""))
                if source: cmd_add(source, skill_name=s.get("name")); installed += 1
                else: ui.warning("No source for this skill.")
            else: ui.warning(f"Enter 1-{len(results)}")
        except ValueError:
            if choice.lower() in ("q", "quit", "done"): break
            ui.warning("Enter a number or press Enter.")
    if installed: print(); ui.success(f"{installed} skill(s) installed.")

def cmd_add(source, skill_name=None, install_all=False, do_audit=False):
    cfg = SkillsConfig()
    src = parse_source(source)
    print(); ui.bold("Sage — Add Skills"); print()

    if src.type == "github":
        ui.info(f"Discovering skills in {src.owner}/{src.repo}...")
        skills = discover_skills_github(src.owner, src.repo, src.path)
        if not skills: ui.warning(f"No skills found in {src.owner}/{src.repo}"); return
        skills = enrich_skill_meta(src.owner, src.repo, skills, src.branch)
        source_str = f"{src.owner}/{src.repo}"
        branch = src.branch
    elif src.type == "local":
        ui.info(f"Discovering skills in {src.url}...")
        skills = discover_skills_local(src.url)
        if not skills: ui.warning(f"No SKILL.md files found in {src.url}"); return
        source_str = src.url; branch = ""
    elif src.type == "wellknown":
        ui.info(f"Discovering skills at {src.url}...")
        skills = discover_skills_wellknown(src.url)
        if not skills: ui.warning(f"No skills found at {src.url}"); return
        source_str = src.url; branch = ""
    else: ui.error(f"Unsupported source: {src.type}"); return

    if do_audit and src.type == "github":
        slugs = [s["name"] for s in skills]
        ui.info("Running security audit...")
        result = audit_skills(source_str, slugs)
        for slug, partners in result.items():
            for partner, info in partners.items():
                risk = info.get("risk", "unknown")
                if risk in ("medium", "high", "critical"):
                    ui.warning(f"  {slug}: {risk} risk ({partner})")
                else:
                    ui.dim(f"  {slug}: {risk} ({partner})")
        if result: print()

    if skill_name:
        match = [s for s in skills if s["name"] == skill_name]
        if not match:
            match = [s for s in skills if s["name"].lower() == skill_name.lower()]
        if not match:
            ui.error(f"Skill '{skill_name}' not found in {source_str}")
            ui.dim(f"Available: {', '.join(s['name'] for s in skills[:10])}"); return
        ok = install_one(match[0], match[0]["name"], src, source_str, cfg, branch)
        if ok: print(); ui.bold(f"Installed: {match[0]['name']}"); ui.dim(f"Source: {source_str}")
        return

    if install_all:
        print_discovered(skills)
        ok = sum(1 for s in skills if install_one(s, s["name"], src, source_str, cfg, branch))
        print(); ui.success(f"{ok}/{len(skills)} skill(s) installed from {source_str}."); return

    print_discovered(skills)
    try: choice = input(f"  [1-{len(skills)}] Select (comma-separated)  |  [A] All  |  [Enter] Cancel: ").strip()
    except (EOFError, KeyboardInterrupt): print(); return
    if not choice: return

    if choice.upper() == "A":
        selected = skills
    else:
        indices = []
        for part in choice.split(","):
            try:
                idx = int(part.strip()) - 1
                if 0 <= idx < len(skills): indices.append(idx)
            except ValueError: pass
        if not indices: ui.warning("No valid selection."); return
        selected = [skills[i] for i in indices]

    print()
    ok = sum(1 for s in selected if install_one(s, s["name"], src, source_str, cfg, branch))
    print(); ui.success(f"{ok}/{len(selected)} skill(s) installed from {source_str}.")

def cmd_remove(skill_name):
    cfg = SkillsConfig()
    if not re.match(r"^[a-zA-Z0-9_.-]+$", skill_name):
        raise ValueError(f'Invalid: "{skill_name}"')
    src = cfg.get_source(skill_name)
    if src == "built-in":
        ui.warning(f"'{skill_name}' is built-in.")
        try: c = input("    Remove anyway? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt): print(); return
        if c != "y": ui.info("Skipped."); return
    t = cfg.skills_dir / skill_name
    if t.exists():
        shutil.rmtree(t); cfg.remove_skill(skill_name)
        undeploy_from_platform(skill_name, cfg.project_dir)
        ui.success(f"Removed: {skill_name}")
    else: ui.warning(f'"{skill_name}" not found.')

def cmd_list():
    cfg = SkillsConfig()
    tracked = cfg.read().get("skills", {})
    if not cfg.skills_dir.is_dir(): ui.warning("No skills directory."); return
    skills = [{"name": e.name, "source": tracked.get(e.name, {}).get("source", "untracked"),
               "installs": tracked.get(e.name, {}).get("installs", 0)}
              for e in sorted(cfg.skills_dir.iterdir()) if e.is_dir() and (e / "SKILL.md").is_file()]
    if not skills: ui.warning("No skills installed."); return
    bi = [s for s in skills if s["source"] == "built-in"]
    cm = [s for s in skills if s["source"] not in ("built-in", "untracked")]
    ut = [s for s in skills if s["source"] == "untracked"]
    if bi: print(); ui.bold(f"Built-in ({len(bi)}):"); [ui.dim(f"  {s['name']}") for s in bi]
    if cm:
        print(); ui.bold(f"Community ({len(cm)}):")
        for s in cm:
            inst = f"  ({fmt_installs(s['installs'])})" if s["installs"] else ""
            ui.text(f"  {s['name']}  ({s['source']}){inst}")
    if ut: print(); ui.bold(f"Untracked ({len(ut)}):"); [ui.dim(f"  {s['name']}") for s in ut]
    print(); ui.dim(f"  {len(skills)} total")

def cmd_update(target=None):
    cfg = SkillsConfig()
    community = cfg.community_skills()
    if not community: ui.info("No community skills. Built-in update with 'sage upgrade'."); return
    if target and "/" not in target:
        if target not in community:
            if cfg.get_source(target) == "built-in": ui.info(f"'{target}' is built-in. Use 'sage upgrade'.")
            else: ui.warning(f"'{target}' not found.")
            return
        _update_one(target, community[target], cfg); return
    if target and "/" in target:
        matching = {k: v for k, v in community.items() if v.get("source") == target}
        if not matching: ui.warning(f"No skills from {target}"); return
        ui.info(f"Updating {len(matching)} skill(s) from {target}...")
        for n, info in matching.items(): _update_one(n, info, cfg)
        return
    by_src = {}
    for n, info in community.items(): by_src.setdefault(info.get("source", "?"), []).append(n)
    print(); ui.bold("Community skills to update:"); print()
    total = 0
    for i, (src, names) in enumerate(sorted(by_src.items()), 1):
        ui.text(f"  {i}. {src}  ({len(names)} skill{'s' if len(names) != 1 else ''})")
        for n in names: ui.dim(f"     {n}")
        total += len(names)
    print(); ui.text(f"  {len(by_src)} source(s), {total} skill(s)")
    ui.dim("  (Built-in skills update with 'sage upgrade')"); print()
    try: ch = input("  [A] Update all  |  [C] Cancel: ").strip().upper()
    except (EOFError, KeyboardInterrupt): print(); return
    if ch != "A": ui.info("Cancelled."); return
    print(); ok = 0
    for n, info in community.items():
        try: _update_one(n, info, cfg); ok += 1
        except Exception as e: ui.error(f"Failed: {n}: {e}")
    print(); ui.success(f"{ok}/{total} updated.")

def _update_one(name, info, cfg):
    source = info.get("source", "")
    skill_path = info.get("path", f"skills/{name}")
    try: src = parse_source(source)
    except ValueError: ui.error(f"Cannot parse source for {name}: {source}"); return
    target = cfg.skills_dir / name
    if target.exists(): shutil.rmtree(target)
    try:
        if src.type == "github":
            all_skills = discover_skills_github(src.owner, src.repo)
            match = [s for s in all_skills if s["name"] == name]
            if match:
                gh_download_skill(src.owner, src.repo, match[0], target)
            else:
                skill = {"name": name, "path": skill_path, "files": [f"{skill_path}/SKILL.md"]}
                gh_download_skill(src.owner, src.repo, skill, target)
        elif src.type == "wellknown":
            skills = discover_skills_wellknown(src.url)
            match = [s for s in skills if s["name"] == name]
            if match: download_skill_wellknown(match[0], target)
            else: raise FileNotFoundError(f"'{name}' not found at {src.url}")
        elif src.type == "local":
            local_src = Path(src.url) / name
            if local_src.is_dir(): shutil.copytree(local_src, target)
            else: raise FileNotFoundError(f"'{name}' not found at {src.url}")
        deploy_to_platform(name, target, cfg.project_dir)
        ui.success(f"Updated: {name}")
    except Exception as e: ui.error(f"Failed to update {name}: {e}")

# ── CLI ──
def build_parser():
    p = argparse.ArgumentParser(prog="sage-skills", description="Sage skill manager (powered by skills.sh)")
    sub = p.add_subparsers(dest="command", required=True)
    pf = sub.add_parser("find", help="Search skills.sh catalog")
    pf.add_argument("query", help="Search keywords")
    pf.add_argument("--limit", type=int, default=10)
    pf.add_argument("--json", action="store_true")
    pa = sub.add_parser("add", help="Install skills from a source")
    pa.add_argument("source", help="owner/repo, URL, or local path")
    pa.add_argument("--skill", dest="skill_name")
    pa.add_argument("--all", dest="install_all", action="store_true")
    pa.add_argument("--audit", action="store_true")
    pr = sub.add_parser("remove", help="Uninstall a skill")
    pr.add_argument("skill")
    sub.add_parser("list", help="List installed skills")
    pu = sub.add_parser("update", help="Update community skills")
    pu.add_argument("target", nargs="?")
    return p

def main():
    args = build_parser().parse_args()
    try:
        if args.command == "find": cmd_find(args.query, limit=args.limit, as_json=args.json)
        elif args.command == "add": cmd_add(args.source, skill_name=args.skill_name,
                                            install_all=args.install_all, do_audit=args.audit)
        elif args.command == "remove": cmd_remove(args.skill)
        elif args.command == "list": cmd_list()
        elif args.command == "update": cmd_update(target=args.target)
    except (FileNotFoundError, ValueError, RuntimeError) as e: ui.error(str(e)); sys.exit(1)
    except KeyboardInterrupt: print(); sys.exit(130)

if __name__ == "__main__": main()
