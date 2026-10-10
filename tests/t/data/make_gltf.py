# Makes the glTF test files (tests/t/gltf.jo): python3 make_gltf.py, in this directory.
#   tri.gltf  JSON, its buffer and a 2x2 PNG as data: URIs; nodes: a translation, then a child
#             scaled by 2 with an indexed triangle (no normals: flat ones) and a textured material
#   strip.glb binary; a triangle strip of 4 vertices with u8 normalized texture coordinates
#             (KHR_mesh_quantization) and vertex colors, under a matrix node; a second mesh in
#             another buffer named by URI ("more.bin", given to the loader)
#   arm.gltf  a skin of two joints ("rig:Root", "rig:Elbow" 1 up, under a node turned by a
#             matrix) bending a triangle (u8 joints, float weights); an animation "Bend": the
#             elbow turning 90 degrees round z over a second, the root stepping 2 along x
import base64, json, struct, zlib

def png2x2():
    raw = b"".join(b"\0" + bytes(row) for row in ([255, 0, 0, 255, 0, 255, 0, 255], [0, 0, 255, 255, 255, 255, 255, 255]))
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")

pos = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
idx = struct.pack("<3H", 0, 1, 2) + b"\0\0"
buf = pos + idx
doc = {
    "asset": {"version": "2.0"},
    "scene": 0, "scenes": [{"nodes": [0]}],
    "nodes": [{"translation": [1, 2, 3], "children": [1]}, {"scale": [2, 2, 2], "mesh": 0}],
    "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
    "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.25, 1, 1], "baseColorTexture": {"index": 0}}, "emissiveFactor": [0, 0.5, 0.25]}],
    "textures": [{"source": 0, "sampler": 0}], "samplers": [{"magFilter": 9728}],
    "images": [{"uri": "data:image/png;base64," + base64.b64encode(png2x2()).decode()}],
    "buffers": [{"byteLength": len(buf), "uri": "data:application/octet-stream;base64," + base64.b64encode(buf).decode()}],
    "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36}, {"buffer": 0, "byteOffset": 36, "byteLength": 6}],
    "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 0]},
                  {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"}],
}
open("tri.gltf", "w").write(json.dumps(doc, indent=1))

# the strip: positions, normals, u8 texture coordinates (normalized), colors (VEC3 float)
pos = struct.pack("<12f", 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 1, 0)
nrm = struct.pack("<12f", *([0, 0, 1] * 4))
uv = bytes([0, 0, 255, 0, 0, 255, 255, 255])
col = struct.pack("<12f", 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1)
bin0 = pos + nrm + uv + col
more = struct.pack("<9f", 0, 0, 0, 0, 0, -1, 0, -2, 0)
doc = {
    "asset": {"version": "2.0"},
    "extensionsRequired": ["KHR_mesh_quantization"], "extensionsUsed": ["KHR_mesh_quantization"],
    "scenes": [{"nodes": [0, 1]}],
    "nodes": [{"matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 0, 0, 1], "mesh": 0}, {"mesh": 1}],
    "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2, "COLOR_0": 3}, "mode": 5}]},
               {"primitives": [{"attributes": {"POSITION": 4}}]}],
    "buffers": [{"byteLength": len(bin0)}, {"byteLength": len(more), "uri": "more.bin"}],
    "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 48}, {"buffer": 0, "byteOffset": 48, "byteLength": 48},
                    {"buffer": 0, "byteOffset": 96, "byteLength": 8}, {"buffer": 0, "byteOffset": 104, "byteLength": 48},
                    {"buffer": 1, "byteOffset": 0, "byteLength": 36}],
    "accessors": [{"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3"},
                  {"bufferView": 1, "componentType": 5126, "count": 4, "type": "VEC3"},
                  {"bufferView": 2, "componentType": 5121, "normalized": True, "count": 4, "type": "VEC2"},
                  {"bufferView": 3, "componentType": 5126, "count": 4, "type": "VEC3"},
                  {"bufferView": 4, "componentType": 5126, "count": 3, "type": "VEC3"}],
}
js = json.dumps(doc).encode()
js += b" " * (-len(js) % 4)
b0 = bin0 + b"\0" * (-len(bin0) % 4)
glb = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(b0)) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(b0), 0x004E4942) + b0
open("strip.glb", "wb").write(glb)
open("more.bin", "wb").write(more)

# the arm: joints are nodes 1 (root) and 2 (elbow); node 0 holds the mesh; node 3, a matrix
# (a quarter turn round y, scaled by 2), is the rig's parent
import math
pos = struct.pack("<9f", 0, 0, 0, 0, 2, 0, 1, 0, 0)
joints = bytes([0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0])
weights = struct.pack("<12f", 1, 0, 0, 0, 1, 0, 0, 0, 0.5, 0.5, 0, 0)
ibm = struct.pack("<32f", *([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] + [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -1, 0, 1]))
times = struct.pack("<2f", 0, 1)
h = math.sqrt(0.5)
rots = struct.pack("<8f", 0, 0, 0, 1, 0, 0, h, h)
steps = struct.pack("<6f", 0, 0, 0, 2, 0, 0)
buf = pos + joints + weights + ibm + times + rots + steps
views, o = [], 0
for part in (pos, joints, weights, ibm, times, rots, steps):
    views.append({"buffer": 0, "byteOffset": o, "byteLength": len(part)})
    o += len(part)
doc = {
    "asset": {"version": "2.0"},
    "scene": 0, "scenes": [{"nodes": [0, 3]}],
    "nodes": [{"mesh": 0, "skin": 0, "translation": [9, 9, 9]},
              {"name": "rig:Root", "children": [2]},
              {"name": "rig:Elbow", "translation": [0, 1, 0]},
              {"name": "Turn", "matrix": [0, 0, -2, 0, 0, 2, 0, 0, 2, 0, 0, 0, 0, 0, 0, 1], "children": [1]}],
    "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "JOINTS_0": 1, "WEIGHTS_0": 2}}]}],
    "skins": [{"joints": [1, 2], "inverseBindMatrices": 3}],
    "animations": [{"name": "Bend", "channels": [{"sampler": 0, "target": {"node": 2, "path": "rotation"}},
                                                 {"sampler": 1, "target": {"node": 1, "path": "translation"}}],
                    "samplers": [{"input": 4, "output": 5}, {"input": 4, "output": 6, "interpolation": "STEP"}]}],
    "buffers": [{"byteLength": len(buf), "uri": "data:application/octet-stream;base64," + base64.b64encode(buf).decode()}],
    "bufferViews": views,
    "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                  {"bufferView": 1, "componentType": 5121, "count": 3, "type": "VEC4"},
                  {"bufferView": 2, "componentType": 5126, "count": 3, "type": "VEC4"},
                  {"bufferView": 3, "componentType": 5126, "count": 2, "type": "MAT4"},
                  {"bufferView": 4, "componentType": 5126, "count": 2, "type": "SCALAR"},
                  {"bufferView": 5, "componentType": 5126, "count": 2, "type": "VEC4"},
                  {"bufferView": 6, "componentType": 5126, "count": 2, "type": "VEC3"}],
}
open("arm.gltf", "w").write(json.dumps(doc, indent=1))
