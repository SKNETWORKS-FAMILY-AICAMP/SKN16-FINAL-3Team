import zipfile
import lxml.etree as ET

TARGET = "temp.docx"
with zipfile.ZipFile(TARGET, "r") as zin:
    xml = zin.read("word/document.xml")
    other_files = {item.filename: zin.read(item.filename) for item in zin.infolist() if item.filename != "word/document.xml"}

ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
root = ET.fromstring(xml)
texts = root.findall('.//w:t', ns)

replacements = {
    108: "kb",
    143: "  \uacf5\ud1b5 \ubd88\uc6a9\uc5b4 \uc81c\uac70: is, are, the \ub4f1 \uc81c\uc678",
    195: "kb",
}

for idx, value in replacements.items():
    texts[idx].text = value

with zipfile.ZipFile('temp_updated.docx', 'w') as zout:
    for filename, data in other_files.items():
        zout.writestr(filename, data)
    zout.writestr('word/document.xml', ET.tostring(root, encoding='utf-8'))

import os
os.replace('temp_updated.docx', TARGET)
