import pytest

import numpy

from pynn import network
from pynn.architecture import rbf
from pynn.architecture import transfer

def test_gaussian_output():
    # Given known inputs, test expected outputs
    layer = rbf.GaussianOutput(2, 1)
    layer._weights[0][0] = 0.5
    layer._weights[1][0] = -0.5
    assert layer.activate(numpy.array([1, 1])) == 0.0

    layer._weights[0][0] = 1.0
    layer._weights[1][0] = 2.0
    assert layer.activate(numpy.array([1, 1])) == 3.0