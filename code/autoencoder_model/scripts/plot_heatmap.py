from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import numpy.random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cv2
import ast
from config_aa import *

data = np.load(os.path.join(TEST_RESULTS_DIR, 'attention_weights_2.npy'))
data = data[4]
# print (data.shape)
# exit(0)
# Generate some test data
for i in range(10):
    frame = data[i]
    frame_1 = data[i]
    print (frame.shape)
    x = frame[0]
    x = np.reshape(x, (64,))
    y = frame[1]
    y = np.reshape(y, (64,))
    frame = np.reshape(frame, (64, 64))

    # cv2.imwrite('image.png', frame_1)
    #
    # heatmap, xedges, yedges = np.histogram2d(x, y, bins=(128, 128))
    # extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
    #
    # # plt.clf()
    # plt.imshow(heatmap.T, origin='low')
    # plt.show()

    plt.clf()
    plt.imshow(frame, cmap='hot', interpolation='nearest')
    plt.cbar_axes[1].colorbar()
    plt.savefig(os.path.join(TEST_RESULTS_DIR, 'plot_' + str(i) + '.png'))