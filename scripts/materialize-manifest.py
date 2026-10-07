#!/usr/bin/env python3
"""Write the pinned Android manifest using configured public HTTPS remotes."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlunsplit

workspace = Path(__file__).resolve().parents[1]
manifest = ET.parse(workspace / "manifests/final-platform.xml")
remotes = json.loads((workspace / "config/source-remotes.json").read_text())
for remote in manifest.getroot().findall("remote"):
    endpoint = remotes[remote.get("name")]
    assert endpoint["scheme"] == "https"
    assert endpoint["host"] and "@" not in endpoint["host"]
    remote.set("fetch", urlunsplit((endpoint["scheme"], endpoint["host"], endpoint["path"], "", "")))
destination = Path(sys.argv[1])
destination.parent.mkdir(parents=True, exist_ok=True)
ET.indent(manifest)
manifest.write(destination, encoding="utf-8", xml_declaration=True)
print(f"Materialized {len(manifest.getroot().findall('project'))} pinned projects.")
