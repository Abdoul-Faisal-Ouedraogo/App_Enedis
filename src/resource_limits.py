"""Deux threads au maximum pour les calculs natifs et les forêts."""
import os


def configure():
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"]:
        os.environ[name] = "2"
