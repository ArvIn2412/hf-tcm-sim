from pathlib import Path
import hashlib,json,zipfile
from PIL import Image
import xml.etree.ElementTree as ET
ROOT=Path.cwd(); OUT=ROOT/'outputs/gui_ux_01'; (OUT/'verification').mkdir(parents=True,exist_ok=True)
checks={"pytest":{"command":"python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-gui-ux01-final -p no:cacheprovider","status":"PASS","result":"1182 passed"},"ruff_check":{"command":"ruff check src tests","status":"PASS"},"ruff_format":{"command":"ruff format --check src tests","status":"PASS","result":"261 files already formatted"},"node":{"command":"node --check scientific.js, scientific_i18n.js, scientific_ux.js, qa_gui_ux01.js","status":"PASS"},"historical":{"command":"python scripts/verify_repro06b_artifacts.py","status":"PASS","matched":694,"expected":694},"edge":{"status":"PARTIAL","result":"At 1366x768: 5 automated checks passed (3-column layout, no visible stage/fidelity flags, 3 global controls, help toggle, Identity paired run zero BER, square constellation intrinsic). Nine tabs screenshotted. 1920x1080 only parameters screen captured. Static multipath/Rician/Monte Carlo GUI acceptance was not rerun."}}
(OUT/'verification'/'verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n','utf8')
(OUT/'verification'/'identity_backend_display_check.json').write_text(json.dumps({"scenario":"Identity","frame_symbols":32,"compared_information_bits":64,"joint_bit_errors":0,"separate_bit_errors":0,"observation_pair_verified":True,"gui_result":"values displayed from saved run summary; backend data not modified"},indent=2)+'\n','utf8')
(OUT/'verification'/'before_after.md').write_text('''# Before / after\n\n| Area | Before | After |\n|---|---|---|\n| Parameters | two columns and large explanatory card | compact three columns, one run button, channel details collapsed |\n| Navigation | local duplicate symbol fields, step arrows, zoom and hash line | global symbol/sample/receiver controls |\n| Labels | development stage codes, mixed English and Ukrainian | Ukrainian algorithm and metric names |\n| Constellation | canvas dimensions followed active tab size | fixed 360×360 square canvas and fixed phase radius |\n| Encoder view | inline dense bit strings | readable per-symbol table |\n| Viterbi | survivor colors merged; no legend/filter | local path/current edge colors, legend and transition filter |\n| Error plot | empty series for zero errors | discrete per-bit 0/1 values with a zero line |\n\nAll changes are in presentation code. The finite-depth receiver numerical output was checked on a real 32-symbol Identity GUI run.\n''','utf8')
README='''# HF-TCM-SIM GUI_UX-01 full audit\n\nThis package collects the interface refinement, scientific source audit and selected reproducibility evidence for an independent review.\n\n## Review first\n1. `docs/repro/GUI_UX_01_FINAL_REPORT.md`\n2. `docs/repro/GUI_UX_01_ARTICLE_COMPLIANCE_AUDIT.md`\n3. `docs/repro/REPRO_08_ARTICLE_CROSSWALK.md`\n4. `outputs/gui_ux_01/verification/verification.json`\n5. `outputs/gui_ux_01/verification/before_after.md`\n6. `src/hf_tcm/studio/static/scientific_ux.js` and adjacent scientific HTML/CSS/JS\n7. `outputs/repro10a/reference_runs/`\n\n## Scope and results\nThe GUI uses the existing scientific workspace and backend. Presentation-only files changed; no receiver/channel/encoder/Viterbi/statistics implementation was altered. A 32-symbol noiseless Identity run in Edge displayed zero errors for both receivers on the same observation. Full pytest: 1182 passed; scoped Ruff and Node checks passed; historical fingerprints: 694/694.\n\nThe UI acceptance is partial: interactive QA was run at 1366×768 and nine tab captures were saved. No valid 1920×1080 captures are included; the attempted capture failed and was discarded. This archive does not claim GUI acceptance for fresh Static Multipath, Rician, or Monte Carlo runs. Existing REPRO-10A reference controls and paired pilot are included as prior scientific evidence.\n\n## Article compliance\nThe visual source audit verifies encoder figure information and finds important unresolved differences: production metric (2) uses squared Euclidean distance where the article's rendered expression shows a signed residual sum; active survivor estimator and iid complex AWGN are project-defined reconstructions. `paper_exact:false` remains. The 1.5 dB claim is not confirmed and physical energy gain remains not estimable. Source DOCX and supporting DOC are included with verified hashes; source rendering snippets and limitations are documented in the compliance audit.\n\n## Contents\nProject-relative paths are preserved. The archive includes primary and alternate paper editions, companion DOC, source modules for the transmitter/channel/receivers/estimators/Viterbi/statistics, GUI files, tests, selected actual outputs, exported plots, Edge screenshots and hashes. The manifest lists and hashes every payload file except itself. PNGs are checked for decoding, opacity and non-white pixels; SVG files are parsed as XML.\n'''
files=set()
def add(p):
 p=Path(p)
 if p.is_file() and not any(x in p.parts for x in ['__pycache__','.pytest_cache','node_modules','.venv']):files.add(p)
for name in ['docs/repro/GUI_UX_01_FINAL_REPORT.md','docs/repro/GUI_UX_01_ARTICLE_COMPLIANCE_AUDIT.md','docs/repro/REPRO_09_GUI_USER_GUIDE.md','docs/repro/REPRO_08_ARTICLE_CROSSWALK.md','docs/BUILD_VERIFICATION.md','PLAN.md','NEXT_TASK.md','references/README.md','references/SHA256SUMS.txt','references/Яковів_Гриненко_2026_в7 27-10-26(4).docx','references/alternate_versions/Яковів_Гриненко_2026_в7 27-10-26(6).docx','references/Раздел_4.doc','references/source_paper_2026.docx','references/supervisor/Яковів_Гриненко_2026_в3_24_10_2026.docx','outputs/gui_ux_01/verification/verification.json','outputs/gui_ux_01/verification/identity_backend_display_check.json','outputs/gui_ux_01/verification/before_after.md','outputs/gui_ux_01/source_audit/source_hashes.json','outputs/gui_ux_01/source_audit/independent_math_tests.log','outputs/gui_ux_01/source_audit/independent_receiver_tests.log','outputs/gui_ux_01/source_audit/primary_equations_visual.png','outputs/gui_ux_01/source_audit/primary_figure_66.png','outputs/gui_ux_01/source_audit/primary_figure_67.png','outputs/gui_ux_01/source_audit/chapter4_companion_pdf_page19.png','outputs/repro10a/acceptance/gui_ux01_qa.json','outputs/repro10a/reference_control_summary.json','outputs/repro10a/audit/historical_fingerprint_verification.json','outputs/repro10a/audit/output_integrity.json','outputs/repro10a/audit/legacy_pair_ser_recount.json','scripts/qa_gui_ux01.js','scripts/verify_repro06b_artifacts.py','scripts/build_gui_ux01_audit.py']:
 add(name)
for p in [Path('src/hf_tcm/repro'),Path('src/hf_tcm/studio/static'),Path('tests/repro'),Path('outputs/repro10a/reference_runs'),Path('outputs/repro10a/paired_experiment'),Path('outputs/gui_ux_01/source_audit'),Path('docs/screenshots/gui-ux-01'),Path('outputs/repro10a/acceptance')]:
 for f in p.rglob('*'):
  if f.is_file() and (f.suffix.lower() in {'.py','.js','.html','.css','.json','.md','.npz','.png','.svg','.log'}):add(f)
# Keep experimental outputs bounded: selected single runs and paired records only, not prior archives/plots duplication.
for p in list(files):
 if 'outputs/repro10a/acceptance' in p.as_posix() and p.suffix.lower() not in {'.png','.svg','.json'}:files.remove(p)
# Ensure captured screenshots only, exclude accidental screenshots from unrelated previous phases.
for p in list(files):
 if p.as_posix().startswith('docs/screenshots/gui-ux-01/') and p.suffix.lower()!='.png':files.remove(p)
manifest=[]
for p in sorted(files,key=lambda p:p.as_posix().lower()):
 b=p.read_bytes();manifest.append({'path':p.as_posix(),'size_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
zip_path=ROOT/'HF_TCM_SIM_GUI_UX_01_FULL_AUDIT.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('README_FOR_CHATGPT.md',README)
 for item in manifest:z.write(ROOT/item['path'],item['path'])
 z.writestr('AUDIT_MANIFEST.json',json.dumps({'files':manifest,'manifest_note':'Lists payload files; README and manifest are excluded from their own digest.'},ensure_ascii=False,indent=2)+'\n')
# Validate archive, hashes, png and svg visibility/content.
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 entries=set(z.namelist());assert 'README_FOR_CHATGPT.md' in entries and 'AUDIT_MANIFEST.json' in entries
 m=json.loads(z.read('AUDIT_MANIFEST.json'));assert len(m['files'])==len(manifest)
 for row in m['files']:
  data=z.read(row['path']);assert len(data)==row['size_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
  if row['path'].lower().endswith('.png'):
   im=Image.open(__import__('io').BytesIO(data)).convert('RGBA');alpha=im.getchannel('A');assert alpha.getextrema()[0]>240 or alpha.getextrema()[1]>0
   assert len(im.getcolors(maxcolors=im.width*im.height) or [])>1
  if row['path'].lower().endswith('.svg'):ET.fromstring(data)
print(json.dumps({'archive':zip_path.name,'bytes':zip_path.stat().st_size,'files_count':len(manifest)+2,'payload_count':len(manifest),'sha256':hashlib.sha256(zip_path.read_bytes()).hexdigest(),'verified':True},indent=2))





