#!/usr/bin/env python3
"""把 Homebrew tap 里的真实版本号渲染成一张终端会话 SVG。

**这张图只回答一个问题：怎么装。**

profile 页面自己已经给了身份（侧边栏）、项目是什么（Pinned 卡片）、活跃度
（贡献图）。上一版 README 把这三样又画了一遍 —— 同一份贡献数据上下相隔
200px 出现两次，Pinned 里的四张卡在终端里以 `ls -l` 又列一次。热闹，但信息
量是零。删干净之后剩下的就是原生页面唯一没有的东西：安装命令。

两条刻意的约束：

1. 不依赖任何第三方图床或 Vercel 服务 —— SVG 自己生成、提交进仓库，README
   引相对路径。github-readme-stats 那类服务说挂就挂（写这段时官方实例正好
   是 503），挂了你的门面就空一块。
2. **内容全静态，只有光标会动。**

   README 里的 SVG 由 <img> 加载，而 <img> 语境里的动画支持很不可靠：
   CSS @keyframes 完全不执行；SMIL 的时间轴也不跟真实时间走 —— 试过逐行
   淡入的写法，等 6 秒截图，光标（无限循环的动画）在闪，而所有带
   fill="freeze" 的文本还停在时间轴起点，一片空白。

   同一份文件直接在浏览器里打开一切正常，套进 <img> 就是另一回事。既然
   这是一段 5 行的安装说明，打字动画本来也不是重点，索性让文本全部静态、
   只留一个循环闪烁的光标 —— 那个是实测在 <img> 里可靠的。
"""

import base64
import json
import os
import re
import subprocess

USER = "xinghelee"
TAP = "xinghelee/homebrew-tap"
CASKS = ["termite", "berth"]     # 顺序即展示顺序


def cask(name):
    """从 tap 仓库里读 cask，版本号和描述都用作者自己写的，不另造文案。"""
    raw = subprocess.run(
        ["gh", "api", f"repos/{TAP}/contents/Casks/{name}.rb", "--jq", ".content"],
        capture_output=True, text=True, check=True,
    ).stdout
    src = base64.b64decode(raw).decode()
    pick = lambda k: (re.search(rf'{k}\s+"([^"]+)"', src) or [None, ""])[1]
    return {"name": pick("name"), "version": pick("version"), "desc": pick("desc")}


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


CW = 8.4          # 等宽字体的字符宽度
W = 900
PAD = 26
BAR = 38          # 标题栏高度
LH = 23           # 行高
FS = 13.5

THEMES = {
    "dark": dict(chrome="#2b2f36", bar="#22262c", body="#0f1216", text="#c9d1d9",
                 dim="#6e7681", prompt="#39d353", cmd="#79c0ff", accent="#39d353",
                 ver="#e3b341", shadow="0.45"),
    "light": dict(chrome="#dcdfe4", bar="#eceff3", body="#ffffff", text="#1f2328",
                  dim="#8b949e", prompt="#1a7f37", cmd="#0550ae", accent="#1a7f37",
                  ver="#9a6700", shadow="0.14"),
}


def build(apps, theme):
    t = THEMES[theme]
    pad_name = max(len(a["name"]) for a in apps)
    pad_ver = max(len(a["version"]) for a in apps)

    rows = [("cmd", f"brew tap {TAP.split('/')[0]}/tap"),
            ("cmd", "brew install --cask " + " ".join(CASKS))]
    rows += [("app", a) for a in apps]
    rows.append(("cursor", None))

    y = BAR + PAD
    plan = []
    for kind, payload in rows:
        plan.append((kind, payload, y))
        y += LH
    H = int(y - LH + FS + PAD)

    body = []

    for i, (kind, payload, ly) in enumerate(plan):
        if kind == "cmd":
            body.append(
                f'<text x="{PAD}" y="{ly}" class="mono">'
                f'<tspan fill="{t["prompt"]}">~ $ </tspan>'
                f'<tspan fill="{t["cmd"]}">{esc(payload)}</tspan></text>'
            )
        elif kind == "app":
            a = payload
            x = PAD
            body.append(
                f'<text x="{x}" y="{ly}" class="mono">'
                f'<tspan fill="{t["dim"]}">==&gt; </tspan>'
                f'<tspan fill="{t["accent"]}" font-weight="600">'
                f'{esc(a["name"].ljust(pad_name))}</tspan>'
                f'<tspan fill="{t["ver"]}">  {esc(a["version"].ljust(pad_ver))}</tspan>'
                f'<tspan fill="{t["text"]}">   {esc(a["desc"])}</tspan></text>'
            )
        elif kind == "cursor":
            body.append(
                f'<text x="{PAD}" y="{ly}" class="mono">'
                f'<tspan fill="{t["prompt"]}">~ $ </tspan></text>'
                f'<rect x="{PAD+4*CW}" y="{ly-FS+1}" width="{CW}" height="{FS+2}" '
                f'fill="{t["accent"]}" opacity="1">'
                f'<animate attributeName="opacity" values="0;1;1;0;0" '
                f'keyTimes="0;0.001;0.5;0.501;1" dur="1.1s" '
                f'begin="0s" repeatCount="indefinite"/></rect>'
            )

    dots = "".join(f'<circle cx="{22+i*18}" cy="{BAR/2}" r="6" fill="{c}"/>'
                   for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]))
    style = (".mono{font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,"
             f"'Cascadia Code','Roboto Mono',Consolas,monospace;font-size:{FS}px}}")

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="brew install termite berth">
<title>{USER} — install</title>
<defs><filter id="sh" x="-20%" y="-20%" width="140%" height="140%">
<feDropShadow dx="0" dy="8" stdDeviation="14" flood-opacity="{t["shadow"]}"/></filter>
<clipPath id="win"><rect x="0" y="0" width="{W}" height="{H}" rx="12"/></clipPath></defs>
<style>{style}</style>
<g filter="url(#sh)"><rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="{t["chrome"]}"/></g>
<g clip-path="url(#win)">
<rect x="0" y="0" width="{W}" height="{BAR}" fill="{t["bar"]}"/>
<rect x="0" y="{BAR}" width="{W}" height="{H-BAR}" fill="{t["body"]}"/>
{dots}
<text x="{W/2}" y="{BAR/2+4.5}" text-anchor="middle" class="mono" font-size="12" fill="{t["dim"]}">{USER} — zsh</text>
{"".join(body)}
</g></svg>'''


def main():
    apps = [cask(c) for c in CASKS]
    out = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for theme in ("dark", "light"):
        path = os.path.join(out, f"terminal-{theme}.svg")
        with open(path, "w") as f:
            f.write(build(apps, theme))
        print(f"wrote {path}  {os.path.getsize(path)} bytes")
    for a in apps:
        print(f"  {a['name']} {a['version']} — {a['desc']}")


if __name__ == "__main__":
    main()
