﻿import numpy
import random

##############################
# Pattern selection functions
##############################
def select_iterative(input_matrix, target_matrix):
    """Return all rows in order."""
    return input_matrix, target_matrix

def select_sample(input_matrix, target_matrix, size=None):
    """Return a random selection of rows, without replacement.

    Rows are returned in random order.
    Returns all rows in random order by default.
    """
    num_rows = input_matrix.shape[0]
    if size is None:
        size = num_rows

    selected_rows = random.sample(range(num_rows), size)
    return input_matrix[selected_rows], target_matrix[selected_rows]

def select_random(input_matrix, target_matrix, size=None):
    """Return a random selection of rows, with replacement.

    Rows are returned in random order.
    """
    num_rows = input_matrix.shape[0]
    if size is None:
        size = num_rows

    max_index = num_rows-1
    selected_rows = [random.randint(0, max_index) for _ in range(size)]
    return input_matrix[selected_rows], target_matrix[selected_rows]

class Model(object):
    """A supervised learning model."""
    def __init__(self):
        self._post_pattern_callback = None

        # Bookkeeping
        self.logging = True
        self.iteration = 0

    def _reset_bookkeeping(self):
        self.iteration = 0

    def reset(self):
        """Reset this model."""
        raise NotImplementedError()

    def activate(self, inputs):
        """Return the model outputs for given inputs."""
        raise NotImplementedError()

    def train(self, input_matrix, target_matrix,
              iterations=1000, retries=0, error_break=0.002,
              error_stagnant_distance=5, error_stagnant_threshold=0.00001,
              pattern_select_func=select_iterative, post_pattern_callback=None):
        """Train model to converge on a dataset.

        Note: Override this method for batch learning models.

        Args:
            input_matrix: A matrix with samples in rows and attributes in columns.
            target_matrix: A matrix with samples in rows and target values in columns.
            iterations: Max iterations to train model.
            retries: Number of times to reset model and retries if it does not converge.
                Convergence is defined as reaching error_break.
            error_break: Training will end once error is less than this.
            pattern_select_func: Function that takes (input_matrix, target_matrix),
                and returns a selection of rows. Use partial function to embed arguments.
        """
        # Make sure matrix parameters are np arrays
        if not isinstance(input_matrix, numpy.ndarray):
            input_matrix = numpy.array(input_matrix, dtype='float64')
        if not isinstance(target_matrix, numpy.ndarray):
            target_matrix = numpy.array(target_matrix, dtype='float64')

        self._reset_bookkeeping()
        self._post_pattern_callback = post_pattern_callback # For calling in other method

        # Initialize error history with errors that are
        # unlikey to be close in reality
        error_history = [1e10]*error_stagnant_distance

        # Learn on each pattern for each iteration
        for attempt in range(retries+1):
            for self.iteration in range(1, iterations+1):
                selected_patterns = pattern_select_func(input_matrix, target_matrix)

                # Learn each selected pattern
                self.pre_iteration(*selected_patterns)
                error = self.train_step(*selected_patterns)
                self.post_iteration(*selected_patterns)

                # Logging and breaking
                if self.logging:
                    print "Iteration {}, Error: {}".format(self.iteration, error)

                if error is not None:
                    # Break early to prevent overtraining
                    if error < error_break:
                        break

                    # Break if no progress is made
                    # TODO: Change to break if best error has not improved within n iterations
                    if _all_close(error_history, error, error_stagnant_threshold):
                        # Break if not enough difference between all resent errors
                        # and current error
                        break

                    error_history.append(error)
                    error_history.pop(0)

            # End when out of retries or model converged
            # TODO: Should we use use defined error function?
            # Check if we are out of retires, so we don't waste time calculating
            # avg_mse
            if attempt >= retries or (error is not None
                                      and self.avg_mse(input_matrix, target_matrix) <= error_break):
                break
            self.reset()


    def train_step(self, input_matrix, target_matrix):
        """Adjust the model towards the targets for given inputs.

        Train on a mini-batch.

        Optional.
        Model must either override train_step or implement _train_increment.
        """
        # Learn each selected pattern
        error = 0.0
        for input_vec, target_vec in zip(input_matrix, target_matrix):
            # Learn
            errors = self._train_increment(input_vec, target_vec)

            # Optional callback for user extension,
            # such as a visualization or history tracking
            if self._post_pattern_callback:
                self._post_pattern_callback(self, input_vec, target_vec)

            # Sum errors
            try:
                error += numpy.mean(errors**2)
            except TypeError:
                # train_step doesn't return error
                error = None

        # Logging and breaking
        try:
            return error / input_matrix.shape[0]
        except TypeError:
            # _train_increment doesn't return error
            return None

    def _train_increment(self, input_vec, target_vec):
        """Train on a single input, target pair.

        Optional.
        Model must either override train_step or implement _train_increment.
        """
        raise NotImplementedError()

    def pre_iteration(self, input_matrix, target_matrix):
        """Optional. Callback performed before each training iteration.

        Note: If self.train is overwritten, this may not be called.
        """
        pass

    def post_iteration(self, input_matrix, target_matrix):
        """Optional. Callback performed after each training iteration.

        Note: If self.train is overwritten, this may not be called.
        """
        pass

    def serialize(self):
        """Convert model into string.

        Returns:
            string; A string representing this network.
        """
        raise NotImplementedError()

    @classmethod
    def unserialize(cls, serialized_model):
        """Convert serialized model into Model.

        Returns:
            Model; A Model object.
        """
        raise NotImplementedError()

    ##################
    # Helper methods
    ##################
    def test(self, input_matrix, target_matrix):
        """Print corresponding inputs and outputs from a dataset."""
        for inp_vec, tar_vec in zip(input_matrix, target_matrix):
            print(tar_vec, '->', self.activate(inp_vec))

    def avg_mse(self, input_matrix, target_matrix):
        """Return the average mean squared error for a dataset."""
        error = 0.0
        for input_vec, target_vec in zip(input_matrix, target_matrix):
            error = error + self.mse(input_vec, target_vec)

        return error/len(input_matrix)

    def mse(self, input_vec, target_vec):
        """Return the mean squared error (MSE) for a pattern."""
        # Mean squared error
        return numpy.mean(numpy.subtract(self.activate(input_vec), target_vec)**2)


def _all_close(values, other_value, threshold):
    """Return true if all values are within threshold distance of other_value."""
    for value in values:
        if abs(value - other_value) > threshold:
            return False
    return True
