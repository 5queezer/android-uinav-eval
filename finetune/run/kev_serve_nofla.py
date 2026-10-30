"""kev.serve with flash-linear-attention hidden (its Triton kernels need a GPU): the torch path, for CPU-only serving."""
import runpy
import sys

sys.modules["fla"] = None
runpy.run_module("kev.serve", run_name="__main__")
