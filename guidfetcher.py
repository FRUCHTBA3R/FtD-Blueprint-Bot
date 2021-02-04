import os
import json

# search every file for json tag ComponentId
FORCE_COMPLETE_FILE_SEARCH = True

# mods folder of From The Depths
ftdmodsfolder = "O:/SteamLibrary/steamapps/common/From The Depths/From_The_Depths_Data/StreamingAssets/Mods"
invalid_file_ends = ["buildguide", "mtl", "wav", "blueprint", "dll", "obj", "cs",
                     "prefab", "mat", "png_hcm.swatch", "jpeg", "cache", "jpg",
                     "png", "animclip", "sln", "csprojAssemblyReference.cache", "csproj",
                     "csproj.FileListAbsolute.txt", "csproj.CopyComplete",
                     "csproj.CoreCompileInputs.cache", "helpage"]
guiddict = {}
extrainvguiddict = {}
for root, dirs, files in os.walk(ftdmodsfolder):
    found = False
    for file in files:
        if file == "guidmap.json":
            found = True
            c_file = os.path.join(root, file)
            with open(c_file, "r") as f:
                try:
                    data = json.loads(f.read())
                    data = {v:{"Name":k} for k,v in data.items()}
                    extrainvguiddict.update(data)
                except:
                    print("json load failed for file:", c_file)
            break
    if found or FORCE_COMPLETE_FILE_SEARCH:
        for file in files:
            fileend = file.split(".", 1)[1]
            if fileend in invalid_file_ends:
                break
            data = None
            c_file = os.path.join(root, file)
            with open(c_file, "r") as f:
                try:
                    data = json.loads(f.read())
                except:
                    print("json load failed for file:", c_file)
                    data = {}
                if "ComponentId" in data:
                    if data["ComponentId"]["Name"] in guiddict:
                        extrainvguiddict[guiddict[data["ComponentId"]["Name"]]] = {"Name":data["ComponentId"]["Name"]}
                    guiddict[data["ComponentId"]["Name"]] = data["ComponentId"]["Guid"]
# invert dict with values as dict
invguiddict = {v:{"Name":k} for k,v in guiddict.items()}
if len(extrainvguiddict) > 0:
    print(len(invguiddict), "&", len(extrainvguiddict))
    invguiddict.update(extrainvguiddict)
    print("->", len(invguiddict))


# load config
materials = None
materials_file = "materials.json"
with open(materials_file, "r") as f:
    materials = json.loads(f.read())
sizedict = {"1m": 1, "2m": 2, "3m": 3, "4m": 4, "6m": 6, "8m": 8,
            "1x1": 1, "3x3": 33, "5x5": 34, "7x7": 35,
            "2m3x3": 40, "3m5x5": 41, "3m3x3": 42, "2m2x2": 43,
            " 5m": 50, " 7m": 51, " 9m": 52,
            "2mUpright": 62, "3mUpright": 63, "4mUpright": 64, "3mCenteredUpright": 70,
            "2mSideways": 80, "1m3x3Sideways": 82, "1m5x5Sideways": 84, "2m3x3Sideways": 86, "3m5x5Sideways": 88,  # mirrored pieces have index + 1
            "3x3Upright": 90, "5x5Upright": 91, "3m3x3Upright": 92,
            }

#map
for k in invguiddict:
    v = invguiddict[k]["Name"].lower().replace("(", "").replace(")", "")
    v = f" {v} "
    invguiddict[k]["Material"] = "Missing"  # default material
    invguiddict[k]["Length"] = 1  # default length
    for m in materials:
        ml = f" {m.lower()} "
        if v.find(ml) >= 0:
            invguiddict[k]["Material"] = m
            break
    for size in sizedict:
        if v.find(size) >= 0:
            invguiddict[k]["Length"] = sizedict[size]
            break

    # wheels
    if v.find(" wheel ") >= 0:
        mirrored = 0
        if v.find(" mirror ") >= 0:
            mirrored = 1
        if invguiddict[k]["Length"] == 1:
            if v.find(" balloon ") >= 0:
                invguiddict[k]["Length"] = sizedict["2mSideways"] + mirrored
            # else just use length 1 which is already set
        elif invguiddict[k]["Length"] == 3:
            if v.find(" balloon ") >= 0:
                invguiddict[k]["Length"] = sizedict["2m3x3Sideways"] + mirrored
            else:
                invguiddict[k]["Length"] = sizedict["1m3x3Sideways"] + mirrored
        elif invguiddict[k]["Length"] == 50: # 5m gets mapped to 50
            if v.find(" balloon ") >= 0:
                invguiddict[k]["Length"] = sizedict["3m5x5Sideways"] + mirrored
            else:
                invguiddict[k]["Length"] = sizedict["1m5x5Sideways"] + mirrored
        continue

    # turrets
    if v.find(" turret ") >= 0:
        if invguiddict[k]["Length"] == 3:
            invguiddict[k]["Length"] = sizedict["3x3Upright"]
        elif invguiddict[k]["Length"] == 50:  # 5m gets mapped to 50
            invguiddict[k]["Length"] = sizedict["5x5Upright"]
        continue

    # rtgs
    if v.find(" rtg ") >= 0:
        if invguiddict[k]["Length"] == 2:
            invguiddict[k]["Length"] = sizedict["2mUpright"]
        elif invguiddict[k]["Length"] == 4:
            invguiddict[k]["Length"] = sizedict["4mUpright"]
        elif invguiddict[k]["Length"] == 3:  # 3x3m gets mapped to 3
            invguiddict[k]["Length"] = sizedict["3m3x3Upright"]
        continue

    # batteries
    if v.find(" battery ") >= 0:
        if v.find(" beam ") >= 0:
            invguiddict[k]["Length"] = 4
        elif v.find(" medium ") >= 0:
            invguiddict[k]["Length"] = sizedict["2m2x2"]
        elif v.find(" large ") >= 0:
            invguiddict[k]["Length"] = sizedict["3x3Upright"]
        continue

    # square backed corners
    if invguiddict[k]["Name"].find("Square backed corner") >= 0:
        invguiddict[k]["Length"] = 2
        continue
    if invguiddict[k]["Name"].find("1m to 3m slope transition right") >= 0:
        invguiddict[k]["Length"] = 2
        continue


# manual fixes
invguiddict["867cea4e-6ea4-4fe2-a4a1-b6230308f8f1"]["Length"] = 4
invguiddict["5e574e3c-24af-409c-b165-f079ba9c1946"]["Material"] = "Metal"
invguiddict["ab59ab39-179c-4fd8-bad3-2f3251f0a55a"]["Material"] = "Metal"
invguiddict["c489a675-78ad-461c-b772-b1dc1ae16beb"]["Material"] = "Metal"
invguiddict["5e236eef-c91e-45bc-afc4-bff4d133ac14"]["Material"] = "Metal"
invguiddict["e7fc9ece-d2f4-4671-a3e8-77196601cf4e"]["Material"] = "Metal"
invguiddict["52b78a75-115a-4962-96f1-35177b46ba93"]["Material"] = "Metal"
# truss fixes
invguiddict["fe88a923-b85b-4471-bce5-8ceb1d0ddb14"]["Length"] = sizedict["4mUpright"]  # truss 4m
invguiddict["1dd66387-6293-4fa0-a1da-6f0e4cb80dfa"]["Length"] = sizedict["4mUpright"]  # truss 4m
invguiddict["21646640-41cf-42a3-931a-3c40b9c79d83"]["Length"] = sizedict["3mUpright"]  # truss 3m
invguiddict["ac24cd04-449e-47b9-bf8c-bf58d9997264"]["Length"] = sizedict["3mUpright"]  # truss 3m
invguiddict["de17ff79-e670-4f08-ab59-df1ecac3905b"]["Length"] = sizedict["2mUpright"]  # truss 2m
invguiddict["19a1d5ad-99e3-4a18-8943-22a82f554231"]["Length"] = sizedict["2mUpright"]  # truss 2m
# mantlet fixes
invguiddict["5396a3df-77ca-430a-96bf-bd81324c05ba"]["Length"] = sizedict["2mUpright"]  # aa mantlet 2m
invguiddict["627957c0-d34a-46b1-a5eb-c08a34748b77"]["Length"] = sizedict["2mUpright"]  # aa mantlet 2m
invguiddict["2f87caef-8e9d-468f-925e-b0bf98e071f3"]["Length"] = sizedict["2mUpright"]  # aa mantlet 2m
invguiddict["a4eb415c-7ba9-4e27-a118-2d450c48c236"]["Length"] = sizedict["3mCenteredUpright"]  # elevation mantlet 3m
invguiddict["19e0aacf-5bcc-45da-8c4f-a50984514bbf"]["Length"] = sizedict["3mCenteredUpright"]  # elevation mantlet 3m
invguiddict["c624a6cd-31dc-49d3-a1e9-5482d06acbc6"]["Length"] = sizedict["3mCenteredUpright"]  # elevation mantlet 3m
invguiddict["04e813ed-9011-49bc-b15a-36c5095e56b6"]["Length"] = sizedict["3x3"]  # omni mantlet 3x3
invguiddict["09d28633-cff1-4cc4-9e11-161f350dbf60"]["Length"] = sizedict["3x3"]  # omni mantlet 3x3


# missing
invguiddict["missing"] = {"Name": "Missing", "Length": 1, "Material": "Missing"}
invguiddict["missing rotation"] = {"Name": "Missing Rotation", "Length": 1, "Material": "Missing Rotation"}

# save
blocks_file = "blocks.json"
with open(blocks_file, "w") as f:
    json.dump(invguiddict, f, indent="\t", sort_keys=True)
            
# print
print(len(guiddict), "->", len(invguiddict))
# for v in list(invguiddict.values())[100:200]:
#    print(v)
    
input("Press Enter key to exit")
exit()
