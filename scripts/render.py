#!/usr/bin/env python3
"""把 GitHub 的真实数据渲染成一张终端会话 SVG。

两条刻意的约束：

1. 不依赖任何第三方图床或 Vercel 服务 —— 生成的 SVG 直接提交回本仓库，
   README 引用相对路径。别人的服务挂了（github-readme-stats 就经常 503），
   这张图照样在。
2. 动画一律用 SMIL <animate>，不用 CSS @keyframes。GitHub 的 README 是用
   <img> 加载 SVG 的，而在 <img> 语境里 CSS 动画不执行 —— 实测过：直接打开
   SVG 动画正常，套进 <img> 就永远停在 opacity:0，整张图只剩窗口框。
"""

import json
import os
import subprocess
import sys
from datetime import date

USER = os.environ.get("PROFILE_USER", "xinghelee")
SITE = "xinghelee.com"
TAGLINE = "I build small, focused native tools."

# 展示哪些项目、以及给它们一句人话说明。写死顺序是有意的：
# 按“我最想让人先看到什么”排，而不是按 star 排。
PROJECTS = [
    ("Termite", "macOS terminal · sessions survive quit"),
    ("Berth", "SSH client · Metal-rendered, split panes"),
    ("SandboxServer", "iOS debug SDK · inspect a running app"),
    ("v2ex", "iOS client · SwiftUI, Liquid Glass"),
    ("Interline", "browser ext · inline bilingual translation"),
]

GRAPHQL = """
{
  user(login: "%s") {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      nodes { name stargazerCount primaryLanguage { name } }
    }
  }
}
""" % USER


def fetch():
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", "query=" + GRAPHQL],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)["data"]["user"]


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


# 终端里等宽字体的字符宽度。CJK 按两格算，否则中文名后面的东西会对不齐。
CW = 8.4


def adv(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)


def shade(hex_color, k):
    """把颜色按系数 k 提亮/压暗，用来区分等距方块的三个面。"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    f = lambda v: max(0, min(255, round(v * k)))
    return f"#{f(r):02x}{f(g):02x}{f(b):02x}"


# 等距投影的网格步长，接近标准 2:1。
#
# 第一版用了 18×6 的扁投影，想着能压低整张图的高度 —— 结果 7 天的进深只剩
# 18px，整块贡献图糊成一条细斜带，完全看不出是个网格。等距投影里 y 方向的
# 进深就是靠 TH 撑的，压扁 TH 等于把第二个维度抹掉。
TW, TH = 26, 11
TILE = 0.86         # 实际方块比网格步长小一点，留出格缝
BAR_MAX = 52        # 贡献最多那天的柱高
BAR_MIN = 4         # 有贡献就至少冒头，否则和空地分不出来


THEMES = {
    "dark": dict(
        chrome="#2b2f36", bar="#22262c", body="#0f1216", text="#c9d1d9",
        dim="#6e7681", prompt="#39d353", cmd="#79c0ff", accent="#39d353",
        star="#e3b341", empty="#161b22",
        scale=["#0e4429", "#006d32", "#26a641", "#39d353"],
        shadow="0.45",
    ),
    "light": dict(
        chrome="#dcdfe4", bar="#eceff3", body="#ffffff", text="#1f2328",
        dim="#8b949e", prompt="#1a7f37", cmd="#0550ae", accent="#1a7f37",
        star="#9a6700", empty="#ebedf0",
        scale=["#aceebb", "#4ac26b", "#2da44e", "#116329"],
        shadow="0.14",
    ),
}

W = 900
PAD = 26
BAR = 38
LH = 23          # 行高
FS = 13.5        # 字号


def build(data, theme_name):
    t = THEMES[theme_name]
    cal = data["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    total = cal["totalContributions"]
    stars = {r["name"]: r["stargazerCount"] for r in data["repositories"]["nodes"]}
    langs = {r["name"]: (r["primaryLanguage"] or {}).get("name", "") for r in data["repositories"]["nodes"]}

    rows = []           # (kind, text-or-payload)
    rows.append(("cmd", "whoami"))
    rows.append(("out", f"{data.get('__name__','')}".strip() or ""))
    rows.append(("name", None))
    rows.append(("gap", None))
    rows.append(("cmd", "ls -l ~/shipped"))
    for name, desc in PROJECTS:
        rows.append(("proj", (name, desc, stars.get(name, 0), langs.get(name, ""))))
    rows.append(("gap", None))
    rows.append(("cmd", f'git log --oneline --since="1 year ago" | wc -l'))
    rows.append(("graph", weeks))
    rows.append(("out", f"{total} contributions in the last year"))
    rows.append(("gap", None))
    rows.append(("cmd", f"open https://{SITE}"))
    rows.append(("cursor", None))
    rows = [r for r in rows if not (r[0] == "out" and not r[1])]

    # 先算总高：贡献图那行占的高度和文字行不一样
    # 等距图的高度 = 纵向铺开的深度 + 最高的柱子 + 上下留白
    GRAPH_H = int((52 + 6) * TH / 2 + BAR_MAX + TH + 8)
    y = BAR + PAD
    plan = []
    for kind, payload in rows:
        if kind == "gap":
            y += LH * 0.5
            continue
        plan.append((kind, payload, y))
        y += GRAPH_H if kind == "graph" else LH
    H = int(y + PAD)

    body = []
    delay = 0.35        # 累积动画延迟

    def appear(dur=0.3):
        """一段淡入。用 SMIL 而不是 CSS —— 见模块开头的说明。"""
        return (f'<animate attributeName="opacity" from="0" to="1" '
                f'dur="{dur}s" begin="{delay:.2f}s" fill="freeze"/>')

    for i, (kind, payload, ly) in enumerate(plan):
        if kind == "cmd":
            text = payload
            n = adv(text)
            dur = max(0.35, n * 0.045)
            # 宽度要带上 "~ $ " 这 4 格提示符，否则命令会被剪掉 4 个字符
            PROMPT = 4
            steps = ";".join(str(round((PROMPT + k) * CW, 1)) for k in range(n + 1))
            times = ";".join(str(round(k / n, 4)) for k in range(n + 1))
            body.append(
                f'<clipPath id="c{i}"><rect x="{PAD}" y="{ly-FS}" height="{LH}" width="{PROMPT*CW}">'
                f'<animate attributeName="width" dur="{dur:.2f}s" begin="{delay:.2f}s" '
                f'fill="freeze" calcMode="discrete" values="{steps}" keyTimes="{times}"/>'
                f'</rect></clipPath>'
                f'<g clip-path="url(#c{i})" opacity="0">{appear(0.01)}'
                f'<text x="{PAD}" y="{ly}" class="mono">'
                f'<tspan fill="{t["prompt"]}">~ $ </tspan>'
                f'<tspan fill="{t["cmd"]}">{esc(text)}</tspan></text></g>'
            )
            delay += dur + 0.28
        elif kind == "name":
            body.append(
                f'<text x="{PAD}" y="{ly}" class="mono" opacity="0">{appear()}'
                f'<tspan fill="{t["text"]}" font-weight="600">李星河</tspan>'
                f'<tspan fill="{t["dim"]}">  ·  </tspan>'
                f'<tspan fill="{t["text"]}">{esc(TAGLINE)}</tspan></text>'
            )
            delay += 0.3
        elif kind == "proj":
            name, desc, star, lang = payload
            x = PAD
            body.append(
                f'<g opacity="0">{appear(0.22)}'
                f'<text x="{x}" y="{ly}" class="mono">'
                f'<tspan fill="{t["dim"]}">drwxr-xr-x</tspan>'
                f'<tspan x="{x+11*CW}" fill="{t["accent"]}" font-weight="600">{esc(name)}</tspan>'
                f'<tspan x="{x+27*CW}" fill="{t["text"]}">{esc(desc)}</tspan></text>'
                f'<text x="{W-PAD}" y="{ly}" text-anchor="end" class="mono">'
                f'<tspan fill="{t["dim"]}">{esc(lang)}</tspan>'
                # 刚起步的项目挂个 "0 ★" 比不挂还难看
                + (f'<tspan fill="{t["star"]}">   {star} ★</tspan>' if star else "")
                + f'</text></g>'
            )
            delay += 0.11
        elif kind == "graph":
            # 等距（isometric）贡献图。自己画而不是调 github-profile-3d-contrib：
            # 那个 Action 产出的是一整张独立 SVG，塞不进终端窗口，配色也另成一套。
            days = [(wi, (date.fromisoformat(d["date"]).weekday() + 1) % 7,
                     d["contributionCount"])
                    for wi, wk in enumerate(payload)
                    for d in wk["contributionDays"]]
            mx = max((c for _, _, c in days), default=1) or 1

            # 原点：把整块图水平居中。x 的最小值出现在 col=0,row=6 处。
            span = (len(payload) - 1 + 6) * TW / 2
            ox = PAD + 6 * TW / 2 + (W - 2 * PAD - span - TW) / 2
            oy = ly - FS + BAR_MAX + 8

            # 画家算法：(col+row) 越大越靠近观察者，必须后画才能正确遮挡。
            cols = {}
            for col, row, c in sorted(days, key=lambda d: d[0] + d[1]):
                cx = ox + (col - row) * TW / 2
                cy = oy + (col + row) * TH / 2
                h = 0 if c == 0 else BAR_MIN + (c / mx) * (BAR_MAX - BAR_MIN)
                if c == 0:
                    base = t["empty"]
                else:
                    q = min(3, int(c / mx * 4)) if mx > 3 else min(3, c - 1)
                    base = t["scale"][max(0, q)]

                hw, hh = TW / 2 * TILE, TH / 2 * TILE
                top = (f'{cx},{cy-h-hh} {cx+hw},{cy-h} '
                       f'{cx},{cy-h+hh} {cx-hw},{cy-h}')
                piece = [f'<polygon points="{top}" fill="{shade(base,1.0)}"/>']
                if h > 0:
                    left = (f'{cx-hw},{cy-h} {cx},{cy-h+hh} '
                            f'{cx},{cy+hh} {cx-hw},{cy}')
                    right = (f'{cx+hw},{cy-h} {cx},{cy-h+hh} '
                             f'{cx},{cy+hh} {cx+hw},{cy}')
                    # 左面压暗、右面更暗，靠明度差把体积感做出来
                    piece.append(f'<polygon points="{left}" fill="{shade(base,0.72)}"/>')
                    piece.append(f'<polygon points="{right}" fill="{shade(base,0.5)}"/>')
                cols.setdefault(col, []).append("".join(piece))

            # 按周分组逐列亮起，像城市天际线一格一格点亮
            weeks_svg = []
            n_cols = len(cols)
            for ci, col in enumerate(sorted(cols)):
                d0 = delay + ci * (0.9 / max(1, n_cols))
                weeks_svg.append(
                    f'<g opacity="0">'
                    f'<animate attributeName="opacity" from="0" to="1" dur="0.35s" '
                    f'begin="{d0:.2f}s" fill="freeze"/>{"".join(cols[col])}</g>'
                )
            body.append("".join(weeks_svg))
            delay += 1.15
        elif kind == "out":
            body.append(
                f'<text x="{PAD}" y="{ly}" class="mono" opacity="0" '
                f'fill="{t["dim"]}">{appear()}{esc(payload)}</text>'
            )
            delay += 0.25
        elif kind == "cursor":
            body.append(
                f'<text x="{PAD}" y="{ly}" class="mono" opacity="0">{appear(0.01)}'
                f'<tspan fill="{t["prompt"]}">~ $ </tspan></text>'
                f'<rect x="{PAD+4*CW}" y="{ly-FS+1}" width="{CW}" height="{FS+2}" '
                f'fill="{t["accent"]}" opacity="0">'
                f'<animate attributeName="opacity" values="0;1;1;0;0" '
                f'keyTimes="0;0.001;0.5;0.501;1" dur="1.1s" '
                f'begin="{delay:.2f}s" repeatCount="indefinite"/></rect>'
            )

    # 只放静态样式。动画全在 SMIL 里，原因见模块开头。
    style = (
        ".mono{font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,"
        "'Cascadia Code','Roboto Mono',Consolas,monospace;font-size:%gpx}" % FS
    )

    dots = "".join(
        f'<circle cx="{22+i*18}" cy="{BAR/2}" r="6" fill="{c}"/>'
        for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"])
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{USER} terminal profile">
<title>{USER} — terminal</title>
<defs><filter id="sh" x="-20%" y="-20%" width="140%" height="140%">
<feDropShadow dx="0" dy="10" stdDeviation="18" flood-opacity="{t["shadow"]}"/></filter>
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
    data = fetch()
    out = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("dark", "light"):
        svg = build(data, name)
        path = os.path.join(out, f"terminal-{name}.svg")
        with open(path, "w") as f:
            f.write(svg)
        print(f"wrote {path}  {len(svg)} bytes")


if __name__ == "__main__":
    main()
