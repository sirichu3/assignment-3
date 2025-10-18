import base64
import mimetypes
import os

ROOT = os.path.dirname(__file__)
INDEX = os.path.join(ROOT, 'index.html')
OUT = os.path.join(ROOT, 'index.bundle.html')


def b64_data_uri(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        if path.lower().endswith('.mp3'):
            mime = 'audio/mpeg'
        elif path.lower().endswith('.png'):
            mime = 'image/png'
        else:
            mime = 'application/octet-stream'
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    return f'data:{mime};base64,{b64}'


def collect_embed() -> dict:
    embed = {}
    for rel in ('resource', 'sounds'):
        dir_path = os.path.join(ROOT, rel)
        if not os.path.isdir(dir_path):
            continue
        for name in os.listdir(dir_path):
            if name.startswith('.'):
                continue
            fp = os.path.join(dir_path, name)
            if not os.path.isfile(fp):
                continue
            uri = b64_data_uri(fp)
            embed[f'{rel}/{name}'] = uri
    return embed


def generate_embed_js(embed: dict) -> str:
    # 格式化为 const EMBED = { 'path': 'data:...' };
    lines = ["const EMBED = {"]
    first = True
    for k, v in embed.items():
        sep = '' if first else ','
        lines.append(f"{sep}\n  '{k}': '{v}'")
        first = False
    lines.append('\n};')
    return '\n'.join(lines)


def build():
    embed = collect_embed()
    with open(INDEX, 'r', encoding='utf-8') as f:
        html = f.read()
    embed_js = generate_embed_js(embed)
    placeholder = 'const EMBED = {};'
    if placeholder in html:
        out_html = html.replace(placeholder, embed_js, 1)
    else:
        anchor = 'const HOVER_PAD = 12;'
        out_html = html.replace(anchor, anchor + '\n\n' + embed_js, 1)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(out_html)
    print(f'Wrote {OUT} with {len(embed)} assets embedded.')


if __name__ == '__main__':
    build()