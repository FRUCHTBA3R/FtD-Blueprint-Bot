import numpy as np
import cv2


class FiringAnimator:
    def __init__(self):
        self.firing_positions = np.zeros((0, 3), dtype=int)
        self.firing_directions = np.zeros((0, 3), dtype=int)
        self.firing_strengths = np.zeros(0, dtype=np.float16)
        # side animation
        self.animation = [cv2.imread("firing_animation/frame0.png", cv2.IMREAD_UNCHANGED),
                          cv2.imread("firing_animation/frame1.png", cv2.IMREAD_UNCHANGED),
                          cv2.imread("firing_animation/frame2.png", cv2.IMREAD_UNCHANGED),
                          cv2.imread("firing_animation/frame3.png", cv2.IMREAD_UNCHANGED),
                          cv2.imread("firing_animation/frame4.png", cv2.IMREAD_UNCHANGED),
                          cv2.imread("firing_animation/frame5.png", cv2.IMREAD_UNCHANGED)]
                         # [cv2.imread("firing_animation/frameB0.png", cv2.IMREAD_UNCHANGED),
                         #  cv2.imread("firing_animation/frameB1.png", cv2.IMREAD_UNCHANGED),
                         #  cv2.imread("firing_animation/frameB2.png", cv2.IMREAD_UNCHANGED)]
        self.animation_depth = [0, 1, 2, 2, 3, 3]
        self.animation_origin = np.array([15, 0])
        # front animation
        self.animation_front = [cv2.imread("firing_animation/frame_front0.png", cv2.IMREAD_UNCHANGED),
                                cv2.imread("firing_animation/frame_front1.png", cv2.IMREAD_UNCHANGED),
                                cv2.imread("firing_animation/frame_front2.png", cv2.IMREAD_UNCHANGED),
                                cv2.imread("firing_animation/frame_front3.png", cv2.IMREAD_UNCHANGED),
                                cv2.imread("firing_animation/frame_front4.png", cv2.IMREAD_UNCHANGED),
                                cv2.imread("firing_animation/frame_front5.png", cv2.IMREAD_UNCHANGED)]
        self.animation_front_depth = [1, 4, 6, 6, 7, 7]
        self.animation_front_origin = np.array([15, 15])
        # back animation
        self.animation_back = [self.animation_front[0],
                               cv2.imread("firing_animation/frame_back1.png", cv2.IMREAD_UNCHANGED),
                               cv2.imread("firing_animation/frame_back2.png", cv2.IMREAD_UNCHANGED),
                               *self.animation_front[3:]]
        # anim offsets
        a, b = self.animation_origin
        c, d = self.animation[0].shape[0:2]
        self.__animation_offset_list = np.array([[a, b],
                                                 [d - 5, c - a - 5],
                                                 [c - a - 5, d - 5],
                                                 [-b, c - a - 5],
                                                 self.animation_front_origin,
                                                 self.animation_front_origin])

        self.max_frames = len(self.animation) * 5
        self.state = None

        self.__current_frame = None
        self.__current_index = None
        self.__total_frames = None

    def append(self, firing_positions, firing_directions, firing_strengths):
        self.firing_positions = np.concatenate((self.firing_positions, firing_positions), axis=0)
        self.firing_directions = np.concatenate((self.firing_directions, firing_directions), axis=0)
        self.firing_strengths = np.concatenate((self.firing_strengths, firing_strengths), axis=0)

    def get_total_frame_count(self):
        if self.state is None:
            raise Exception("Call setup_ordered first.")
        return self.__total_frames

    def setup_order(self, axis=2, ascending=False):
        """
        Animation setup.
        :param axis: Axis selection for ordering, -1 for random order, -2 for all at once
        :param ascending: Sort axis ascending or descending.
        """
        max_spaced_frame_count = min(len(self.firing_positions) * len(self.animation), self.max_frames)
        available_frames = max_spaced_frame_count - len(self.animation) + 1
        shots_per_frame = len(self.firing_positions) / available_frames
        self.state = np.zeros(len(self.firing_positions), dtype=np.int8)
        if axis == -2:
            # fire all at the same time
            self.__total_frames = len(self.animation)
            return
        elif axis == -1:
            # random firing order
            order = np.arange(len(self.firing_positions))
            np.random.shuffle(order)
        else:
            order = np.argsort(self.firing_positions[:, axis])
            if not ascending:
                order = np.flip(order)
        # loop
        start_frame = 0
        i = 0
        shots_available = shots_per_frame
        do_loop = len(self.firing_positions) > 0
        while do_loop:
            while shots_available < 1:
                shots_available += shots_per_frame
                start_frame -= 1
            while shots_available >= 1:
                self.state[order[i]] = start_frame
                i += 1
                if i >= len(order):
                    do_loop = False
                    break
                shots_available -= 1
        self.__total_frames = abs(start_frame) + len(self.animation)

    def iter_frames(self):
        if self.state is None:
            raise Exception("Call setup_ordered first.")
        for self.__current_frame in range(self.get_total_frame_count()):
            yield self.__current_frame
            self.state += 1
        self.__current_frame = None

    def iter_ordered(self, axis):
        order = np.argsort(self.firing_positions[:, axis])
        for self.__current_index in order:
            yield self.firing_positions[self.__current_index], self.firing_directions[self.__current_index], \
                  self.firing_strengths[self.__current_index]
        self.__current_index = None

    def get_animation(self, rotation_id=0):
        """Returns current animation image, animation depth and offset to its origin.
        :param rotation_id: 0 = right, 1 = up, 2 = left, 3 = down, 4 = forwards, 5 = backwards
        :return: image, depth and offset
        """
        state = self.state[self.__current_index]
        if state < 0:
            return None
        #flipA = False
        #flipB = False
        if state >= len(self.animation):
            return None
            #state = len(self.animation) - 1
            #flipA = np.random.randint(0, 2, dtype=np.bool)
            #flipB = np.random.randint(0, 2, dtype=np.bool)

            #state = np.random.randint(-2, 0) + len(self.animation)
            #alpha_mul = pow(.999, state - len(self.animation) + 1)

            #state = len(self.animation) - 1
        img = self.animation[state]
        depth = self.animation_depth[state]
        if rotation_id == 1:
            img = np.flipud(np.transpose(img, (1, 0, 2)))
        elif rotation_id == 2:
            img = np.fliplr(img)
        elif rotation_id == 3:
            img = np.fliplr(np.transpose(img, (1, 0, 2)))
        elif rotation_id == 4:
            img = self.animation_front[state]
            depth = self.animation_front_depth[state]
        elif rotation_id == 5:
            img = self.animation_back[state]
            depth = 0  # self.animation_back_depth[state]
        #if alpha_mul:
        #    img[:, :, 3] = img[:, :, 3] * alpha_mul
        #if flipA:
        #    img = np.fliplr(img)
        #if flipB:
        #    img = np.flipud(img)
        return img, depth, self.__animation_offset_list[rotation_id]
