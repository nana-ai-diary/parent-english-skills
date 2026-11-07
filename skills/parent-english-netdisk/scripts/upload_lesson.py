#!/usr/bin/env python3
"""把亲子英语某课的 MP4(定稿)/PDF/整视频MP3 上传到【夸克】和【百度】两个网盘的
《油管亲子英语》/<序号>.<主题>/ 下，文件名统一为 <序号>.<主题>.<ext>。

规则（与用户确认的永久规则一致）：
  - 视频 MP4：取自 <DELIVERY_DIR>/<序号>.<主题>.mp4（定稿原片，
    绝不用项目里压缩过的 video/*.mp4）。
  - 音频 MP3 + PDF：取自项目 outputs/亲子英语/<slug>/audio 与 全套PDF。
  - 命名：<序号>.<主题>.<ext>（如 47.警察.mp4 / 47.警察.mp3 / 47.警察.pdf）。
  - 目标文件夹：两个网盘都用《油管亲子英语》/<序号>.<主题>/（百度落在 /apps/bdpan/ 下）。
  - PDF 与 MP3 两个网盘都要传（MP4 也传）。

用法:
    python upload_lesson.py --no 46 --project <项目根> [--root 油管亲子英语] [--apply]
默认 dry-run：只打印将要上传的文件与目标，不实际上传；加 --apply 才真传。
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from threading import Lock

DEFAULT_EXE = os.path.expanduser("<TOOLS_DIR>/quark-nd-mcp/quark-nd-mcp.exe")
DEFAULT_CFG = os.path.expanduser("<QUARK_CONFIG>")


class MCP:
    def __init__(self, exe, cfg):
        self.proc = subprocess.Popen([exe, "-config", cfg],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, encoding="utf-8")
        self.lines = []
        self.lock = Lock()
        self.id = 0
        threading.Thread(target=self._reader, daemon=True).start()
        self._send({"jsonrpc": "2.0", "id": 99999, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "ul", "version": "1"}}})
        time.sleep(1.2)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        time.sleep(0.3)

    def _reader(self):
        try:
            for line in self.proc.stdout:
                with self.lock:
                    self.lines.append(line)
        except Exception:
            pass

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def call(self, name, args, timeout=60):
        self.id += 1
        myid = self.id
        self._send({"jsonrpc": "2.0", "id": myid, "method": "tools/call",
                    "params": {"name": name, "arguments": args}})
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                for i, l in enumerate(self.lines):
                    try:
                        o = json.loads(l)
                    except Exception:
                        continue
                    if o.get("id") == myid:
                        # 归一化工具级错误：本 MCP 把失败包成 result.isError=true，
                        # 而非 JSON-RPC 顶层 error。统一成顶层 error，方便调用方判定。
                        res = o.get("result")
                        if isinstance(res, dict) and res.get("isError"):
                            txt = "".join(c.get("text", "")
                                          for c in res.get("content", [])
                                          if isinstance(c, dict))
                            o["error"] = txt or "tool reported isError"
                        del self.lines[i]
                        return o
            time.sleep(0.2)
        return None

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


def find_lesson(series_path, no):
    d = json.load(open(series_path, encoding="utf-8"))
    lessons = d.get("lessons", [])
    for l in lessons:
        if str(l.get("n")) == no:
            return l
    for l in lessons:
        if no in str(l.get("slug", "")):
            return l
    return None


def collect_sources(out, slug, no, zh):
    """按目录扫描 + 前缀/特征匹配，兼容真实命名（不强制 <slug>.mp4 / full.mp3）。"""
    sources = []
    # ---- MP4：优先「定稿」目录 <序号>.<主题>.mp4（高清成品）；否则退回项目 video/ 下任意 .mp4 ----
    final_dir = os.path.expanduser("<DELIVERY_DIR>")
    final_mp4 = os.path.join(final_dir, "%s.%s.mp4" % (no, zh))
    if os.path.isfile(final_mp4):
        sources.append((final_mp4, "MP4视频"))
    else:
        vd = os.path.join(out, slug, "video")
        if os.path.isdir(vd):
            mp4s = [f for f in os.listdir(vd) if f.lower().endswith(".mp4")]
            mp4 = None
            for key in (slug, zh):                       # 优先含 slug / zh 的文件名
                hit = [f for f in mp4s if key and key in f]
                if hit:
                    mp4 = hit[0]
                    break
            if not mp4 and mp4s:                         # 退路：取体积最大者
                mp4 = max(mp4s, key=lambda f: os.path.getsize(os.path.join(vd, f)))
            if mp4:
                sources.append((os.path.join(vd, mp4), "MP4视频"))
            else:
                print("WARN  缺失 MP4视频:", vd)
        else:
            print("WARN  缺失 video 目录:", vd)

    # ---- MP3：整视频音频。full.mp3 → <序号>.<...>.mp3 → 任意非 seg 的 mp3 ----
    ad = os.path.join(out, slug, "audio")
    mp3 = None
    if os.path.isdir(ad):
        files = os.listdir(ad)
        h = [f for f in files if f.lower() == "full.mp3"]
        if not h:
            h = [f for f in files
                 if f.startswith(no + ".") and f.lower().endswith(".mp3")]
        if not h:
            h = [f for f in files
                 if f.lower().endswith(".mp3") and not re.match(r"seg\d+", f, re.I)]
        if h:
            mp3 = os.path.join(ad, h[0])
    if mp3 and os.path.isfile(mp3):
        sources.append((mp3, "整视频MP3"))
    else:
        print("WARN  缺失 整视频MP3:", ad)

    # ---- PDF：全套PDF/ 下 <序号>. 前缀的 .pdf（可能多个，全收）----
    pdf_dir = os.path.join(out, "全套PDF")
    if os.path.isdir(pdf_dir):
        pdfs = [f for f in os.listdir(pdf_dir)
                if f.startswith(no + ".") and f.lower().endswith(".pdf")]
        for f in pdfs:
            sources.append((os.path.join(pdf_dir, f), "PDF"))
    else:
        print("WARN  缺失 全套PDF 目录:", pdf_dir)
    return sources


def resolve_target(mcp, root, no, candidate):
    """list 父目录，按「序号.」前缀复用已有文件夹；未命中返回 candidate（待新建）。"""
    r = mcp.call("list_files", {"path": "/%s" % root}, timeout=20)
    if r and "result" in r:
        try:
            items = json.loads(r["result"]["content"][0]["text"])
        except Exception:
            items = []
        for it in items:
            if it.get("is_folder") and it.get("name", "").startswith(no + "."):
                return "/%s/%s" % (root, it["name"]), it["name"]
    return candidate, None


def dest_names(no, zh, sources):
    """计算每类资源在网盘上的文件名：<序号>.<主题>.<ext>（与 PDF 命名一致）。
    多个同类型（如多份 PDF）追加 _2/_3 避免互相覆盖。返回的 name 是网盘目标名，
    本地文件名可能不同（如 video/police-officer.mp4），上传时按 name 做临时副本改名。"""
    kind_by_label = {"MP4视频": "mp4", "整视频MP3": "mp3", "PDF": "pdf"}
    counters = {}
    out = []
    for p, label in sources:
        kind = kind_by_label.get(label, "file")
        counters[kind] = counters.get(kind, 0) + 1
        if kind == "pdf" and counters[kind] > 1:
            name = "%s.%s_%d.pdf" % (no, zh, counters[kind])
        else:
            name = "%s.%s.%s" % (no, zh, kind)
        out.append((p, label, name))
    return out


# ===================== 百度网盘（bdpan CLI） =====================
def find_bdpan():
    """定位 bdpan 命令行可执行文件。"""
    cands = [
        os.path.expanduser("<BDPAN_EXE>"),
        os.path.expanduser("~/.local/bdpan/versions/3.8.4/bdpan.exe"),
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    return shutil.which("bdpan")


def bdpan_env():
    """bdpan(Go CLI) 不读系统代理，须显式注入；本机用 本机代理 <PROXY>。
    若环境已配代理则不覆盖；可用 BD_PAN_PROXY 显式指定。"""
    env = os.environ.copy()
    proxy = env.get("BD_PAN_PROXY")
    if not proxy and "HTTP_PROXY" not in env and "HTTPS_PROXY" not in env:
        proxy = "<PROXY>"
    if proxy:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            env[k] = proxy
    return env


def _parse_bdpan_json(text):
    """bdpan 可能输出多段 JSON，稳妥截取首个 [..] 或 {..} 段。"""
    try:
        s = (text or "").strip()
        i, j = s.find("["), s.rfind("]")
        if i != -1 and j > i:
            return json.loads(s[i:j + 1])
        i, j = s.find("{"), s.rfind("}")
        if i != -1 and j > i:
            return json.loads(s[i:j + 1])
    except Exception:
        pass
    return None


def baidu_ls(bdpan, path, env):
    """返回 {文件名: 大小}（仅文件）。"""
    try:
        r = subprocess.run([bdpan, "ls", path, "--json"], env=env,
                           capture_output=True, text=True, timeout=40)
        data = _parse_bdpan_json(r.stdout)
    except Exception:
        return {}
    out = {}
    if isinstance(data, list):
        for it in data:
            if isinstance(it, dict) and not it.get("isdir"):
                out[it.get("server_filename")] = it.get("size")
    return out


def baidu_mkdir(bdpan, path, env):
    try:
        r = subprocess.run([bdpan, "mkdir", path], env=env,
                           capture_output=True, text=True, timeout=40)
        return '"status": "ok"' in (r.stdout + r.stderr)
    except Exception:
        return False


def baidu_upload_file(bdpan, local, remote, env, overwrite, src_size):
    cmd = [bdpan, "upload", local, remote]
    if overwrite:
        cmd.append("--overwrite")
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True,
                           timeout=max(300, int(src_size / 1024 / 1024 * 3) + 120))
        ok = '"status": "ok"' in (r.stdout + r.stderr)
    except Exception as e:
        print("FAIL  [百度] %s -> %s : %s" % (os.path.basename(local), remote, e))
        return
    if ok:
        print("OK    [百度] %s -> %s" % (os.path.basename(local), remote))
    else:
        print("FAIL  [百度] %s -> %s : %s" % (
            os.path.basename(local), remote, (r.stdout + r.stderr)[:300]))


def baidu_upload(root, no, zh, sources, apply):
    """把同一批 (本地路径, 标签, 网盘名) 上传到百度《油管亲子英语》/<序号>.<主题>/。"""
    bdpan = find_bdpan()
    if not bdpan:
        print("WARN  找不到 bdpan 命令行，跳过百度上传（安装后重跑即可）。")
        return
    env = bdpan_env()
    folder = "%s/%s.%s" % (root, no, zh)
    if apply:
        baidu_mkdir(bdpan, root, env)          # 根文件夹（已存在则忽略）
        baidu_mkdir(bdpan, folder, env)        # 课程文件夹
        existing = baidu_ls(bdpan, folder, env)
    else:
        existing = {}
    for p, label, name in dest_names(no, zh, sources):
        remote = "%s/%s" % (folder, name)
        if apply:
            src_size = os.path.getsize(p)
            if name in existing and existing[name] == src_size:
                print("SKIP  [百度][%s] %s 已存在且大小一致，跳过" % (label, name))
                continue
            if os.path.basename(p) == name:
                up, tmp = p, None
            else:
                tmp = tempfile.mkdtemp(prefix="bd_")
                up = os.path.join(tmp, name)
                shutil.copy2(p, up)            # 临时副本改名，不动本地
            baidu_upload_file(bdpan, up, remote, env,
                              overwrite=(name in existing), src_size=src_size)
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            flag = "" if os.path.basename(p) == name else "  (本地为 %s，上传时改名)" % os.path.basename(p)
            print("  [百度][%s] %s%s" % (label, name, flag))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no", required=True, help="课程号，如 46")
    ap.add_argument("--project", required=True,
                    help="parent-english-html 项目根（含 outputs/ 与 tools/series.json）")
    ap.add_argument("--root", default="油管亲子英语", help="夸克网盘根下的父文件夹")
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--cfg", default=DEFAULT_CFG)
    ap.add_argument("--apply", action="store_true", help="默认 dry-run；加此开关才真实上传")
    args = ap.parse_args()

    # 1) lesson
    sp = os.path.join(args.project, "tools", "series.json")
    if not os.path.isfile(sp):
        sp = os.path.join(args.project, "series.json")
    if not os.path.isfile(sp):
        print("ERROR: 找不到 series.json:", sp)
        sys.exit(1)
    lesson = find_lesson(sp, args.no)
    if not lesson:
        print("ERROR: series.json 找不到序号", args.no)
        sys.exit(1)
    slug = lesson["slug"]
    zh = lesson.get("zh", "")

    # 2) 源文件（按目录扫描 + 前缀/特征匹配，兼容真实命名）
    out = os.path.join(args.project, "outputs", "亲子英语")
    sources = collect_sources(out, slug, args.no, zh)
    if not sources:
        print("ERROR: 无任何可上传文件")
        sys.exit(1)

    candidate = "/%s/%s.%s" % (args.root, args.no, zh)
    print("课程 %s -> slug=%s zh=%s" % (args.no, slug, zh))
    print("候选目标文件夹（无复用时新建）: %s" % candidate)
    print("待上传文件:")
    for p, label in sources:
        print("  [%s] %s" % (label, p))

    if not args.apply:
        # dry-run：连一次网盘，预测会复用还是新建哪个文件夹（读操作，安全）
        print("\n[夸克 dry-run] 目标文件名（统一为 <序号>.<主题>.<ext>）:")
        for p, label, name in dest_names(args.no, zh, sources):
            flag = "" if os.path.basename(p) == name else "  (本地为 %s，上传时改名)" % os.path.basename(p)
            print("  [%s] %s%s" % (label, name, flag))
        print("\n[百度 dry-run] 目标文件名预览:")
        baidu_upload(args.root, args.no, zh, sources, apply=False)
        try:
            mcp = MCP(args.exe, args.cfg)
            target, hit = resolve_target(mcp, args.root, args.no, candidate)
            mcp.close()
            if hit:
                print("\n[dry-run] 预测命中已有文件夹，将复用: %s" % target)
            else:
                print("\n[dry-run] 预测将新建文件夹: %s" % target)
        except Exception as e:
            print("\n[dry-run] 未连网盘预览（忽略）: %s" % e)
        print("[dry-run] 以上为预览，未实际上传。确认无误后加 --apply 真实上传。")
        return

    # 3) 真实上传（网盘文件名统一为 <序号>.<主题>.<ext>；本地文件名不同时用临时副本改名上传）
    mcp = MCP(args.exe, args.cfg)
    tmpdir = tempfile.mkdtemp(prefix="ul_")
    try:
        target, hit = resolve_target(mcp, args.root, args.no, candidate)
        if hit:
            print("命中已有文件夹，复用: %s" % target)
        else:
            cr = mcp.call("create_folder", {"path": candidate}, timeout=20)
            if cr and "error" in cr:
                print("WARN  create_folder 失败:", cr["error"])
                target = candidate
            else:
                print("已新建文件夹: %s" % candidate)
                target = candidate
        # 已存在的文件名→大小：同名且大小一致才跳过；大小不一致则重传（幂等且能覆盖旧版）
        existing_sizes = {}
        lr = mcp.call("list_files", {"path": target}, timeout=25)
        if lr and "result" in lr:
            try:
                for it in json.loads(lr["result"]["content"][0]["text"]):
                    existing_sizes[it.get("name")] = it.get("size")
            except Exception:
                pass
        for p, label, name in dest_names(args.no, zh, sources):
            src_size = os.path.getsize(p)
            if name in existing_sizes:
                if existing_sizes[name] == src_size:
                    print("SKIP  [%s] %s 已存在且大小一致，跳过" % (label, name))
                    continue
                print("UPDATE [%s] %s 大小不一致，重新上传" % (label, name))
                mcp.call("delete", {"paths": [target + "/" + name]}, timeout=30)
            if os.path.basename(p) == name:
                up = p  # 本地已是目标名，直接传
            else:
                up = os.path.join(tmpdir, name)
                shutil.copy2(p, up)  # 临时副本改名，不动本地工作文件
            ur = mcp.call("upload_file", {"dest_path": target, "local_path": up},
                          timeout=max(300, int(src_size / 1024 / 1024 * 3) + 120))
            if ur and "error" in ur:
                print("FAIL  [%s] %s -> %s" % (label, name, ur["error"]))
            else:
                print("OK    [%s] %s -> %s" % (label, name, target))
        # 百度网盘上传（同一批文件，目标文件夹同为 油管亲子英语/<序号>.<主题>/）
        print("\n===== 百度网盘上传 =====")
        baidu_upload(args.root, args.no, zh, sources, apply=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        mcp.close()


if __name__ == "__main__":
    main()
