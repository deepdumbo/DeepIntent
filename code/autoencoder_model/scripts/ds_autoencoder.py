from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import hickle as hkl
import numpy as np

np.random.seed(2 ** 10)
from keras import backend as K
K.set_image_dim_ordering('tf')
from keras.layers import Dropout
from keras.models import Sequential
from keras.layers.core import Activation
from keras.utils.vis_utils import plot_model
from keras.layers.wrappers import TimeDistributed
from keras.layers.convolutional import Conv2D
from keras.layers.convolutional import Conv2DTranspose
from keras.layers.convolutional import Conv3D
from keras.layers.convolutional import Conv3DTranspose
from keras.layers.convolutional_recurrent import ConvLSTM2D
from keras.layers.normalization import BatchNormalization
from keras.layers.core import Reshape
from keras.callbacks import LearningRateScheduler
from keras.layers.advanced_activations import LeakyReLU
from config_ds import *

import tb_callback
import lrs_callback
import argparse
import math
import os
import cv2
from sys import stdout


def encoder_model():
    model = Sequential()

    # 10x64x64
    model.add(Conv3D(filters=256,
                     strides=(1, 2, 2),
                     kernel_size=(3, 11, 11),
                     padding='same',
                     input_shape=(int(VIDEO_LENGTH/2), 64, 64, 1)))
    model.add(TimeDistributed(BatchNormalization()))
    model.add(TimeDistributed(LeakyReLU(alpha=0.2)))
    model.add(TimeDistributed(Dropout(0.5)))

    # 10x32x32
    # model.add(Conv3D(filters=128,
    #                  strides=(1, 2, 2),
    #                  kernel_size=(3, 5, 5),
    #                  padding='same'))
    # model.add(TimeDistributed(BatchNormalization()))
    # model.add(TimeDistributed(LeakyReLU(alpha=0.2)))
    # model.add(TimeDistributed(Dropout(0.5)))

    # 10x32x32
    model.add(Conv3D(filters=128,
                     strides=(1, 2, 2),
                     kernel_size=(3, 5, 5),
                     padding='same'))
    model.add(TimeDistributed(BatchNormalization()))
    model.add(TimeDistributed(LeakyReLU(alpha=0.2)))
    model.add(TimeDistributed(Dropout(0.5)))

    return model


def decoder_model():
    model = Sequential()

    # 10x32x32
    model.add(Conv3DTranspose(filters=64,
                              kernel_size=(3, 5, 5),
                              padding='same',
                              strides=(1, 1, 1),
                              input_shape=(10, 16, 16, 128)))
    model.add(TimeDistributed(BatchNormalization()))
    # model.add(TimeDistributed(Activation('relu')))
    model.add(TimeDistributed(LeakyReLU(alpha=0.2)))
    model.add(TimeDistributed(Dropout(0.5)))

    # 10x64x64
    model.add(Conv3DTranspose(filters=128,
                              kernel_size=(3, 5, 5),
                              padding='same',
                              strides=(1, 2, 2)))
    model.add(TimeDistributed(BatchNormalization()))
    # model.add(TimeDistributed(Activation('relu')))
    model.add(TimeDistributed(LeakyReLU(alpha=0.2)))
    model.add(TimeDistributed(Dropout(0.5)))

    # 10x64x64
    model.add(Conv3DTranspose(filters=64,
                              kernel_size=(3, 5, 5),
                              padding='same',
                              strides=(1, 2, 2)))
    model.add(TimeDistributed(BatchNormalization()))
    # model.add(TimeDistributed(Activation('relu')))
    model.add(TimeDistributed(LeakyReLU(alpha=0.2)))
    model.add(TimeDistributed(Dropout(0.5)))

    # 10x128x128
    model.add(Conv3DTranspose(filters=1,
                              kernel_size=(3, 5, 5),
                              strides=(1, 1, 1),
                              padding='same'))
    model.add(TimeDistributed(BatchNormalization()))
    model.add(TimeDistributed(Activation('tanh')))
    model.add(TimeDistributed(Dropout(0.5)))

    return model


def set_trainability(model, trainable):
    model.trainable = trainable
    for layer in model.layers:
        layer.trainable = trainable


def autoencoder_model(encoder, decoder):
    model = Sequential()
    model.add(encoder)
    model.add(decoder)
    return model


def combine_images(X, y, generated_images):
    # Unroll all generated video frames
    n_frames = generated_images.shape[0] * generated_images.shape[1]
    frames = np.zeros((n_frames,) + generated_images.shape[2:], dtype=generated_images.dtype)

    frame_index = 0
    for i in range(generated_images.shape[0]):
        for j in range(generated_images.shape[1]):
            frames[frame_index] = generated_images[i, j]
            frame_index += 1

    num = frames.shape[0]
    width = int(math.sqrt(num))
    height = int(math.ceil(float(num) / width))
    shape = frames.shape[1:]
    image = np.zeros((height * shape[0], width * shape[1], shape[2]), dtype=generated_images.dtype)
    for index, img in enumerate(frames):
        i = int(index / width)
        j = index % width
        image[i * shape[0]:(i + 1) * shape[0], j * shape[1]:(j + 1) * shape[1], :] = img

    n_frames = X.shape[0] * X.shape[1]
    orig_frames = np.zeros((n_frames,) + X.shape[2:], dtype=X.dtype)

    # Original frames
    frame_index = 0
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            orig_frames[frame_index] = X[i, j]
            frame_index += 1

    num = orig_frames.shape[0]
    width = int(math.sqrt(num))
    height = int(math.ceil(float(num) / width))
    shape = orig_frames.shape[1:]
    orig_image = np.zeros((height * shape[0], width * shape[1], shape[2]), dtype=X.dtype)
    for index, img in enumerate(orig_frames):
        i = int(index / width)
        j = index % width
        orig_image[i * shape[0]:(i + 1) * shape[0], j * shape[1]:(j + 1) * shape[1], :] = img

    # Ground truth
    truth_frames = np.zeros((n_frames,) + y.shape[2:], dtype=y.dtype)
    frame_index = 0
    for i in range(y.shape[0]):
        for j in range(y.shape[1]):
            truth_frames[frame_index] = y[i, j]
            frame_index += 1

    num = truth_frames.shape[0]
    width = int(math.sqrt(num))
    height = int(math.ceil(float(num) / width))
    shape = truth_frames.shape[1:]
    truth_image = np.zeros((height * shape[0], width * shape[1], shape[2]), dtype=y.dtype)
    for index, img in enumerate(truth_frames):
        i = int(index / width)
        j = index % width
        truth_image[i * shape[0]:(i + 1) * shape[0], j * shape[1]:(j + 1) * shape[1], :] = img

    return orig_image, truth_image, image


def load_weights(weights_file, model):
    model.load_weights(weights_file)


def run_utilities(encoder, decoder, autoencoder, ENC_WEIGHTS, DEC_WEIGHTS):
    if PRINT_MODEL_SUMMARY:
        print (encoder.summary())
        print (decoder.summary())
        print (autoencoder.summary())
        # exit(0)

    # Save model to file
    if SAVE_MODEL:
        print ("Saving models to file...")
        model_json = encoder.to_json()
        with open(os.path.join(MODEL_DIR, "encoder.json"), "w") as json_file:
            json_file.write(model_json)

        model_json = decoder.to_json()
        with open(os.path.join(MODEL_DIR, "decoder.json"), "w") as json_file:
            json_file.write(model_json)

        model_json = autoencoder.to_json()
        with open(os.path.join(MODEL_DIR, "autoencoder.json"), "w") as json_file:
            json_file.write(model_json)

        if PLOT_MODEL:
            plot_model(encoder, to_file=os.path.join(MODEL_DIR, 'encoder.png'), show_shapes=True)
            plot_model(decoder, to_file=os.path.join(MODEL_DIR, 'decoder.png'), show_shapes=True)
            plot_model(autoencoder, to_file=os.path.join(MODEL_DIR, 'autoencoder.png'), show_shapes=True)

    if ENC_WEIGHTS != "None":
        print ("Pre-loading encoder with weights...")
        load_weights(ENC_WEIGHTS, encoder)
    if DEC_WEIGHTS != "None":
        print ("Pre-loading decoder with weights...")
        load_weights(DEC_WEIGHTS, decoder)


def load_X(videos_list, index, data_dir):
    X = np.zeros((BATCH_SIZE, VIDEO_LENGTH,) + IMG_SIZE)
    for i in range(BATCH_SIZE):
        for j in range(VIDEO_LENGTH):
            filename = "frame_" + str(videos_list[(index*BATCH_SIZE + i), j]) + ".png"
            im_file = os.path.join(data_dir, filename)
            try:
                frame = cv2.imread(im_file, cv2.IMREAD_COLOR)
                X[i, j] = (frame.astype(np.float32) - 127.5) / 127.5
            except AttributeError as e:
                print (im_file)
                print (e)

    return X


def train(BATCH_SIZE, ENC_WEIGHTS, DEC_WEIGHTS):
    print ("Loading data...")
    mnist = np.load(os.path.join(DATA_DIR, 'mnist_test_seq.npy'))
    mnist = np.expand_dims(mnist, axis=4)

    # Build the Spatio-temporal Autoencoder
    print ("Creating models...")
    encoder = encoder_model()
    decoder = decoder_model()
    autoencoder = autoencoder_model(encoder, decoder)

    run_utilities(encoder, decoder, autoencoder, ENC_WEIGHTS, DEC_WEIGHTS)

    autoencoder.compile(loss='mean_squared_error', optimizer=OPTIM)

    NB_ITERATIONS = int(mnist.shape[1]/BATCH_SIZE)

    # Setup TensorBoard Callback
    TC = tb_callback.TensorBoard(log_dir=TF_LOG_DIR, histogram_freq=0, write_graph=False, write_images=False)
    # LRS = lrs_callback.LearningRateScheduler(schedule=schedule)
    # LRS.set_model(autoencoder)

    print ("Beginning Training...")
    # Begin Training
    for epoch in range(NB_EPOCHS):
        print("\n\nEpoch ", epoch)
        loss = []

        # Set learning rate every epoch
        # LRS.on_epoch_begin(epoch=epoch)
        lr = K.get_value(autoencoder.optimizer.lr)
        print ("Learning rate: " + str(lr))

        for index in range(NB_ITERATIONS):
            # Train Autoencoder
            X_train = np.zeros(shape=(10, 10, 64, 64, 1))
            y_train = np.zeros(shape=(10, 10, 64, 64, 1))
            for i in range(BATCH_SIZE):
                X_train[i] = mnist[0 : int(VIDEO_LENGTH/2), index+i]
                y_train[i] = mnist[int(VIDEO_LENGTH/2), index+i]

            X_train = (X_train.astype(np.float32) - 127.5) / 127.5
            y_train = (y_train.astype(np.float32) - 127.5) / 127.5

            loss.append(autoencoder.train_on_batch(X_train, y_train))

            arrow = int(index / (NB_ITERATIONS / 40))
            stdout.write("\rIteration: " + str(index) + "/" + str(NB_ITERATIONS-1) + "  " +
                         "loss: " + str(loss[len(loss)-1]) +
                         "\t    [" + "{0}>".format("="*(arrow)))
            stdout.flush()

        if SAVE_GENERATED_IMAGES:
            # Save generated images to file
            predicted_images = autoencoder.predict(X_train, verbose=0)
            orig_image, truth_image, pred_image = combine_images(X_train, y_train, predicted_images)
            pred_image = pred_image * 127.5 + 127.5
            orig_image = orig_image * 127.5 + 127.5
            truth_image = truth_image * 127.5 + 127.5
            if epoch == 0 :
                cv2.imwrite(os.path.join(GEN_IMAGES_DIR, str(epoch) + "_" + str(index) + "_orig.png"), orig_image)
                cv2.imwrite(os.path.join(GEN_IMAGES_DIR, str(epoch) + "_" + str(index) + "_truth.png"), truth_image)
            cv2.imwrite(os.path.join(GEN_IMAGES_DIR, str(epoch) + "_" + str(index) + ".png"), pred_image)

        # then after each epoch/iteration
        avg_loss = sum(loss)/len(loss)
        logs = {'loss': avg_loss}
        TC.on_epoch_end(epoch, logs)

        # Log the losses
        with open(os.path.join(LOG_DIR, 'losses.json'), 'a') as log_file:
            log_file.write("{\"epoch\":%d, \"d_loss\":%f};\n" % (epoch, avg_loss))

        print("\nAvg loss: " + str(avg_loss))

        # Save model weights per epoch to file
        encoder.save_weights(os.path.join(CHECKPOINT_DIR, 'encoder_epoch_'+str(epoch)+'.h5'), True)
        decoder.save_weights(os.path.join(CHECKPOINT_DIR, 'decoder_epoch_' + str(epoch) + '.h5'), True)

    # End TensorBoard Callback
    TC.on_train_end('_')


def test(ENC_WEIGHTS, DEC_WEIGHTS):

    # Create models
    print ("Creating models...")
    encoder = encoder_model()
    decoder = decoder_model()
    autoencoder = autoencoder_model(encoder, decoder)

    run_utilities(encoder, decoder, autoencoder, ENC_WEIGHTS, DEC_WEIGHTS)
    autoencoder.compile(loss='mean_squared_error', optimizer=OPTIM)

    # Build video progressions
    frames_source = hkl.load(os.path.join(TEST_DATA_DIR, 'sources_test_128.hkl'))
    videos_list = []
    start_frame_index = 1
    end_frame_index = VIDEO_LENGTH + 1
    while (end_frame_index <= len(frames_source)):
        frame_list = frames_source[start_frame_index:end_frame_index]
        if (len(set(frame_list)) == 1):
            videos_list.append(range(start_frame_index, end_frame_index))
            start_frame_index = start_frame_index + VIDEO_LENGTH
            end_frame_index = end_frame_index + VIDEO_LENGTH
        else:
            start_frame_index = end_frame_index - 1
            end_frame_index = start_frame_index + VIDEO_LENGTH

    videos_list = np.asarray(videos_list, dtype=np.int32)
    n_videos = videos_list.shape[0]

    # Test model by making predictions
    loss = []
    NB_ITERATIONS = int(n_videos / BATCH_SIZE)
    for index in range(NB_ITERATIONS):
        # Test Autoencoder
        X = load_X(videos_list, index, TEST_DATA_DIR)
        X_test = X[:, 0: int(VIDEO_LENGTH / 2)]
        y_test = X[:, int(VIDEO_LENGTH / 2):]
        loss.append(autoencoder.test_on_batch(X_test, y_test))
        y_pred = autoencoder.predict_on_batch(X_test)

        arrow = int(index / (NB_ITERATIONS / 40))
        stdout.write("\rIteration: " + str(index) + "/" + str(NB_ITERATIONS - 1) + "  " +
                     "loss: " + str(loss[len(loss) - 1]) +
                     "\t    [" + "{0}>".format("=" * (arrow)))
        stdout.flush()

        orig_image, truth_image, pred_image = combine_images(X_test, y_test, y_pred)
        pred_image = pred_image * 127.5 + 127.5
        orig_image = orig_image * 127.5 + 127.5
        truth_image = truth_image * 127.5 + 127.5

        cv2.imwrite(os.path.join(TEST_RESULTS_DIR, str(index) + "_orig.png"), orig_image)
        cv2.imwrite(os.path.join(TEST_RESULTS_DIR, str(index) + "_truth.png"), truth_image)
        cv2.imwrite(os.path.join(TEST_RESULTS_DIR, str(index) + "_pred.png"), pred_image)

    avg_loss = sum(loss) / len(loss)
    print("\nAvg loss: " + str(avg_loss))


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str)
    parser.add_argument("--enc_weights", type=str, default="None")
    parser.add_argument("--dec_weights", type=str, default="None")
    parser.add_argument("--batch_size", type=int, default=BATCH_SIZE)
    parser.add_argument("--nice", dest="nice", action="store_true")
    parser.set_defaults(nice=False)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = get_args()

    if args.mode == "train":
        train(BATCH_SIZE=args.batch_size,
              ENC_WEIGHTS=args.enc_weights,
              DEC_WEIGHTS=args.dec_weights)

    if args.mode == "test":
        test(ENC_WEIGHTS=args.enc_weights,
             DEC_WEIGHTS=args.dec_weights)