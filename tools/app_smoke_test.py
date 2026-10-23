# MobileStudio in-app python smoke test (runs inside the app-simulated env)
import sys, os
print("python:", sys.version.split()[0], "| prefix:", sys.prefix)

import numpy as np
print("numpy", np.__version__, "| dot:", int(np.arange(9).reshape(3, 3).sum()))

import cv2
print("cv2", cv2.__version__, "| cvtColor:", cv2.cvtColor(
    np.zeros((4, 4, 3), "uint8"), cv2.COLOR_BGR2GRAY).shape)

import scipy.linalg
print("scipy", __import__("scipy").__version__, "| inv:",
      np.round(scipy.linalg.inv(np.array([[4.0, 7.0], [2.0, 6.0]])), 2).tolist())

import pandas as pd
print("pandas", pd.__version__, "| sum:", int(pd.DataFrame({"y": [1, 2, 3]}).y.sum()))

import sklearn
from sklearn.linear_model import LinearRegression
m = LinearRegression().fit([[1], [2], [3]], [2, 4, 6])
print("sklearn", sklearn.__version__, "| fit:", m.predict([[4]])[0])

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.plot([1, 2, 3]); print("matplotlib", matplotlib.__version__, "plot-ok")

import onnx
from onnx import helper
g = helper.make_graph([], "t", [], [])
print("onnx", onnx.__version__, "| graph:", helper.make_model(g).ir_version >= 0)

import onnxruntime as ort
print("onnxruntime", ort.__version__, "| providers:", ort.get_available_providers())

import tflite_runtime.interpreter as tfl
print("tflite_runtime ok (", tfl.Interpreter.__module__, ")")

import tokenizers
print("tokenizers", tokenizers.__version__)

import safetensors
print("safetensors", safetensors.__version__)

import numba
from numba import njit

@njit
def _f(x):
    s = 0
    for i in range(x):
        s += i
    return s

print("numba", numba.__version__, "| jit(10) =", _f(10))

import pydantic
from pydantic import BaseModel

class M(BaseModel):
    x: int

print("pydantic", pydantic.VERSION, "| M(x='5').x =", M(x="5").x)

print("ALL-SMOKE-OK")
