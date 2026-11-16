from pathlib import Path
import json,hashlib,zipfile,io,xml.etree.ElementTree as ET
from PIL import Image
R=Path.cwd();files=set()
def add(p):
 p=Path(p)
 if p.is_file() and not any(x in p.parts for x in ['__pycache__','.git','.venv','node_modules','.pytest_cache']):files.add(p)
for d in ['src','tests','docs/research','docs/repro','docs/screenshots/gui-ux-02','outputs/gui_ux_02','references']:
 for p in Path(d).rglob('*'):
  if p.suffix.lower() in {'.py','.js','.html','.css','.json','.md','.npz','.png','.svg','.log','.txt','.doc','.docx','.pdf','.emf','.wmf'}:add(p)
for p in ['pyproject.toml','PLAN.md','NEXT_TASK.md','AGENTS.md','docs/BUILD_VERIFICATION.md','docs/THESIS_MASTER_DRAFT_UK.md','docs/THESIS_CLAIM_EVIDENCE_MATRIX.md','docs/THESIS_FIGURE_REGISTER.md','docs/THESIS_TABLE_REGISTER.md','docs/TECHNICAL_SPECIFICATION.md','scripts/qa_gui_ux02.js','scripts/validate_gui_ux02.py','scripts/report_gui_ux02.py','scripts/package_gui_ux02.py','scripts/verify_repro06b_artifacts.py']:add(p)
readme='''# HF-TCM-SIM final GUI and scientific audit\n\nStart with docs/research/HF_TCM_SIM_FINAL_SCIENTIFIC_AUDIT.md, ARTICLE_COMPLIANCE_FINAL_AUDIT.md, MASTER_THESIS_READINESS_AUDIT.md, EXPERIMENT_READINESS_ASSESSMENT.md, NEXT_SCIENTIFIC_STEPS.md.\n\nGUI changes: four Tx/Rx I/Q curves; independent series switches; fixed constellation; readable trellis; metadata and methods dialogs; phase SER stage labels. Mathematical backend unchanged. GUI verdict PARTIAL: specialized estimated/predicted trajectories remain incomplete; final BER-toggle/color browser recheck stalled. The 12-check Edge report and 22 screenshots describe the successful preceding GUI acceptance, not a nonexistent later PASS.\n\n1182 full pytest passed; 109 source-audit independent tests; Ruff/Node passed; 694/694 historical fingerprints. Five F32 controls with real bits/decodes/traces/manifests are in outputs/gui_ux_02/controls. Ten independent paired F32 trials at noise .01/.1 and hash-verified resume are in outputs/gui_ux_02/monte_carlo. Exploratory only, not a large confirmatory series.\n\nPrimary/alternate v7 and supporting DOC are in references with source hashes and rendered equations in outputs/gui_ux_02/article. Article compliance PARTIAL: metric (2), estimator and noise discrepancies are documented. Physical energy gain NOT_ESTIMABLE, paper_exact:false. Official signed thesis assignment absent; existing thesis draft is historical and contains placeholders. No main scientific experiment started.\n\nSource modules, tests, logs and rendered screenshots/exports are included with project-relative paths. Manifest hashes every payload, including this README, except the manifest itself. ZIP CRC, payload hashes and image/XML content are checked by the package script. Prior historical runs are not overwritten.\n'''
payload={p.as_posix():p.read_bytes() for p in files};payload['README_FOR_CHATGPT.md']=readme.encode('utf8')
manifest={'files':[{'path':n,'size_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(payload.items())]}
p=R/'HF_TCM_SIM_FINAL_GUI_AND_SCIENTIFIC_AUDIT.zip'
with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in payload.items():z.writestr(n,b)
 z.writestr('AUDIT_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 for row in manifest['files']:
  b=z.read(row['path']);assert len(b)==row['size_bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
  if row['path'].endswith('.png'):
   im=Image.open(io.BytesIO(b)).convert('RGBA');assert im.getchannel('A').getextrema()[1]>0;assert len(im.getcolors(im.width*im.height) or [])>1
  if row['path'].endswith('.svg'):ET.fromstring(b)
r={'archive':p.name,'size_bytes':p.stat().st_size,'files_count':len(payload)+1,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'verification':'PASS'}
print(json.dumps(r,indent=2));(R/'outputs/gui_ux_02/archive_verification.json').write_text(json.dumps(r,indent=2),'utf8')
