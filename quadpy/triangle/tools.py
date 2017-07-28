# -*- coding: utf-8 -*-
#
import numpy

from .centroid import Centroid
from .dunavant import Dunavant

from .. import helpers


def show(
        scheme,
        triangle=numpy.array([
            [-0.5, 0.0],
            [+0.5, 0.0],
            [0, 0.5 * (numpy.sqrt(3))],
            ]),
        show_axes=False
        ):
    '''Shows the quadrature points on a given triangle. The size of the circles
    around the points coincides with their weights.
    '''
    from matplotlib import pyplot as plt

    plt.plot(triangle[:, 0], triangle[:, 1], '-k')
    plt.plot(
        [triangle[-1, 0], triangle[0, 0]],
        [triangle[-1, 1], triangle[0, 1]],
        '-k'
        )

    if not show_axes:
        plt.gca().set_axis_off()

    transformed_pts = \
        + numpy.outer(
            (1.0 - scheme.points[:, 0] - scheme.points[:, 1]),
            triangle[0]
            ) \
        + numpy.outer(scheme.points[:, 0], triangle[1]) \
        + numpy.outer(scheme.points[:, 1], triangle[2])

    vol = integrate(lambda x: numpy.ones(1), triangle, Centroid())
    helpers.plot_disks(
        plt, transformed_pts, scheme.weights, vol
        )

    plt.axis('equal')
    plt.show()
    return


def _area(triangle):
    edges = triangle[[1, 2, 0]] - triangle
    ei_dot_ej = numpy.einsum(
            '...k, ...k->...',
            edges[[1, 2, 0]],
            edges[[2, 0, 1]]
            )
    return 0.5 * numpy.sqrt(
        + ei_dot_ej[2] * ei_dot_ej[0]
        + ei_dot_ej[0] * ei_dot_ej[1]
        + ei_dot_ej[1] * ei_dot_ej[2]
        )


def integrate(f, triangle, scheme, sumfun=helpers.kahan_sum):
    xi = scheme.points.T
    x = \
        + numpy.multiply.outer(1.0 - xi[0] - xi[1], triangle[0]) \
        + numpy.multiply.outer(xi[0], triangle[1]) \
        + numpy.multiply.outer(xi[1], triangle[2])
    x = x.T
    return sumfun(
        numpy.moveaxis(scheme.weights * f(x), -1, 0) * _area(triangle)
        )


def _numpy_all_except(a, axis=-1):
    axes = numpy.arange(a.ndim)
    axes = numpy.delete(axes, axis)
    return numpy.all(a, axis=tuple(axes))


# pylint: disable=too-many-arguments
# pylint: disable=too-many-locals
def adaptive_integrate(
        f, triangles, eps,
        minimum_triangle_area=None,
        scheme1=Dunavant(5),
        scheme2=Dunavant(10),
        sumfun=helpers.kahan_sum
        ):
    triangles = numpy.array(triangles)
    if len(triangles.shape) == 2:
        # add dimension in the second-to-last place
        triangles = numpy.expand_dims(triangles, -2)

    areas = _area(triangles)
    total_area = sumfun(areas)

    if minimum_triangle_area is None:
        minimum_triangle_area = total_area * 0.25**10

    val1 = integrate(f, triangles, scheme1, sumfun=sumfun)
    val2 = integrate(f, triangles, scheme2, sumfun=sumfun)
    error_estimate = abs(val1 - val2)

    # Mark intervals with acceptable approximations. For this, take all()
    # across every dimension except the last one, which is the interval index.
    is_good = _numpy_all_except(
            error_estimate < eps * areas / total_area,
            axis=-1
            )

    # add values from good intervals to sum
    quad_sum = sumfun(val1[..., is_good], axis=-1)
    global_error_estimate = sumfun(error_estimate[..., is_good], axis=-1)

    is_bad = numpy.logical_not(is_good)
    while any(is_bad):
        # split the bad triangles into four #triforce
        #
        #         /\
        #        /__\
        #       /\  /\
        #      /__\/__\
        #
        triangles = triangles[..., is_bad, :]
        midpoints = [
            0.5 * (triangles[1] + triangles[2]),
            0.5 * (triangles[2] + triangles[0]),
            0.5 * (triangles[0] + triangles[1]),
            ]
        triangles = numpy.array([
            numpy.concatenate([
                triangles[0], triangles[1], triangles[2], midpoints[0]
                ]),
            numpy.concatenate([
                midpoints[1], midpoints[2], midpoints[0], midpoints[1]
                ]),
            numpy.concatenate([
                midpoints[2], midpoints[0], midpoints[1], midpoints[2]
                ]),
            ])
        areas = _area(triangles)
        assert all(areas > minimum_triangle_area)

        # compute values and error estimates for the new intervals
        val1 = integrate(f, triangles, scheme1, sumfun=sumfun)
        val2 = integrate(f, triangles, scheme2, sumfun=sumfun)
        error_estimate = abs(val1 - val2)

        # mark good intervals, gather values and error estimates
        is_good = _numpy_all_except(
                error_estimate < eps * areas / total_area,
                axis=-1
                )
        # add values from good intervals to sum
        quad_sum += sumfun(val1[..., is_good], axis=-1)
        global_error_estimate += sumfun(error_estimate[..., is_good], axis=-1)
        is_bad = numpy.logical_not(is_good)

    return quad_sum, global_error_estimate
