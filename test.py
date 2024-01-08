import numpy as np
from scipy.integrate import quad


def samples_in_interval(n, start_point, end_point):
    """Calculate the number of samples within a defined range

    Args:
        n (int): number of samples per second
        start_point (int): start time of sampling in seconds
        end_point (int): end time of sampling in seconds

    Returns:
        int: the number of samples between start_point and end_point
    """
    return int(n * (end_point - start_point))


def integral_sin_wave(a, b, T):
    """
    Calculate the true integral of a sine wave with period T from a to b.

    Parameters:
    a (float): Lower limit of the integral
    b (float): Upper limit of the integral
    T (float): Period of the sine wave

    Returns:
    float: The integral of the sine wave from a to b
    """
    # Sine wave function
    sine_wave = lambda x: np.sin(2 * np.pi * x / T)

    # Calculate the integral
    result, _ = quad(sine_wave, a, b)

    return result


def riemann_sum_sin(n, T, start_point, end_point):
    """Calculate the left reimann sum of a sin wave

    Args:
        n (int): sample rate
        T (int): period of sin wave
        start_point (int): time of beginning of calculation
        end_point (int): time of end of calculation

    Returns:
        int: Riemann sum value
    """
    # Calculate the number of samples in one quarter period
    n_samples = samples_in_interval(n, start_point, end_point)
    # Calculate the time between samples
    sample_spacing = (end_point - start_point) / n_samples
    assert sample_spacing == 1 / n  # Sanity check

    sum_value = 0
    # Calculate the Riemann sum for the quarter period
    for i in range(0, n_samples):  # Beginning at 0 for every sample
        x_i = sample_spacing * i  # Our current x value
        sum_value += (
            np.sin(2 * np.pi * x_i / T) * sample_spacing
        )  # Add our current y value * the time length of the sample

    return sum_value


def sps(msps):
    """Converts msps (mega samples per second) to samples per second

    Args:
        msps (int): msps

    Returns:
        int: samples per second
    """
    return int(msps * 1000000)


def percent_error(actual_value, estimated_value):
    """
    Calculate the percent error between an actual value and an estimated value.

    Parameters:
    actual_value (float): The actual, true or theoretical value
    estimated_value (float): The estimated or measured value

    Returns:
    float: Percent error
    """
    error = abs(actual_value - estimated_value)
    percent_error = (
        (error / abs(actual_value)) * 100 if actual_value != 0 else float("inf")
    )
    return percent_error


assert samples_in_interval(90, 0, 1) == 90  # 90 sps over 1 s
assert samples_in_interval(90, 0, 0.5) == 45  # 90 sps over 0.5 s is 45
assert samples_in_interval(1000, 0, 0.01) == 10  # 1000 sps over 0.01 s is 10


n = sps(1)  # Sample rate in MSPS
T = 0.001  # Period of the sine wave in seconds
start = 0  # start of calculation (x)
end = 0.00025  # end of calculation

rei = riemann_sum_sin(n, T, 0, 0.1)
intg = integral_sin_wave(start, end, T)

print("Riemann sum: " + str(rei))
print("True integral: " + str(intg))
# print("Error: " + str(percent_error(intg, rei)))
