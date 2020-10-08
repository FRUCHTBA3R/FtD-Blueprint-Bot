import json
import numpy as np
import quaternion
import cv2
import time

#rotation to direction
rot_to_dir = {-1: np.array([0, 0, 0]), #invalid
              0: np.array([0, 0, 1]),
              1: np.array([1, 0, 0]),
              2: np.array([0, 0, -1]),
              3: np.array([-1, 0, 0]),
              4: np.array([0, -1, 0]),
              5: np.array([0, -1, 0]),
              6: np.array([0, -1, 0]),
              7: np.array([0, -1, 0]),
              8: np.array([0, 1, 0]),
              9: np.array([0, 1, 0]),
              10: np.array([0, 1, 0]),
              11: np.array([0, 1, 0]),
              12: np.array([0, 0, 1]),
              13: np.array([1, 0, 0]),
              14: np.array([0, 0, -1]),
              15: np.array([-1, 0, 0]),
              16: np.array([0, 0, 1]),
              17: np.array([0, 0, -1]),
              18: np.array([0, 0, 1]),
              19: np.array([0, 0, -1]),
              20: np.array([1, 0, 0]),
              21: np.array([-1, 0, 0]),
              22: np.array([1, 0, 0]),
              23: np.array([-1, 0, 0])}
#convert dir to quaternion
for k in rot_to_dir: rot_to_dir[k] = np.quaternion(0, *rot_to_dir[k])

blocks = None
blocks_file = "blocks.json"

materials = None
materials_file = "materials.json"

with open(blocks_file, "r") as f:
    blocks = json.loads(f.read())

with open(materials_file, "r") as f:
    materials = json.loads(f.read())
    

def load_blueprint_file(bp_fname):
    """Load and init blueprint file"""
    with open(bp_fname, "r") as f:
        bp = json.loads(f.read())

    blueprint = bp["Blueprint"]
    bp_info(bp)
    #convert main and all subconstruct data to numpy data and co
    __construct_init(blueprint, True)
    #convert item dict keys to int
    __itemdict_init(bp)
    #init coordinates
    __coordinates_init(blueprint)
    return bp
    

def bp_info(bp):
    """Print basic info of blueprint"""
    print(f"FileModelVersion: {bp['FileModelVersion']['Major']}.{bp['FileModelVersion']['Minor']}")
    print(f"Name: {bp['Name']}")
    print(f"Version: {bp['Version']}")
    print(f"SavedTotalBlockCount: {bp['SavedTotalBlockCount']}")
    print(f"SavedMaterialCost: {bp['SavedMaterialCost']}")
    maxC = bp['Blueprint']['MaxCords']
    minC = bp['Blueprint']['MinCords']
    maxC = np.array(maxC.split(","), dtype=np.int32) + 1 #this is a block
    minC = np.array(minC.split(","), dtype=np.int32)
    print(f"Main construct size: {maxC - minC}")


#Blueprint:
#CSI: block color
#COL: craft colors ["float,float,float"]
#SCs:
#BLP: block position ["int,int,int"]
#BLR: block rotation [int]
#BP1
#BP2
#BCI: maybe block color index
#BEI:

#BlockIds: block ids [int]



def __construct_init(base_blueprint, ismainbp = False, desc="base"):
        """Initialize base blueprint and all sub blueprints"""
        for i in range(base_blueprint["BlockCount"]):
            base_blueprint["BLP"][i] = np.array(base_blueprint["BLP"][i].split(","), dtype=float).astype(int)
        base_blueprint["BLP"] = np.array(base_blueprint["BLP"])
        if ismainbp:
            #convert local rotation to quaternion
            base_blueprint["LocalRotation"] = np.quaternion(1, 0, 0, 0)
            #convert local position to np array
            base_blueprint["LocalPosition"] = np.array([0,0,0])
        else:
            #convert local rotation to quaternion
            #print(desc, base_blueprint["LocalRotation"])
            base_blueprint["LocalRotation"] = np.quaternion(*(np.array(
                base_blueprint["LocalRotation"].split(","), dtype=float))[[3,0,1,2]])
            #convert local position to np array
            base_blueprint["LocalPosition"] = np.array(base_blueprint["LocalPosition"].split(","), dtype=float).astype(int)
        #convert max/min cords to np array
        base_blueprint['MaxCords'] =  np.array(base_blueprint['MaxCords'].split(","), dtype=float).astype(int)
        base_blueprint['MinCords'] =  np.array(base_blueprint['MinCords'].split(","), dtype=float).astype(int)
        
        #iterate subconstructs
        for sc_i in range(len(base_blueprint["SCs"])):
            __construct_init(base_blueprint["SCs"][sc_i], desc=f"{desc}:{sc_i}")


def __itemdict_init(bp):
    """Convert ItemDictionary keys to integer"""
    keys = list(bp["ItemDictionary"].keys())
    for k in keys:
        bp["ItemDictionary"][int(k)] = bp["ItemDictionary"][k]
        del bp["ItemDictionary"][k]

def __coordinates_init(blueprint):
    """Initialize blueprint coordinates"""
    #get bp size
    def getMinMaxCoords(base_blueprint, desc="base"):
        #get coords as quaternions
        maxcoords = np.quaternion(0, *base_blueprint['MaxCords'])
        mincoords = np.quaternion(0, *base_blueprint['MinCords'])
        #rotate coords
        rot = base_blueprint["LocalRotation"]
        maxcoords = rot * maxcoords * rot.inverse()
        mincoords = rot * mincoords * rot.inverse()
        #add local position
        local_pos = base_blueprint["LocalPosition"]
        maxcoords = maxcoords.vec + local_pos
        mincoords = mincoords.vec + local_pos
        #re-max / re-min (necessary due to rotation)
        mem = np.maximum(maxcoords, mincoords)
        mincoords = np.minimum(maxcoords, mincoords)
        maxcoords = mem
        #print(desc, mincoords, maxcoords)
        #iterate subconstructs
        for sc_i in range(len(base_blueprint["SCs"])):
            sc_mincoords, sc_maxcoords = getMinMaxCoords(base_blueprint["SCs"][sc_i], f"{desc}:{sc_i}")
            maxcoords = np.maximum(maxcoords, sc_maxcoords)
            mincoords = np.minimum(mincoords, sc_mincoords)
        return (mincoords, maxcoords)

    mincoords_all, maxcoords_all = getMinMaxCoords(blueprint)
    mincoords_all = np.rint(mincoords_all).astype(int)
    maxcoords_all = np.rint(maxcoords_all).astype(int)
    blueprint['MaxCords'] =  blueprint['MaxCords'] + 1 #this is a block
    blueprint['MaxOriginCords'] = np.max(blueprint["BLP"], 0)
    blueprint['MinOriginCords'] = np.min(blueprint["BLP"], 0)
    blueprint['MaxAllCords'] = maxcoords_all #np.maximum(blueprint['MaxCords'], blueprint['MaxOriginCords'])
    blueprint['MinAllCords'] = mincoords_all #np.minimum(blueprint['MinCords'], blueprint['MinOriginCords'])
    blueprint['Size'] = maxcoords_all - mincoords_all + 1 #blueprint['MaxCords'] - blueprint['MinCords']
    print("Total size with subconstructs:", blueprint['Size'])


#create image
def createImage(bp, axis0, axis1, silent=False, print_type=0):
    """Create an image of axis0 axis1 plane"""
    blueprint = bp["Blueprint"]
    #create block matrix and height matrix
    block_guid_mat = [["" for i in range(blueprint['Size'][axis1])] for j in range(blueprint['Size'][axis0])]
    block_height_mat = np.full((blueprint['Size'][axis0],blueprint['Size'][axis1]), -1, dtype=int)
    haxis = 3 ^ (axis0 | axis1)
    #fill function
    def fill_from_blueprint(construct_blueprint):
        local_rotation = construct_blueprint["LocalRotation"]
        local_rotation_inv = local_rotation.inverse()
        for i in range(construct_blueprint["BlockCount"]):
            block_guid = bp["ItemDictionary"][construct_blueprint["BlockIds"][i]]
            if block_guid in blocks:
                block_pos = np.quaternion(0, *construct_blueprint["BLP"][i])
                #rotate position
                block_pos = local_rotation*block_pos*local_rotation_inv
                block_pos = np.rint(block_pos.vec).astype(int)
                #offset
                block_pos = block_pos + construct_blueprint["LocalPosition"] - blueprint['MinAllCords']
                block_rot = construct_blueprint["BLR"][i]
                #rotate dir
                block_rot_dir = local_rotation*rot_to_dir[block_rot]*local_rotation_inv
                block_rot_dir = np.rint(block_rot_dir.vec).astype(int)
                #invisible material filter
                if "Material" in blocks[block_guid] and "Invisible" in materials[blocks[block_guid]["Material"]] \
                   and materials[blocks[block_guid]["Material"]]["Invisible"] == True:
                    continue
                if "Length" in blocks[block_guid]:
                    block_length = blocks[block_guid]["Length"]
                else:
                    block_length = 1
                if block_rot not in rot_to_dir:
                    if not silent: print(f"WARN: Block Rotation {block_rot} is misssing (only one block drawn)")
                    block_length = 1
                    block_rot = -1
                    block_guid = "missing rotation"
                if type(block_length) == int:
                    for k in range(block_length):
                        try:
                            if block_height_mat[block_pos[axis0]][block_pos[axis1]] <= block_pos[haxis]:
                                block_guid_mat[block_pos[axis0]][block_pos[axis1]] = block_guid
                                block_height_mat[block_pos[axis0]][block_pos[axis1]] = block_pos[haxis]
                        except:
                            print("ERROR")
                        block_pos += block_rot_dir
                elif type(block_length) == list and len(block_length) == 2:
                    print(f"WARN: Area blocks are not implemented")
                    None
                else:
                    print(f"WARN: Unknown block length {block_length} of block {block_guid}")
            else:
                if not silent: print(f"WARN: Block Guid {block_guid} missing in {blocks_file} at {block_pos}")
                if block_height_mat[block_pos[axis0]][block_pos[axis1]] <= block_pos[haxis]:
                    block_guid_mat[block_pos[axis0]][block_pos[axis1]] = "missing"
                    block_height_mat[block_pos[axis0]][block_pos[axis1]] = block_pos[haxis]

    #fill main construct
    fill_from_blueprint(blueprint)
    #iterate subconstructs
    def subconstruct_iter(base_blueprint):
        for sc_i in range(len(base_blueprint["SCs"])):
            #print("Subconstruct:", sc_i)
            fill_from_blueprint(base_blueprint["SCs"][sc_i])
            subconstruct_iter(base_blueprint["SCs"][sc_i])
    subconstruct_iter(blueprint)

    #create blank image, swap axis
    #content scaling
    img_minsize = 50
    padding = 10
    img_w = blueprint['Size'][axis0]
    img_h = blueprint['Size'][axis1]
    img_current_maxsize = max(img_w, img_h)
    img_scaleup = img_minsize / img_current_maxsize
    if (img_scaleup > 1.0):
        img_scaleup = int(np.ceil(img_scaleup))
        img_scaleup += (img_scaleup+1) % 2
    else: img_scaleup = 0
    img_scaleup = max(img_scaleup, 5)
    #scale + padding
    img_h = img_h * img_scaleup + padding + padding
    img_w = img_w * img_scaleup + padding + padding
    #image
    img = np.zeros((img_h, img_w, 3), dtype=np.uint8)
    #color padding for dbg
    img[:,:] += np.array([255, 118, 33], dtype=np.uint8)
    #img[padding:img_h-padding,padding:img_w-padding] = 0
    #offset to center of block
    img_center_offset = (img_scaleup - 1) // 2
    #fill img
    i_img = img_h - padding - img_scaleup
    if print_type == 0:#just color
        for i in range(blueprint['Size'][axis1]):
            j_img = padding
            for j in range(blueprint['Size'][axis0]):
                block = block_guid_mat[j][i]
                if (block != ""):
                    if "Material" in blocks[block]:
                        block_material = blocks[block]["Material"]
                    else:
                        block_material = "Missing"
                    block_color = materials[block_material]["Color"]
                    img[i_img:i_img+img_scaleup, j_img:j_img+img_scaleup] = block_color
                j_img += img_scaleup
            i_img -= img_scaleup
    elif print_type == 1:#just height
        maxheight = np.amax(block_height_mat)
        for i in range(blueprint['Size'][axis1]):
            j_img = padding
            for j in range(blueprint['Size'][axis0]):
                blockheight = block_height_mat[j][i]
                if (blockheight > -1):
                    block_color = np.array([155+100*blockheight/maxheight]*3)
                    img[i_img:i_img+img_scaleup, j_img:j_img+img_scaleup] = block_color
                j_img += img_scaleup
            i_img -= img_scaleup
    elif print_type == 2:#color with height shading
        maxheight = np.amax(block_height_mat)
        for i in range(blueprint['Size'][axis1]):
            j_img = padding
            for j in range(blueprint['Size'][axis0]):
                block = block_guid_mat[j][i]
                blockheight = block_height_mat[j][i]
                if (block != ""):
                    if "Material" in blocks[block]:
                        block_material = blocks[block]["Material"]
                    else:
                        block_material = "Missing"
                    block_color = np.array(materials[block_material]["Color"], dtype=float)
                    block_color *= 0.5+1.*(blockheight/maxheight)
                    block_color = np.clip(block_color, 0, 255)
                    img[i_img:i_img+img_scaleup, j_img:j_img+img_scaleup] = block_color.astype(np.uint8)
                j_img += img_scaleup
            i_img -= img_scaleup
    elif print_type == 3:#height contour lines
        #diagonal line offsets
        diag_point_offset = {0b1010: (0, 0, img_scaleup-1, img_scaleup-1),
                             0b1001: (img_scaleup-1, 0, 0, img_scaleup-1),
                             0b0110: (img_scaleup-1, 0, 0, img_scaleup-1),
                             0b0101: (0, 0, img_scaleup-1, img_scaleup-1)}
        ishighstep = lambda c, x: 1 if ((x == -1) or (c > x + 1)) else 0
        issuperstep = lambda c, x: 1 if (x == -1) else 0
        maxheight = np.amax(block_height_mat)
        for i in range(0,blueprint['Size'][axis1]):
            j_img = padding
            for j in range(0,blueprint['Size'][axis0]):
                block = block_guid_mat[j][i]
                blockheight = block_height_mat[j][i]
                if (block != ""):
                    if "Material" in blocks[block]:
                        block_material = blocks[block]["Material"]
                    else:
                        block_material = "Missing"
                    block_color = np.array(materials[block_material]["Color"], dtype=float)
                    block_color *= 0.5+1.*(blockheight/maxheight)
                    block_color = np.clip(block_color, 0, 255)
                    img[i_img:i_img+img_scaleup, j_img:j_img+img_scaleup] = block_color.astype(np.uint8)
                blockheight = block_height_mat[j][i]
                if (blockheight > -1):
                    if i < blueprint['Size'][axis1] - 1:
                        dup = ishighstep(blockheight, block_height_mat[j][i+1])
                        sup = issuperstep(blockheight, block_height_mat[j][i+1])
                    else:
                        dup = 1
                        sup = 1
                    
                    if i > 0:
                        ddown = ishighstep(blockheight, block_height_mat[j][i-1])
                        sdown = issuperstep(blockheight, block_height_mat[j][i-1])
                    else:
                        ddown = 1
                        sdown = 1
                    
                    if j < blueprint['Size'][axis0] - 1:
                        dleft = ishighstep(blockheight, block_height_mat[j+1][i])
                        sleft = issuperstep(blockheight, block_height_mat[j+1][i])
                    else:
                        dleft = 1
                        sleft = 1
                    
                    if j > 0:
                        dright = ishighstep(blockheight, block_height_mat[j-1][i])
                        sright = issuperstep(blockheight, block_height_mat[j-1][i])
                    else:
                        dright = 1
                        sright = 1

                    #count
                    dcount = dup + ddown + dleft + dright
                    #all four, draw circle
                    if dcount == 4:
                        cv2.circle(img, (j_img+img_center_offset, i_img+img_center_offset),
                                         img_center_offset, (255,255,255))
                    else:
                        #only 2 neighbouring, draw diagonal line
                        if dcount == 2 and not (dup == ddown and dleft == dright):
                            state = (dup << 3) | (ddown << 2) | (dleft << 1) | dright
                            p1x, p1y, p2x, p2y = diag_point_offset[state]
                            p1x += j_img
                            p1y += i_img
                            p2x += j_img
                            p2y += i_img
                            cv2.line(img, (p1x, p1y), (p2x, p2y), (255,255,255))
                        else:
                            if dup:
                                p1 = (j_img, i_img)
                                p2 = (j_img+img_scaleup-1, i_img)
                                cv2.line(img, p1, p2, (255,255,255))
                            if ddown:
                                p1 = (j_img, i_img+img_scaleup-1)
                                p2 = (j_img+img_scaleup-1, i_img+img_scaleup-1)
                                cv2.line(img, p1, p2, (255,255,255))
                            if dleft:
                                p1 = (j_img+img_scaleup-1, i_img)
                                p2 = (j_img+img_scaleup-1, i_img+img_scaleup-1)
                                cv2.line(img, p1, p2, (255,255,255))
                            if dright:
                                p1 = (j_img, i_img)
                                p2 = (j_img, i_img+img_scaleup-1)
                                cv2.line(img, p1, p2, (255,255,255))

                        #super count
                        scount = sup + sdown + sleft + sright
                        #super step
                        if scount == 1:
                            if sup:
                                p1 = (j_img, i_img)
                                p2 = (j_img+img_scaleup-1, i_img)
                                cv2.line(img, p1, p2, (255,255,255))
                            if sdown:
                                p1 = (j_img, i_img+img_scaleup-1)
                                p2 = (j_img+img_scaleup-1, i_img+img_scaleup-1)
                                cv2.line(img, p1, p2, (255,255,255))
                            if sleft:
                                p1 = (j_img+img_scaleup-1, i_img)
                                p2 = (j_img+img_scaleup-1, i_img+img_scaleup-1)
                                cv2.line(img, p1, p2, (255,255,255))
                            if sright:
                                p1 = (j_img, i_img)
                                p2 = (j_img, i_img+img_scaleup-1)
                                cv2.line(img, p1, p2, (255,255,255))
                         
                j_img += img_scaleup
            i_img -= img_scaleup
    return img

def print_blueprint(bp_fname, print_type=3):
    """Process and print blueprint from file"""
    print("Starting print...")
    ts = time.time()
    bp = load_blueprint_file(bp_fname)
    img_xy = createImage(bp, 0, 1, print_type=print_type) #frontal view with upward pointing up
    img_xz = createImage(bp, 2, 0, print_type=print_type) #top down view with frontside pointing up
    img_yz = createImage(bp, 2, 1, print_type=print_type) #right side view with front pointing right
    img_fname = bp_fname[:-10]
    img_front = img_fname + "_front.png"
    img_top = img_fname + "_top.png"
    img_side = img_fname + "_side.png"
    cv2.imwrite(img_front, img_xy)
    cv2.imwrite(img_top, img_xz)
    cv2.imwrite(img_side, img_yz)
    print("Finished print. Took", time.time() - ts, "s")
    return (bp["Name"], img_front, img_top, img_side)

def example_print():
    bp = load_blueprint_file("example blueprints/PreDread Forwards 2xMain 4xSec.blueprint")
    draw_height = 3
    #plane views, vehicle forward is z, upward is z, right is x
    img_xz = createImage(bp, 2, 0, print_type=draw_height) #top down view with frontside pointing up
    #show
    cv2.namedWindow("TopImg", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("TopImg", img_xz.shape[1], img_xz.shape[0])
    cv2.imshow("TopImg", img_xz)
    if True:
        img_xy = createImage(bp, 0, 1, print_type=draw_height) #frontal view with upward pointing up
        cv2.namedWindow("FrontImg", cv2.WINDOW_NORMAL)
        cv2.imshow("FrontImg", img_xy)
        cv2.resizeWindow("FrontImg", img_xy.shape[1], img_xy.shape[0])
    if True:
        img_yz = createImage(bp, 2, 1, print_type=draw_height) #right side view with front pointing right
        cv2.namedWindow("RightImg", cv2.WINDOW_NORMAL)
        cv2.imshow("RightImg", img_yz)
        cv2.resizeWindow("RightImg", img_yz.shape[1], img_yz.shape[0])

if __name__ == "__main__":
    pass
    #example_print()



