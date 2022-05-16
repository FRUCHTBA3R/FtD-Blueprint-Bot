import json, time
import numpy as np
import quaternion
import cv2
from PIL import ImageFont
from firing_animator import FiringAnimator
import imageio
from pygifsicle import optimize
#from scipy.signal import convolve2d

# block rotation directions
rot_normal = np.array([
                        [ 0, 0, 1],  # 0
                        [ 1, 0, 0],  # 1
                        [ 0, 0,-1],  # 2
                        [-1, 0, 0],  # 3
                        [ 0,-1, 0],  # 4
                        [ 0,-1, 0],  # 5
                        [ 0,-1, 0],  # 6
                        [ 0,-1, 0],  # 7
                        [ 0, 1, 0],  # 8
                        [ 0, 1, 0],  # 9
                        [ 0, 1, 0],  # 10
                        [ 0, 1, 0],  # 11
                        [ 0, 0, 1],  # 12
                        [ 1, 0, 0],  # 13
                        [ 0, 0,-1],  # 14
                        [-1, 0, 0],  # 15
                        [ 0, 0, 1],  # 16
                        [ 0, 0,-1],  # 17
                        [ 0, 0, 1],  # 18
                        [ 0, 0,-1],  # 19
                        [ 1, 0, 0],  # 20
                        [-1, 0, 0],  # 21
                        [ 1, 0, 0],  # 22
                        [-1, 0, 0]])  # 23
#not testet!!!
rot_tangent = np.array([
                        [ 0, 1, 0],  # 0
                        [ 0, 1, 0],  # 1
                        [ 0, 1, 0],  # 2
                        [ 0, 1, 0],  # 3
                        [ 0, 0, 1],  # 4
                        [ 1, 0, 0],  # 5
                        [ 0, 0,-1],  # 6
                        [-1, 0, 0],  # 7
                        [ 0, 0, 1],  # 8
                        [ 1, 0, 0],  # 9
                        [ 0, 0,-1],  # 10
                        [-1, 0, 0],  # 11
                        [ 0,-1, 0],  # 12 this from [1,0,0] with 16
                        [ 0,-1, 0],  # 13 this from [0,0,-1] with 22 this from [0,0,1] with 20
                        [ 0,-1, 0],  # 14 this from [-1,0,0] with 17
                        [ 0,-1, 0],  # 15 this from [0,0,1] with 21
                        [ 1, 0, 0],  # 16 this from [0,-1,0] with 12
                        [ 1, 0, 0],  # 17 this from [0,-1,0] with 14
                        [-1, 0, 0],  # 18
                        [-1, 0, 0],  # 19
                        [ 0, 0, 1],  # 20 this from [0,-1,0] with 13
                        [ 0, 0, 1],  # 21 this from [0,-1,0] with 15
                        [ 0, 0,-1],  # 22 this from [0,0,1] with 13
                        [ 0, 0,-1]])  # 23
rot_bitangent = np.cross(rot_normal, rot_tangent)

# transpose
rot_normal = rot_normal.T
rot_tangent = rot_tangent.T
rot_bitangent = rot_bitangent.T

# load blocks and materials configuration
with open("blocks.json", "r") as f:
    blocks = json.loads(f.read())
with open("materials.json", "r") as f:
    materials = json.loads(f.read())
# add missing "Invisible" keys to materials
for k in materials:
    if "Invisible" not in materials[k]:
        materials[k]["Invisible"] = False
    materials[k]["Color"] = np.array(materials[k]["Color"])
# load size id dictionary
with open("size_id_dictionary.json", "r") as f:
    size_id_dict = json.load(f)
size_id_dict = {int(k): v for k, v in size_id_dict.items()}

# store game version
bp_gameversion = None

# load font
bahnschrift = ImageFont.truetype("bahnschrift.ttf", 14)
bahnschrift.set_variation_by_axes([300, 85])

# firing animator
firing_animator = FiringAnimator()

# Blueprint:
# CSI: block color (color shininess increase?)
# COL: craft colors ["float,float,float,float"]
# SCs: sub-constructs
# BLP: block position ["int,int,int"]
# BLR: block rotation [int]
# BP1
# BP2
# BCI: block color index
# BEI:

# BlockIds: block ids [int]


async def process_blueprint(fname, silent=False, standaloneMode=False, use_player_colors=True, create_gif=False,
                            firing_order=2):
    """Load and init blueprint data. Returns blueprint, calculation times, image filename"""
    global bp_gameversion, firing_animator
    bp_gameversion = None
    main_img_fname = fname[:-10] + "_view"
    if not silent:
        print("Processing blueprint \"", fname, "\"", sep="")
    ts1 = time.time()
    with open(fname, "r", encoding="utf-8") as f:
        bp = json.load(f)
    ts1 = time.time() - ts1
    if not silent:
        print("JSON parse completed in", ts1, "s")
    # convert to numpy data
    ts2 = time.time()
    __convert_blueprint(bp)
    ts2 = time.time() - ts2
    if not silent:
        print("Conversion completed in", ts2, "s")
    # fetch infos
    ts3 = time.time()
    bp_infos, bp_gameversion = __fetch_infos(bp)
    ts3 = time.time() - ts3
    if not silent:
        print("Infos gathered in", ts3, "s")
    # create top, side, front view matrices
    ts4 = time.time()
    firing_animator.clear()  # clear here and at the end (if it crashes)
    top_mats, side_mats, front_mats = \
        __create_view_matrices(bp, use_player_colors=use_player_colors, create_gif=create_gif)
    ts4 = time.time() - ts4
    if not silent:
        print("View matrices completed in", ts4, "s")
    # create images
    ts5 = time.time()
    if create_gif:
        main_img = __create_images(top_mats, side_mats, front_mats, bp_infos, gif_args=firing_animator,
                                   firing_order=firing_order, file_name=main_img_fname)
    else:
        main_img = __create_images(top_mats, side_mats, front_mats, bp_infos, gif_args=None)
    ts5 = time.time() - ts5
    if not silent:
        print("Image creation completed in", ts5, "s")
    # save image
    if not create_gif:
        main_img_fname += ".png"
        if not cv2.imwrite(main_img_fname, main_img):  # TODO: raise exception
            print("ERROR: image could not be saved", main_img_fname)
    else:
        main_img_fname += ".gif"
        firing_animator.clear()
    if standaloneMode:
        return bp, [ts1, ts2, ts3, ts4, ts5], main_img
    else:
        return main_img_fname, [ts1, ts2, ts3, ts4, ts5]


def __convert_blueprint(bp):
    """Convert data to numpy data"""

    def blueprint_iter(blueprint, parentglobalrotation=quaternion.one, parentglobalposition=0):
        """Iterate blueprint and sub blueprints"""
        # convert rotation ids to np array
        blueprint["BLR"] = np.array(blueprint["BLR"])
        # convert local rotation to quaternion
        localrot_split = blueprint["LocalRotation"].split(",")
        globalrotation = np.quaternion(float(localrot_split[3]),
                                       float(localrot_split[0]),
                                       float(localrot_split[1]),
                                       float(localrot_split[2]))
        globalrotation = parentglobalrotation * globalrotation
        localrot = quaternion.as_rotation_matrix(globalrotation)
        localrot_arg = np.argmax(np.abs(localrot), axis=1)
        localrot_max = np.sign(localrot[[0, 1, 2], localrot_arg])
        localrot[:, :] = 0
        localrot[[0, 1, 2], localrot_arg] = localrot_max
        blueprint["LocalRotation"] = localrot

        # convert local position to np array
        blueprint["LocalPosition"] = np.array(blueprint["LocalPosition"].split(","),
                                              dtype=float).round().astype(int)
        blueprint["LocalPosition"] = (parentglobalrotation * quaternion.quaternion(*blueprint["LocalPosition"]) *
                                      parentglobalrotation.inverse()).vec.astype(int) + parentglobalposition
        # convert min/max coordinates to np array
        mincords = np.array(blueprint["MinCords"].split(","), dtype=float)
        maxcords = np.array(blueprint["MaxCords"].split(","), dtype=float)
        # rotate
        mincords = (blueprint["LocalRotation"] @ mincords) + blueprint["LocalPosition"]
        maxcords = (blueprint["LocalRotation"] @ maxcords) + blueprint["LocalPosition"]
        # (round to int) ((done after iteration))
        mincords = mincords  # .round().astype(int)
        maxcords = maxcords  # .round().astype(int)
        # re-min/max
        blueprint["MinCords"] = np.minimum(mincords, maxcords)
        blueprint["MaxCords"] = np.maximum(mincords, maxcords)

        # create new arrays
        blockcount = blueprint["BlockCount"]
        if blockcount != len(blueprint["BLP"]):
            blockcount = len(blueprint["BLP"])
            print("[WARN] Block count is not equal to length of block position array.")
        #blockguid_array = np.zeros(blockcount, dtype="<U36") not using guid here
        blockid_array = np.array(blueprint["BlockIds"], dtype=int)
        # block loop
        for i in range(blockcount):
            # blockguid_array[i] = bp["ItemDictionary"][str(blueprint["BlockIds"][i])] not using guid here
            blueprint["BLP"][i] = blueprint["BLP"][i].split(",")
        # below does the same as the loop above, but way slower
        #blueprint["BLP"] = np.vectorize(lambda x: np.array(x.split(","), dtype=float), signature="()->(n)")(blueprint["BLP"])

        blueprint["BlockIds"] = blockid_array  # guid_array not using guid here

        # rotate block position via local rotation and add local position
        blueprint["BLP"] = np.array(blueprint["BLP"], dtype=float)
        blockposition_array = np.dot(blueprint["LocalRotation"], blueprint["BLP"].T).T
        blueprint["BLP"] = blockposition_array.round().astype(int) + blueprint["LocalPosition"]

        # check min/max coords with blp
        #mincords = np.min(blueprint["BLP"], 0)
        #maxcords = np.max(blueprint["BLP"], 0)
        #print(mincords, maxcords)
        #print(blueprint["MinCords"], blueprint["MaxCords"])
        # re-min/max
        #blueprint["MinCords"] = np.minimum(mincords, blueprint["MinCords"])
        #blueprint["MaxCords"] = np.maximum(mincords, blueprint["MaxCords"])

        # rotate rot_normal, rot_tangent and rot_bitangent via local rotation
        blueprint["RotNormal"] = np.dot(blueprint["LocalRotation"], rot_normal).T.round().astype(int)
        blueprint["RotTangent"] = np.dot(blueprint["LocalRotation"], rot_tangent).T.round().astype(int)
        blueprint["RotBitangent"] = np.dot(blueprint["LocalRotation"], rot_bitangent).T.round().astype(int)

        # sub blueprint iteration
        for sub_bp in blueprint["SCs"]:
            blueprint_iter(sub_bp, globalrotation, blueprint["LocalPosition"])
            # merge min/max
            blueprint["MinCords"] = np.minimum(blueprint["MinCords"], sub_bp["MinCords"])
            blueprint["MaxCords"] = np.maximum(blueprint["MaxCords"], sub_bp["MaxCords"])

    # item dictionary conversion
    bp["ItemDictionary"] = {int(k): v for k, v in bp["ItemDictionary"].items()}
    # main bp fix
    bp["Blueprint"]["LocalRotation"] = "0,0,0,1"
    bp["Blueprint"]["LocalPosition"] = "0,0,0"
    blueprint_iter(bp["Blueprint"])
    # set size
    bp["Blueprint"]["MinCords"] = bp["Blueprint"]["MinCords"].round().astype(int)
    bp["Blueprint"]["MaxCords"] = bp["Blueprint"]["MaxCords"].round().astype(int)
    bp["Blueprint"]["Size"] = bp["Blueprint"]["MaxCords"] - bp["Blueprint"]["MinCords"] + 1
    # player colors
    #color_array = np.vectorize(lambda x: np.array(str.split(x, ",")).astype(float),signature="()->(n)")(bp["Blueprint"]["COL"])
    for i in range(len(bp["Blueprint"]["COL"])):
        bp["Blueprint"]["COL"][i] = bp["Blueprint"]["COL"][i].split(",")
    color_array = np.array(bp["Blueprint"]["COL"], dtype=float)
    # early alpha blending
    bp["Blueprint"]["COL"] = (255 * color_array[:, 2::-1] * color_array[:, np.newaxis, 3]).astype(np.uint8)
    bp["Blueprint"]["ONE_MINUS_ALPHA"] = 1. - color_array[:, 3]


def __fetch_infos(bp):
    """Gathers important information of blueprint"""
    def safe_max(a, b):
        """Returns max(a,b) or the one which is not None or None if both are None."""
        if a is None:
            return b
        if b is None:
            return a
        return max(a, b)

    infos = {"Name": bp.get("Name")}
    if infos["Name"] is None:
        infos["Name"] = "Unknown"
    infos["Blocks"] = safe_max(bp.get("SavedTotalBlockCount"), bp["Blueprint"].get("TotalBlockCount"))
    if infos["Blocks"] is None:
        print("Error while gathering blueprint block count info.")
        infos["Blocks"] = "?"
    try:
        infos["Cost"] = str(round(bp.get("SavedMaterialCost")))
    except Exception as err:
        print("Error while gathering blueprint cost info:", err)
        infos["Cost"] = "?"
    try:
        infos["Size"] = "W:{0} H:{1} L:{2}".format(*bp.get("Blueprint").get("Size"))
    except Exception as err:
        print("Error while gathering blueprint size info:", err)
        infos["Size"] = "?"
    try:
        infos["Author"] = bp.get("Blueprint").get("AuthorDetails").get("CreatorReadableName")
    except Exception as err:
        print("Error while gathering blueprint author info:", err)
        infos["Author"] = "Unknown"

    # gameversion
    try:
        gameversion = bp.get("Blueprint").get("GameVersion").split(".")
        for i in range(len(gameversion)):
            if gameversion[i].isnumeric():
                gameversion[i] = int(gameversion[i])
            else:
                numonly = ""
                for c in gameversion[i]:
                    if c.isnumeric():
                        numonly += c
                gameversion[i] = int(numonly)
    except Exception as err:
        print("Error while gathering blueprint gameversion info:", err)
        gameversion = "?"

    return infos, gameversion


def __create_view_matrices(bp, use_player_colors=True, create_gif=True):
    """Create top, side, front view matrices (color matrix and height matrix)"""
    def blueprint_iter(blueprint, mincords, blueprint_desc = "main"):
        """Iterate blueprint and sub blueprints"""
        nonlocal actual_min_cords
        global firing_animator
        # subtract min cords
        blueprint["BLP"] -= mincords
        #print("ViewMat at", blueprint_desc)

        # numpyfication
        # vectorize is slower
        #a_guid = np.vectorize(itemdict.get, otypes=["<U36"])(blueprint["BlockIds"])
        a_guid = np.zeros((len(blueprint["BlockIds"])), dtype="<U36")
        for i in range(len(a_guid)):
            a_guid[i] = itemdict.get(blueprint["BlockIds"][i])
        missing_block = blocks.get("missing")
        # new version
        #a_sizeid = np.vectorize(lambda x: blocks.get(x, missing_block).get("SizeId"), otypes=[np.uint8])(a_guid)
        a_sizeid = np.zeros((len(a_guid)), dtype=np.uint8)
        for i in range(len(a_guid)):
            a_sizeid[i] = blocks.get(a_guid[i], missing_block).get("SizeId")
        # end new
        a_pos = blueprint["BLP"]
        a_dir = blueprint["RotNormal"][blueprint["BLR"]]
        a_dir_tan = blueprint["RotTangent"][blueprint["BLR"]]
        a_dir_bitan = blueprint["RotBitangent"][blueprint["BLR"]]
        #a_material = np.vectorize(lambda x: blocks.get(x, missing_block).get("Material"))(a_guid)
        #a_color = np.vectorize(lambda x: materials.get(x)["Color"], signature="()->(n)")(a_material)
        #a_invisible = np.vectorize(lambda x: materials.get(x)["Invisible"])(a_material)  # unused
        a_color = np.zeros((len(a_guid), 3), dtype=np.uint8)
        for i in range(len(a_guid)):
            a_color[i] = materials.get(blocks.get(a_guid[i], missing_block).get("Material"))["Color"]

        if create_gif:
            blocks_that_go_bang = ["c94e1719-bcc7-4c6a-8563-505fad2f9db9",  # 16 pounder
                                   "58305289-16ea-43cf-9144-2f23b383da81",  # 32 pounder
                                   "e1d1bcae-f5e4-42bb-9781-6dde51b8e390",  # 64 pounder
                                   "16b67fbc-25d5-4a35-a0df-4941e7abf6ef",  # Revolving Blast-Gun
                                   "d3e8e14a-58e7-4bdd-b1b3-0f37e4723a73",  # Shard cannon
                                   #"7101e1cb-a501-49bd-8bbe-7a960881e72b",  # .50 AA Gun
                                   #"b92a4ce6-ea93-4c0c-97d7-494ea611caa9",  # 20mm AA gun
                                   #"d8c5639a-ff5f-448e-a761-c2f69fac661a",  # 40mm Quad AA Gun
                                   #"268d79bf-c266-48ed-b01b-76c8d4d31c92",  # 40mm Twin AA Gun
                                   #"3be0cab1-643b-4e3a-9f49-45995e4eb9fb",  # 40mm Octuple AA Gun
                                   "2311e4db-a281-448f-ad53-0a6127573a96",  # 60mm Grenade Launcher
                                   "742f063f-d0fe-4f41-8717-a2c75c38d5e0",  # 30mm Assault Cannon
                                   "9b8657b9-c820-43a0-ad19-25ea45a100f1",  # 60mm Auto Cannon
                                   "f9f36cb3-cbfd-446a-9313-40f8e31e6e89",  # 3.7" Gun
                                   "1217043c-e786-4555-ba24-46cd1f458bf9",  # 3.7" Gun Shield
                                   "0aa0fa2e-1a85-4493-9c4c-0a69c385395d",  # 130mm Casemate
                                   "aa070f63-c454-4f95-82fd-d946a32a1b66"   # 150mm Casemate
                                   ]
            blocks_that_go_brrr = ["5cf2b4da-c1b8-4005-930b-73cc39ac9d28"  # (Simple) Laser
                                   ]
            blocks_with_barrels_that_go_bang = ["dc8f69fe-f97c-404f-996c-1b934afa17b5",  # Adv. Firing piece
                                                "a97e03b0-e8da-49e2-9913-ad8c1826d869"  # Firing piece
                                                ]
            blocks_with_barrels_that_go_brrr = ["fd2b6afb-da6f-4a8e-bfc0-e4202b87300d",  # Short range laser combiner
                                                "7dc67bed-fd0f-4145-9525-5840bbcc4822"  # Laser combiner
                                                ]
            blocks_with_barrels_that_go_zap = ["9896747c-39a5-43bc-8ba9-ccf2f645cca1",  # PAC lens (symmetric)
                                               "1a1c9de5-6db5-4092-97ac-a4883383fadd",  # Small PAC lens (cross inputs)
                                               "2e429412-2982-4335-bf3c-a6c6609c8cbf",  # Small PAC lens (rear inputs)
                                               "2eea241a-6a32-41c6-a9e4-d082c7e854de",  # PAC lens (rear inputs)
                                               "f1746662-adec-4054-98bd-94b553bc6c6d",  # Particle Accelerator Lens
                                               #"2099a233-181e-4f50-9a0e-78a547969a8e",  # Particle Melee Lens
                                               "3d82f1a3-ad2a-4e81-a4e3-cb88c968f6e9",  # Particle Cannon
                                               ]
            largest_axis = np.argmax(bp["Blueprint"]["Size"])
            # simple cannons loop
            for fire_type, blocks_simple in enumerate([blocks_that_go_bang, blocks_that_go_brrr]):
                for cannon_guid in blocks_simple:
                    cannon, = np.nonzero(a_guid == cannon_guid)
                    if len(cannon) > 0:
                        firing_pos = a_pos[cannon] + a_dir_tan[cannon] * size_id_dict[a_sizeid[cannon[0]]]["yp"] + \
                            a_dir[cannon] * (size_id_dict[a_sizeid[cannon[0]]]["zp"] + 1)
                        firing_animator.append(firing_pos, a_dir[cannon], np.full(len(cannon), fire_type + 1, dtype=np.uint8))
            # cannons with barrels marching loop
            for fire_type, blocks_with_barrels in enumerate([blocks_with_barrels_that_go_bang,
                    blocks_with_barrels_that_go_brrr, blocks_with_barrels_that_go_zap]):
                for cannon_guid in blocks_with_barrels:
                    cannon, = np.nonzero(a_guid == cannon_guid)
                    if len(cannon) > 0:
                        firing_pos = a_pos[cannon] + a_dir_tan[cannon] * (size_id_dict[a_sizeid[cannon[0]]]["yp"] // 2) + \
                            a_dir[cannon] * (size_id_dict[a_sizeid[cannon[0]]]["zp"] + 1)
                        barrel_end_firing_pos = np.empty(firing_pos.shape, dtype=firing_pos.dtype)
                        for i in range(len(firing_pos)):
                            slicer = np.index_exp[largest_axis, (largest_axis + 1) % 3, (largest_axis + 2) % 3]
                            iter_count = 0
                            while iter_count < 100:
                                iter_count += 1
                                # search the largest axis in hopes of getting less false hits
                                index_largest, = np.nonzero(a_pos[:, slicer[0]] == firing_pos[i, slicer[0]])
                                if len(index_largest) < 1:
                                    break
                                index_a, = np.nonzero(a_pos[index_largest, slicer[1]] == firing_pos[i, slicer[1]])
                                if len(index_a) < 1:
                                    break
                                index_b, = np.nonzero(a_pos[index_largest[index_a], slicer[2]] == firing_pos[i, slicer[2]])
                                if len(index_b) < 1:
                                    break
                                final_index = index_largest[index_a[index_b]][0]
                                if blocks.get(a_guid[final_index], missing_block).get("Material") == "Missing":
                                    break
                                firing_pos[i] += (size_id_dict[a_sizeid[final_index]]["zp"] + 1) * a_dir[final_index]
                            barrel_end_firing_pos[i] = firing_pos[i]
                        firing_animator.append(barrel_end_firing_pos, a_dir[cannon], np.full(len(cannon), fire_type + 1, dtype=np.uint8))

        # player colors
        if use_player_colors:
            a_block_color = bp["Blueprint"]["COL"][blueprint["BCI"]]
            a_block_one_minus_alpha = bp["Blueprint"]["ONE_MINUS_ALPHA"][blueprint["BCI"]][:, np.newaxis]

        def fill_color_and_height(color_mat, height_mat, sel_arr, pos_sel_arr, axisX, axisZ, axisY):
            """Fills color_mat and height_mat with selected blocks (sel_arr as index and pos_sel_arr as position).
            axisY is the height axis."""
            nonlocal a_color#, a_invisible  # unused
            # create slicing indices for axes
            axisA = axisX
            axisB = axisZ+1 if axisZ > axisX else None
            axisS = axisZ - axisX

            # selection of higher height
            if height_mat.shape[0] <= np.max(pos_sel_arr[:, axisX]):
                errortext = f"Axis overflow: {height_mat.shape[0]} to {np.max(pos_sel_arr[:, axisX])}\n" \
                            f"Block guid: {a_guid[sel_arr[np.argmax(pos_sel_arr[:, axisX])]]}"
                raise IndexError(errortext)
            if height_mat.shape[1] <= np.max(pos_sel_arr[:, axisZ]):
                errortext = f"Axis overflow: {height_mat.shape[1]} to {np.max(pos_sel_arr[:, axisZ])}\n" \
                            f"Block guid: {a_guid[sel_arr[np.argmax(pos_sel_arr[:, axisZ])]]}"
                raise IndexError(errortext)
            height_sel_arr = height_mat[pos_sel_arr[:, axisX], pos_sel_arr[:, axisZ]] < pos_sel_arr[:, axisY]
            # position of selection
            height_pos_sel_arr = pos_sel_arr[height_sel_arr]

            # select only max height for each x,z coord
            # sort index of heights
            sorted_index = np.argsort(height_pos_sel_arr[:, axisY], axis=0)[::-1]
            # sort pos
            sorted_pos = height_pos_sel_arr[sorted_index]
            # find index of unique (x,z) cords
            unique_pos, unique_index = np.unique(sorted_pos[:, axisA:axisB:axisS], return_index=True, axis=0)

            # coloring
            if use_player_colors:
                color_mat[unique_pos[:, 0], unique_pos[:, 1]] = a_color[sel_arr][height_sel_arr][sorted_index][unique_index] * a_block_one_minus_alpha[sel_arr][height_sel_arr][sorted_index][unique_index]
                # player color
                color_mat[unique_pos[:, 0], unique_pos[:, 1]] += a_block_color[sel_arr][height_sel_arr][sorted_index][unique_index]
            else:
                color_mat[unique_pos[:, 0], unique_pos[:, 1]] = a_color[sel_arr][height_sel_arr][sorted_index][unique_index]
            # new height
            height_mat[unique_pos[:, 0], unique_pos[:, 1]] = sorted_pos[:, axisY][unique_index]

        # positiv size
        for sizeid in size_id_dict:
            # block selection
            a_sel, = np.nonzero(a_sizeid == sizeid)
            if len(a_sel) == 0:
                continue

            # load size
            xp = size_id_dict[sizeid]["xp"]
            yp = size_id_dict[sizeid]["yp"]
            zp = size_id_dict[sizeid]["zp"]
            xn = size_id_dict[sizeid]["xn"]
            yn = size_id_dict[sizeid]["yn"]
            zn = size_id_dict[sizeid]["zn"]
            size_x = xp + xn
            size_y = yp + yn
            size_z = zp + zn

            # initial position
            a_pos[a_sel] -= zn * a_dir[a_sel] + yn * a_dir_tan[a_sel] + xp * a_dir_bitan[a_sel]  # here xp instead ...
            # ... of xn as the negative x axis in game is the bitan direction here
            a_z_times_dir = a_dir[a_sel] * size_z
            a_y_times_dir = a_dir_tan[a_sel] * size_y

            # volume loop
            for j in range(size_x + 1):
                for k in range(size_y + 1):
                    for l in range(size_z + 1):
                        # select position here as loop changes a_pos
                        a_pos_sel = a_pos[a_sel]
                        # fill
                        fill_color_and_height(top_color, top_height, a_sel, a_pos_sel, 0, 2, 1)
                        fill_color_and_height(side_color, side_height, a_sel, a_pos_sel, 1, 2, 0)
                        fill_color_and_height(front_color, front_height, a_sel, a_pos_sel, 1, 0, 2)
                        # min cords
                        actual_min_cords = np.minimum(np.amin(a_pos_sel, 0), actual_min_cords)
                        # step in z direction (dir)
                        if l < size_z:
                            a_pos[a_sel] += a_dir[a_sel]
                    # reset z axis
                    a_pos[a_sel] -= a_z_times_dir
                    # step in y direction (tan)
                    if k < size_y:
                        a_pos[a_sel] += a_dir_tan[a_sel]
                # reset y axis
                a_pos[a_sel] -= a_y_times_dir
                # step in x direction (bitan)
                if j < size_x:
                    a_pos[a_sel] += a_dir_bitan[a_sel]

        # sub blueprints iteration
        for i, sub_bp in enumerate(blueprint["SCs"]):
            blueprint_iter(sub_bp, mincords, blueprint_desc+":"+str(i))

    # calculate min cords again, cause "MinCords" are not always true
    actual_min_cords = np.full((3), np.iinfo(np.int32).max, dtype=np.int32)
    # create matrices
    top_color = np.full((*bp["Blueprint"]["Size"][[0, 2]], 3), np.array([255, 118, 33]), dtype=np.uint8)
    top_height = np.full(bp["Blueprint"]["Size"][[0, 2]], -12345, dtype=int)
    side_color = np.full((*bp["Blueprint"]["Size"][[1, 2]], 3), np.array([255, 118, 33]), dtype=np.uint8)
    side_height = np.full(bp["Blueprint"]["Size"][[1, 2]], -12345, dtype=int)
    front_color = np.full((*bp["Blueprint"]["Size"][[1, 0]], 3), np.array([255, 118, 33]), dtype=np.uint8)
    front_height = np.full(bp["Blueprint"]["Size"][[1, 0]], -12345, dtype=int)
    # blueprint iteration
    itemdict = bp["ItemDictionary"]
    blueprint_iter(bp["Blueprint"], bp["Blueprint"]["MinCords"])
    # re-center based on actual min coordinates
    # print("Actual min cords:", actual_min_cords)
    if np.any(actual_min_cords < bp["Blueprint"]["MinCords"]):
        top_color = np.roll(top_color, (-actual_min_cords[0], -actual_min_cords[2]), (0, 1))
        top_height = np.roll(top_height, (-actual_min_cords[0], -actual_min_cords[2]), (0, 1))
        side_color = np.roll(side_color, (-actual_min_cords[1], -actual_min_cords[2]), (0, 1))
        side_height = np.roll(side_height, (-actual_min_cords[1], -actual_min_cords[2]), (0, 1))
        front_color = np.roll(front_color, (-actual_min_cords[1], -actual_min_cords[0]), (0, 1))
        front_height = np.roll(front_height, (-actual_min_cords[1], -actual_min_cords[0]), (0, 1))

    # flip
    side_color = cv2.flip(side_color, 0)
    side_height = cv2.flip(side_height, 0)
    front_color = cv2.flip(front_color, -1)
    front_height = cv2.flip(front_height, -1)
    # print(side_height)

    return ([top_color, top_height],  # , actual_min_cords[1]],
            [side_color, side_height],  # , actual_min_cords[0]],
            [front_color, front_height]  # , actual_min_cords[2]])
            )


def __copy_to_image(dst, start_pos, src_preblend, mask_start_pos, mask, mask_compare, mask_upscale):
    """
    Copies src_preblend[0] (image RGB uint8) to dst at starting_pos with alpha blending.
    Mask as depth test: mask < mask_compare
    :param dst: Destination image RGB uint8
    :param start_pos: [x, y]
    :param src_preblend: [Source image * source alpha RGB uint8, 1. - alpha float16]
    :param mask_start_pos: [x, y]
    :param mask: Depth image
    :param mask_compare: Depth to compare
    :param mask_upscale: Scaling for mask
    """
    #if src.shape == (3, ):
    #    src = np.array([[src]])
    # dst slice
    start_pos_dst = np.maximum(start_pos, 0)  # TODO: needs to be clipped to single images
    end_pos_dst = np.minimum(dst.shape[:2], start_pos + src_preblend[0].shape[:2])
    slicer_dst = np.index_exp[start_pos_dst[0]:end_pos_dst[0], start_pos_dst[1]:end_pos_dst[1]]
    # mask slice
    start_pos_mask = np.maximum(mask_start_pos, 0)
    end_pos_mask = np.minimum(mask.shape[:2], mask_start_pos + np.array(src_preblend[0].shape[:2])//mask_upscale)
    slicer_mask = np.index_exp[start_pos_mask[0]:end_pos_mask[0], start_pos_mask[1]:end_pos_mask[1]]
    # src slice
    start_pos = start_pos_dst - start_pos
    end_pos = start_pos + end_pos_dst - start_pos_dst
    slicer_src = np.index_exp[start_pos[0]:end_pos[0], start_pos[1]:end_pos[1]]
    # masking
    mask = mask[slicer_mask] < mask_compare
    mask = mask.repeat(mask_upscale, axis=1).repeat(mask_upscale, axis=0)
    dst[slicer_dst] = np.where(mask[:, :, np.newaxis], src_preblend[0][slicer_src] + dst[slicer_dst] * src_preblend[1], dst[slicer_dst])


def __line_on_image(dst, start_pos, draw_start, draw_size, src_preblend, rotation, line_offset, line_width, mask_start_pos, mask, mask_compare, mask_upscale):
    """
    Draws a line with color src_preblend[0] (RGB uint8) to dst at starting_pos with alpha blending.
    Mask as depth test: mask < mask_compare
    :param dst: Destination image RGB uint8
    :param start_pos: [x, y]
    :param draw_start: [x, y] start coordinate in combined view image
    :param draw_size: [x, y] size of view
    :param src_preblend: [Value * alpha RGB uint8, 1. - alpha float16]
    :param rotation: Rotation of line
    :param mask_start_pos: [x, y]
    :param mask: Depth image
    :param mask_compare: Depth to compare
    :param mask_upscale: Scaling for mask
    """
    #if src.shape == (3, ):
    #    src = np.array([[src]])
    # dst slice
    if rotation == 0:
        start_pos[0] += line_offset
        start_pos_dst = start_pos + draw_start
        end_pos_dst = [start_pos_dst[0] + line_width, dst.shape[1]]
    elif rotation == 1:
        start_pos += mask_upscale - 1
        start_pos[1] -= line_offset
        end_pos_dst = start_pos + draw_start + 1
        start_pos_dst = [0, end_pos_dst[1] - line_width]
    elif rotation == 2:
        start_pos += mask_upscale
        start_pos[0] -= line_offset
        end_pos_dst = start_pos + draw_start
        start_pos_dst = [end_pos_dst[0] - line_width, 0]
    elif rotation == 3:
        start_pos[1] += line_offset
        start_pos_dst = start_pos + draw_start
        end_pos_dst = [dst.shape[0], start_pos_dst[1] + line_width]
    else:
        start_pos += line_offset
        start_pos_dst = start_pos + draw_start
        end_pos_dst = start_pos_dst + line_width
    start_pos_dst = np.clip(start_pos_dst, draw_start + 2, draw_start + draw_size - 1 - 2)
    end_pos_dst = np.clip(end_pos_dst, draw_start + 1 + 2, draw_start + draw_size - 2)
    slicer_dst = np.index_exp[start_pos_dst[0]:end_pos_dst[0], start_pos_dst[1]:end_pos_dst[1]]
    # mask slice
    start_pos_mask = np.maximum(mask_start_pos, 0)
    end_pos_mask = mask.shape[:2]
    slicer_mask = np.index_exp[start_pos_mask[0]:end_pos_mask[0], start_pos_mask[1]:end_pos_mask[1]]
    # masking
    mask = mask[slicer_mask] < mask_compare
    mask = mask.repeat(mask_upscale, axis=1).repeat(mask_upscale, axis=0)
    #dst[slicer_dst] = np.where(mask[:, :, np.newaxis], src_preblend[0] + dst[slicer_dst] * src_preblend[1], dst[slicer_dst])
    dst[slicer_dst] = src_preblend[0] + dst[slicer_dst] * src_preblend[1]


def __create_images(top_mat, side_mat, front_mat, bp_infos, contours=True, upscale_f=5,
                    gif_args=None, firing_order=2, file_name="unknown"):
    """Create images from view matrices"""
    def create_image(mat, upscale_f, axis):
        """Create single image. Contents of mat will be changed."""
        # border
        if gif_args is None:
            mat[0] = cv2.copyMakeBorder(mat[0], 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=(255, 118, 33))
            mat[1] = cv2.copyMakeBorder(mat[1], 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=-12345)
        else:
            mat[0] = cv2.copyMakeBorder(mat[0], gif_border, gif_border, gif_border, gif_border, cv2.BORDER_CONSTANT,
                                        value=(255, 118, 33))
            mat[1] = cv2.copyMakeBorder(mat[1], gif_border, gif_border, gif_border, gif_border, cv2.BORDER_CONSTANT,
                                        value=-12345)
        height = mat[1]
        # height coloring
        hmax = np.max(height)
        hmap = height
        hmap = np.where(hmap == -12345, hmax, hmap)
        hmin = np.min(hmap)  # mat[2]
        if hmin == hmax:
            hmin -= 1
        dh = hmax - hmin
        dhN = dh + dh + dh + dh
        hmap = (hmap + (dhN - hmin))/(dh + dhN)
        mat[0] = np.multiply(mat[0], hmap[:, :, np.newaxis])
        # clip and convert to uint8
        mat[0] = np.clip(mat[0], 0, 255).astype(np.uint8)
        # height = height.astype
        # resize
        mat[0] = cv2.resize(mat[0], (mat[0].shape[1]*upscale_f, mat[0].shape[0]*upscale_f),
                            interpolation=cv2.INTER_AREA)

        if contours:
            # contours
            # rolling
            roll_up = np.roll(height, 1, 0)  # rolled down for up difference calculation
            roll_down = np.roll(height, -1, 0)
            roll_left = np.roll(height, 1, 1)
            roll_right = np.roll(height, -1, 1)

            # difference
            dup = np.where(height - roll_up > 1, 1, 0).astype(np.int8)  # dtype of where is int32
            ddown = np.where(height - roll_down > 1, 1, 0).astype(np.int8)
            dleft = np.where(height - roll_left > 1, 1, 0).astype(np.int8)
            dright = np.where(height - roll_right > 1, 1, 0).astype(np.int8)

            # not used as roll_... is required later
            #cv2 filter2D
            #sci_dup = convolve2d(height, np.array([[0],[1],[-1]]), mode="same", fillvalue=-1)
            #sci_ddown = convolve2d(height, np.array([[-1],[1],[0]]), mode="same", fillvalue=-1)
            #sci_dleft = convolve2d(height, np.array([[0,1,-1]]), mode="same", fillvalue=-1)
            #sci_dright = convolve2d(height, np.array([[-1,1,0]]), mode="same", fillvalue=-1)

            # "super" difference
            superable = height > -12345
            superup = np.where((roll_up == -12345) & superable, 1, 0).astype(np.int8)  # dtype is bool ???
            superdown = np.where((roll_down == -12345) & superable, 1, 0).astype(np.int8)
            superleft = np.where((roll_left == -12345) & superable, 1, 0).astype(np.int8)
            superright = np.where((roll_right == -12345) & superable, 1, 0).astype(np.int8)
            boolsupersum1 = (superup + superdown + superleft + superright) == 1
            superup = (superup == 1) & boolsupersum1
            superdown = (superdown == 1) & boolsupersum1
            superleft = (superleft == 1) & boolsupersum1
            superright = (superright == 1) & boolsupersum1

            # sum, circle, edges
            dsum = dup + ddown + dleft + dright
            booldcircle = dsum == 4
            dcircle = np.where(booldcircle, 1, 0).astype(np.int8)

            # remove circles
            dup[booldcircle] = 0
            ddown[booldcircle] = 0
            dleft[booldcircle] = 0
            dright[booldcircle] = 0

            # diag A is / ; diag B is \
            booldsum2 = dsum == 2
            boolddiagA = booldsum2 & (dup == dleft)
            boolddiagB = booldsum2 & (dup == dright)
            ddiagA = np.where(boolddiagA, 1, 0).astype(np.int8)  # dtype of where is int32
            ddiagB = np.where(boolddiagB, 1, 0).astype(np.int8)

            # remove diags
            dup[boolddiagA] = 0
            ddown[boolddiagA] = 0
            dleft[boolddiagA] = 0
            dright[boolddiagA] = 0
            dup[boolddiagB] = 0
            ddown[boolddiagB] = 0
            dleft[boolddiagB] = 0
            dright[boolddiagB] = 0

            # re-add super
            dup[superup] = 1
            ddown[superdown] = 1
            dleft[superleft] = 1
            dright[superright] = 1

            # kronecker upscale
            dupimg = np.kron(dup, linetop)
            dup = None  # does
            ddownimg = np.kron(ddown, linedown)
            ddown = None  # this
            dleftimg = np.kron(dleft, lineleft)
            dleft = None  # help
            drightimg = np.kron(dright, lineright)
            dright = None  # with
            dcircleimg = np.kron(dcircle, linecircle)
            dcircle = None  # memory
            ddiagAimg = np.kron(ddiagA, linediagA)
            ddiagA = None  # consumption
            ddiagBimg = np.kron(ddiagB, linediagB)
            ddiagB = None  # ?
            dimg = dupimg + ddownimg + dleftimg + drightimg + dcircleimg + ddiagAimg + ddiagBimg

            mat[0][dimg > 0] = 255


    # upscale_f = 5
    gif_border = 10
    # lines
    linetop = np.zeros((upscale_f, upscale_f), dtype=np.int8)
    linetop[0] = 1
    linedown = np.zeros((upscale_f, upscale_f), dtype=np.int8)
    linedown[-1] = 1
    lineleft = np.zeros((upscale_f, upscale_f), dtype=np.int8)
    lineleft[:, 0] = 1
    lineright = np.zeros((upscale_f, upscale_f), dtype=np.int8)
    lineright[:, -1] = 1
    linecircle = np.zeros((upscale_f, upscale_f), dtype=np.int8)
    cv2.circle(linecircle, (upscale_f//2, upscale_f//2), upscale_f//2, 1)
    linediagB = np.identity(upscale_f, dtype=np.int8)
    linediagA = np.flip(linediagB, 1)
    # create images
    height_map = [None, None, None]
    #top_img_old_shape = top_mat[0].shape
    side_img_old_shape = side_mat[0].shape
    front_img_old_shape = front_mat[0].shape
    create_image(top_mat, upscale_f, 1)
    top_img, height_map[1] = top_mat
    create_image(side_mat, upscale_f, 0)
    side_img, height_map[0] = side_mat
    create_image(front_mat, upscale_f, 2)
    front_img, height_map[2] = front_mat

    # info img
    fontFace = cv2.FONT_HERSHEY_SIMPLEX
    # find max size text
    if bp_infos is None:
        info_img = np.full((front_img.shape[1], front_img.shape[1], 3), np.array([255, 118, 33]),
                           dtype=np.uint8)
        fontScale = 12. / cv2.getTextSize("I", fontFace, 1, 1)[0][1]  # scale to 12 pixels
        cv2.putText(info_img, "Error", (5, info_img.shape[0]//2), fontFace,
                    fontScale, (255, 255, 255))
    else:
        # find max length text
        maxlen = 0
        maxtxt = None
        for k in bp_infos:
            txt = f"{k}: {bp_infos[k]}"
            if len(txt) > maxlen:
                maxlen = len(txt)
                maxtxt = txt

        pixel = 14  # minimum text height in pixel

        # get size of text with scaling 1
        # (width, height), baseline = cv2.getTextSize(maxtxt, fontFace, 1, 1)
        # fontScale = pixel/(height+baseline) #scale to "pixel" pixels
        # above code will result in:
        fontScale = 0.4375

        # get size of text with scaling "fontScale"
        (width, height), baseline = cv2.getTextSize(maxtxt, fontFace, fontScale, 1)

        # reverse scaling calculation for text upscaling
        reverse_scale_height = (top_img.shape[0] / 2 / len(bp_infos)) / (height+baseline)
        reverse_scale_width = top_img.shape[0] / width / (1 + pixel / width)
        reverse_scale = min(reverse_scale_height, reverse_scale_width) * fontScale
        if fontScale < reverse_scale:  # larger scale is possible
            pixel = int(np.floor(pixel * min(reverse_scale_height, reverse_scale_width)))
            fontScale = reverse_scale

        # calculate height and limit minimum width/height to top view img height
        height = len(bp_infos) * (height+baseline) * 2
        height = max(height, top_img.shape[0])
        width = width+pixel  # int(np.ceil(width + pixel)) #required width + padding for text
        width = max(width, top_img.shape[0])
        info_img = np.full((height, width, 3), np.array([255, 118, 33]), dtype=np.uint8)

        # write info
        fontThickness = max(1, int(pixel * 0.07))
        px = pixel//2
        py = pixel-baseline+pixel//2
        for k in bp_infos:
            txt = f"{k}: {bp_infos[k]}"
            cv2.putText(info_img, txt, (px, py), fontFace, fontScale, (255, 255, 255), fontThickness)
            py += pixel+pixel

    darkBlue = np.array([255, 100, 0])

    # save shape of images for later use, so images can be freed
    side_img_shape = np.array(side_img.shape)
    front_img_shape = np.array(front_img.shape)
    top_img_shape = np.array(top_img.shape)
    # combine images
    bottombuffer = np.full((max(0, info_img.shape[0]-top_img.shape[0]), top_img.shape[1], 3),
                           np.array([255, 118, 33]), dtype=np.uint8)
    rightbuffer = np.full((front_img.shape[0], max(0, info_img.shape[1]-front_img.shape[1]), 3),
                          np.array([255, 118, 33]), dtype=np.uint8)
    # update stored shapes
    front_img_shape[1] += rightbuffer.shape[1]
    front_img_shape[0] += bottombuffer.shape[0]
    # border side to front
    side_img[:, -2:] = darkBlue
    front_img[:, :2] = darkBlue
    toprow = np.concatenate((side_img, front_img, rightbuffer), 1)
    bottomrow = np.concatenate((top_img, bottombuffer), 0)
    # border top to info
    bottomrow[:, -2:] = darkBlue
    info_img[:, :2] = darkBlue
    bottomrow = np.concatenate((bottomrow, info_img), 1)
    # border toprow to bottomrow
    toprow[-2:, :] = darkBlue
    bottomrow[:2, :] = darkBlue
    res = np.concatenate((toprow, bottomrow), 0)

    # gif animation
    # TODO: optimize
    if gif_args:
        file_name += ".gif"
        with imageio.get_writer(file_name, format="gif", mode="I", duration=[2.5, 0.1], subrectangles=True) as writer:
            writer.append_data(cv2.cvtColor(res, cv2.COLOR_BGR2RGB))
            gif_args.setup_order(axis=firing_order)
            for i in gif_args.iter_frames():
                frame = np.array(res)
                for axis in range(3):
                    # TODO: these are constant values, create them somewhere else
                    if axis == 0:
                        # side view
                        axis_flip_add = np.array([side_img_old_shape[0] - 1, 0], dtype=int)
                        axis_flip_mul = np.array([-1, 1], dtype=int)
                        axisA = 1
                        axisB = 2
                        offset = np.zeros(2, dtype=int)
                        size = side_img_shape[:2]# - 2
                    elif axis == 2:
                        # front view
                        axis_flip_add = np.array([front_img_old_shape[0] - 1, front_img_old_shape[1] - 1], dtype=int)
                        axis_flip_mul = np.array([-1, -1], dtype=int)
                        axisA = 1
                        axisB = 0
                        offset = np.array([0, side_img_shape[1]], dtype=int)
                        size = front_img_shape[:2]# - np.array([2, 0])
                    else:
                        # top view
                        axis_flip_add = np.zeros(2, dtype=int)
                        axis_flip_mul = np.ones(2, dtype=int)
                        axisA = 0
                        axisB = 2
                        offset = np.array([side_img_shape[0], 0], dtype=int)
                        size = top_img_shape[:2]# - np.array([0, 2])

                    for position, direction, strength in gif_args.iter_ordered(axis):
                        rotation = 0
                        if direction[axisA] == 1:
                            rotation = 3 if axis == 1 else 1
                        elif direction[axisA] == -1:
                            rotation = 1 if axis == 1 else 3
                        elif direction[axisB] == 1:
                            rotation = 2 if axis == 2 else 0
                        elif direction[axisB] == -1:
                            rotation = 0 if axis == 2 else 2
                        elif direction[axis] == 1:
                            rotation = 4
                        elif direction[axis] == -1:
                            rotation = 5

                        firing_type = gif_args.get_animation_type()
                        if firing_type == 1:
                            # normal shot
                            anim = gif_args.get_animation(rotation_id=rotation)
                            if anim is not None:
                                anim_image, anim_depth, anim_offset = anim
                                transformed_pos = position[[axisA, axisB]] * axis_flip_mul + axis_flip_add + gif_border
                                transformed_pos = transformed_pos - anim_offset // upscale_f
                                __copy_to_image(frame, transformed_pos * upscale_f + offset, anim_image,
                                                transformed_pos, height_map[axis], position[axis] + anim_depth,
                                                upscale_f)
                        elif firing_type == 2:
                            if gif_args.get_animation_state() is not None:
                                # red laser
                                transformed_pos = position[[axisA, axisB]] * axis_flip_mul + axis_flip_add + gif_border
                                # laser color bgr = [0, 19, 255]
                                __line_on_image(frame, transformed_pos * upscale_f, offset, size,
                                                [np.array([0, 11, 153], dtype=np.uint8), 0.4],
                                                rotation, 2, 1, transformed_pos, height_map[axis], position[axis],
                                                upscale_f)
                        elif firing_type == 3:
                            if gif_args.get_animation_state() is not None:
                                # blue particle beam
                                transformed_pos = position[[axisA, axisB]] * axis_flip_mul + axis_flip_add + gif_border
                                # beam color bgr = [201, 121, 80]
                                __line_on_image(frame, transformed_pos * upscale_f, offset, size,
                                                [np.array([229, 229, 229], dtype=np.uint8), 0.1],
                                                rotation, 1, 3, transformed_pos, height_map[axis], position[axis],
                                                upscale_f)

                writer.append_data(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        optimize(file_name)
        # no need to return image, as gif is stored on disk
        return None

    return res


async def speed_test(fname):
    """Just some speed testing"""
    global main_img, blueprint, bp
    testlen = 100
    t1 = np.zeros(testlen)
    t2 = np.zeros(testlen)
    t3 = np.zeros(testlen)
    t4 = np.zeros(testlen)
    t5 = np.zeros(testlen)
    for i in range(testlen):
        bp, timing, main_img = await process_blueprint(fname, True, True)
        t1[i] = timing[0]
        t2[i] = timing[1]
        t3[i] = timing[2]
        t4[i] = timing[3]
        t5[i] = timing[4]
    print("Timing:")
    print("t1:", np.sum(t1)/testlen, "dt:", np.sum(np.abs(t1-np.sum(t1)/testlen))/testlen, "max:", np.max(t1))
    print("t2:", np.sum(t2)/testlen, "dt:", np.sum(np.abs(t2-np.sum(t2)/testlen))/testlen, "max:", np.max(t2))
    print("t3:", np.sum(t3)/testlen, "dt:", np.sum(np.abs(t3-np.sum(t3)/testlen))/testlen, "max:", np.max(t3))
    print("t4:", np.sum(t4)/testlen, "dt:", np.sum(np.abs(t4-np.sum(t4)/testlen))/testlen, "max:", np.max(t4))
    print("t5:", np.sum(t5)/testlen, "dt:", np.sum(np.abs(t5-np.sum(t5)/testlen))/testlen, "max:", np.max(t5))

    blueprint = bp["Blueprint"]
    # show image
    #cv2.imshow("Blueprint", main_img)
    #cv2.waitKey()

if __name__ == "__main__":
    # file
    fname = "../example blueprints/exampleAllWeapons.blueprint"

    main_img = np.zeros(0)

    import asyncio

    if False:
        asyncio.run(speed_test(fname))
    else:
        import sys, os
        if len(sys.argv) > 1:
            if os.path.exists(sys.argv[1]):
                fname = sys.argv[1]

        async def async_main():
            global bp, timing, main_img
            bp, timing, main_img = await process_blueprint(fname, False, True, True, False, 2)
        asyncio.run(async_main())
        if main_img is None:
            exit()
        cv2.namedWindow("Blueprint", cv2.WINDOW_NORMAL)
        sY, sX, _ = main_img.shape
        sM = min(980 / sY, 1820 / sX)
        if sM < 1.0:
            cv2.resizeWindow("Blueprint", int(sX * sM), int(sY * sM))
        else:
            cv2.resizeWindow("Blueprint", sX, sY)
        cv2.imshow("Blueprint", main_img)
        cv2.waitKey()
        if not __debug__:
            exit()
