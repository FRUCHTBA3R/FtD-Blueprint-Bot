import json, time
import numpy as np
import quaternion
import cv2
#from scipy.signal import convolve2d

# block rotation directions
rot_normal = np.array([
                       [ 0, 0, 1], #0
                       [ 1, 0, 0], #1
                       [ 0, 0,-1], #2
                       [-1, 0, 0], #3
                       [ 0,-1, 0], #4
                       [ 0,-1, 0], #5
                       [ 0,-1, 0], #6
                       [ 0,-1, 0], #7
                       [ 0, 1, 0], #8
                       [ 0, 1, 0], #9
                       [ 0, 1, 0], #10
                       [ 0, 1, 0], #11
                       [ 0, 0, 1], #12
                       [ 1, 0, 0], #13
                       [ 0, 0,-1], #14
                       [-1, 0, 0], #15
                       [ 0, 0, 1], #16
                       [ 0, 0,-1], #17
                       [ 0, 0, 1], #18
                       [ 0, 0,-1], #19
                       [ 1, 0, 0], #20
                       [-1, 0, 0], #21
                       [ 1, 0, 0], #22
                       [-1, 0, 0]]) #23
#not testet!!!
rot_tangent = np.array([
                        [ 0, 1, 0], #0
                        [ 0, 1, 0], #1
                        [ 0, 1, 0], #2
                        [ 0, 1, 0], #3
                        [ 0, 0, 1], #4
                        [ 1, 0, 0], #5
                        [ 0, 0,-1], #6
                        [-1, 0, 0], #7
                        [ 0, 0, 1], #8
                        [ 1, 0, 0], #9
                        [ 0, 0,-1], #10
                        [-1, 0, 0], #11
                        [ 0,-1, 0], #12 this from [1,0,0] with 16
                        [ 0,-1, 0], #13 this from [0,0,-1] with 22 this from [0,0,1] with 20
                        [ 0,-1, 0], #14 this from [-1,0,0] with 17
                        [ 0,-1, 0], #15 this from [0,0,1] with 21
                        [ 1, 0, 0], #16 this from [0,-1,0] with 12
                        [ 1, 0, 0], #17 this from [0,-1,0] with 14
                        [-1, 0, 0], #18
                        [-1, 0, 0], #19
                        [ 0, 0, 1], #20 this from [0,-1,0] with 13
                        [ 0, 0, 1], #21 this from [0,-1,0] with 15
                        [ 0, 0,-1], #22 this from [0,0,1] with 13
                        [ 0, 0,-1]]) #23
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

# Blueprint:
# CSI: block color
# COL: craft colors ["float,float,float"]
# SCs:
# BLP: block position ["int,int,int"]
# BLR: block rotation [int]
# BP1
# BP2
# BCI: maybe block color index
# BEI:

# BlockIds: block ids [int]

async def process_blueprint(fname, silent=False, standaloneMode=False):
    """Load and init blueprint data. Returns blueprint, calculation times, image filename"""
    global  bp_gameversion
    bp_gameversion = None
    if not silent: print("Processing blueprint \"", fname, "\"", sep="")
    ts1 = time.time()
    with open(fname, "r") as f:
        bp = json.load(f)
    ts1 = time.time() - ts1
    if not silent: print("JSON parse completed in", ts1, "s")
    # convert to numpy data
    ts2 = time.time()
    __convert_blueprint(bp)
    ts2 = time.time() - ts2
    if not silent: print("Conversion completed in", ts2, "s")
    # fetch infos
    ts3 = time.time()
    bp_infos, bp_gameversion = __fetch_infos(bp)
    ts3 = time.time() - ts3
    if not silent: print("Infos gathered in", ts3, "s")
    # create top, side, front view matrices
    ts4 = time.time()
    top_mats, side_mats, front_mats = __create_view_matrices(bp)
    ts4 = time.time() - ts4
    if not silent: print("View matrices completed in", ts4, "s")
    # create images
    ts5 = time.time()
    main_img = __create_images(top_mats, side_mats, front_mats, bp_infos)
    ts5 = time.time() - ts5
    if not silent: print("Image creation completed in", ts5, "s")
    # save image
    main_img_fname = fname[:-10] + "_view.png"
    if not cv2.imwrite(main_img_fname, main_img):
        print("ERROR: image could not be saved", main_img_fname)
    # return
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
        globalrotation *= parentglobalrotation
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
                                      parentglobalrotation.conj()).vec.astype(int) + parentglobalposition
        # convert min/max coordinates to np array
        mincords = np.array(blueprint["MinCords"].split(","),
                                         dtype=float)
        maxcords = np.array(blueprint["MaxCords"].split(","),
                                         dtype=float)
        # rotate
        mincords = (blueprint["LocalRotation"] @ mincords) + blueprint["LocalPosition"]
        maxcords = (blueprint["LocalRotation"] @ maxcords) + blueprint["LocalPosition"]
        # (round to int) ((done after iteration))
        mincords = mincords# .round().astype(int)
        maxcords = maxcords# .round().astype(int)
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
            
        blueprint["BlockIds"] = blockid_array # guid_array not using guid here
        
        # rotate block position via local rotation and add local position
        blockposition_array = np.array(blueprint["BLP"], dtype=float).T
        blockposition_array = np.dot(blueprint["LocalRotation"], blockposition_array).T
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

    return infos, gameversion


def __create_view_matrices(bp):
    """Create top, side, front view matrices (color matrix and height matrix)"""
    def blueprint_iter(blueprint, mincords, blueprint_desc = "main"):
        """Iterate blueprint and sub blueprints"""
        nonlocal actual_min_cords
        # subtract min cords
        blueprint["BLP"] -= mincords
        #print("ViewMat at", blueprint_desc)

        # numpyfication
        a_guid = np.vectorize(itemdict.get)(blueprint["BlockIds"])
        missing_block = blocks.get("missing")
        a_length = np.vectorize(lambda x: blocks.get(x, missing_block).get("Length"))(a_guid)
        # new version
        a_sizeid = np.vectorize(lambda x: blocks.get(x, missing_block).get("SizeId"))(a_guid)
        a_sizeid_neg = np.vectorize(lambda x: blocks.get(x, missing_block).get("SizeIdNeg"))(a_guid)
        # end new
        a_pos = blueprint["BLP"]
        a_dir = blueprint["RotNormal"][blueprint["BLR"]]
        a_dir_tan = blueprint["RotTangent"][blueprint["BLR"]]
        a_dir_bitan = blueprint["RotBitangent"][blueprint["BLR"]]
        a_material = np.vectorize(lambda x: blocks.get(x, missing_block).get("Material"))(a_guid)
        a_color = np.vectorize(lambda x: materials.get(x)["Color"], signature="()->(n)")(a_material)
        a_invisible = np.vectorize(lambda x: materials.get(x)["Invisible"])(a_material)

        def fill_color_and_height(color_mat, height_mat, sel_arr, pos_sel_arr, axisX, axisZ, axisY):
            """Fills color_mat and height_mat with selected blocks (sel_arr as index and pos_sel_arr as position).
            axisY is the height axis."""
            nonlocal a_color, a_invisible
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
    top_color = np.full((*bp["Blueprint"]["Size"][[0, 2]], 3), np.array([255, 118, 33]), dtype=np.uint16)
    top_height = np.full(bp["Blueprint"]["Size"][[0, 2]], -12345, dtype=int)
    side_color = np.full((*bp["Blueprint"]["Size"][[1, 2]], 3), np.array([255, 118, 33]), dtype=np.uint16)
    side_height = np.full(bp["Blueprint"]["Size"][[1, 2]], -12345, dtype=int)
    front_color = np.full((*bp["Blueprint"]["Size"][[1, 0]], 3), np.array([255, 118, 33]), dtype=np.uint16)
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
    
    return ([top_color, top_height],#, actual_min_cords[1]],
            [side_color, side_height],#, actual_min_cords[0]],
            [front_color, front_height])#, actual_min_cords[2]])


def __create_images(top_mat, side_mat, front_mat, bp_infos, contours=True, upscale_f=5):
    """Create images from view matrices"""
    def create_image(mat, upscale_f):
        """Create single image"""
        # flip
        #img = cv2.flip(mat[0], 0)
        img = mat[0]
        #height = cv2.flip(mat[1], 0)
        height = mat[1]
        # border
        img = cv2.copyMakeBorder(img, 1, 1, 1, 1, cv2.BORDER_CONSTANT,value=(255, 118, 33))
        height = cv2.copyMakeBorder(height, 1, 1, 1, 1, cv2.BORDER_CONSTANT,value=-12345)
        # height coloring
        hmax = np.max(height)
        hmap = height
        hmap = np.where(hmap == -12345, hmax, hmap)
        hmin = np.min(hmap) #mat[2]
        if hmin == hmax:
            hmin -= 1
        dh = hmax - hmin
        dhN = dh + dh + dh + dh
        hmap = (hmap + (dhN - hmin))/(dh + dhN)
        img = np.multiply(img, hmap[:,:,np.newaxis])
        # clip and convert to uint8
        img = np.clip(img, 0, 255).astype(np.uint8)
        # height = height.astype
        # resize
        img = cv2.resize(img, (img.shape[1]*upscale_f,img.shape[0]*upscale_f),
                         interpolation=cv2.INTER_AREA)

        if contours:
            # contours
            # rolling
            roll_up = np.roll(height, 1, 0)  # rolled down for up difference calculation
            roll_down = np.roll(height, -1, 0)
            roll_left = np.roll(height, 1, 1)
            roll_right = np.roll(height, -1, 1)
            
            # difference
            dup = np.where(height - roll_up > 1, 1, 0)
            ddown = np.where(height - roll_down > 1, 1, 0)
            dleft = np.where(height - roll_left > 1, 1, 0)
            dright = np.where(height - roll_right > 1, 1, 0)

            # not used as roll_... is required later
            #cv2 filter2D
            #sci_dup = convolve2d(height, np.array([[0],[1],[-1]]), mode="same", fillvalue=-1)
            #sci_ddown = convolve2d(height, np.array([[-1],[1],[0]]), mode="same", fillvalue=-1)
            #sci_dleft = convolve2d(height, np.array([[0,1,-1]]), mode="same", fillvalue=-1)
            #sci_dright = convolve2d(height, np.array([[-1,1,0]]), mode="same", fillvalue=-1)
            
            # "super" difference
            superable = height > -12345
            superup = np.where((roll_up == -12345) & superable, 1, 0)
            superdown = np.where((roll_down == -12345) & superable, 1, 0)
            superleft = np.where((roll_left == -12345) & superable, 1, 0)
            superright = np.where((roll_right == -12345) & superable, 1, 0)
            boolsupersum1 = (superup + superdown + superleft + superright) == 1
            superup = (superup == 1) & boolsupersum1
            superdown = (superdown == 1) & boolsupersum1
            superleft = (superleft == 1) & boolsupersum1
            superright = (superright == 1) & boolsupersum1
            
            # sum, circle, edges
            dsum = dup + ddown + dleft + dright
            booldcircle = dsum == 4
            dcircle = np.where(booldcircle, 1, 0)
            
            # remove circles
            dup[booldcircle] = 0
            ddown[booldcircle] = 0
            dleft[booldcircle] = 0
            dright[booldcircle] = 0
            
            # diag A is / ; diag B is \
            booldsum2 = dsum == 2
            boolddiagA = booldsum2 & (dup == dleft)
            boolddiagB = booldsum2 & (dup == dright)
            ddiagA = np.where(boolddiagA, 1, 0)
            ddiagB = np.where(boolddiagB, 1, 0)
            
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
            ddownimg = np.kron(ddown, linedown)
            dleftimg = np.kron(dleft, lineleft)
            drightimg = np.kron(dright, lineright)
            dcircleimg = np.kron(dcircle, linecircle)
            ddiagAimg = np.kron(ddiagA, linediagA)
            ddiagBimg = np.kron(ddiagB, linediagB)
            dimg = dupimg + ddownimg + dleftimg + drightimg + dcircleimg + ddiagAimg + ddiagBimg

            img[dimg > 0] = 255
        return img

    # upscale_f = 5
    # lines
    linetop = np.zeros((upscale_f, upscale_f))
    linetop[0] = 1
    linedown = np.zeros((upscale_f, upscale_f))
    linedown[-1] = 1
    lineleft = np.zeros((upscale_f, upscale_f))
    lineleft[:, 0] = 1
    lineright = np.zeros((upscale_f, upscale_f))
    lineright[:, -1] = 1
    linecircle = np.zeros((upscale_f, upscale_f))
    cv2.circle(linecircle, (upscale_f//2, upscale_f//2), upscale_f//2, 1)
    linediagB = np.identity(upscale_f)
    linediagA = np.flip(linediagB, 1)
    # create images
    top_img = create_image(top_mat, upscale_f)
    side_img = create_image(side_mat, upscale_f)
    front_img = create_image(front_mat, upscale_f)

    # info img
    fontFace = cv2.FONT_HERSHEY_SIMPLEX
    # find max size text
    if bp_infos is None:
        info_img = np.full((front_img.shape[1],front_img.shape[1],3), np.array([255, 118, 33]),
                       dtype=np.uint8)
        fontScale = 12./cv2.getTextSize("I", fontFace, 1, 1)[0][1]  # scale to 12 pixels
        cv2.putText(info_img, "Error", (5,info_img.shape[0]//2), fontFace,
                    fontScale, (255,255,255))
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
        info_img = np.full((height,width,3), np.array([255, 118, 33]), dtype=np.uint8)
        
        # write info
        fontThickness = max(1, int(pixel * 0.07))
        px = pixel//2
        py = pixel-baseline+pixel//2
        for k in bp_infos:
            txt = f"{k}: {bp_infos[k]}"
            cv2.putText(info_img, txt, (px,py), fontFace, fontScale, (255,255,255), fontThickness)
            py += pixel+pixel

    darkBlue = np.array([255, 100, 0])
    
    #combine images
    bottombuffer = np.full((max(0,info_img.shape[0]-top_img.shape[0]),top_img.shape[1],3),
                           np.array([255, 118, 33]), dtype=np.uint8)
    rightbuffer = np.full((front_img.shape[0],max(0, info_img.shape[1]-front_img.shape[1]),3),
                           np.array([255, 118, 33]), dtype=np.uint8)
    #border side to front
    side_img[:,-2:] = darkBlue
    front_img[:,:2] = darkBlue
    toprow = np.concatenate((side_img, front_img, rightbuffer), 1)
    bottomrow = np.concatenate((top_img, bottombuffer), 0)
    #border top to info
    bottomrow[:,-2:] = darkBlue
    info_img[:,:2] = darkBlue
    bottomrow = np.concatenate((bottomrow, info_img), 1)
    #border toprow to bottomrow
    toprow[-2:,:] = darkBlue
    bottomrow[:2,:] = darkBlue
    res = np.concatenate((toprow, bottomrow), 0)
    return res


async def speed_test(fname):
    """Just some speed testing"""
    global main_img, blueprint, bp
    testlen = 10
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
    print("t1:", np.sum(t1)/testlen, "dt:", np.sum(np.abs(t1-np.sum(t1)/testlen))/testlen)
    print("t2:", np.sum(t2)/testlen, "dt:", np.sum(np.abs(t2-np.sum(t2)/testlen))/testlen)
    print("t3:", np.sum(t3)/testlen, "dt:", np.sum(np.abs(t3-np.sum(t3)/testlen))/testlen)
    print("t4:", np.sum(t4)/testlen, "dt:", np.sum(np.abs(t4-np.sum(t4)/testlen))/testlen)
    print("t5:", np.sum(t5)/testlen, "dt:", np.sum(np.abs(t5-np.sum(t5)/testlen))/testlen)
    
    blueprint = bp["Blueprint"]
    # show image
    cv2.imshow("Blueprint", main_img)

if __name__ == "__main__":
    # file
    fname = "../example blueprints/LightArmorBaracke.blueprint"

    import asyncio
    
    if False: asyncio.run(speed_test(fname))
    else:
        import sys, os
        if len(sys.argv) > 1:
            if os.path.exists(sys.argv[1]):
                fname = sys.argv[1]

        async def async_main():
            global bp, timing, main_img
            bp, timing, main_img = await process_blueprint(fname, False, True)
        asyncio.run(async_main())
        cv2.namedWindow("Blueprint", cv2.WINDOW_NORMAL)
        sY, sX, _ = main_img.shape
        sM = min(980 / sY, 1820 / sX)
        if sM < 1.0:
            cv2.resizeWindow("Blueprint", (int(sX * sM), int(sY * sM)))
        else:
            cv2.resizeWindow("Blueprint", (sX, sY))
        cv2.imshow("Blueprint", main_img)
        cv2.waitKey()
