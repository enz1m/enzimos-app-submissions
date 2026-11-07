#!/usr/bin/env python3
"""Controlled Flatpak builder. App commands run only inside flatpak-builder's sandbox."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.parse

PREDICATE='https://enzim.dev/attestations/flatpak-build/v1'
SHA=re.compile('[0-9a-f]{40}')
APP=re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){2,}')


def require(value,message):
    if not value:raise ValueError(message)


def relative(value):
    require(isinstance(value,str) and 0<len(value)<300 and '\\' not in value,'Invalid manifest path')
    path=PurePosixPath(value)
    require(not path.is_absolute() and all(part not in ('.','..') for part in path.parts),'Manifest must be inside the selected source')
    return str(path)


def source_file(root,path):
    root=Path(root).resolve();file=root/relative(path)
    require(file.resolve().is_relative_to(root) and not any(p.is_symlink() for p in [file,*file.parents] if p!=root),'Manifest symlinks are not accepted')
    require(file.is_file() and file.stat().st_size<=256*1024,'Manifest missing or too large')
    return file


def resolve(manifest,repository,commit):
    manifest=copy.deepcopy(manifest)
    def modules(items):
        if not isinstance(items,list):return
        for item in items:
            if not isinstance(item,dict):continue
            for source in item.get('sources',[]):
                if isinstance(source,dict) and source.get('commit')=='@ENZIM_SOURCE_COMMIT@':
                    require(source.get('url','').rstrip('/').removesuffix('.git')=='https://github.com/'+repository,'Source placeholder belongs only to this repository')
                    source['commit']=commit
            modules(item.get('modules'))
    modules(manifest.get('modules'))
    return manifest


def inspect(manifest,repository,commit,app_id):
    manifest=resolve(manifest,repository,commit)
    require(SHA.fullmatch(commit) and APP.fullmatch(app_id) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository),'Invalid build identity')
    require(isinstance(manifest,dict) and manifest.get('app-id',manifest.get('id'))==app_id,'Manifest application ID differs')
    require(not manifest.get('add-extensions') and not manifest.get('build-extensions'),'Additional extensions need manual packaging review')
    for key in ('runtime','sdk'):
        require(re.fullmatch(r'org\.(freedesktop|gnome|kde)\.[A-Za-z0-9_.-]+',manifest.get(key,'')),'Use a reviewed Flathub runtime/SDK')
    require(re.fullmatch(r'[A-Za-z0-9_.-]{1,50}',manifest.get('runtime-version','')),'Invalid runtime version')
    require(re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',manifest.get('command','')),'Invalid application command')
    require(re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',manifest.get('branch','master')),'Invalid Flatpak branch')
    matched=False;sources=[]
    def options(node):
        require(not any(key in node for key in ('build-args','sdk-extensions','platform-extensions','extra-data')),'Host build arguments, extra-data and extensions require separate review')
        if isinstance(node.get('build-options'),dict):options(node['build-options'])
    def modules(items,depth=0):
        nonlocal matched
        require(isinstance(items,list) and 0<len(items)<=100 and depth<=8,'Invalid or external module include')
        for module in items:
            require(isinstance(module,dict),'Module includes must be expanded into the manifest')
            options(module)
            for source in module.get('sources',[]):
                require(isinstance(source,dict) and source.get('type') in ('git','archive','file'),'Only declared Git/archive/file sources are accepted')
                url=source.get('url','');parsed=urllib.parse.urlsplit(url)
                require(parsed.scheme=='https' and parsed.hostname and '.' in parsed.hostname and not parsed.username and not parsed.password and not parsed.port and not parsed.hostname.endswith(('.local','.internal')),'Sources must use public HTTPS URLs')
                require(not any(key in source for key in ('branch','tag','commands','path','paths','mirror-urls')),'Moving or undeclared source inputs are not accepted')
                if source['type']=='git':
                    require(SHA.fullmatch(source.get('commit','')),'Git dependencies need full commits')
                    require(source.get('disable-submodules') is True,'Declare dependencies explicitly and set disable-submodules: true')
                    if url.rstrip('/').removesuffix('.git')=='https://github.com/'+repository and source['commit']==commit:matched=True
                else:require(re.fullmatch('[0-9a-f]{64}',source.get('sha256','')),'Downloaded inputs need SHA-256 checksums')
                sources.append({key:source[key] for key in ('type','url','commit','sha256') if key in source})
            if 'modules' in module:modules(module['modules'],depth+1)
    options(manifest);modules(manifest.get('modules'))
    require(matched,'Manifest must build the selected repository at the selected commit')
    permissions=manifest.get('finish-args',[])
    require(isinstance(permissions,list) and all(isinstance(value,str) and value.startswith('--') for value in permissions),'Invalid application permissions')
    return {'sources':sources,'permissions':permissions,'runtime':manifest['runtime'],'sdk':manifest['sdk'],'runtime_version':manifest['runtime-version']}


def configuration(raw):
    if not raw:return {}
    require(len(raw)<=16000,'Build configuration too large')
    values=json.loads(raw)
    require(isinstance(values,dict) and len(values)<=20,'Build configuration must be a small object')
    require(all(re.fullmatch(r'ENZIM_[A-Z][A-Z0-9_]{0,60}',key) and isinstance(value,str) and len(value)<=1000 and all(ord(c)>=32 for c in value) for key,value in values.items()),'Build values must be scalar ENZIM_* application settings')
    return values


def run(args):subprocess.run(args,check=True)


def build(args):
    root=Path(args.source).resolve();manifest_file=source_file(root,args.manifest)
    require(subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==args.commit,'Checkout differs from selected source')
    raw=manifest_file.read_bytes();manifest=resolve(json.loads(raw),args.repository,args.commit);inspect(manifest,args.repository,args.commit,args.app)
    public_manifest=json.dumps(manifest).encode()
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    # This working manifest is outside the app checkout. No source-controlled host
    # helper is executed. The selected manifest is self-contained by policy.
    working=output.parent/'build-manifest.json';working.write_bytes(public_manifest)
    runtime=manifest['runtime']+'//'+manifest['runtime-version'];sdk=manifest['sdk']+'//'+manifest['runtime-version']
    run(['flatpak','--user','remote-add','--if-not-exists','flathub','https://dl.flathub.org/repo/flathub.flatpakrepo'])
    run(['flatpak','--user','install','-y','--noninteractive','flathub',runtime,sdk])
    state=str(output.parent/'builder-state');directory=str(output.parent/'app-build');repo=str(output.parent/'unsigned-repo')
    base=['flatpak-builder','--user','--sandbox','--state-dir='+state]
    run(base+['--download-only','--disable-cache',directory,str(working)])
    values=configuration(os.environ.pop('ENZIM_BUILD_CONFIG',''))
    if values:
        for value in values.values():
            if value:print('::add-mask::'+value.replace('%','%25'),flush=True)
        options=manifest.setdefault('build-options',{});options.setdefault('env',{}).update(values)
        working.write_text(json.dumps(manifest))
    run(base+['--build-only','--disable-download','--disable-cache','--force-clean',directory,str(working)])
    # Export public build instructions without deliberately including private
    # settings. Values compiled into the application remain extractable.
    working.write_bytes(public_manifest)
    run(base+['--finish-only','--disable-download','--disable-cache','--repo='+repo,directory,str(working)])
    run(['flatpak','build-bundle',repo,str(output/'app.flatpak'),args.app,manifest.get('branch','master')])
    working.unlink(missing_ok=True)


def record(args):
    raw=source_file(args.source,args.manifest).read_bytes();details=inspect(json.loads(raw),args.repository,args.commit,args.app)
    root=Path(args.output);package=root/'app.flatpak';require(package.is_file(),'Build artifact missing')
    sha=hashlib.file_digest(package.open('rb'),'sha256').hexdigest()
    result={'schema':1,'repository':args.repository,'repository_id':int(os.environ['GITHUB_REPOSITORY_ID']),'source_commit':args.commit,'manifest_path':relative(args.manifest),'manifest_sha256':hashlib.sha256(raw).hexdigest(),'app_id':args.app,'ticket':args.ticket,'package_sha256':sha,'run_id':int(os.environ['GITHUB_RUN_ID']),'run_attempt':int(os.environ['GITHUB_RUN_ATTEMPT']),**details}
    (root/'build-record.json').write_text(json.dumps(result,indent=2)+'\n')
    (root/'manifest.json').write_bytes(raw)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['build','record'])
    for name in ('source','repository','commit','manifest','app','ticket','output'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    try:build(args) if args.operation=='build' else record(args)
    except (ValueError,OSError) as error:parser.exit(1,'Build refused: '+str(error)+'\n')
