import sys

print("python", sys.version)
print("prefix", sys.prefix)

import torch

print("=== PyTorch ===")
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("device_count", torch.cuda.device_count())
print("cuda_version", torch.version.cuda)
if torch.cuda.is_available():
    print("device_name", torch.cuda.get_device_name(0))
    print("capability", torch.cuda.get_device_capability(0))
    x = torch.ones(1024, 1024, device="cuda")
    y = x @ x
    print("matmul_ok", float(y.sum()))
else:
    print("device_name", None)

import tensorflow as tf

print("=== TensorFlow ===")
print("tf", tf.__version__)
print("built_with_cuda", tf.test.is_built_with_cuda())
print("gpus", tf.config.list_physical_devices("GPU"))
if tf.config.list_physical_devices("GPU"):
    with tf.device("/GPU:0"):
        a = tf.ones((1024, 1024))
        b = tf.matmul(a, a)
        print("tf_matmul_ok", float(tf.reduce_sum(b)))
        print("tf_tensor_device", b.device)
