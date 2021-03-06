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
"""Radial Basis Function network."""
import operator

import numpy

from learning import calculate, optimize, Model, SOM, MeanSquaredError
from learning.optimize import Problem

INITIAL_WEIGHTS_RANGE = 0.25


# TODO: Add support for penalty functions
class RBF(Model):
    """Radial Basis Function network.

    Args:
        attributes: int; Number of attributes in dataset.
        num_clusters: Number of clusters in intermediate layer.
        num_outputs: int; Number of output values in dataset.
            If onehot vector, this should equal the number of classes.
        optimizer: Instance of learning.optimize.optimizer.Optimizer.
        error_func: Instance of learning.error.ErrorFunc.
        jacobian_norm_break: Training will end if objective gradient norm
            is less than this value.
        variance: float; Variance of Gaussian similarity.
        scale_by_similarity: bool; Whether or not to normalize similarity.
        clustering_model: Model; Model used to cluster input space.
        cluster_incrementally: bool; If False, clustering_model will
          apply clustering once before training main RBF model.
          If True, clustering_model will train one step before
          every main RBF step.
    """
    # TODO: Remove attributes,
    # clustering_model can take int as shorthand for attributes with default
    def __init__(self,
                 attributes,
                 num_clusters,
                 num_outputs,
                 optimizer=None,
                 error_func=None,
                 jacobian_norm_break=1e-10,
                 variance=None,
                 scale_by_similarity=True,
                 clustering_model=None,
                 cluster_incrementally=False):
        super(RBF, self).__init__()

        # Clustering algorithm
        self._cluster_incrementally = cluster_incrementally
        if clustering_model is None:
            # TODO: Replace with k-means
            clustering_model = SOM(
                attributes,
                num_clusters,
                move_rate=0.1,
                neighborhood=2,
                neighbor_move_rate=1.0)
            clustering_model.logging = False
        self._clustering_model = clustering_model

        # Variance for gaussian
        if variance is None:
            variance = 4.0 / num_clusters
        self._variance = variance

        # Weight matrix and bias for output
        self._shape = (num_clusters, num_outputs)
        self._weight_matrix = self._random_weight_matrix(self._shape)
        self._bias_vec = self._random_weight_matrix(self._shape[1])

        # Optimizer to optimize weight_matrix
        if optimizer is None:
            optimizer = optimize.make_optimizer(
                reduce(operator.mul, self._weight_matrix.shape))

        self._optimizer = optimizer

        # Error function for training
        if error_func is None:
            error_func = MeanSquaredError()
        self._error_func = error_func

        # Convergence criteria
        self._jacobian_norm_break = jacobian_norm_break

        # Optional scaling output by total gaussian similarity
        self._scale_by_similarity = scale_by_similarity

        # For training
        self._similarity_tensor = None

    def reset(self):
        """Reset this model."""
        super(RBF, self).reset()

        self._clustering_model.reset()
        self._optimizer.reset()

        self._weight_matrix = self._random_weight_matrix(
            self._weight_matrix.shape)
        self._bias_vec = self._random_weight_matrix(self._shape[1])

        self._similarity_tensor = None

    def _random_weight_matrix(self, shape):
        """Return a random weight matrix."""
        # TODO: Random weight matrix should be a function user can pass in
        return (2 * numpy.random.random(shape) - 1) * INITIAL_WEIGHTS_RANGE

    def activate(self, input_tensor):
        """Return the model outputs for given input_tensor."""
        # Get distance to each cluster center, and apply gaussian for similarity
        self._similarity_tensor = calculate.gaussian(
            self._clustering_model.activate(input_tensor), self._variance)

        if self._scale_by_similarity:
            self._similarity_tensor /= numpy.sum(
                self._similarity_tensor, axis=-1, keepdims=True)

            # Replace 0. / 0. (nan) with uniform vector
            self._similarity_tensor[numpy.isnan(self._similarity_tensor)] = (
                1.0 / self._similarity_tensor.shape[-1])

        # Get output by weighted summation of similarities, weighted by weights
        output = numpy.dot(self._similarity_tensor,
                           self._weight_matrix) + self._bias_vec

        return output

    def train_step(self, input_matrix, target_matrix):
        """Adjust the model towards the targets for given inputs.

        Train on a mini-batch.

        Optional.
        Model must either override train_step or implement _train_increment.
        """
        if self._cluster_incrementally:
            # Update clusters
            self._clustering_model.train_step(input_matrix, target_matrix)

        # Train RBF
        error, flat_weights = self._optimizer.next(
            Problem(
                obj_func=
                lambda xk: self._get_obj(xk, input_matrix, target_matrix),
                obj_jac_func=
                lambda xk: self._get_obj_jac(xk, input_matrix, target_matrix)),
            _flatten_weights(self._weight_matrix, self._bias_vec))
        self._bias_vec, self._weight_matrix = _unflatten_weights(
            flat_weights, self._shape)

        self.converged = self._optimizer.jacobian is not None and numpy.linalg.norm(
            self._optimizer.jacobian) < self._jacobian_norm_break
        return error

    def _pre_train(self, input_matrix, target_matrix):
        """Call before Model.train.

        Optional.
        """
        if not self._cluster_incrementally:
            # Cluster input space
            self._clustering_model.train(input_matrix, target_matrix)

    def _post_train(self, input_matrix, target_matrix):
        """Call after Model.train.

        Optional.
        """
        # Reset optimizer, because problem may change on next train call
        self._optimizer.reset()

    ######################################
    # Helper functions for optimizer
    ######################################
    def _get_obj(self, parameter_vec, input_matrix, target_matrix):
        """Helper function for Optimizer to get objective value."""
        self._bias_vec, self._weight_matrix = _unflatten_weights(parameter_vec, self._shape)
        return self._error_func(self.activate(input_matrix), target_matrix)

    def _get_obj_jac(self, parameter_vec, input_matrix, target_matrix):
        """Helper function for Optimizer to get objective value and derivative."""
        self._bias_vec, self._weight_matrix = _unflatten_weights(parameter_vec, self._shape)
        error, weight_jacobian, bias_jacobian = self._get_jacobian(
            input_matrix, target_matrix)
        return error, _flatten_weights(weight_jacobian, bias_jacobian)

    ######################################
    # Objective Derivative
    ######################################
    def _get_jacobian(self, input_matrix, target_matrix):
        """Return jacobian and error for given dataset."""
        output_matrix = self.activate(input_matrix)

        error, error_jac = self._error_func.derivative(output_matrix,
                                                       target_matrix)

        weight_jacobian = self._similarity_tensor.T.dot(error_jac)
        bias_jacobian = numpy.sum(error_jac, axis=0)

        return error, weight_jacobian, bias_jacobian


def _flatten_weights(weight_matrix, bias_vec):
    """Return flat vector of model parameters."""
    return numpy.hstack([bias_vec, weight_matrix.ravel()])


def _unflatten_weights(flat_weights, shape):
    """Set model parameters from flat vector."""
    return flat_weights[:shape[1]], flat_weights[shape[1]:].reshape(shape)
