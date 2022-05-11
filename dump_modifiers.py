# -*- coding: utf-8 -*-
"""Utilities to modify UM dumps (fields files)."""
from warnings import warn

from mule.operators import AddScalarOperator, ScaleFactorOperator

__all__ = ("zero_operator", "set_fields_to_real")

zero_operator = ScaleFactorOperator(0.0)


def set_fields_to_real(ff, cube, lbuser4):
    """
    Set fields to a float-type number taken from an iris cube.

    Can be used to setting a 3D variable to a horizontally uniform value
    from a 1D profile of the same length as the number of 2D fields, in which
    the 3D variable is split in a Fields File.

    Parameters
    ----------
    ff: mule.DumpFile
        Fields file loaded by mule.
    cube: iris.cube.Cube
        One-dimensional cube.
    lbuser4: int
        STASH item code of the relevant variable.
    """
    ilev = 0
    for ifield, field in enumerate(ff.fields):
        if field.lbuser4 == lbuser4:
            try:
                value = float(cube.data[ilev])
                value_operator = AddScalarOperator(value)
                ff.fields[ifield] = value_operator(zero_operator(field))
            except IndexError:
                warn(f"Skipping level {ilev:>3d}")
            ilev += 1
