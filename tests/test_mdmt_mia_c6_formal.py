import subprocess,sys
from pathlib import Path
def test_synthetic_formal_path():
 r=subprocess.run([sys.executable,'scripts/run_mdmt_mia_c6_formal.py','--synthetic'],cwd=Path(__file__).parents[1],env={'PYTHONNOUSERSITE':'1','PYTHONHASHSEED':'0'},capture_output=True,text=True)
 assert r.returncode==0 and '"status": "PASS"' in r.stdout
