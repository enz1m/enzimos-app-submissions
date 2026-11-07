#!/usr/bin/env python3
"""Read proposed listings as data; never execute submitted builds or helpers."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import warnings
import xml.etree.ElementTree as ET
from PIL import Image

ID = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){2,}')
LOGIN = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?')
CATEGORIES = {'AudioVideo','Audio','Video','Development','Education','Game','Graphics','Network','Office','Science','Settings','System','Utility'}
Image.MAX_IMAGE_PIXELS = 9_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, name, maximum=4000):
    require(isinstance(value,str) and 0 < len(value.strip()) <= maximum and '\0' not in value, f'invalid {name}')
    return value


def url(value, name):
    text(value,name,1000)
    parsed=urllib.parse.urlsplit(value)
    require(parsed.scheme=='https' and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment and not parsed.query, f'{name} needs a public HTTPS URL without credentials/query/fragment')
    host=parsed.hostname.lower()
    require('.' in host and not host.endswith(('.local','.localhost','.internal','.invalid','.test')), f'{name} must be public')
    try:
        address=ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        require(address.is_global,f'{name} cannot use a private/local address')
    return value


def read_json(path):
    require(path.stat().st_size <= 256*1024, f'JSON too large: {path.name}')
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,f'duplicate JSON key: {key}')
            result[key]=value
        return result
    result=json.loads(path.read_text(),object_pairs_hook=pairs)
    require(isinstance(result,dict),f'{path.name} must be an object')
    return result


def tracked(root):
    names=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
    names=[name for name in names if name]
    require(len(names)<=10000,'repository has too many files')
    result={}
    for name in names:
        path=root/name
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),f'nonregular/escaping file: {name}')
        require(path.stat().st_size<=8*1024**2,f'file exceeds 8 MiB: {name}')
        result[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def image(root,relative,icon=False):
    require(isinstance(relative,str) and re.fullmatch(r'(?:icon\.png|screenshots/[A-Za-z0-9_.-]+\.(?:png|jpg|jpeg|webp))',relative), 'invalid image path')
    path=root/relative
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),'missing/escaping image')
    require(path.stat().st_size <= (2 if icon else 8)*1024**2, 'image exceeds size limit')
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(path) as data:
            width,height=data.size
            require(data.format in ('PNG','JPEG','WEBP') and getattr(data,'n_frames',1)==1,'unsupported/animated image')
            if icon:
                require(data.format=='PNG' and width==height and 128<=width<=1024,'icon must be a square 128–1024px PNG')
            else:
                require(640<=width<=3840 and 360<=height<=2160,'screenshot dimensions outside 640×360–3840×2160')
            data.verify()
        with Image.open(path) as data:
            data.load()
    return relative


def validate_app(root, app_id, files):
    require(ID.fullmatch(app_id) is not None,'invalid application ID')
    directory=root/'apps'/app_id
    entry=read_json(directory/'submission.json')
    required={'schema','id','name','summary','description','version','release_notes','developer','maintainers','license','homepage','support_url','source','categories','privacy','manifest','metainfo','icon','screenshots','permissions'}
    require(set(entry)==required,'listing must contain exactly the documented fields; review status is not a developer field')
    require(entry['schema']==1 and entry['id']==app_id,'listing schema/ID differs from directory')
    for field,limit in [('name',80),('summary',150),('description',8000),('version',80),('release_notes',4000),('developer',150),('license',100)]:text(entry[field],field,limit)
    require(isinstance(entry['maintainers'],list) and 1<=len(entry['maintainers'])<=20 and all(isinstance(m,str) and LOGIN.fullmatch(m) for m in entry['maintainers']),'invalid maintainer list')
    require(len({m.lower() for m in entry['maintainers']})==len(entry['maintainers']),'duplicate maintainers')
    require(isinstance(entry['categories'],list) and 1<=len(entry['categories'])<=3 and all(c in CATEGORIES for c in entry['categories']),'invalid categories')
    for field in ['homepage','support_url']:url(entry[field],field)
    source=entry['source']; require(isinstance(source,dict) and set(source)=={'url','commit'},'invalid source identity')
    url(source['url'],'source URL');require(isinstance(source['commit'],str) and re.fullmatch('[0-9a-f]{40}',source['commit']),'source must pin a full Git commit')
    privacy=entry['privacy'];require(isinstance(privacy,dict) and set(privacy)=={'policy_url','data_collection'},'privacy policy and collection statement required')
    url(privacy['policy_url'],'privacy policy');text(privacy['data_collection'],'data collection')
    require(entry['manifest']=='manifest.json' and entry['metainfo']=='metainfo.xml' and entry['icon']=='icon.png','use canonical manifest/metainfo/icon file names')
    used={'submission.json','manifest.json','metainfo.xml',image(directory,entry['icon'],True)}
    shots=entry['screenshots'];require(isinstance(shots,list) and 1<=len(shots)<=8,'one to eight screenshots required')
    for shot in shots:
        require(isinstance(shot,dict) and set(shot)=={'file','caption'},'screenshot file and caption required')
        text(shot['caption'],'screenshot caption',300)
        path=image(directory,shot['file']);require(path not in used,'duplicate screenshot');used.add(path)
    app_files={name[len(f'apps/{app_id}/'):] for name in files if name.startswith(f'apps/{app_id}/')}
    require(app_files==used,'app directory contains missing or unexpected files')
    manifest=read_json(directory/'manifest.json')
    require(manifest.get('app-id',manifest.get('id'))==app_id,'manifest ID differs from listing')
    require('id' not in manifest or manifest['id']==app_id,'conflicting manifest IDs')
    for field in ['runtime','runtime-version','sdk','command']:text(manifest.get(field),field,150)
    permissions=manifest.get('finish-args',[])
    require(isinstance(permissions,list) and len(permissions)<=100 and all(isinstance(p,str) and p.startswith('--') and '\n' not in p for p in permissions),'invalid finish-args')
    require(len(permissions)==len(set(permissions)) and isinstance(entry['permissions'],dict) and set(entry['permissions'])==set(permissions),'every finish-arg needs a matching permission explanation')
    for reason in entry['permissions'].values():text(reason,'permission explanation')
    matched=False
    def modules(values,depth=0):
        nonlocal matched
        require(isinstance(values,list) and 0<len(values)<=100 and depth<=8,'invalid/excessive manifest modules')
        for module in values:
            require(isinstance(module,dict),'external/moving module includes are not accepted')
            for source_item in module.get('sources',[]):
                require(isinstance(source_item,dict) and source_item.get('type') in ('git','archive','file'),'only pinned public git/archive/file sources are accepted')
                location=url(source_item.get('url'),'module source')
                require('branch' not in source_item and 'tag' not in source_item,'moving source selectors are forbidden')
                if source_item['type']=='git':
                    commit=source_item.get('commit');require(isinstance(commit,str) and re.fullmatch('[0-9a-f]{40}',commit),'module Git source must pin its commit')
                    if location.rstrip('/').removesuffix('.git')==source['url'].rstrip('/').removesuffix('.git') and commit==source['commit']:matched=True
                else:
                    require(isinstance(source_item.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',source_item['sha256']),'archive/file source requires SHA-256')
                    if source['commit'] in location:matched=True
            if 'modules' in module:modules(module['modules'],depth+1)
    modules(manifest.get('modules'));require(matched,'manifest does not reference the declared upstream source commit')
    xml=(directory/'metainfo.xml').read_bytes();require(len(xml)<=512*1024 and b'<!DOCTYPE' not in xml.upper() and b'<!ENTITY' not in xml.upper(),'unsafe/oversized AppStream XML')
    component=ET.fromstring(xml)
    require(component.tag=='component' and component.get('type')=='desktop-application' and component.findtext('id')==app_id,'AppStream identity differs from app')
    for field in ['name','summary','metadata_license','project_license']:text(component.findtext(field),'AppStream '+field,300)
    require(component.findtext('project_license')==entry['license'],'AppStream and listing licences differ')
    require(component.find('screenshots/screenshot') is not None,'AppStream screenshots required')
    return entry


def check(root, base=None, actor=None):
    root=Path(root).resolve();files=tracked(root)
    ids=sorted({name.split('/')[1] for name in files if name.startswith('apps/') and name!='apps/.gitkeep'})
    entries={app_id:validate_app(root,app_id,files) for app_id in ids}
    if base is not None:
        base=Path(base).resolve();previous=tracked(base)
        reviewers={name.lower() for name in read_json(base/'reviewers.json')['reviewers']}
        require(actor is not None and LOGIN.fullmatch(actor),'PR actor required')
        actor=actor.lower()
        changed={name for name in set(files)|set(previous) if files.get(name)!=previous.get(name)}
        app_changes={name.split('/')[1] for name in changed if name.startswith('apps/') and name!='apps/.gitkeep'}
        if actor not in reviewers:
            require(changed and all(name.startswith('apps/') and name!='apps/.gitkeep' for name in changed),'app submitters may change only their app directory')
            require(len(app_changes)==1,'change exactly one app per PR')
        for app_id in sorted(app_changes):
            require(app_id in entries or actor in reviewers,'withdrawal/removal needs a reviewer decision')
            if app_id not in entries:continue
            old_path=base/'apps'/app_id/'submission.json'
            old=read_json(old_path) if old_path.exists() else None
            authorised={name.lower() for name in (old or entries[app_id])['maintainers']}
            require(actor in reviewers or actor in authorised,'PR actor is not an approved maintainer; proposed self-addition grants no authority')
            if old:
                changes=[field for field in ['maintainers','permissions','privacy','source','version','screenshots'] if old.get(field)!=entries[app_id].get(field)]
                print(f'{app_id}: reviewer must inspect changes to '+', '.join(changes))
            else:print(f'{app_id}: NEW APP — ownership, licensing, permissions and runtime review required')
    print(f'Metadata/assets valid for {len(entries)} app(s). No builds, ownership verification or publication performed.')
    return entries


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='.');parser.add_argument('--base-tree');parser.add_argument('--actor')
    args=parser.parse_args()
    try:check(args.root,args.base_tree,args.actor)
    except (ValueError,OSError,ET.ParseError,Image.DecompressionBombError,Image.DecompressionBombWarning) as error:
        parser.exit(1,f'Submission rejected: {error}\n')
