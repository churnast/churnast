"""Renders README.md like GitHub does (dark and light) into one self-contained HTML page.
Every asset is inlined as a data: URI, so the page works offline and shows live SVG animation.
Usage: python preview.py <out.html>
"""
import base64, html, re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MIME = {".svg": "image/svg+xml", ".gif": "image/gif", ".png": "image/png", ".webp": "image/webp"}


def remote_uri(url):
    import urllib.request
    data = urllib.request.urlopen(url).read()
    return f"data:{MIME[Path(url).suffix]};base64,{base64.b64encode(data).decode()}"


def data_uri(rel):
    p = ROOT / rel
    return f"data:{MIME[p.suffix]};base64,{base64.b64encode(p.read_bytes()).decode()}"


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def slug(t):
    return re.sub(r"[^a-z0-9 -]", "", t.lower()).replace(" ", "-")


def render(md):
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1; continue
        if ln.startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"): j += 1
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1; continue
        m = re.match(r"(#{1,3}) (.*)", ln)
        if m:
            n, t = len(m.group(1)), m.group(2)
            out.append(f'<h{n} id="{slug(t)}">{inline(t)}</h{n}>'); i += 1; continue
        if ln.startswith("- "):
            j = i
            items = []
            while j < len(lines) and lines[j].startswith("- "):
                items.append("<li>" + inline(lines[j][2:]) + "</li>"); j += 1
            out.append("<ul>" + "".join(items) + "</ul>"); i = j; continue
        if ln.strip() == "---":
            out.append("<hr>"); i += 1; continue
        j = i
        block = []
        while j < len(lines) and lines[j].strip() and not lines[j].startswith("```"):
            block.append(lines[j]); j += 1
        text = "\n".join(block)
        if text.lstrip().startswith("<"):
            out.append(text)
        else:
            out.append("<p>" + inline(text) + "</p>")
        i = j
    h = "\n".join(out)
    # <picture> becomes two images toggled by the page theme (prefers-color-scheme can't follow a toggle)
    def pic(m):
        dark = re.search(r'dark\)" srcset="([^"]+)"', m.group(0)).group(1)
        light = re.search(r'light\)" srcset="([^"]+)"', m.group(0)).group(1)
        alt = re.search(r'alt="([^"]+)"', m.group(0)).group(1)
        return (f'<img class="only-dark" src="{dark}" width="100%" alt="{alt}">'
                f'<img class="only-light" src="{light}" width="100%" alt="{alt}">')
    h = re.sub(r"<picture>.*?</picture>", pic, h, flags=re.S)
    h = re.sub(r'src="(assets/[^"]+)"', lambda m: f'src="{data_uri(m.group(1))}"', h)
    h = re.sub(r'src="(https://github\.com/churnast/[^"]+/raw/[^"]+)"', lambda m: f'src="{remote_uri(m.group(1))}"', h)
    h = h.replace('href="src/build.py"', 'href="#"')
    h = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', h)
    return h


PAGE = """<title>GitHub-профиль с совой</title>
<style>
/* Layout: a note for Nastya, then the profile exactly as GitHub would show it, inside a GitHub-like frame. */
:root{
  --bg:#ffffff; --fg:#1f2328; --muted:#59636e; --border:#d1d9e0; --canvas:#f6f8fa; --link:#0969da;
  --code-bg:#f6f8fa; --note-bg:#fff4e6; --note-fg:#5b4766; --amber:#c46a1a;
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0d1117; --fg:#f0f6fc; --muted:#9198a1; --border:#3d444d; --canvas:#010409; --link:#4493f8;
  --code-bg:#151b23; --note-bg:#1c2440; --note-fg:#d9cfe6; --amber:#f2b544; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0d1117; --fg:#f0f6fc; --muted:#9198a1; --border:#3d444d; --canvas:#010409; --link:#4493f8;
  --code-bg:#151b23; --note-bg:#1c2440; --note-fg:#d9cfe6; --amber:#f2b544; color-scheme:dark}
.only-dark{display:none}.only-light{display:block}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .only-dark{display:block}:root:not([data-theme="light"]) .only-light{display:none}}
:root[data-theme="dark"] .only-dark{display:block}:root[data-theme="dark"] .only-light{display:none}
body{background:var(--canvas);color:var(--fg);font:16px/1.5 var(--font);padding:24px 16px}
.wrap{max-width:900px;margin:0 auto;display:flex;flex-direction:column;gap:16px}
.note{background:var(--note-bg);color:var(--note-fg);border-radius:12px;padding:14px 18px;font-size:14px;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;justify-content:space-between}
.note b{color:var(--amber)}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.seg button{font:inherit;font-size:13px;padding:6px 14px;border:0;background:transparent;color:var(--fg);cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--amber);color:#1f1307}
.seg button:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
.card{background:var(--bg);border:1px solid var(--border);border-radius:6px;min-width:0}
.card-h{padding:10px 16px;border-bottom:1px solid var(--border);font-size:14px;color:var(--muted);font-family:var(--mono)}
.card-h b{color:var(--fg);font-weight:600}
.md{padding:24px 32px;overflow-wrap:break-word}
@media (max-width:600px){.md{padding:16px}}
.md img{max-width:100%;vertical-align:middle;border:0}
.md h2{font-size:1.5em;font-weight:600;padding-bottom:.3em;border-bottom:1px solid var(--border);margin:24px 0 16px}
.md h3{font-size:1.25em;font-weight:600;margin:24px 0 16px}
.md p{margin:0 0 16px}
.md ul{margin:0 0 16px;padding-left:2em}
.md li+li{margin-top:.25em}
.md a{color:var(--link);text-decoration:none}
.md code{font-family:var(--mono);font-size:85%;background:var(--code-bg);padding:.2em .4em;border-radius:6px}
.md pre{background:var(--code-bg);padding:16px;border-radius:6px;overflow-x:auto;margin:0 0 16px}
.md pre code{background:none;padding:0;font-size:85%}
.md hr{border:0;height:.25em;background:var(--border);margin:24px 0}
.md sub{color:var(--muted)}
</style>
<div class="wrap">
  <div class="note"><span><b>Черновик, на GitHub не опубликован.</b> Так будет выглядеть churnast/README.md.</span>
    <span class="seg" role="group" aria-label="Тема GitHub"><button id="t-dark" data-t="dark">Тёмная тема</button><button id="t-light" data-t="light">Светлая тема</button></span></div>
  <div class="card"><div class="card-h">churnast / <b>README.md</b></div><article class="md">
__BODY__
  </article></div>
</div>
<script>
(function(){
  var root=document.documentElement, btns=document.querySelectorAll('.seg button');
  function cur(){return root.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}
  function sync(){var c=cur();btns.forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.t===c))})}
  btns.forEach(function(b){b.addEventListener('click',function(){root.setAttribute('data-theme',b.dataset.t);sync()})});
  if(location.hash==='#light'||location.hash==='#dark')root.setAttribute('data-theme',location.hash.slice(1));
  sync();
})();
</script>
"""

if __name__ == "__main__":
    body = render((ROOT / "README.md").read_text())
    Path(sys.argv[1]).write_text(PAGE.replace("__BODY__", body))
    print("ok", len(body))
