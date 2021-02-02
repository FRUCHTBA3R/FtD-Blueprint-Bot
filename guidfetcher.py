import os
import json

#search every file for json tag ComponentId
FORCE_COMPLETE_FILE_SEARCH = True

#mods folder of From The Depths
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
#invert dict with values as dict
invguiddict = {v:{"Name":k} for k,v in guiddict.items()}
if len(extrainvguiddict) > 0:
    print(len(invguiddict), "&", len(extrainvguiddict))
    invguiddict.update(extrainvguiddict)
    print("->", len(invguiddict))


#load config
materials = None
materials_file = "materials.json"
with open(materials_file, "r") as f:
    materials = json.loads(f.read())
sizedict = {"1m": 1, "2m": 2, "3m": 3, "4m": 4, "1x1": 1, "3x3": 33, "5x5": 34, "7x7": 35, " 5m": 50, " 7m": 51, " 9m": 52,
            "2mUpright": 62, "3mUpright": 63, "4mUpright": 64}

#map
for k in invguiddict:
    v = invguiddict[k]["Name"].lower().replace("(", "").replace(")", "")
    v = f" {v} "
    invguiddict[k]["Material"] = "Missing" #default material
    invguiddict[k]["Length"] = 1 #default length
    for m in materials:
        ml = f" {m.lower()} "
        if v.find(ml) >= 0:
            invguiddict[k]["Material"] = m
            break
    for size in sizedict:
        if v.find(size) >= 0:
            invguiddict[k]["Length"] = sizedict[size]
            break

#manual fixes
invguiddict["867cea4e-6ea4-4fe2-a4a1-b6230308f8f1"]["Length"] = 4
invguiddict["5e574e3c-24af-409c-b165-f079ba9c1946"]["Material"] = "Metal"
invguiddict["ab59ab39-179c-4fd8-bad3-2f3251f0a55a"]["Material"] = "Metal"
invguiddict["c489a675-78ad-461c-b772-b1dc1ae16beb"]["Material"] = "Metal"
invguiddict["5e236eef-c91e-45bc-afc4-bff4d133ac14"]["Material"] = "Metal"
invguiddict["e7fc9ece-d2f4-4671-a3e8-77196601cf4e"]["Material"] = "Metal"
invguiddict["52b78a75-115a-4962-96f1-35177b46ba93"]["Material"] = "Metal"
#truss fixes
invguiddict["fe88a923-b85b-4471-bce5-8ceb1d0ddb14"]["Length"] = sizedict["4mUpright"] #truss 4m
invguiddict["1dd66387-6293-4fa0-a1da-6f0e4cb80dfa"]["Length"] = sizedict["4mUpright"] #truss 4m
invguiddict["21646640-41cf-42a3-931a-3c40b9c79d83"]["Length"] = sizedict["3mUpright"] #truss 3m
invguiddict["ac24cd04-449e-47b9-bf8c-bf58d9997264"]["Length"] = sizedict["3mUpright"] #truss 3m
invguiddict["de17ff79-e670-4f08-ab59-df1ecac3905b"]["Length"] = sizedict["2mUpright"] #truss 2m
invguiddict["19a1d5ad-99e3-4a18-8943-22a82f554231"]["Length"] = sizedict["2mUpright"] #truss 2m

#missing
invguiddict["missing"] = {"Name": "Missing", "Length": 1, "Material": "Missing"}
invguiddict["missing rotation"] = {"Name": "Missing Rotation", "Length": 1, "Material": "Missing Rotation"}

#save
blocks_file = "blocks.json"
with open(blocks_file, "w") as f:
    json.dump(invguiddict, f, indent="\t", sort_keys=True)
            
#print
print(len(guiddict), "->", len(invguiddict))
#for v in list(invguiddict.values())[100:200]:
#    print(v)
    
input("Press Enter key to exit")
exit()
