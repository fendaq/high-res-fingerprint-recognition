import tensorflow as tf


class Net:
  def __init__(self,
               inputs,
               output_shape=128,
               reuse=False,
               training=True,
               scope='description'):
    with tf.variable_scope(scope):
      # conv 1
      net = tf.layers.conv2d(
          inputs,
          filters=64,
          kernel_size=3,
          strides=1,
          padding='valid',
          activation=tf.nn.relu,
          use_bias=False,
          name='conv_1',
          reuse=reuse)
      net = tf.layers.batch_normalization(
          net, training=training, name='batchnorm_1', reuse=reuse)

      # max pooling 1
      net = tf.layers.max_pooling2d(
          net, pool_size=3, strides=1, name='maxpool_1')

      # conv 2
      net = tf.layers.conv2d(
          net,
          filters=128,
          kernel_size=3,
          strides=1,
          padding='valid',
          activation=tf.nn.relu,
          use_bias=False,
          name='conv_2',
          reuse=reuse)
      net = tf.layers.batch_normalization(
          net, training=training, name='batchnorm_2', reuse=reuse)

      # max pooling 2
      net = tf.layers.max_pooling2d(
          net, pool_size=3, strides=1, padding='valid', name='maxpool_2')

      # conv 3
      net = tf.layers.conv2d(
          net,
          filters=128,
          kernel_size=3,
          strides=1,
          padding='valid',
          activation=tf.nn.relu,
          use_bias=False,
          name='conv_3',
          reuse=reuse)
      net = tf.layers.batch_normalization(
          net, training=training, name='batchnorm_3', reuse=reuse)

      # max pooling 3
      net = tf.layers.max_pooling2d(
          net, pool_size=3, strides=1, padding='valid', name='maxpool_3')

      # conv 4
      net = tf.layers.conv2d(
          net,
          filters=128,
          kernel_size=3,
          strides=1,
          padding='valid',
          activation=None,
          use_bias=False,
          name='conv_4',
          reuse=reuse)
      net = tf.layers.batch_normalization(
          net, training=training, name='batchnorm_4', reuse=reuse)

      # max pooling 4
      net = tf.layers.max_pooling2d(
          net, pool_size=3, strides=1, name='maxpool_4')

      # descriptors
      self.spatial_descriptors = tf.nn.l2_normalize(
          net, axis=-1, name='spatial_descriptors')
      self.descriptors = tf.reshape(
          self.spatial_descriptors, [-1, 128], name='descriptors')

  def build_loss(self, labels):
    # make labels' shape compatible with triplet loss
    labels = tf.reshape(labels, (-1, ))

    self.loss = tf.contrib.losses.metric_learning.triplet_semihard_loss(
        labels, self.descriptors)

    return self.loss

  def build_train(self, learning_rate):
    global_step = tf.Variable(1, name='global_step', trainable=False)
    optimizer = tf.train.GradientDescentOptimizer(learning_rate)
    update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
    with tf.control_dependencies(update_ops):
      self.train = optimizer.minimize(self.loss, global_step=global_step)

    return self.train

  def build_validation(self, labels, thresholds):
    # flatten labels
    labels = tf.reshape(labels, (-1, ))

    # recognition labels matrix with (i, j) = label[i] == label[j]
    labels_matrix = tf.tile(
        tf.expand_dims(labels, -1),
        tf.shape(tf.expand_dims(labels, 0)),
        name='labels_matrix')
    rec_labels = tf.equal(
        labels_matrix, tf.transpose(labels_matrix), name='recognition_labels')
    rec_labels = tf.cast(rec_labels, tf.int32)

    # distances matrix
    r_desc = tf.reduce_sum(self.descriptors * self.descriptors, axis=1)
    distances = tf.expand_dims(r_desc, -1) - 2 * tf.matmul(
        self.descriptors, self.descriptors, transpose_b=True) + r_desc

    # mask for extraction of strict upper triangular band of matrices
    ones = tf.ones_like(distances)
    mask = tf.cast(ones - tf.matrix_band_part(ones, -1, 0), dtype=tf.bool)

    # make thresholds and distances shapes broadcast compatible
    thresholds = tf.reshape(thresholds, (-1, 1, 1))
    distances = tf.expand_dims(distances, 0)

    # recognition predictions over thresholds
    rec_preds = tf.less(distances, thresholds, name='recognition_predictions')
    rec_preds = tf.cast(rec_preds, tf.int32)

    # statistics over thresholds
    # false positives
    false_pos_mat = tf.cast(tf.greater(rec_preds, rec_labels), tf.int32)
    false_pos = tf.reduce_sum(
        tf.boolean_mask(false_pos_mat, mask, axis=1), axis=1)

    # false negatives
    false_neg_mat = tf.cast(tf.less(rec_preds, rec_labels), tf.int32)
    false_neg = tf.reduce_sum(
        tf.boolean_mask(false_neg_mat, mask, axis=1), axis=1)

    # true positives
    pos_mat = tf.cast(tf.greater_equal(rec_preds, 1), tf.int32)
    pos = tf.reduce_sum(tf.boolean_mask(pos_mat, mask, axis=1), axis=1)
    true_pos = pos - false_pos

    # true negatives
    neg_mat = tf.cast(tf.less_equal(rec_preds, 0), tf.int32)
    neg = tf.reduce_sum(tf.boolean_mask(neg_mat, mask, axis=1), axis=1)
    true_neg = neg - false_neg

    self.validation = [true_pos, true_neg, false_pos, false_neg]

    return self.validation
