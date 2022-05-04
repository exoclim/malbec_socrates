# -*- coding: utf-8 -*-
"""Utilities to work with PSG data."""
import re
from io import StringIO

import pandas as pd

__all__ = ("read_psg_lyr_atm_prof", "read_psg_cfg")

PSG_REGEX = r"<(.+?)>(.*)"


def read_psg_cfg(filepath):
    """
    Read NASA-GSFC PSG configuration file.

    Parameters
    ----------
    filepath: Path-like
        Path to the PSG cfg file.

    Returns
    -------
    psg_cfg_dict: dict
        Dictionary with the parsed data.
    """
    with filepath.open("r") as opened_file:
        raw_text = opened_file.read()
    matches = re.finditer(PSG_REGEX, raw_text, re.MULTILINE)

    ret = {}
    for match in matches:
        key = match.group(1)
        value = match.group(2)
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                value = value
        ret[key] = value
    return ret


def read_psg_lyr_atm_prof(filepath):
    """
    Read NASA-GSFC PSG layer-by-layer atmospheric profile.

    Parameters
    ----------
    filepath: Path-like
        Path to the PSG lyr file.

    Returns
    -------
    psg_lyr_df: pandas.DataFrame
        Pandas dataframe containing the layer-by-layer data.
    """
    with filepath.open("r") as opened_file:
        raw_text = opened_file.read()
    # Find the data boundaries
    data_idx_start = None
    data_idx_end = None
    for count, line in enumerate(raw_text.split("\n")):
        if "Alt[km]" in line:
            data_idx_start = count + 3
        if "Curtis-Godson" in line:
            data_idx_end = count - 2
    try:
        data_len = data_idx_end - data_idx_start + 1
    except TypeError:
        raise Exception("Cannot identify data lines.")
    # Reorganise comment characters in the raw text
    mod_text = StringIO(
        re.sub(r"^-{1,}", "#", re.sub(r"^# ", "", raw_text, flags=re.M), flags=re.M)
    )
    # Load the modified text as a pandas DataFrame
    psg_lyr_df = pd.read_csv(
        mod_text,
        skiprows=data_idx_start - 3,
        nrows=data_len,
        sep=r"\s+",
        comment="#",
    )
    return psg_lyr_df
