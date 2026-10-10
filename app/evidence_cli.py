"""Freeze and independently replay upstream evidence without downstream code."""
import argparse,json,os
from pathlib import Path
from sqlalchemy.orm import Session
from .db import make_engine,DATABASE_URL
from .contract import freeze_v1,replay_v1,export_v1

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['export','freeze','replay'])
    parser.add_argument('path')
    args=parser.parse_args()
    target=Path(args.path)
    if args.operation=='replay': print(json.dumps(replay_v1(target),indent=2));return
    target.parent.mkdir(parents=True,exist_ok=True)
    with Session(make_engine(DATABASE_URL)) as s:
        storage=os.getenv('SNAPSHOT_DIR','data/snapshots')
        if args.operation=='freeze': print(freeze_v1(s,storage,target))
        else:
            with target.open('x') as file: json.dump(export_v1(s,storage),file,indent=2)
if __name__=='__main__': main()
