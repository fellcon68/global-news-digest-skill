#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_skill.py — 把技能源码同步到 GitHub 仓库（技能库）
- 若仓库不存在则自动创建（public）
- 递归上传技能目录核心文件（排除 outputs/ 生成物、.git、__pycache__）
- Token 从环境变量 GH_PAGES_TOKEN 或同目录 .ghtoken 读取

用法：
  python publish_skill.py [--repo global-news-digest-skill] [--user fellcon68]
"""
import os, sys, json, base64, argparse
from urllib import request, error

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com"

# 需要跳过的目录/文件
SKIP_DIRS = {".git", "__pycache__", "outputs", "node_modules"}
SKIP_FILES = {".DS_Store", "Thumbs.db", ".ghtoken", ".gitignore"}

EXCLUDE_EXT = set()  # 全部源码都上传

USER_DEFAULT = "fellcon68"
REPO_DEFAULT = "global-news-digest-skill"


def load_token():
    if os.environ.get("GH_PAGES_TOKEN"):
        return os.environ["GH_PAGES_TOKEN"].strip()
    for cand in (os.path.join(SKILL_DIR, ".ghtoken"),
                 os.path.join(os.path.dirname(SKILL_DIR), "github-pages", ".ghtoken")):
        if os.path.exists(cand):
            with open(cand, encoding="utf-8") as f:
                t = f.read().strip()
            if t:
                return t
    return None


def api(method, url, token, data=None, accept="application/vnd.github+json"):
    headers = {"Authorization": "Bearer " + token,
               "Accept": accept}
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    else:
        body = None
    req = request.Request(url, data=body, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=60) as r:
            txt = r.read().decode("utf-8")
            return r.status, (json.loads(txt) if txt else {})
    except error.HTTPError as e:
        txt = e.read().decode("utf-8", "ignore")
        try:
            err = json.loads(txt)
        except Exception:
            err = {"message": txt[:200]}
        return e.code, err
    except Exception as e:
        return 0, {"message": str(e)}


def ensure_repo(user, repo, token):
    st, _ = api("GET", f"{API}/repos/{user}/{repo}", token)
    if st == 200:
        print(f"  [库] {user}/{repo} 已存在，复用")
        return
    if st == 404:
        st2, j2 = api("POST", f"{API}/user/repos", token, {
            "name": repo, "private": False,
            "description": "每日全球热点新闻简要 · WorkBuddy 技能源码（global-news-digest）",
        })
        if st2 in (200, 201):
            print(f"  [库] 已创建 {user}/{repo}")
        else:
            print(f"  [库] 创建失败 HTTP {st2}: {j2.get('message')}")
            sys.exit(1)
        return
    print(f"  [库] 检查仓库失败 HTTP {st}")
    sys.exit(1)


def get_sha(user, repo, path, token):
    st, j = api("GET", f"{API}/repos/{user}/{repo}/contents/{path}", token)
    if st == 200 and isinstance(j, dict) and "sha" in j:
        return j["sha"]
    return None


def upload_file(user, repo, local_path, repo_path, token):
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")
    # 用绝对路径当 message 的唯一锚；GitHub 要求 content 为 base64 字符串
    data = {"message": f"sync skill: {repo_path}", "content": content, "branch": "main"}
    sha = get_sha(user, repo, repo_path, token)
    if sha:
        data["sha"] = sha
    st, j = api("PUT", f"{API}/repos/{user}/{repo}/contents/{repo_path}", token, data)
    if st in (200, 201):
        return True
    print(f"  [上传失败] {repo_path} HTTP {st}: {j.get('message')}")
    return False


def walk_upload(user, repo, token):
    ok = 0
    fail = 0
    for root, dirs, files in os.walk(SKILL_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if fn in SKIP_FILES:
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, SKILL_DIR).replace(os.sep, "/")
            if upload_file(user, repo, full, rel, token):
                ok += 1
            else:
                fail += 1
    return ok, fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=USER_DEFAULT)
    ap.add_argument("--repo", default=REPO_DEFAULT)
    args = ap.parse_args()
    token = load_token()
    if not token:
        sys.stderr.write("未找到 GitHub Token（设置 GH_PAGES_TOKEN 或 .ghtoken）\n")
        sys.exit(1)
    print(f"== 同步技能到 GitHub：{args.user}/{args.repo} ==")
    ensure_repo(args.user, args.repo, token)
    ok, fail = walk_upload(args.user, args.repo, token)
    print(f"== 完成：成功 {ok} 个文件，失败 {fail} 个 ==")
    if fail == 0:
        print(f"GitHub 技能库：https://github.com/{args.user}/{args.repo}")
        print(f"可下载 zip：https://github.com/{args.user}/{args.repo}/archive/refs/heads/main.zip")


if __name__ == "__main__":
    main()
