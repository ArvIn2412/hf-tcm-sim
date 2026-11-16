from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
from xml.sax.saxutils import escape as xml_escape
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "copyright"
DESCRIPTION = ROOT / "Опис_компютерної_програми_HF-TCM-SIM.docx"
SOURCE_DOC = ROOT / "Текст_програми_HF-TCM-SIM.docx"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS = {"w": W, "r": R, "a": A, "wp": WP, "mc": MC}
ET.register_namespace("w", W)
ET.register_namespace("r", R)
ET.register_namespace("a", A)
ET.register_namespace("wp", WP)
ET.register_namespace("mc", MC)

SOURCE_FILES = [
    "src/hf_tcm/repro/scientific_studio.py",
    "src/hf_tcm/studio/server.py",
    "src/hf_tcm/studio/scientific.py",
    "src/hf_tcm/studio/energy.py",
    "src/hf_tcm/studio/scientific_exp03b_results.py",
    "src/hf_tcm/studio/static/scientific.html",
    "src/hf_tcm/studio/static/scientific.js",
    "src/hf_tcm/repro/source_bits.py",
    "src/hf_tcm/repro/encoder.py",
    "src/hf_tcm/repro/transmitter.py",
    "src/hf_tcm/repro/modulator.py",
    "src/hf_tcm/repro/channel_runner.py",
    "src/hf_tcm/repro/noise.py",
    "src/hf_tcm/repro/rician_fading.py",
    "src/hf_tcm/repro/multipath_channel.py",
    "src/hf_tcm/repro/joint_receiver.py",
    "src/hf_tcm/repro/survivor_channel_estimator.py",
    "src/hf_tcm/repro/joint_viterbi.py",
    "src/hf_tcm/repro/separate_receiver.py",
    "src/hf_tcm/repro/hard_8psk_demodulator.py",
    "src/hf_tcm/repro/hamming_metric.py",
    "src/hf_tcm/repro/hamming_viterbi.py",
    "src/hf_tcm/repro/information_pair_metrics.py",
    "src/hf_tcm/repro/energy_experiment.py",
    "src/hf_tcm/repro/energy_gain.py",
    "src/hf_tcm/repro/energy_statistics.py",
    "src/hf_tcm/repro/paired_experiment.py",
]

SCREENSHOTS = [
    ("docs/screenshots/gui-ux-02/parameters-1920x1080.png", "Рисунок 1 – головна панель комп'ютерної програми HF-TCM-SIM"),
    ("docs/screenshots/gui-ux-02/transmitter-1920x1080.png", "Рисунок 2 – формування сигналу TCM/8PSK"),
    ("docs/screenshots/gui-ux-02/channel-1920x1080.png", "Рисунок 3 – переданий і прийнятий сигнали в моделі радіоканалу"),
    ("docs/screenshots/gui-ux-02/viterbi-1920x1080.png", "Рисунок 4 – решітка Вітербі та локальна траєкторія декодування"),
    ("docs/screenshots/gui-energy-01b-energy-1920x1080.png", "Рисунок 5 – енергетичні характеристики та результати порівняння приймачів"),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def xml_namespaces(xml_data: bytes) -> dict[str | None, str]:
    found: dict[str | None, str] = {}
    for _, value in ET.iterparse(__import__("io").BytesIO(xml_data), events=("start-ns",)):
        prefix, uri = value
        found[prefix or None] = uri
    return found


def append_missing_namespace_declarations(xml_data: bytes, namespaces: dict[str | None, str]) -> bytes:
    text = xml_data.decode("utf-8")
    opening = re.search(r"<w:document\b[^>]*", text)
    if not opening:
        return xml_data
    tag = opening.group(0)
    for prefix, uri in namespaces.items():
        if prefix is None:
            attr = "xmlns=\"{}\"".format(uri)
        else:
            attr = "xmlns:{}=\"{}\"".format(prefix, uri)
        if attr.split("=", 1)[0] not in tag:
            tag += " " + attr
    return (text[: opening.start()] + tag + text[opening.end() :]).encode("utf-8")


def source_para_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))


def make_text_paragraph(prototype: ET.Element, text: str, *, bold: bool | None = None) -> ET.Element:
    paragraph = copy.deepcopy(prototype)
    ppr = paragraph.find("w:pPr", NS)
    for child in list(paragraph):
        if child is not ppr:
            paragraph.remove(child)
    run = ET.SubElement(paragraph, f"{{{W}}}r")
    rpr_source = prototype.find("w:r/w:rPr", NS)
    if rpr_source is not None:
        rpr = copy.deepcopy(rpr_source)
        if bold is not None:
            b = rpr.find("w:b", NS)
            if bold and b is None:
                ET.SubElement(rpr, f"{{{W}}}b")
            elif not bold and b is not None:
                rpr.remove(b)
        run.append(rpr)
    t = ET.SubElement(run, f"{{{W}}}t")
    t.set(f"{{http://www.w3.org/XML/1998/namespace}}space", "preserve")
    t.text = text
    return paragraph


def first_text_prototype(paragraphs: list[ET.Element], predicate) -> ET.Element:
    for paragraph in paragraphs:
        text = source_para_text(paragraph).strip()
        if text and predicate(text, paragraph):
            return paragraph
    raise ValueError("Could not find required paragraph prototype")


def description_content(template: zipfile.ZipFile, image_geometry: dict[str, tuple[int, int, str]]) -> tuple[bytes, list[dict[str, Any]]]:
    """Edit paragraph text while preserving the sample's original Word XML markup.

    ElementTree round-tripping the sample's DrawingML/compatibility markup makes
    Microsoft Word reject the package. This writer only substitutes text and
    paragraph identifiers in raw XML and leaves all unrelated markup untouched.
    """
    original = template.read("word/document.xml")
    body_match = re.search(rb"(<w:body\b[^>]*>)(.*?)(</w:body>)", original, re.DOTALL)
    if body_match is None:
        raise ValueError("Could not locate Word document body")
    body_inner = body_match.group(2)
    sect_match = re.search(rb"<w:sectPr\b", body_inner)
    if sect_match is None:
        raise ValueError("Could not locate Word section properties")
    paragraph_bytes = re.findall(rb"<w:p\b[^>]*>.*?</w:p>", body_inner[: sect_match.start()], re.DOTALL)
    parsed_root = ET.fromstring(original)
    parsed_body = parsed_root.find("w:body", NS)
    assert parsed_body is not None
    parsed = [node for node in list(parsed_body) if node.tag == f"{{{W}}}p"]
    if len(parsed) != len(paragraph_bytes):
        raise ValueError("Raw paragraph scan does not match parsed document structure")
    texts = [source_para_text(paragraph) for paragraph in parsed]

    def find_proto(predicate) -> bytes:
        for raw, text, element in zip(paragraph_bytes, texts, parsed, strict=True):
            if text.strip() and predicate(text, element):
                return raw
        raise ValueError("Could not find paragraph prototype in DOCX template")

    prototypes = {
        "title": find_proto(lambda text, p: text.startswith("Опис комп")),
        "body": find_proto(lambda text, p: text.startswith("Програма являє")),
        "heading": find_proto(lambda text, p: text == "Основні компоненти:"),
        "component": find_proto(lambda text, p: text.startswith("1. Рівень статистичного")),
        "step": find_proto(lambda text, p: text.startswith("1. Сенсор отримує")),
        "demo_heading": find_proto(lambda text, p: text.startswith("Демонстрація роботи")),
        "demo": find_proto(lambda text, p: text.startswith("На рисунку 1")),
        "caption": find_proto(lambda text, p: text.startswith("Рисунок 1 –")),
        "conclusion": find_proto(lambda text, p: text.startswith("Програма забезпечує")),
        "authors": find_proto(lambda text, p: text.startswith("Автори:")),
    }
    image_paragraphs = [
        raw for raw, element in zip(paragraph_bytes, parsed, strict=True) if element.find(".//w:drawing", NS) is not None
    ]
    if len(image_paragraphs) != 5:
        raise ValueError(f"Expected five template image paragraphs, found {len(image_paragraphs)}")

    def replace_text(paragraph: bytes, text: str, *, para_id: str) -> bytes:
        run_count = 0

        def replace_run(match: re.Match[bytes]) -> bytes:
            nonlocal run_count
            opening, content, closing = match.groups()
            if run_count == 0:
                if b"xml:space=" not in opening:
                    opening = opening[:-1] + b' xml:space="preserve">'
                replacement = xml_escape(text).encode("utf-8")
            else:
                replacement = b""
            run_count += 1
            return opening + replacement + closing

        result = re.sub(rb"(<w:t\b[^>]*>)(.*?)(</w:t>)", replace_run, paragraph, flags=re.DOTALL)
        if run_count == 0:
            raise ValueError("Paragraph prototype has no text run")
        result, changed = re.subn(rb'w14:paraId="[0-9A-Fa-f]+"', f'w14:paraId="{para_id}"'.encode(), result, count=1)
        if not changed:
            raise ValueError("Template paragraph has no w14:paraId attribute")
        return result

    used_ids = {
        value.decode("ascii")
        for raw in image_paragraphs
        for value in re.findall(rb'w14:paraId="([0-9A-Fa-f]+)"', raw)
    }
    output_paragraphs: list[bytes] = []
    image_index = 0
    for index, item in enumerate(description_spec()):
        if item["kind"] == "image":
            image_paragraph = image_paragraphs[image_index]
            rel_match = re.search(rb'r:embed="([^"]+)"', image_paragraph)
            if rel_match is None:
                raise ValueError("Image paragraph has no relationship id")
            rid = rel_match.group(1).decode("ascii")
            cx, cy, caption = image_geometry[rid]
            extent_pattern = rb'(<wp:extent\b[^>]*cx=")[0-9]+(" cy=")[0-9]+("/>)'
            image_paragraph, extent_count = re.subn(
                extent_pattern,
                lambda match: match.group(1) + str(cx).encode("ascii") + match.group(2) + str(cy).encode("ascii") + match.group(3),
                image_paragraph,
                count=1,
            )
            if extent_count != 1:
                raise ValueError("Image paragraph has no inline extent")
            transform_pattern = rb'(<a:ext\b[^>]*cx=")[0-9]+(" cy=")[0-9]+("/>)'
            image_paragraph, transform_count = re.subn(
                transform_pattern,
                lambda match: match.group(1) + str(cx).encode("ascii") + match.group(2) + str(cy).encode("ascii") + match.group(3),
                image_paragraph,
                count=1,
            )
            if transform_count != 1:
                raise ValueError("Image paragraph has no DrawingML image extent")
            escaped_caption = xml_escape(caption, {'"': "&quot;"}).encode("utf-8")
            def add_alt_text(match: re.Match[bytes]) -> bytes:
                attributes = re.sub(rb'\s+(?:descr|title)="[^"]*"', b"", match.group(1))
                return b"<wp:docPr" + attributes + b' descr="' + escaped_caption + b'" title="' + escaped_caption + b'"/>'

            image_paragraph, alt_count = re.subn(rb"<wp:docPr([^>]*)/>", add_alt_text, image_paragraph, count=1)
            if alt_count != 1:
                raise ValueError("Image paragraph has no docPr accessibility element")
            output_paragraphs.append(image_paragraph)
            image_index += 1
            continue
        base = prototypes[item["kind"]]
        unique = hashlib.sha256(f"copyright-docs-01-{index}-{item['text']}".encode("utf-8")).hexdigest()[:8].upper()
        while unique in used_ids:
            unique = hashlib.sha256((unique + "x").encode("ascii")).hexdigest()[:8].upper()
        used_ids.add(unique)
        output_paragraphs.append(replace_text(base, item["text"], para_id=unique))

    body_prefix = body_inner[: re.search(rb"<w:p\b", body_inner).start()] if re.search(rb"<w:p\b", body_inner) else b""
    body_suffix = body_inner[sect_match.start() :]
    updated_body = body_prefix + b"".join(output_paragraphs) + body_suffix
    updated = original[: body_match.start(2)] + updated_body + original[body_match.end(2) :]
    return updated, []


def code_content(template: zipfile.ZipFile, paths: list[str]) -> tuple[bytes, list[dict[str, Any]], list[tuple[str, list[str]]]]:
    original = template.read("word/document.xml")
    namespaces = xml_namespaces(original)
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix or "", uri)
    root = ET.fromstring(original)
    body = root.find("w:body", NS)
    assert body is not None
    paragraphs = [node for node in list(body) if node.tag == f"{{{W}}}p"]
    title_1 = paragraphs[0]
    title_2 = paragraphs[1]
    header_proto = first_text_prototype(paragraphs, lambda text, p: text == "main.py")
    code_proto = first_text_prototype(paragraphs, lambda text, p: text == "import argparse")
    blank_proto = copy.deepcopy(code_proto)
    records: list[dict[str, Any]] = []
    decoded_sources: list[tuple[str, list[str]]] = []
    new_body: list[ET.Element] = [
        make_text_paragraph(title_1, "Друкований текст програмного коду"),
        make_text_paragraph(title_2, "комп'ютерної програми «HF-TCM-SIM»"),
        make_text_paragraph(blank_proto, ""),
    ]

    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        lines = text.splitlines()
        if text and not lines:
            lines = [text]
        new_body.append(make_text_paragraph(header_proto, relative, bold=True))
        for line in lines:
            new_body.append(make_text_paragraph(code_proto, line, bold=False))
        digest = sha256(raw)
        records.append(
            {
                "path": relative.replace("\\", "/"),
                "sha256": digest,
                "size_bytes": len(raw),
                "line_count": len(lines),
                "included_range": f"1-{len(lines)}" if lines else "none",
                "transferred_lines": len(lines),
                "complete_file": True,
                "line_ending": "CRLF" if b"\r\n" in raw else "LF",
            }
        )
        decoded_sources.append((relative.replace("\\", "/"), lines))

    sect = body.find("w:sectPr", NS)
    for child in list(body):
        if child is not sect:
            body.remove(child)
    for paragraph in new_body:
        if sect is None:
            body.append(paragraph)
        else:
            body.insert(list(body).index(sect), paragraph)
    xml_data = append_missing_namespace_declarations(
        ET.tostring(root, encoding="utf-8", xml_declaration=True), namespaces
    )
    return xml_data, records, decoded_sources


def screenshot_mapping(template: zipfile.ZipFile) -> tuple[dict[str, bytes], list[dict[str, Any]], dict[str, tuple[int, int, str]]]:
    rels_data = template.read("word/_rels/document.xml.rels")
    relroot = ET.fromstring(rels_data)
    rel_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
    targets = {node.attrib["Id"]: node.attrib["Target"] for node in relroot.findall("rel:Relationship", rel_ns)}
    doc = ET.fromstring(template.read("word/document.xml"))
    image_paragraphs = [p for p in doc.findall(".//w:body/w:p", NS) if p.find(".//w:drawing", NS) is not None]
    replacements: dict[str, bytes] = {}
    records = []
    geometry: dict[str, tuple[int, int, str]] = {}
    for (relative, caption), paragraph in zip(SCREENSHOTS, image_paragraphs, strict=True):
        image_path = ROOT / relative
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        embed = paragraph.find(".//a:blip", NS)
        if embed is None:
            raise ValueError(f"No image relationship in template paragraph for {relative}")
        rid = embed.attrib[f"{{{R}}}embed"]
        target = targets[rid]
        package_path = "word/" + target.replace("\\", "/").lstrip("/")
        image_bytes = image_path.read_bytes()
        replacements[package_path] = image_bytes
        from PIL import Image
        import io

        with Image.open(io.BytesIO(image_bytes)) as im:
            width, height = im.size
        extent = paragraph.find(".//wp:extent", NS)
        if extent is not None:
            cx = 5_303_520
            cy = round(cx * height / width)
            extent.set("cx", str(cx))
            extent.set("cy", str(cy))
            transform_extent = paragraph.find(".//a:xfrm/a:ext", NS)
            if transform_extent is not None:
                transform_extent.set("cx", str(cx))
                transform_extent.set("cy", str(cy))
        docpr = paragraph.find(".//wp:docPr", NS)
        if docpr is not None:
            docpr.set("name", Path(relative).stem)
            docpr.set("descr", caption)
            docpr.set("title", caption)
        geometry[rid] = (cx, cy, caption)
        records.append(
            {
                "path": relative.replace("\\", "/"),
                "caption": caption,
                "width_px": width,
                "height_px": height,
                "size_bytes": len(image_bytes),
                "sha256": sha256(image_bytes),
                "embedded_relationship": rid,
                "embedded_package_part": package_path,
            }
        )
    return replacements, records, geometry


def write_package(template_path: Path, destination: Path, document_xml: bytes, replacements: dict[str, bytes]) -> None:
    with zipfile.ZipFile(template_path, "r") as source, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as output:
        for entry in source.infolist():
            data = document_xml if entry.filename == "word/document.xml" else replacements.get(entry.filename)
            if data is None:
                data = source.read(entry.filename)
            output.writestr(entry, data)


def verify_code_document(path: Path, source_records: list[dict[str, Any]], expected: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as docx:
        root = ET.fromstring(docx.read("word/document.xml"))
    body = root.find("w:body", NS)
    assert body is not None
    paragraphs = [node for node in list(body) if node.tag == f"{{{W}}}p"]
    cursor = 3
    verification = []
    for record, (relative, lines) in zip(source_records, expected, strict=True):
        heading = source_para_text(paragraphs[cursor])
        cursor += 1
        if heading != relative:
            raise AssertionError(f"Module heading mismatch: {heading!r} != {relative!r}")
        actual = [source_para_text(p) for p in paragraphs[cursor : cursor + len(lines)]]
        cursor += len(lines)
        if actual != lines:
            mismatch = next((i for i, pair in enumerate(zip(actual, lines)) if pair[0] != pair[1]), None)
            raise AssertionError(f"Source text mismatch in {relative} at line {mismatch}")
        if len(actual) != record["line_count"]:
            raise AssertionError(f"Line count mismatch in {relative}")
        source_raw = (ROOT / relative).read_bytes()
        if sha256(source_raw) != record["sha256"]:
            raise AssertionError(f"Source changed while building document: {relative}")
        verification.append({"path": relative, "lines_verified": len(actual), "sha256_match": True})
    return verification


def description_spec() -> list[dict[str, str]]:
    components = [
        "1. Передавач — формує двійкову інформаційну послідовність, виконує згорткове кодування та відображає кодові переходи на сигнальні символи 8PSK із подальшим формуванням дискретних комплексних відліків.",
        "2. Модель радіоканалу — формує прийняте спостереження для заданих умов AWGN, статичного багатопроменевого поширення або райсівського AR(1)-каналу з урахуванням затримок променів.",
        "3. Спільний приймач — обробляє прийняті відліки, оцінює параметри сигналу в межах реалізованого алгоритму, обчислює евклідові метрики переходів і формує рішення декодера Вітербі.",
        "4. Роздільний приймач — спочатку виконує жорстку демодуляцію 8PSK, а потім декодує отриману послідовність за решіткою згорткового коду з метрикою Хемінга; для підтримуваних статичних умов доступний режим із компенсацією каналу.",
        "5. Модулі статистичного моделювання — запускають незалежні або парні випробування з керованими початковими числами генераторів, зберігають записи випробувань і формують агреговані показники BER, SER інформаційних пар та FER у тих режимах, де ці показники передбачені обчислювальним модулем.",
        "6. Модуль енергетичного аналізу — обчислює енергію переданих дискретних відліків і на інформаційний біт, відображає енергетичні залежності та оцінює модельний виграш лише за наявності достатніх статистичних даних і допустимих перетинів кривих.",
        "7. Scientific Workspace — локальний вебінтерфейс для налаштування одиничного моделювання та статистичних серій, перегляду сигналів, сузір'я 8PSK, метрик і решітки Вітербі, порівняння результатів, енергетичного аналізу та збережених експериментів.",
    ]
    algorithm = [
        "1. Користувач задає довжину послідовності, початкові числа генераторів, профіль каналу, параметри шуму та завмирань, а також доступні режими приймання.",
        "2. Генератор формує інформаційні біти відповідно до заданої конфігурації та передає їх кодеру парами.",
        "3. Згортковий кодер формує кодові переходи й трійки; таблиця відображення переводить їх у фазові індекси 8PSK, після чого модулятор формує комплексні символи та дискретні відліки сигналу.",
        "4. Модуль каналу застосовує вибрану модель поширення: AWGN, затримані промені або райсівські завмирання з адитивним комплексним шумом.",
        "5. Для обох приймачів зберігається прийняте комплексне спостереження та його відповідність індексам символів і відліків; оцінювання результату виконується окремо після декодування.",
        "6. Спільний приймач формує кандидатні оцінки сигналу, обчислює евклідові метрики переходів і використовує їх у декодуванні за алгоритмом Вітербі.",
        "7. Роздільний приймач визначає жорсткі фазові рішення 8PSK і виконує декодування Вітербі з метрикою Хемінга; доступність канального режиму залежить від вибраної конфігурації.",
        "8. Декодовану інформаційну послідовність порівнюють із переданою для отримання кількості бітових, парних та кадрових помилок і відповідних відносних показників.",
        "9. У статистичному режимі випробування агрегують за заданими енергетичними точками; для збережених парних спостережень обчислюють довірчі інтервали й модельні енергетичні оцінки відповідно до доступного аналізатора.",
        "10. Інтерфейс показує числові результати та графіки, а завершені запуски й серії зберігаються для подальшого перегляду та відтворюваного аналізу.",
    ]
    demo = [
        "На рисунку 1 показано головну панель Scientific Workspace з основними налаштуваннями передавача, радіоканалу та приймачів, а також доступом до вкладок аналізу.",
        "На рисунку 2 наведено відображення переданих складових I/Q, структуру інформаційних пар і кодових переходів, а також незмінне нормоване сузір'я 8PSK із позначеним поточним символом.",
        "На рисунку 3 відображено передані та прийняті квадратурні складові сигналу й приклад внеску затриманих променів у дискретне спостереження.",
        "На рисунку 4 показано розширену решітку Вітербі, альтернативні переходи та виділену локальну survivor-траєкторію для поточного вікна декодування.",
        "На рисунку 5 наведено енергетичну вкладку з фактичними характеристиками одного запуску та графіками збереженої статистичної серії. Показники на екрані є результатами дискретної моделі й не означають автоматичного підтвердження фізичного Eb/N0.",
    ]
    result = [
        {"kind": "title", "text": "Опис комп'ютерної програми «HF-TCM-SIM»"},
        {"kind": "body", "text": "HF-TCM-SIM є офлайновим комп'ютерним програмним засобом для імітаційного дослідження цифрового передавання радіосигналів із решітчастою кодовою модуляцією TCM та восьмипозиційною фазовою маніпуляцією 8PSK. Програма моделює формування інформаційної послідовності, згорткове кодування, проходження сигналу через заданий радіоканал, приймання та декодування за алгоритмом Вітербі."},
        {"kind": "body", "text": "Засіб призначений для дослідження завадостійкості та дискретних енергетичних характеристик різних способів демодуляції й декодування за умов адитивного білого гаусівського шуму, статичного багатопроменевого поширення та райсівських завмирань. Scientific Workspace надає керування параметрами, візуалізацію сигналів і декодерних метрик, парне порівняння приймачів, статистичне моделювання, енергетичні графіки та засоби збереження результатів. Розрахункова шкала програми є моделлю дискретного сигналу; сама собою вона не підтверджує фізичне Eb/N0 або точне відтворення окремої наукової статті."},
        {"kind": "heading", "text": "Основні компоненти:"},
        *[{"kind": "component", "text": text} for text in components],
        {"kind": "heading", "text": "Алгоритм роботи програми:"},
        *[{"kind": "step", "text": text} for text in algorithm],
        {"kind": "heading", "text": "Демонстрація роботи програми:"},
    ]
    for index, ((image_path, caption), explanation) in enumerate(zip(SCREENSHOTS, demo, strict=True), start=1):
        result.extend(
            [
                {"kind": "demo", "text": explanation},
                {"kind": "image", "text": f"[[PIC_{index}]]", "path": image_path},
                {"kind": "caption", "text": caption},
            ]
        )
    result.extend(
        [
            {"kind": "conclusion", "text": "HF-TCM-SIM дає змогу відтворювано досліджувати формування та цифрове оброблення сигналів TCM/8PSK, оцінювати вплив модельних параметрів радіоканалу на достовірність приймання й аналізувати дискретні енергетичні характеристики спільної та роздільної демодуляції й декодування. Програма є офлайновим засобом імітаційного моделювання; вона не є системою реального радіозв'язку та не керує радіообладнанням або безпілотними літальними апаратами."},
            {"kind": "authors", "text": "Автори: [ПІБ автора/авторів комп'ютерної програми]"},
        ]
    )
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    desc_template = next(ROOT.glob("Опис_NIDS-Core.docx"))
    code_template = next(ROOT.glob("Текст_програми_NIDS-Core.docx"))
    with zipfile.ZipFile(desc_template) as template:
        image_replacements, screenshot_records, image_geometry = screenshot_mapping(template)
        desc_xml, _ = description_content(template, image_geometry)
    write_package(desc_template, DESCRIPTION, desc_xml, image_replacements)
    (OUT / "DESCRIPTION_CONTENT.json").write_text(
        json.dumps(description_spec(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "DESCRIPTION_DOCX_PATH.txt").write_text(str(DESCRIPTION), encoding="utf-8")
    (OUT / "DESCRIPTION_TEMPLATE_PATH.txt").write_text(str(desc_template), encoding="utf-8")
    (OUT / "SOURCE_CODE_DOCX_PATH.txt").write_text(str(SOURCE_DOC), encoding="utf-8")

    with zipfile.ZipFile(code_template) as template:
        code_xml, source_records, expected = code_content(template, SOURCE_FILES)
    write_package(code_template, SOURCE_DOC, code_xml, {})
    verification = verify_code_document(SOURCE_DOC, source_records, expected)

    (OUT / "SOURCE_FILES_INCLUDED.json").write_text(
        json.dumps({"files": source_records, "verification": verification}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "SCREENSHOTS_USED.json").write_text(
        json.dumps({"screenshots": screenshot_records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"description": str(DESCRIPTION), "source_code": str(SOURCE_DOC), "source_files": len(source_records), "source_lines": sum(x["line_count"] for x in source_records), "source_integrity": "PASS", "screenshots": len(screenshot_records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
