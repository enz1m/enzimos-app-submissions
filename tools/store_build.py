#!/usr/bin/env python3
"""Controlled Flatpak builder. App commands run only inside flatpak-builder's sandbox."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from build_policy import inspect, require, resolve

PREDICATE='https://enzim.dev/attestations/flatpak-build/v1'


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
    extensions = [name + '//' + manifest['runtime-version']
                  for name in manifest.get('sdk-extensions', [])]
    run(['flatpak','--user','install','-y','--noninteractive','flathub',runtime,sdk,*extensions])
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
    run(['flatpak','build-bundle',repo,str(output/'app.flatpak'),args.app,manifest['branch']])
    environment={'runtime_commit':subprocess.check_output(['flatpak','--user','info','--show-commit',runtime],text=True).strip(),'sdk_commit':subprocess.check_output(['flatpak','--user','info','--show-commit',sdk],text=True).strip(),'configuration_names':sorted(values)}
    environment['sdk_extension_commits'] = {
        ref: subprocess.check_output(['flatpak', '--user', 'info', '--show-commit', ref], text=True).strip()
        for ref in extensions
    }
    (output/'build-inputs.json').write_text(json.dumps(environment)+'\n')
    working.unlink(missing_ok=True)


def record(args):
    raw=source_file(args.source,args.manifest).read_bytes();details=inspect(json.loads(raw),args.repository,args.commit,args.app)
    root=Path(args.output);package=root/'app.flatpak';require(package.is_file(),'Build artifact missing')
    sha=hashlib.file_digest(package.open('rb'),'sha256').hexdigest()
    environment=json.loads((root/'build-inputs.json').read_text())
    require(all(re.fullmatch('[0-9a-f]{64}',environment.get(key,'')) for key in ('runtime_commit','sdk_commit')),'Build environment commits are missing')
    extension_commits = environment.get('sdk_extension_commits', {})
    expected_extensions = {name + '//' + details['runtime_version']
                           for name in json.loads(raw).get('sdk-extensions', [])}
    require(isinstance(extension_commits, dict) and set(extension_commits) == expected_extensions
            and all(isinstance(commit, str) and re.fullmatch('[0-9a-f]{64}', commit)
                    for commit in extension_commits.values()), 'SDK extension commits are missing or invalid')
    require(isinstance(environment.get('configuration_names'),list) and len(environment['configuration_names'])<=20 and all(isinstance(key,str) and re.fullmatch(r'ENZIM_[A-Z][A-Z0-9_]{0,60}',key) for key in environment['configuration_names']),'Invalid build configuration names')
    result={'schema':1,'repository':args.repository,'repository_id':int(os.environ['GITHUB_REPOSITORY_ID']),'source_commit':args.commit,'manifest_path':relative(args.manifest),'manifest_sha256':hashlib.sha256(raw).hexdigest(),'app_id':args.app,'ticket':args.ticket,'package_sha256':sha,'run_id':int(os.environ['GITHUB_RUN_ID']),'run_attempt':int(os.environ['GITHUB_RUN_ATTEMPT']),'build_environment':environment,**details}
    (root/'build-record.json').write_text(json.dumps(result,indent=2)+'\n')
    (root/'manifest.json').write_bytes(raw)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['build','record'])
    for name in ('source','repository','commit','manifest','app','ticket','output'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    try:build(args) if args.operation=='build' else record(args)
    except (ValueError,OSError) as error:parser.exit(1,'Build refused: '+str(error)+'\n')
