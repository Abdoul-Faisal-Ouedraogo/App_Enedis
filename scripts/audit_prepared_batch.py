"""Audit d'un lot conservé : sources, volume et pointeur exclusivement en lecture seule."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CODE="""
import json,hashlib
from pathlib import Path
from src.version_store import VersionStore
from src.expert_data import audit_existing_version
store=VersionStore('/app/runtime')
def snapshot():
    return {str(p.relative_to(store.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in store.root.rglob('*') if p.is_file()}
before=snapshot()
result=audit_existing_version(VERSION,store)
assert before==snapshot(),'Le volume a change pendant audit'
result['volume_unchanged']=True
result['active']=store.active()
print(json.dumps(result,ensure_ascii=False,indent=2))
"""


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--docker-volume")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}",args.version):
        parser.error("Identifiant de version invalide")
    if args.docker_volume:
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+",args.docker_volume):
            parser.error("Nom de volume invalide")
        subprocess.run(["docker","volume","inspect",args.docker_volume],check=True,capture_output=True)
        command=["docker","run","--rm","--read-only","--cpus","2","--mount",f"type=volume,src={args.docker_volume},dst=/app/runtime,readonly"]
        for path in ["src","config","output/cleaned_data.csv","output/cleaned_data_metadata.csv","data/communes-france-2025.csv"]:
            command += ["--mount",f"type=bind,src={(ROOT/path).as_posix()},dst=/app/{path},readonly"]
        command += ["--entrypoint","python","habitat-energie:local","-c",CODE.replace("VERSION",repr(args.version))]
        result=json.loads(subprocess.check_output(command,encoding="utf-8"))
    else:
        from src.expert_data import audit_existing_version
        result=audit_existing_version(args.version)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        target=args.output.resolve()
        # Un audit ne doit jamais servir à réécrire un manifeste ou un fichier source.
        if not target.is_relative_to(ROOT/"output"/"audit") or target.exists():
            parser.error("La sortie doit être un nouveau fichier sous output/audit/")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(text,encoding="utf-8")
    print(text)
