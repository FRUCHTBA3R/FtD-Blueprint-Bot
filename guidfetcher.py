import os
import json
import legend_generator as legend

from dotenv import load_dotenv

load_dotenv()

# mods folder of From The Depths
ftdmodsfolder = os.getenv("GAME_DIRECTORY")
invalid_file_ends = ["buildguide", "mtl", "wav", "blueprint", "dll", "obj", "object", "cs",
                     "prefab", "mat", "png_hcm.swatch", "jpeg", "cache", "jpg",
                     "png", "animclip", "sln", "csprojAssemblyReference.cache", "csproj",
                     "csproj.FileListAbsolute.txt", "csproj.CopyComplete", "csproj.CoreCompileInputs.cache",
                     "helpage", "pdf", "manifest", "uielements", "mesh", "material", "texture", "audioclip"]
invalid_files = ["guidmap.json"]
valid_file_ends = ["item", "itemduplicateandmodify"]

assert os.path.isdir(ftdmodsfolder), "Game directory invalid"

# load old blocks
with open("blocks.json", "r") as f:
    old_blocks = json.loads(f.read())

guiddict = {}
guiddict_noname = {}
guiddict_nosize = {}
for root, dirs, files in os.walk(ftdmodsfolder):
    for file in files:
        if file in invalid_files:
            continue
        fileend = file.split(".")[-1]
        #if len(fileend) < 2:
        #    continue
        #fileend = fileend[-1]
        #if fileend in invalid_file_ends:
        #    continue
        #print(fileend)
        if fileend not in valid_file_ends:
            continue
        data = None
        c_file = os.path.join(root, file)
        with open(c_file, "r") as f:
            try:
                data = json.loads(f.read())
            except BaseException:
                print("json load failed for file:", c_file)
                continue
            if "ComponentId" in data:
                guid = data["ComponentId"]["Guid"]
                name = data["ComponentId"]["Name"]
                sizeinfo = data.get("SizeInfo")
                if type(sizeinfo) is dict:
                    sizeinfo = {"SizeNeg": sizeinfo.get("SizeNeg"), "SizePos": sizeinfo.get("SizePos")}
                variant = data.get("InventoryTabOrVariantId", {}).get("Reference", {}).get("Name", "")
                if name is None:
                    if sizeinfo is None:
                        print("No name and no size info on", guid)
                        continue
                    # print("No name on", guid)
                    guiddict_noname[guid] = {"SizeInfo": sizeinfo, "Name": None, "Variant": variant}
                    continue
                elif sizeinfo is None:
                    # print("No size info on", guid)
                    guiddict_nosize[guid] = {"Name": name, "SizeInfo": None, "Variant": variant}
                    continue
                if guid in guiddict:
                    print(f"Multiple occurrences: Guid:{guid} Name:{name} SizeInfo:{sizeinfo}")
                guiddict[guid] = {"Name": name, "SizeInfo": sizeinfo, "Variant": variant}

print(f"No names: {len(guiddict_noname)}; No size info: {len(guiddict_nosize)}")
# merge
for k in guiddict_nosize:
    if k not in guiddict:
        guiddict[k] = guiddict_nosize[k]

#for k in old_blocks:
#    if k not in guiddict:
#        if k in guiddict_nosize and k in guiddict_noname:
#            print(k, "in nosize and noname")
        #elif k in guiddict_nosize:
        #    print(k, "in nosize")
        #elif k in guiddict_noname:
        #    print(k, "in noname")
#        if old_blocks[k]["SizeId"] != 1:
#            print(k, old_blocks[k])

# load config
materials = None
materials_file = "materials.json"
with open(materials_file, "r") as f:
    materials = json.load(f)
for m in materials:
    for i in range(len(materials[m]["Keywords"])):
        materials[m]["Keywords"][i] = f" {materials[m]['Keywords'][i].lower()} "

# create id to size dict
sizeiddict = {0: {0: {0: {0: {0: {0: 1}}}}}}
sizeiddict_nextid = 2


# sizedict update function
def update_sizedict(elem):
    """Update positiv and negativ sizedict with contents of elem. Set elem['SizeIdPos'] and elem['SizeIdNeg']."""
    global sizeiddict, sizeiddict_nextid
    sizeinfo = elem.get("SizeInfo")
    if sizeinfo is None:
        elem["SizeId"] = 1
        if "SizeInfo" in elem:
            del elem["SizeInfo"]
        return

    # read
    precurrent = None
    current = sizeiddict
    for sel in ["SizePos", "SizeNeg"]:
        size = sizeinfo[sel]
        for i in ["x", "y", "z"]:
            if size[i] not in current:
                current[size[i]] = {}
            precurrent = current
            current = current[size[i]]
    if type(current) is dict:
        precurrent[size["z"]] = sizeiddict_nextid
        sizeiddict_nextid += 1
    elem["SizeId"] = precurrent[size["z"]]
    del elem["SizeInfo"]


count_mat_var = 0
variant_to_material_count = {}
# map
for k in guiddict:
    elem = guiddict[k]
    update_sizedict(elem)
    v = elem["Name"].lower().replace("(", "").replace(")", "")
    v = f" {v} "
    elem["Variant"] = elem["Variant"].lower().replace("(", "").replace(")", "")
    variant = f" {elem['Variant']} " if elem["Variant"] != "" else None
    elem["Material"] = "Missing"  # default material
    # set material from name
    for m in materials:
        for keyword in materials[m]["Keywords"]:
            if v.find(keyword) >= 0:
                elem["Material"] = m
                break
    # set material from variation
    if elem["Material"] == "Missing" and variant is not None:
        # only add variant to list if name search has failed
        if variant not in variant_to_material_count:
            variant_to_material_count[variant] = 0
        for m in materials:
            for keyword in materials[m]["Keywords"]:
                if variant.find(keyword) >= 0:
                    elem["Material"] = m
                    count_mat_var += 1
                    variant_to_material_count[variant] += 1
                    break

for k in guiddict:
    # search for blocks without material but given variant name
    if guiddict[k]["Material"] == "Missing" and guiddict[k]["Variant"] == "resources":
        print("Found variant:", k, guiddict[k])
    del guiddict[k]["Variant"]

count_mis_mat = 0
for k in guiddict:
    elem = guiddict[k]["Material"]
    if elem == "Missing":
        count_mis_mat += 1
print(f"Materials set by variation name: {count_mat_var:,}\nMissing materials: {count_mis_mat:,}")
print("Unused variants:")
for k, v in variant_to_material_count.items():
    if v == 0:
        print(k)


# manual fixes
#guiddict["5e574e3c-24af-409c-b165-f079ba9c1946"]["Material"] = "Metal"  # Duct 5x5
#guiddict["ab59ab39-179c-4fd8-bad3-2f3251f0a55a"]["Material"] = "Metal"  # Duct 7x7
#guiddict["c489a675-78ad-461c-b772-b1dc1ae16beb"]["Material"] = "Metal"  # Duct 3x3
guiddict["5e236eef-c91e-45bc-afc4-bff4d133ac14"]["Material"] = "Metal"  # Duct (3x3)
guiddict["e7fc9ece-d2f4-4671-a3e8-77196601cf4e"]["Material"] = "Metal"  # Duct (5x5)
guiddict["52b78a75-115a-4962-96f1-35177b46ba93"]["Material"] = "Metal"  # Duct (7x7)
guiddict["275b820d-dd55-49aa-9b09-48b58e8ab5da"]["Material"] = "Wing"  # aero rudder

# missing
guiddict["missing"] = {"Name": "Missing", "Length": 1, "Material": "Missing", "SizeId": 0}
guiddict["missing rotation"] = {"Name": "Missing Rotation", "Length": 1, "Material": "Missing Rotation", "SizeId": 0}

count_new = 0
for k in guiddict:
    if k not in old_blocks:
        count_new += 1
count_del = 0
for k in old_blocks:
    if k not in guiddict:
        count_del += 1
print(f"Number of blocks: Old: {len(old_blocks):,}  New: {len(guiddict):,}  Delta: +{count_new:,} | -{count_del:,}")
if input("Save (y/n)? ").lower() != "y":
    exit(0)

# save blocks
blocks_file = "blocks.json"
with open(blocks_file, "w") as f:
    json.dump(guiddict, f, indent="\t", sort_keys=True)

# save sizedict
sizedict_save = {}  # {"SizeIdPos": {}, "SizeIdNeg": {}}
for x in sizeiddict:
    for y in sizeiddict[x]:
        for z in sizeiddict[x][y]:
            for a in sizeiddict[x][y][z]:
                for b in sizeiddict[x][y][z][a]:
                    for c in sizeiddict[x][y][z][a][b]:
                        sizedict_save[sizeiddict[x][y][z][a][b][c]] = {"xp": x, "yp": y, "zp": z,
                                                                       "xn": a, "yn": b, "zn": c}
sizedict_file = "size_id_dictionary.json"
with open(sizedict_file, "w") as f:
    json.dump(sizedict_save, f, indent="\t", sort_keys=True)

# re-generate legend
legend.generate()

input("Press Enter key to exit")
exit()
