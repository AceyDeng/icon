#!/usr/bin/env python3
"""Create a separate Surge config copy; alter only icon-url fields in Proxy Group."""
import argparse, json, re
from pathlib import Path
from urllib.parse import urlparse

HOME=Path(__file__).resolve().parent.parent
def resolve(name, manifest, overrides):
    if name in overrides:return overrides[name]
    upper=name.upper()
    for r in manifest['mapping']:
        if r['scope']=='service' and upper==r['group'].upper():return r['asset_id']
    # Country codes win over category suffixes, including all hidden layers.
    found={r['asset_id'] for r in manifest['mapping'] if r['scope']=='region' and re.search(r'(?<![A-Z])'+r['group']+r'(?![A-Z])',upper)}
    if len(found)==1:return found.pop()
    if found:return None
    cleaned=re.sub(r'^[^A-Za-z]+','',name).strip().upper()
    for r in manifest['mapping']:
        if r['scope']=='category' and cleaned==r['group'].upper():return r['asset_id']
    return None

def strip_icons(line):
    return re.sub(r',\s*icon-url\s*=\s*[^,\r\n]*','',line,flags=re.I)

def main():
    p=argparse.ArgumentParser(description='僅改 icon-url，另存新檔；不連網、不覆蓋原檔。')
    p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--base-url',required=True,help='已部署的真實HTTPS目錄，目錄內含png/256/')
    p.add_argument('--names',type=Path,help='選用：精確原組名→asset_id的JSON；只供原名與代碼不同時補充')
    a=p.parse_args();u=urlparse(a.base_url)
    if u.scheme!='https' or not u.hostname or any(c in a.base_url for c in '<>,\r\n'):p.error('base-url 必須為部署後的HTTPS目錄網址')
    if a.input.resolve()==a.output.resolve() or a.output.exists():p.error('輸出必須是不存在的新檔，不能覆蓋原檔')
    m=json.loads((HOME/'manifest.json').read_text());overrides=json.loads(a.names.read_text()) if a.names else {}
    valid={x['id'] for x in m['assets']}
    if any(v not in valid for v in overrides.values()):p.error('names JSON含不在圖包內的asset_id')
    raw=a.input.read_bytes();bom=raw.startswith(b'\xef\xbb\xbf');text=raw.decode('utf-8-sig');lines=text.splitlines(keepends=True)
    section='';result=[];changed=[];unmatched=[]
    for line in lines:
        trimmed=line.strip()
        if trimmed.startswith('['):section=trimmed.split(']',1)[0][1:].strip().lower()
        if section!='proxy group' or trimmed.startswith(('#',';')) or '=' not in line:
            result.append(line);continue
        name=line.split('=',1)[0].strip();slug=resolve(name,m,overrides)
        if not slug:unmatched.append(name);result.append(line);continue
        url=a.base_url.rstrip('/')+'/png/256/'+slug+'.png'
        pat=r'(?i)(,\s*icon-url\s*=\s*)[^,\r\n]*'
        matches=list(re.finditer(pat,line))
        if len(matches)>1:p.error('原組 '+name+' 有多個icon-url；請先檢查原行，未寫輸出')
        if matches:
            new=re.sub(pat,lambda x:x.group(1)+url,line,count=1)
        else:
            core=line.rstrip('\r\n');new=core+', icon-url='+url+line[len(core):]
        if strip_icons(line)!=strip_icons(new):raise RuntimeError('非icon欄位發生變更；已停止')
        result.append(new);changed.append({'group':name,'asset_id':slug})
    if not changed:p.error('沒有可匹配的組名；請用 --names 指定原組名，未寫輸出')
    data=''.join(result).encode('utf-8');a.output.write_bytes((b'\xef\xbb\xbf' if bom else b'')+data)
    print(json.dumps({'output':str(a.output),'changed_icon_only':changed,'unchanged_unmatched_groups':unmatched},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
