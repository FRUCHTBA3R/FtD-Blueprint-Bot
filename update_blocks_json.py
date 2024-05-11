import json
import os.path as path

assert path.isfile("blocks.json")
assert path.isfile("materials.json")

# load blocks and materials configuration
with open("blocks.json", "r") as f:
    blocks = json.loads(f.read())
with open("materials.json", "r") as f:
    materials = json.loads(f.read())

def set_best_material_for_block(block) -> bool:
    """Set the best matching material as block material. 
    Returns true if material was changed."""
    v = block["Name"].lower().replace("(", "").replace(")", "")
    v = f" {v} "
    best_material = "Missing"
    length_longest_found_keyword = 0
    for m in materials:
        for keyword in materials[m]["Keywords"]:
            keywordlow = f" {keyword.lower()} "
            if v.find(keywordlow) >= 0:
                # store best matching material, where matching score is keyword length
                if len(keyword) > length_longest_found_keyword:
                    length_longest_found_keyword = len(keyword)
                    best_material = m
    if length_longest_found_keyword > 0 and block.get("Material") != best_material:
        block["Material"] = best_material
        return True
    return False

count = 0
# map
for k in blocks:
    elem = blocks[k]
    count += set_best_material_for_block(elem)

# save blocks
blocks_file = "blocks.json"
with open(blocks_file, "w") as f:
    json.dump(blocks, f, indent="\t", sort_keys=True)

print(f"Assigned materials to {count} blocks")