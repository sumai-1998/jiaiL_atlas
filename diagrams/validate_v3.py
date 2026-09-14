#!/usr/bin/env python3
"""Static checks and illustrative interface arithmetic, NOT model integration tests."""
from __future__ import annotations
import ast
import hashlib
import math
from pathlib import Path
from urllib.parse import urlparse

from lxml import etree
from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
NS = {"s": "http://www.w3.org/2000/svg"}
FONT_ROOT = Path("/usr/share/fonts/opentype/noto")
PRESERVED = {
    "diagrams/atlas_architecture.svg": "c283344bb89502ea7ed8c42729cbaa4472bc469e16accc6b71eab5d214e7d16b",
    "diagrams/atlas_open_source_map.svg": "9b8896fb8b934aad490fe6a82d9c4ccc508f1a4220f58435b95ed4475300115c",
    "diagrams/atlas_architecture_calibrated.svg": "6cf149d841b4ff2690b631a4b45434830dd86d332b7a126d8e0cb62b54d0edf2",
    "diagrams/atlas_open_source_map_calibrated.svg": "1740ee5e3af800dcfb6ee331838329414165a5461b930db270d0bbbdf9836e3e",
    "ATLAS_REVIEW_2026-09-06.md": "9bd85f9daa44351dddc26f97ee580f18a3358cf2e9df8c3290d4904afd2843ad",
}

def validate_svg(name: str) -> None:
    filename = ROOT / "diagrams" / name
    tree = etree.parse(str(filename), etree.XMLParser(resolve_entities=False, no_network=True))
    root = tree.getroot()
    width, height = float(root.get("width")), float(root.get("height"))
    assert root.get("viewBox") == f"0 0 {int(width)} {int(height)}"
    assert not tree.findall(".//s:image", NS), "Embedded raster image"
    assert not tree.findall(".//s:foreignObject", NS), "Non-native SVG content"
    assert not tree.findall(".//s:script", NS), "Unexpected script"
    ids = [e.get("id") for e in tree.iter() if e.get("id")]
    assert len(ids) == len(set(ids)), "Duplicate SVG ids"
    for e in tree.iter():
        for attr in ("marker-end", "marker-start"):
            value = e.get(attr)
            if value:
                assert value.startswith("url(#") and value[5:-1] in ids, value
    for t in tree.findall(".//s:text", NS):
        label = "".join(t.itertext())
        size = int(t.get("font-size", "21"))
        weight = int(t.get("font-weight", "400"))
        font = ImageFont.truetype(str(FONT_ROOT / (
            "NotoSansCJK-Bold.ttc" if weight >= 600 else "NotoSansCJK-Regular.ttc"
        )), size, index=2)
        extent = font.getlength(label) + max(0, len(label) - 1) * float(t.get("letter-spacing", "0"))
        assert extent <= float(t.get("data-max-width")) + 0.5, (label, extent)
        x, y = float(t.get("x")), float(t.get("y"))
        anchor = t.get("text-anchor", "start")
        left = x - (extent if anchor == "end" else extent / 2 if anchor == "middle" else 0)
        assert 0 <= left and left + extent <= width + 0.5, label
        assert size <= y <= height - size * 0.2, label
    links = tree.findall(".//s:a", NS)
    for a in links:
        href = a.get("href")
        assert href == a.get("{http://www.w3.org/1999/xlink}href")
        parsed = urlparse(href)
        if parsed.scheme:
            assert parsed.scheme == "https" and parsed.netloc
        else:
            assert (filename.parent / parsed.path).resolve().is_file(), href
    print(f"PASS SVG: {name}; {len(tree.findall('.//s:text', NS))} texts; {len(links)} links; native vectors")

def mv(matrix, vector):
    return [sum(a * b for a, b in zip(row, vector)) for row in matrix]

def transpose(matrix):
    return list(map(list, zip(*matrix)))

def mm(a, b):
    return [[sum(x * y for x, y in zip(row, col)) for col in transpose(b)] for row in a]

def close(a, b):
    assert len(a) == len(b)
    assert all(math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-9) for x, y in zip(a, b)), (a, b)

def project(k, point):
    pixel = mv(k, point)
    return [pixel[0] / pixel[2], pixel[1] / pixel[2]]

def camera_contract_examples():
    # OpenCV c2w: nontrivial rotation and translation.
    rotation = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
    translation = [2, -1, 5]
    camera_point = [1, 0.5, 4]
    world_point = [a + b for a, b in zip(mv(rotation, camera_point), translation)]
    reconstructed_camera = mv(transpose(rotation), [a - b for a, b in zip(world_point, translation)])
    close(reconstructed_camera, camera_point)
    k = [[400, 0, 320], [0, 420, 240], [0, 0, 1]]
    uv = project(k, reconstructed_camera)
    close(uv, [420, 292.5])
    unprojected = [(uv[0] - 320) * 4 / 400, (uv[1] - 240) * 4 / 420, 4]
    close(unprojected, camera_point)

    # Normalized intrinsics must be converted back before a pixel-space renderer.
    normalized = [[v / 640 for v in k[0]], [v / 480 for v in k[1]], k[2]]
    recovered = [[v * 640 for v in normalized[0]], [v * 480 for v in normalized[1]], normalized[2]]
    close(project(recovered, camera_point), uv)
    assert project(normalized, camera_point) != uv

    # Resize by 0.5, then pad by (11,23): K_new = A_image @ K.
    image_transform = [[0.5, 0, 11], [0, 0.5, 23], [0, 0, 1]]
    changed_k = mm(image_transform, k)
    close(project(changed_k, camera_point), [0.5 * uv[0] + 11, 0.5 * uv[1] + 23])
    print("PASS illustrative camera arithmetic: c2w inverse, projection/unprojection, pixel K, resize/pad")

def depth_and_state_examples():
    weights, z = [0.2, 0.3], [2.0, 6.0]
    alpha = sum(weights)
    accumulated = sum(w * d for w, d in zip(weights, z))
    expected = accumulated / alpha
    assert math.isclose(accumulated, 2.2)
    assert math.isclose(expected, 4.4)
    assert not math.isclose(accumulated, expected)

    # Illustrative adapter validity policy, not a calibrated model threshold.
    def valid_expected(d, a, threshold=1e-3):
        return d / a if a >= threshold else None
    assert valid_expected(1e-5, 1e-6) is None

    rotation = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
    covariance = [[1, 0, 0], [0, 4, 0], [0, 0, 9]]
    scale = 2
    transformed = [[scale**2 * x for x in row] for row in mm(mm(rotation, covariance), transpose(rotation))]
    close([transformed[i][i] for i in range(3)], [36, 16, 4])
    close([math.exp(math.log(s)) for s in (0.1, 0.2, 0.3)], [0.1, 0.2, 0.3])
    print("PASS illustrative depth/state arithmetic: D vs ED, low-alpha invalidity, Sim(3) covariance, GS activation")

def source_boundary_check():
    source = (ROOT / "WorldWarp" / "pose_control.py").read_text()
    tree = ast.parse(source)
    functions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    def called(function):
        return {n.func.id for n in ast.walk(function) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    entry = functions["run_inference_chunk"]
    assert {"batch_warp_frames_via_3dgs", "sample_sequence"} <= called(entry)
    assert "batch_warp_frames_via_3dgs" not in called(functions["sample_sequence"])
    loaded_names = {n.id for n in ast.walk(entry) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    assert "combined_video_path" not in loaded_names and "cache_all" not in loaded_names
    print("PASS static source boundary: full WorldWarp entry still rebuilds geometry; sampler is a separate function")

def preserved_files_check():
    for name, expected_hash in PRESERVED.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert actual == expected_hash, f"Historical file changed: {name}"
    print("PASS preservation: V1/V2 SVGs and V2 report are unchanged")

if __name__ == "__main__":
    for name in ("atlas_architecture_v3.svg", "atlas_open_source_map_v3.svg"):
        validate_svg(name)
    camera_contract_examples()
    depth_and_state_examples()
    source_boundary_check()
    preserved_files_check()
    print("NOT TESTED: GPU inference, model quality, cross-repository integration or long-horizon consistency.")
