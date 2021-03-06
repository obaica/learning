###############################################################################
# The MIT License (MIT)
#
# Copyright (c) 2017 Justin Lovinger
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
###############################################################################

import pytest
import copy
import random

import numpy

from learning import base, datasets

from learning.testing import helpers


def test_post_pattern_callback():
    dataset = datasets.get_xor()
    model = helpers.EmptyModel()

    inp_history = []
    tar_history = []

    def callback(model, input_vec, target_vec):
        inp_history.append(input_vec)
        tar_history.append(target_vec)

    model.train(*dataset, iterations=1, post_pattern_callback=callback)
    inp_history = numpy.array(inp_history)
    tar_history = numpy.array(tar_history)
    assert (dataset[0] == inp_history).all()
    assert (dataset[1] == tar_history).all()


################################
# Datapoint selection functions
################################
@pytest.fixture()
def seed_random(request):
    random.seed(0)

    def fin():
        import time
        random.seed(time.time())

    request.addfinalizer(fin)


def test_select_sample_size_none_few_samples(seed_random):
    # When number of samples is low, default to all samples

    input_matrix, target_matrix = datasets.get_xor()

    new_inp_matrix, new_tar_matrix = base.select_sample(
        input_matrix, target_matrix)
    assert new_inp_matrix.shape == input_matrix.shape
    assert new_tar_matrix.shape == target_matrix.shape

    for inp_vec in input_matrix:  # all in
        assert inp_vec in new_inp_matrix
    for tar_vec in target_matrix:  # all in
        assert tar_vec in new_tar_matrix

    assert not (new_inp_matrix == input_matrix).all()  # Different order
    assert not (new_tar_matrix == target_matrix).all()  # Different order


def test_select_sample_size_none(seed_random):
    # Default to size smaller than number of samples

    input_matrix, target_matrix = datasets.get_random_classification(
        1000, 1, 2)

    new_inp_matrix, new_tar_matrix = base.select_sample(
        input_matrix, target_matrix)

    assert len(new_inp_matrix) < len(input_matrix)
    assert len(new_inp_matrix) == base._selection_size_heuristic(
        len(input_matrix))

    assert len(new_tar_matrix) < len(input_matrix)
    assert len(new_tar_matrix) == base._selection_size_heuristic(
        len(input_matrix))


def test_select_sample(seed_random):
    input_matrix, target_matrix = datasets.get_xor()

    # Test size param
    new_inp_matrix, new_tar_matrix = base.select_sample(
        input_matrix, target_matrix, size=2)
    assert new_inp_matrix.shape[0] == 2
    assert new_tar_matrix.shape[0] == 2

    # No duplicates
    count = 0
    for inp_vec in new_inp_matrix:
        if inp_vec in input_matrix:
            count += 1
    assert count == 2

    count = 0
    for tar_vec in new_tar_matrix:
        if tar_vec in target_matrix:
            count += 1
    assert count == 2


def test_select_random_size_none_few_samples(monkeypatch):
    # When number of samples is low, default to all samples

    # Monkeypatch so we know that random returns
    # randint always returns 0
    monkeypatch.setattr(random, 'randint', lambda x, y: 0)

    input_matrix, target_matrix = datasets.get_xor()
    new_inp_matrix, new_tar_matrix = base.select_random(
        input_matrix, target_matrix)
    assert new_inp_matrix.shape == input_matrix.shape
    assert new_tar_matrix.shape == target_matrix.shape

    for inp_vec in new_inp_matrix:
        assert (inp_vec == input_matrix[0]).all()  # Due to monkeypatch
    for tar_vec in new_tar_matrix:
        assert (tar_vec == target_matrix[0]).all()  # Due to monkeypatch


def test_select_random_size_none(seed_random):
    # Default to size smaller than number of samples

    input_matrix, target_matrix = datasets.get_random_classification(
        1000, 1, 2)

    new_inp_matrix, new_tar_matrix = base.select_random(
        input_matrix, target_matrix)

    assert len(new_inp_matrix) < len(input_matrix)
    assert len(new_inp_matrix) == base._selection_size_heuristic(
        len(input_matrix))

    assert len(new_tar_matrix) < len(input_matrix)
    assert len(new_tar_matrix) == base._selection_size_heuristic(
        len(input_matrix))


def test_select_random(monkeypatch):
    # Monkeypatch so we know that random returns
    # randint always returns 0
    monkeypatch.setattr(random, 'randint', lambda x, y: 0)

    input_matrix, target_matrix = datasets.get_xor()

    # Test size param
    new_inp_matrix, new_tar_matrix = base.select_random(
        input_matrix, target_matrix, size=2)

    assert new_inp_matrix.shape[0] == 2
    assert new_tar_matrix.shape[0] == 2

    for inp_vec in new_inp_matrix:
        assert (inp_vec == input_matrix[0]).all()  # Due to monkeypatch
    for tar_vec in new_tar_matrix:
        assert (tar_vec == target_matrix[0]).all()  # Due to monkeypatch


#############################
# Model.stochastic_train
#############################
def test_Model_stochastic_train():
    """Train with stochastic gradient descent."""
    from learning import transfer, error, validation, MLP

    dataset = datasets.get_iris()

    model = MLP(
        (len(dataset[0][0]), 3, len(dataset[1][0])),
        transfers=transfer.SoftmaxTransfer(),
        error_func=error.CrossEntropyError())

    # Model should be able to converge with mini-batches
    model.stochastic_train(
        *dataset,
        error_break=0.02,
        pattern_selection_func=lambda X, Y: base.select_sample(X, Y, size=30),
        train_kwargs={'iterations': 5, 'error_break': 0.1})

    assert validation.get_error(model, *dataset) <= 0.03


####################
# Model.train
####################
def test_break_on_stagnation_completely_stagnant():
    # If error doesn't change by enough after enough iterations
    # stop training

    nn = helpers.SetOutputModel(1.0)

    # Stop training if error does not change by more than threshold after
    # distance iterations
    nn.train(
        [[0.0]], [[0.0]],
        error_stagnant_distance=5,
        error_stagnant_threshold=0.01)
    assert nn.iteration == 6  # The 6th is 5 away from the first


def test_break_on_stagnation_dont_break_if_wrapped_around():
    # Should not break on situations like: 1.0, 0.9, 0.8, 0.7, 1.0
    # Since error did change, even if it happens to be the same after
    # n iterations
    nn = helpers.ManySetOutputsModel([[1.0], [0.9], [0.8], [0.7], [1.0], [1.0],
                                      [1.0], [1.0], [1.0]])

    # Should pass wrap around to [1.0], and stop after consecutive [1.0]s
    nn.train(
        [[0.0]], [[0.0]],
        error_stagnant_distance=4,
        error_stagnant_threshold=0.01)
    assert nn.iteration == 9


def test_break_on_no_improvement_completely_stagnant():
    nn = helpers.SetOutputModel(1.0)

    # Stop training if error does not improve after 5 iterations
    nn.train(
        [[0.0]], [[0.0]],
        error_stagnant_distance=10,
        error_stagnant_threshold=None,
        error_improve_iters=5)
    assert nn.iteration == 6  # The 6th is 5 away from the first


def test_break_on_no_improvement():
    nn = helpers.ManySetOutputsModel([[1.0], [0.99], [0.98], [0.97], [0.97],
                                      [0.97], [0.97], [0.97], [0.97]])

    # Stop training if error does not improve after 5 iterations
    nn.train(
        [[0.0]], [[0.0]],
        error_stagnant_distance=10,
        error_stagnant_threshold=None,
        error_improve_iters=5)
    assert nn.iteration == 9


@pytest.mark.skip(reason='Hard to test, but not hard to implement')
def test_model_train_retry():
    # Model should reset and retry if it doesn't converge
    # Train should not calculate avg_mse if it is out of retries
    assert 0


def test_Model_custom_converged():
    class ConvergeModel(helpers.SetOutputModel):
        def train_step(self, *args, **kwargs):
            self.converged = True

    dataset = datasets.get_xor()
    
    model = ConvergeModel([1, 0])
    model.train(*dataset)

    assert model.converged
    assert model.iteration == 1


######################
# Serialization
######################
def test_serialize():
    model = helpers.SetOutputModel(1.0)
    assert isinstance(model.serialize(),
                      str), 'Model.serialize should return string'


def test_unserialize():
    model = helpers.SetOutputModel(random.uniform(0, 1))
    model_copy = helpers.SetOutputModel.unserialize(model.serialize())

    assert model_copy.__dict__ == model.__dict__, 'Should have same content'
    assert model_copy is not model, 'Should have different id'


def test_unserialize_wrong_type():
    """Model.unserialize should raise error if serialized model is of wrong type."""
    with pytest.raises(ValueError):
        base.Model.unserialize(helpers.SetOutputModel(1.0).serialize())
