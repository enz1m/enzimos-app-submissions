#!/usr/bin/env python3
"""Export reviewed main-branch listings for the private release operator.

This does not approve, build, sign, deploy or update the server allowlist.
"""
import argparse
import json
from pathlib import Path
from validate import check

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='.')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    root=Path(args.root).resolve()
    entries=check(root)
    catalog=[]
    for app_id,data in sorted(entries.items()):
        entry={**data,'title':data['name'],'listing_root':str(root/'apps'/app_id)}
        catalog.append(entry)
    output=Path(args.output).resolve()
    if output.exists():parser.error('output already exists; choose a fresh path')
    if output.is_relative_to(root):parser.error('write generated operator state outside the public repository')
    output.write_text(json.dumps({'schema':1,'apps':catalog},indent=2)+'\n')
    print(f'Exported {len(catalog)} listings for operator review; no publication performed.')
