# the Vanguard's forearms and hands only (for a first-person view), with its idle animation:
#   uv run --python 3.11 --with bpy python arms.py -- arms.glb vanguard.glb
import bpy, sys
args = sys.argv[sys.argv.index('--') + 1:]
out, src = args
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
keep_bones = ('ForeArm', 'Hand')
for o in list(bpy.data.objects):
    if o.type != 'MESH': continue
    if 'visor' in o.name.lower():
        bpy.data.objects.remove(o, do_unlink=True)
        continue
    me = o.data
    names = {g.index: g.name for g in o.vertex_groups}
    import bmesh
    drop = set()
    for v in me.vertices:
        w = sum(g.weight for g in v.groups if any(k in names[g.group] for k in keep_bones))
        if w < 0.5: drop.add(v.index)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in drop], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    print('kept', len(me.vertices), 'vertices of', o.name)
    if len(me.vertices) == 0: bpy.data.objects.remove(o, do_unlink=True)
# only the idle animation
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
for t in list(arm.animation_data.nla_tracks):
    if t.name != 'Idle': arm.animation_data.nla_tracks.remove(t)
for a in list(bpy.data.actions):
    if a.name != 'Idle': bpy.data.actions.remove(a)
print([t.name for t in arm.animation_data.nla_tracks], [a.name for a in bpy.data.actions])
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_animation_mode='NLA_TRACKS',
    export_image_format='JPEG', export_jpeg_quality=80, export_optimize_animation_size=True,
    export_morph=False, export_cameras=False, export_lights=False)
