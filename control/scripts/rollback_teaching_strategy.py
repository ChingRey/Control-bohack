"""Withdraw a promoted teaching strategy from future sessions. Run on the host."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend
from agents.strategy_rollback import withdraw

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cohort', required=True, choices=('human','simulation'))
parser.add_argument('--version', type=int, required=True)
parser.add_argument('--reason', required=True)
args=parser.parse_args()
try:
    with backend.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        result=withdraw(conn,args.cohort,args.version,args.reason)
except ValueError as error:
    parser.exit(1,str(error)+'\n')
print(result)
