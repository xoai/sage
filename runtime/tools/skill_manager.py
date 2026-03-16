#!/usr/bin/env python3
"""
skill_manager.py — Skill manager for Sage framework.
Zero pip dependencies — Python 3.8+ stdlib only.

Usage:
    python skill_manager.py find <keyword>              # search + interactive install
    python skill_manager.py find <keyword> --fuzzy      # typo-tolerant search
    python skill_manager.py find <keyword> --refresh    # refresh index first
    python skill_manager.py add <registry> <skill>      # install skill (non-interactive)
    python skill_manager.py remove <skill>              # uninstall skill
    python skill_manager.py list                        # show installed skills
    python skill_manager.py update [target]             # update community skills
    python skill_manager.py index --rebuild             # force rebuild catalog
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

# ── Constants ──
REGISTRY_URL = "https://raw.githubusercontent.com/codeaholicguy/ai-devkit/main/skills/registry.json"
SEED_INDEX_URL = "https://raw.githubusercontent.com/codeaholicguy/ai-devkit/main/skills/index.json"
GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"
HOME = Path.home()
SAGE_GLOBAL = HOME / ".sage"
SKILL_CACHE = SAGE_GLOBAL / "cache"
INDEX_PATH = SAGE_GLOBAL / "skills.json"
SAGE_SKILLS_DIR = "sage/skills"
SKILLS_JSON = "sage/skills/skills.json"
SCRIPT_DIR = Path(__file__).parent
BUNDLED_SEED = SCRIPT_DIR / "seed" / "index.json"

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
def http_get(url,*,accept="application/json",timeout=15):
    from urllib.request import Request,urlopen
    r = Request(url,headers={"Accept":accept,"User-Agent":"sage/1.0"})
    with urlopen(r,timeout=timeout) as resp: return resp.read()
def http_json(url,**kw): return json.loads(http_get(url,**kw))

# ── Git (optional) ──
def has_git():
    try: subprocess.run(["git","--version"],capture_output=True,check=True); return True
    except: return False
def git_clone(dest,url):
    dest.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(["git","clone","--depth","1","--quiet",url,str(dest)],
                   capture_output=True,check=True,timeout=120)
def git_ls_remote(url):
    try:
        r=subprocess.run(["git","ls-remote",url,"HEAD"],capture_output=True,text=True,timeout=30)
        if r.returncode==0 and r.stdout.strip(): return r.stdout.strip().split()[0]
    except: pass
    return None

# ── GitHub API ──
def parse_gh(url):
    m=re.search(r"github\.com/([^/]+)/([^/.]+)",url)
    return (m.group(1),m.group(2)) if m else None

def gh_skill_files(owner,repo,skill_path):
    try:
        data=http_json(f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1")
        pfx=f"{skill_path}/"
        return [i["path"] for i in data.get("tree",[]) if i.get("type")=="blob" and i["path"].startswith(pfx)]
    except: return []

def gh_skill_dirs(owner,repo):
    try:
        data=http_json(f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1")
        return [str(Path(i["path"]).parent) for i in data.get("tree",[])
                if i.get("type")=="blob" and re.match(r"^skills/[^/]+/SKILL\.md$",i.get("path",""))]
    except: return []

def gh_download(owner,repo,path):
    for branch in ["HEAD","main","master"]:
        try: return http_get(f"{GITHUB_RAW}/{owner}/{repo}/{branch}/{path}",accept="application/octet-stream")
        except: continue
    return None

def download_skill_api(owner,repo,skill_path,dest):
    files=gh_skill_files(owner,repo,skill_path)
    if not files: raise FileNotFoundError(f"No files at {skill_path} in {owner}/{repo}")
    dest.mkdir(parents=True,exist_ok=True)
    n=0
    for fp in files:
        content=gh_download(owner,repo,fp)
        if not content: continue
        rel=fp[len(skill_path)+1:]
        local=dest/rel
        local.parent.mkdir(parents=True,exist_ok=True)
        local.write_bytes(content); n+=1
    if n==0: shutil.rmtree(dest,ignore_errors=True); raise RuntimeError("Download failed")
    return n

# ── Config ──
class SkillsConfig:
    def __init__(self,project_dir=None):
        self.project_dir=project_dir or Path.cwd()
        self.config_path=self.project_dir/SKILLS_JSON
        self.skills_dir=self.project_dir/SAGE_SKILLS_DIR
    def exists(self): return self.config_path.is_file()
    def read(self):
        if not self.exists(): return {"skills":{}}
        with open(self.config_path) as f: return json.load(f)
    def write(self,cfg):
        self.config_path.parent.mkdir(parents=True,exist_ok=True)
        with open(self.config_path,"w") as f: json.dump(cfg,f,indent=2)
    def add_skill(self,name,registry):
        c=self.read(); c.setdefault("skills",{})[name]={"source":registry,"added":time.strftime("%Y-%m-%d")}; self.write(c)
    def remove_skill(self,name):
        c=self.read(); c.get("skills",{}).pop(name,None); self.write(c)
    def get_source(self,name):
        e=self.read().get("skills",{}).get(name); return e.get("source") if e else None
    def community_skills(self):
        return {k:v for k,v in self.read().get("skills",{}).items() if v.get("source")!="built-in"}
    def get_registries(self): return {}

# ── Platform deploy ──
def deploy_to_platform(name,source_dir,project_dir):
    agent=project_dir/".agent"/"skills"
    if agent.is_dir():
        dest=agent/name
        if dest.exists(): shutil.rmtree(dest)
        shutil.copytree(source_dir,dest)
        for cf in list(source_dir.glob("constitution/*.md"))+list(source_dir.glob("*constitution*.md")):
            rules=project_dir/".agent"/"rules"
            if rules.is_dir(): shutil.copy2(cf,rules/f"skill-{name}-constitution.md")
        ui.success(f"Deployed to .agent/skills/{name}/")
    claude=project_dir/".claude"
    if claude.is_dir() and not agent.is_dir():
        ui.dim(f"Available at sage/skills/{name}/ (Claude Code reads on-demand)")

def undeploy_from_platform(name,project_dir):
    p=project_dir/".agent"/"skills"/name
    if p.exists(): shutil.rmtree(p); ui.success(f"Removed from .agent/skills/{name}/")
    r=project_dir/".agent"/"rules"/f"skill-{name}-constitution.md"
    if r.exists(): r.unlink()

# ── Registry & Index ──
def fetch_registry(cfg):
    try: default=http_json(REGISTRY_URL).get("registries",{})
    except Exception as e: ui.warning(f"Registry fetch failed: {e}"); default={}
    return {**default,**cfg.get_registries()}

def load_index():
    if not INDEX_PATH.is_file(): return None
    try:
        with open(INDEX_PATH) as f: return json.load(f)
    except: return None

def save_index(idx,path=None):
    t=path or INDEX_PATH; t.parent.mkdir(parents=True,exist_ok=True)
    with open(t,"w") as f: json.dump(idx,f,indent=2)

def ensure_index(cfg,force_refresh=False):
    existing=load_index()
    if existing and not force_refresh: return existing
    if force_refresh:
        try:
            ui.info("Refreshing skill index...")
            data=http_json(SEED_INDEX_URL,timeout=30); save_index(data)
            ui.success(f"Index refreshed: {len(data.get('skills',[]))} skills"); return data
        except Exception as e:
            ui.warning(f"Refresh failed: {e}")
            if existing: ui.warning("Using existing index"); return existing
    if BUNDLED_SEED.is_file():
        try:
            with open(BUNDLED_SEED) as f: seed=json.load(f)
            save_index(seed); ui.dim(f"Loaded bundled catalog: {len(seed.get('skills',[]))} skills"); return seed
        except: pass
    try:
        data=http_json(SEED_INDEX_URL,timeout=30); save_index(data)
        ui.success(f"Index fetched: {len(data.get('skills',[]))} skills"); return data
    except: pass
    raise RuntimeError("No skill index available. Run with --refresh.")

def extract_desc(content):
    found=False
    for line in content.strip().splitlines():
        s=line.strip()
        if not s: continue
        if s.startswith("#"): found=True; continue
        if found or not s.startswith("#"): return re.sub(r"\*\*|__|\*|_|`","",s)
    return ""

# ── Search ──
def _norm(skills):
    for s in skills:
        if "_text" not in s:
            s["_name"]=s.get("name","").lower(); s["_desc"]=s.get("description","").lower()
            s["_text"]=f'{s["_name"]} {s["_desc"]}'
    return skills

def search_exact(skills,keywords):
    skills=_norm(skills); nh,dh=[],[]
    for s in skills:
        if not all(k in s["_text"] for k in keywords): continue
        (nh if any(k in s["_name"] for k in keywords) else dh).append(s)
    return nh+dh

def search_fuzzy(skills,keywords,threshold=0.75):
    skills=_norm(skills); scored=[]
    for s in skills:
        score,ok=0.0,True
        for kw in keywords:
            if kw in s["_text"]: score+=3.0 if kw in s["_name"] else 1.0; continue
            cands=[w for w in s["_text"].split() if abs(len(w)-len(kw))<=2 and len(w)>=3]
            if not cands: ok=False; break
            best=max((SequenceMatcher(None,kw,w).ratio(),w) for w in cands)
            if best[0]>=threshold: score+=(2.0 if best[1] in s["_name"] else 0.5)+best[0]
            else: ok=False; break
        if ok and score>0: scored.append((score,s))
    scored.sort(key=lambda x:x[0],reverse=True)
    return [s for _,s in scored]

# ── Display ──
def print_skills(skills,*,as_json=False,top=None):
    if top: skills=skills[:top]
    if as_json:
        print(json.dumps([{k:s.get(k) for k in ("name","registry","description","path")} for s in skills],indent=2)); return
    if not skills: ui.text("No results found."); return
    max_name=min(max(len(s.get("name","")) for s in skills),40)
    tw=shutil.get_terminal_size((80,24)).columns
    print(); ui.bold(f"Found {len(skills)} skill(s):"); print()
    for i,s in enumerate(skills,1):
        name=s.get("name","?"); reg=s.get("registry","unknown"); desc=s.get("description","")
        dmax=tw-10
        if len(desc)>dmax: desc=desc[:dmax-3]+"..."
        pad=max_name-len(name)+2
        num=ui._c("dim",f"  {i:>3} ")
        nm=ui._c("bold",f" {name}")
        rg=ui._c("dim",f"{'·'*pad} {reg}")
        print(f"{num}{nm}{rg}")
        if desc: print(ui._c("dim",f"       {desc}"))
        print()

def interactive_install(results,cfg):
    if not results or not sys.stdout.isatty(): return
    installed=0
    while True:
        try: choice=input(f"  [1-{len(results)}] Install  |  [Enter] Done: ").strip()
        except (EOFError,KeyboardInterrupt): print(); break
        if not choice: break
        try:
            idx=int(choice)-1
            if 0<=idx<len(results):
                s=results[idx]; add_skill(s["registry"],s["name"],cfg); installed+=1
            else: ui.warning(f"Enter 1-{len(results)}")
        except ValueError:
            if choice.lower() in ("q","quit","done"): break
            ui.warning("Enter a number or press Enter.")
    if installed: print(); ui.success(f"{installed} skill(s) installed.")

# ── Skill operations ──
def add_skill(registry_id,skill_name,cfg):
    if not re.match(r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$",registry_id):
        raise ValueError(f'Invalid registry: "{registry_id}"')
    if not re.match(r"^[a-zA-Z0-9_-]+$",skill_name):
        raise ValueError(f'Invalid skill: "{skill_name}"')
    ui.info(f"Adding: {skill_name} from {registry_id}")
    regs=fetch_registry(cfg)
    git_url=regs.get(registry_id,f"https://github.com/{registry_id}.git")
    parsed=parse_gh(git_url)
    if not parsed: raise ValueError(f"Cannot parse: {registry_id}")
    owner,repo=parsed
    install_name=skill_name; target=cfg.skills_dir/install_name
    if target.exists():
        src=cfg.get_source(skill_name) or "unknown"
        print(); ui.warning(f"Skill '{skill_name}' already exists"); ui.dim(f"From: {src}"); print()
        alt=f"{skill_name}-{registry_id.split('/')[0]}"
        print(f"    1) Skip — keep existing"); print(f"    2) Replace — overwrite with {registry_id}")
        print(f"    3) Install as '{alt}' — keep both"); print()
        try: ch=input("    Choice [1]: ").strip() or "1"
        except: print(); return
        if ch=="1": ui.info("Skipped."); return
        elif ch=="2": shutil.rmtree(target); undeploy_from_platform(skill_name,cfg.project_dir)
        elif ch=="3":
            install_name=alt; target=cfg.skills_dir/install_name
            if target.exists(): ui.error(f"'{alt}' also exists."); return
        else: ui.info("Skipped."); return
    sp=f"skills/{skill_name}"
    try:
        ui.dim(f"Downloading {skill_name}...")
        n=download_skill_api(owner,repo,sp,target)
        ui.success(f"Downloaded {n} files to sage/skills/{install_name}/")
    except Exception as e1:
        if has_git():
            ui.dim("API failed, trying git...")
            cache=SKILL_CACHE/registry_id
            if not cache.is_dir(): git_clone(cache,git_url)
            src=cache/"skills"/skill_name
            if not src.is_dir(): raise FileNotFoundError(f'"{skill_name}" not in {registry_id}')
            shutil.copytree(src,target); ui.success(f"Copied to sage/skills/{install_name}/")
        else: raise RuntimeError(f"Download failed: {e1}")
    cfg.add_skill(install_name,registry_id); ui.success("Tracked in skills.json")
    deploy_to_platform(install_name,target,cfg.project_dir)
    print(); ui.bold(f"Installed: {install_name}"); ui.dim(f"Source: {registry_id}")

def remove_skill(skill_name,cfg):
    if not re.match(r"^[a-zA-Z0-9_-]+$",skill_name): raise ValueError(f'Invalid: "{skill_name}"')
    src=cfg.get_source(skill_name)
    if src=="built-in":
        ui.warning(f"'{skill_name}' is built-in.")
        try: c=input("    Remove anyway? [y/N]: ").strip().lower()
        except: print(); return
        if c!="y": ui.info("Skipped."); return
    t=cfg.skills_dir/skill_name
    if t.exists():
        shutil.rmtree(t); cfg.remove_skill(skill_name)
        undeploy_from_platform(skill_name,cfg.project_dir)
        ui.success(f"Removed: {skill_name}")
    else: ui.warning(f'"{skill_name}" not found.')

def list_skills(cfg):
    tracked=cfg.read().get("skills",{})
    if not cfg.skills_dir.is_dir(): return []
    return [{"name":e.name,"source":tracked.get(e.name,{}).get("source","untracked")}
            for e in sorted(cfg.skills_dir.iterdir()) if e.is_dir() and (e/"SKILL.md").is_file()]

def update_skills(cfg,target=None):
    community=cfg.community_skills()
    if not community: ui.info("No community skills. Built-in update with 'sage upgrade'."); return
    if target and "/" not in target:
        if target not in community:
            if cfg.get_source(target)=="built-in": ui.info(f"'{target}' is built-in. Use 'sage upgrade'.")
            else: ui.warning(f"'{target}' not found.")
            return
        info=community[target]; ui.info(f"Updating: {target}")
        _update_one(target,info["source"],cfg); return
    if target and "/" in target:
        matching={k:v for k,v in community.items() if v.get("source")==target}
        if not matching: ui.warning(f"No skills from {target}"); return
        ui.info(f"Skills from {target}:"); [ui.text(f"    {n}") for n in matching]; print()
        try: c=input(f"  Update {len(matching)} skill(s)? [Y/n]: ").strip().lower()
        except: print(); return
        if c=="n": return
        for n,i in matching.items(): _update_one(n,i["source"],cfg)
        return
    by_reg={}
    for n,i in community.items(): by_reg.setdefault(i.get("source","?"),[]).append(n)
    print(); ui.bold("Community skills to update:"); print()
    total=0
    for i,(reg,names) in enumerate(sorted(by_reg.items()),1):
        ui.text(f"  {i}. {reg}  ({len(names)} skill{'s' if len(names)!=1 else ''})")
        for n in names: ui.dim(f"     {n}")
        total+=len(names)
    print()
    ui.text(f"  {len(by_reg)} repo(s), {total} skill(s)")
    ui.dim("  (Built-in skills update with 'sage upgrade')"); print()
    try: ch=input("  [A] Update all  |  [C] Cancel: ").strip().upper()
    except: print(); return
    if ch!="A": ui.info("Cancelled."); return
    print(); ok=0
    for n,i in community.items():
        try: _update_one(n,i["source"],cfg); ok+=1
        except Exception as e: ui.error(f"Failed: {n}: {e}")
    print(); ui.success(f"{ok}/{total} updated.")

def _update_one(name,registry_id,cfg):
    parsed=parse_gh(f"https://github.com/{registry_id}.git")
    if not parsed: ui.error(f"Cannot parse: {registry_id}"); return
    owner,repo=parsed; target=cfg.skills_dir/name
    if target.exists(): shutil.rmtree(target)
    try:
        download_skill_api(owner,repo,f"skills/{name}",target)
        deploy_to_platform(name,target,cfg.project_dir)
        ui.success(f"Updated: {name}")
    except Exception as e: ui.error(f"Failed: {name} — {e}")

# ── CLI ──
def build_parser():
    p=argparse.ArgumentParser(prog="sage-skills",description="Sage skill manager")
    sub=p.add_subparsers(dest="command",required=True)
    pf=sub.add_parser("find"); pf.add_argument("query"); pf.add_argument("--fuzzy",action="store_true")
    pf.add_argument("--top",type=int); pf.add_argument("--json",action="store_true")
    pf.add_argument("--refresh",action="store_true")
    pa=sub.add_parser("add"); pa.add_argument("registry"); pa.add_argument("skill")
    pr=sub.add_parser("remove"); pr.add_argument("skill")
    sub.add_parser("list")
    pu=sub.add_parser("update"); pu.add_argument("target",nargs="?")
    pi=sub.add_parser("index"); pi.add_argument("--rebuild",action="store_true"); pi.add_argument("--stats",action="store_true")
    return p

def main():
    args=build_parser().parse_args(); cfg=SkillsConfig()
    try:
        if args.command=="find":
            idx=ensure_index(cfg,force_refresh=args.refresh)
            kw=args.query.lower().split()
            res=search_fuzzy(idx["skills"],kw) if args.fuzzy else search_exact(idx["skills"],kw)
            if args.top: res=res[:args.top]
            print_skills(res,as_json=args.json)
            if not args.json: interactive_install(res,cfg)
        elif args.command=="add": add_skill(args.registry,args.skill,cfg)
        elif args.command=="remove": remove_skill(args.skill,cfg)
        elif args.command=="list":
            skills=list_skills(cfg)
            if skills:
                bi=[s for s in skills if s["source"]=="built-in"]
                cm=[s for s in skills if s["source"]!="built-in"]
                if bi: print(); ui.bold(f"Built-in ({len(bi)}):"); [ui.dim(f"  {s['name']}") for s in bi]
                if cm: print(); ui.bold(f"Community ({len(cm)}):"); [ui.text(f"  {s['name']}  ({s['source']})") for s in cm]
                print(); ui.dim(f"  {len(skills)} total")
            else: ui.warning("No skills found.")
        elif args.command=="update": update_skills(cfg,target=args.target)
        elif args.command=="index":
            if args.stats:
                idx=load_index()
                if not idx: ui.warning("No index."); return
                print(); ui.bold("Index stats")
                ui.text(f"  Skills: {len(idx.get('skills',[]))}"); ui.text(f"  File: {INDEX_PATH}")
            elif args.rebuild:
                regs=fetch_registry(cfg); idx=ensure_index(cfg,force_refresh=True)
                ui.success(f"Index rebuilt: {len(idx['skills'])} skills")
            else: idx=ensure_index(cfg); ui.success(f"Index ready: {len(idx['skills'])} skills")
    except (FileNotFoundError,ValueError,RuntimeError) as e: ui.error(str(e)); sys.exit(1)
    except KeyboardInterrupt: print(); sys.exit(130)

if __name__=="__main__": main()
