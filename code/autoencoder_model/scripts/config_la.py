from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from keras.optimizers import SGD
from keras.optimizers import Adam
from keras.optimizers import adadelta
from keras.optimizers import rmsprop
import os

# -------------------------------------------------
# Background config:
# DATA_DIR= '/home/pratik/DeepIntent_Datasets/KITTI_Dataset/'
DATA_DIR= '/local_home/JAAD_Dataset/resized_imgs_128/train/'
# DATA_DIR= '/local_home/data/KITTI_data/'

MODEL_DIR = './../models'
if not os.path.exists(MODEL_DIR):
    os.mkdir(MODEL_DIR)

CHECKPOINT_DIR = './../checkpoints'
if not os.path.exists(CHECKPOINT_DIR):
    os.mkdir(CHECKPOINT_DIR)

GEN_IMAGES_DIR = './../generated_images'
if not os.path.exists(GEN_IMAGES_DIR):
    os.mkdir(GEN_IMAGES_DIR)

LOG_DIR = './../logs'
if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)

TF_LOG_DIR = "./../tf_logs"
if not os.path.exists(TF_LOG_DIR):
    os.mkdir(TF_LOG_DIR)

PRINT_MODEL_SUMMARY = True
SAVE_MODEL = False
SAVE_GENERATED_IMAGES = True
SHUFFLE = True
VIDEO_LENGTH = 10
IMG_SIZE = (128, 128, 3)

# -------------------------------------------------
# Network configuration:
print ("Loading network/training configuration...")

BATCH_SIZE = 32
NB_EPOCHS = 100

# OPTIM = Adam(lr=0.000001, beta_1=0.5)
OPTIM = SGD(lr=0.00001, momentum=0.5, nesterov=True)
# OPTIM = rmsprop(lr=0.00001)

lr_schedule = [10, 20, 30]  # epoch_step

def schedule(epoch_idx):
    if (epoch_idx + 1) < lr_schedule[0]:
        return 0.0001
    elif (epoch_idx + 1) < lr_schedule[1]:
        return 0.00001  # lr_decay_ratio = 10
    elif (epoch_idx + 1) < lr_schedule[2]:
        return 0.00001
    return 0.00001

