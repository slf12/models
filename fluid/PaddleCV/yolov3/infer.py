import os
import time
import numpy as np
import paddle
import paddle.fluid as fluid
import box_utils
import reader
from utility import print_arguments, parse_args
import models.yolov3 as models
# from coco_reader import load_label_names
import json
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval, Params
from config import cfg


def infer():

    if not os.path.exists('output'):
        os.mkdir('output')

    model = models.YOLOv3(cfg.model_cfg_path, is_train=False)
    model.build_model()
    outputs = model.get_pred()
    input_size = model.get_input_size()
    yolo_anchors = model.get_yolo_anchors()
    yolo_classes = model.get_yolo_classes()
    place = fluid.CUDAPlace(0) if cfg.use_gpu else fluid.CPUPlace()
    exe = fluid.Executor(place)
    # yapf: disable
    if cfg.weights:
        def if_exist(var):
            return os.path.exists(os.path.join(cfg.weights, var.name))
        fluid.io.load_vars(exe, cfg.weights, predicate=if_exist)
    # yapf: enable
    feeder = fluid.DataFeeder(place=place, feed_list=model.feeds())
    fetch_list = [outputs]
    image_names = []
    if cfg.image_name is not None:
        image_names.append(cfg.image_name)
    else:
        for image_name in os.listdir(cfg.image_path):
            if image_name.split('.')[-1] in ['jpg', 'png']:
                image_names.append(image_name)
    for image_name in image_names:
        infer_reader = reader.infer(input_size, os.path.join(cfg.image_path, image_name))
        label_names, _ = reader.get_label_infos()
        data = next(infer_reader())
        im_shape = data[0][2]
        outputs = exe.run(
            fetch_list=[v.name for v in fetch_list],
            feed=feeder.feed(data),
            return_numpy=False)
        bboxes = np.array(outputs[0])
        if bboxes.shape[1] != 6:
            print("No object found in {}".format(image_name))
            continue
        labels = bboxes[:, 0].astype('int32')
        scores = bboxes[:, 1].astype('float32')
        boxes = bboxes[:, 2:].astype('float32')

        path = os.path.join(cfg.image_path, image_name)
        box_utils.draw_boxes_on_image(path, boxes, scores, labels, label_names, cfg.draw_thresh)


if __name__ == '__main__':
    args = parse_args()
    print_arguments(args)
    infer()
