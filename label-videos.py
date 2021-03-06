import os
import re
import sys
import cv2
import json
import argparse
import numpy as np
from utils import load_options
from utils import to_labels_array, to_labels_dict
from video_loader import MultipleVideoLoader
from is_wire.core import Logger
from collections import defaultdict, OrderedDict
import time


def place_images(output_image, images, x_offset=0, y_offset=0):
    w, h = images[0].shape[1], images[0].shape[0]
    output_image[0 + y_offset:h + y_offset, 0 + x_offset:w + x_offset, :] = images[0]
    output_image[0 + y_offset:h + y_offset, w + x_offset:2 * w + x_offset, :] = images[1]
    output_image[h + y_offset:2 * h + y_offset, 0 + x_offset:w + x_offset, :] = images[2]
    output_image[h + y_offset:2 * h + y_offset, w + x_offset:2 * w + x_offset, :] = images[3]


def draw_labels(output_image, y_offset, labels, current_pos, n_loaded_frames=None):
    w, h = output_image.shape[1], output_image.shape[0]
    scale = w / len(labels)
    output_image[h - y_offset:, :, :] = 0

    def draw_rect(x, width, color):
        pt1 = (int(x - width / 2), int(h - y_offset))
        pt2 = (int(x + width / 2), int(h))
        cv2.rectangle(img=output_image, pt1=pt1, pt2=pt2, color=color, thickness=cv2.FILLED)

    maybe_begins = scale * np.where(labels == 2)[0]
    begins = scale * np.where(labels == 1)[0]
    gestures = scale * np.where(labels == 3)[0]
    ends = scale * np.where(labels == -1)[0]
    for p in maybe_begins:
        draw_rect(p, scale, (0, 255, 0))
    for p in begins:
        draw_rect(p, scale, (255, 0, 0))
    for p in gestures:
        draw_rect(p, scale, (127, 127, 127))
    for p in ends:
        draw_rect(p, scale, (0, 0, 255))
    draw_rect(scale * current_pos, scale, (0, 255, 255))
    if param.n_loaded_frames is not None:
        not_loaded = len(labels) - param.n_loaded_frames
        x = scale * (not_loaded / 2 + param.n_loaded_frames)
        width = scale * not_loaded
        draw_rect(x, width, (255, 255, 255))


def put_text(image, text, x, y, color=(255, 255, 255), font_scale=1.5, thickness=2):
    cv2.putText(
        img=image,
        text=text,
        org=(int(x), int(y)),
        fontFace=cv2.FONT_HERSHEY_DUPLEX,
        fontScale=font_scale,
        color=color,
        thickness=thickness)


parser = argparse.ArgumentParser(
    description='Utility to capture a sequence of images from multiples cameras')
parser.add_argument(
    '--skip-labeled', '-s', action='store_true', help='If set, skips videos already labeled.')
args = parser.parse_args()

log = Logger(name='LabelVideos')

with open('keymap.json', 'r') as f:
    keymap = json.load(f)
    print(json.dumps(keymap, indent=2))

options = load_options(print_options=False)

if not os.path.exists(options.folder):
    log.critical("Folder '{}' doesn't exist", options.folder)
    sys.exit(-1)

with open('gestures.json', 'r') as f:
    gestures_labels = json.load(f)
    gestures_labels = OrderedDict(sorted(gestures_labels.items(), key=lambda kv: int(kv[0])))

bottom_bar_h = 50
top_bar_h = 75
height = 2 * options.cameras[0].config.image.resolution.height
width = 2 * options.cameras[0].config.image.resolution.width
size = (height + bottom_bar_h + top_bar_h, width, 3)

files = next(os.walk(options.folder))[2]  # only files from first folder level
video_files = list(filter(lambda x: x.endswith('.mp4'), files))

captures = defaultdict(lambda: defaultdict(set))
for video_file in video_files:
    matches = re.search(r'p([0-9]{3})g([0-9]{2})c([0-9]{2}).mp4$', video_file)
    if matches is None:
        continue
    person_id = int(matches.group(1))
    gesture_id = int(matches.group(2))
    camera = int(matches.group(3))
    captures[person_id][gesture_id].add(camera)


class LabelingParameters:
    def __init__(self):
        self.it_frames = 0
        self.n_loaded_frames = 0
        self.update_image = True
        self.big_step = 1

param = LabelingParameters()
param.big_step = keymap['big_step']

def mouse_events(event, x, y, flags, param):
    shift_press = flags & cv2.EVENT_FLAG_SHIFTKEY
    if event == cv2.EVENT_MOUSEWHEEL:
        if flags < 0:
            param.it_frames += param.big_step if shift_press else 1
            param.it_frames = param.it_frames if param.it_frames < param.n_loaded_frames else 0
        else:
            param.it_frames -= param.big_step if shift_press else 1
            param.it_frames = param.n_loaded_frames - 1 if param.it_frames < 0 else param.it_frames
        param.update_image = True


cv2.namedWindow('')
cv2.setMouseCallback('', mouse_events, param)
for person_id, gestures in captures.items():
    for gesture_id, cameras in gestures.items():

        cameras_str = '[' + ', '.join(map(str, cameras)) + ']'
        log.info('Loading PERSON_ID: {:03d} GESTURE_ID: {:02d} CAMERAS: {:s}', person_id,
                 gesture_id, cameras_str)
        video_files = {
            camera: os.path.join(options.folder, 'p{:03d}g{:02d}c{:02d}.mp4'.format(
                person_id, gesture_id, camera))
            for camera in sorted(cameras)
        }
        video_loader = MultipleVideoLoader(video_files)
        labels = np.zeros(video_loader.n_frames(), dtype=np.int8)

        # check if label file already exists
        labels_file = os.path.join(options.folder, 'p{:03d}g{:02d}_spots.json'.format(
            person_id, gesture_id))
        if os.path.exists(labels_file):
            if args.skip_labeled:
                continue
            with open(labels_file, 'r') as f:
                labels = to_labels_array(json.load(f))

        full_image = np.zeros(size, dtype=np.uint8)
        put_text(
            full_image,
            'PERSON_ID: {:03d} GESTURE_ID: {:02d} ({:s})'.format(person_id, gesture_id,
                                                                 gestures_labels[str(gesture_id)]),
            x=20,
            y=0.8 * top_bar_h)
        original_labels = np.copy(labels)
        param.it_frames = 0
        param.update_image, waiting_end, current_begin, current_images = True, False, 0, []
        while True:
            if video_loader.n_loaded_frames() < video_loader.n_frames():
                param.update_image = True
            param.n_loaded_frames = video_loader.load_next()

            if param.update_image:
                frames = video_loader[param.it_frames]
                if frames is not None:
                    frames_list = [frames[cam] for cam in sorted(frames.keys())]
                    place_images(full_image, frames_list, y_offset=top_bar_h)
                    draw_labels(full_image, top_bar_h, labels, param.it_frames, param.n_loaded_frames)
                cv2.imshow('', cv2.resize(full_image, dsize=(0, 0), fx=0.5, fy=0.5))
                param.update_image = False

            key = cv2.waitKey(1)
            if key == -1:
                continue

            if key == ord(keymap['next_frames']):
                param.it_frames += keymap['big_step']
                param.it_frames = param.it_frames if param.it_frames < param.n_loaded_frames else 0
                param.update_image = True

            if key == ord(keymap['next_frame']):
                param.it_frames += 1
                param.it_frames = param.it_frames if param.it_frames < param.n_loaded_frames else 0
                param.update_image = True

            if key == ord(keymap['previous_frames']):
                param.it_frames -= keymap['big_step']
                param.it_frames = param.n_loaded_frames - 1 if param.it_frames < 0 else param.it_frames
                param.update_image = True

            if key == ord(keymap['previous_frame']):
                param.it_frames -= 1
                param.it_frames = param.n_loaded_frames - 1 if param.it_frames < 0 else param.it_frames
                param.update_image = True

            if key == ord(keymap['begin_label']):
                if labels[param.it_frames] == 0 and not waiting_end:
                    labels[param.it_frames] = 2
                    current_begin = param.it_frames
                    waiting_end = True
                    param.update_image = True
                elif param.it_frames == current_begin and waiting_end:
                    labels[param.it_frames] = 0
                    waiting_end = False
                    param.update_image = True
                elif (labels[param.it_frames] == -1 or labels[param.it_frames] == 3) and not waiting_end:
                    previous_begin = np.where(labels[:param.it_frames] == 1)[0][-1]
                    param.it_frames = previous_begin
                    param.update_image = True

            if key == ord(keymap['end_label']):
                if labels[param.it_frames] == 0 and waiting_end:
                    if param.it_frames > current_begin:
                        labels[current_begin] = 1
                        labels[param.it_frames] = -1
                        labels[current_begin + 1:param.it_frames] = 3
                        waiting_end = False
                        param.update_image = True
                elif labels[param.it_frames] == -1:
                    labels[param.it_frames] = 0
                    current_begin = np.where(labels[:param.it_frames] == 1)[0][-1]
                    labels[current_begin] = 2
                    labels[current_begin + 1:param.it_frames] = 0
                    waiting_end = True
                    param.update_image = True
                elif (labels[param.it_frames] == 1 or labels[param.it_frames] == 3) and not waiting_end:
                    next_end = np.where(labels[param.it_frames:] == -1)[0][0] + param.it_frames
                    param.it_frames = next_end
                    param.update_image = True

            if key == ord(keymap['delete_label']):
                if labels[param.it_frames] == 3 and not waiting_end:
                    begin = np.where(labels[:param.it_frames] == 1)[0][-1]
                    end = np.where(labels[param.it_frames:] == -1)[0][0] + param.it_frames
                    labels[begin:end + 1] = 0
                    param.update_image = True

            if key == ord(keymap['save_labels']):
                indexes, counts = np.unique(labels, return_counts=True)
                counts_dict = dict(zip(indexes, counts))
                if not waiting_end and counts_dict[-1] == counts_dict[1]:
                    with open(labels_file, 'w') as f:
                        json.dump(to_labels_dict(labels), f, indent=2)
                        log.info("File '{}' saved", labels_file)
                    original_labels = labels

            if key == ord(keymap['next_sequence']):
                if np.all(labels == original_labels):
                    break
                else:
                    log.warn('You have unsaved changes! Save before move to next sequence.')

            if key == ord(keymap['exit']):
                sys.exit(0)

log.info('Exiting')