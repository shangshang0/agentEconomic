"""Create a verified, isolated branch data root from an automatic snapshot.

This intentionally restores files only: a branch is launched with a separate
Compose project/ports by the experiment controller, never into the parent
world's volumes.
"""
from __future__ import annotations
import hashlib, json, shutil, sys
from pathlib import Path

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def main() -> None:
    if len(sys.argv) != 3: raise SystemExit('usage: create_branch.py SNAPSHOT_DIR BRANCH_DIR')
    source, target = map(Path, sys.argv[1:])
    manifest=json.loads((source/'MANIFEST.json').read_text())
    if target.exists(): raise SystemExit('branch target already exists')
    for rel, expected in manifest['files'].items():
        if sha256(source/rel) != expected: raise SystemExit('snapshot checksum failed: '+rel)
    target.mkdir(parents=True)
    for name in ('authority-world-v1.state.json','authority-world-v1.events.jsonl','agent-state','gateway-data','config'):
        item=source/name
        if item.exists(): shutil.copytree(item,target/name) if item.is_dir() else shutil.copy2(item,target/name)
    (target/'BRANCH_MANIFEST.json').write_text(json.dumps({'base_snapshot':manifest['snapshot_id'],'day':manifest['day'],'event_seq':manifest['event_seq']},indent=2))
    print(target)

if __name__ == '__main__': main()
