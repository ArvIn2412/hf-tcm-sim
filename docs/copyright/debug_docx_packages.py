from pathlib import Path
import zipfile
import io
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent / "debug"
out.mkdir(exist_ok=True)
template = next(root.glob("Опис_NIDS-Core.docx"))
generated = next(root.glob("Опис_*HF-TCM-SIM.docx"))

with zipfile.ZipFile(template) as original, zipfile.ZipFile(generated) as current:
    original_parts = {name: original.read(name) for name in original.namelist()}
    current_media = {
        name: current.read(name) for name in current.namelist() if name.startswith("word/media/")
    }
    current_xml = current.read("word/document.xml")

roundtrip_path = out / "roundtrip_xml.docx"
with zipfile.ZipFile(template) as original:
    xml = original.read("word/document.xml")
    prefixes = {}
    for _, pair in ET.iterparse(io.BytesIO(xml), events=("start-ns",)):
        prefixes[pair[0] or ""] = pair[1]
    for prefix, uri in prefixes.items():
        ET.register_namespace(prefix, uri)
    root_xml = ET.fromstring(xml)
    encoded_xml = ET.tostring(root_xml, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(roundtrip_path, "w", zipfile.ZIP_DEFLATED) as result:
        for entry in original.infolist():
            data = encoded_xml if entry.filename == "word/document.xml" else original.read(entry.filename)
            result.writestr(entry, data)

for name, replacements in (
    ("media_only.docx", current_media),
    ("xml_only.docx", {"word/document.xml": current_xml}),
):
    destination = out / name
    with zipfile.ZipFile(template) as original, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as result:
        for entry in original.infolist():
            result.writestr(entry, replacements.get(entry.filename, original_parts[entry.filename]))
    print(f"{name}: {destination.stat().st_size} bytes")
