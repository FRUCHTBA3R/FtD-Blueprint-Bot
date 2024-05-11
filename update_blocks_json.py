import json
import os.path as path

assert path.isfile("blocks.json")
assert path.isfile("materials.json")

# load blocks and materials configuration
with open("blocks.json", "r") as f:
    blocks = json.loads(f.read())
with open("materials.json", "r") as f:
    materials = json.loads(f.read())

# map
for k in blocks:
    elem = blocks[k]
    v = elem["Name"].lower().replace("(", "").replace(")", "")
    v = f" {v} "
    for m in materials:
        for keyword in materials[m]["Keywords"]:
            keywordlow = f" {keyword.lower()} "
            if v.find(keywordlow) >= 0:
                elem["Material"] = m
                break

# save blocks
blocks_file = "blocks.json"
with open(blocks_file, "w") as f:
    json.dump(blocks, f, indent="\t", sort_keys=True)