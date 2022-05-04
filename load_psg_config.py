# -*- coding: utf-8 -*-
"""
This file contains a function to load a PSG configuration file into a Python
dictionary, and a function demonstrating a possible use case.

If this file is executed as a script, it will ingest the T1A.txt example
configuration file and produce a file output_config.txt, which contains the
same information in a different format.
By default, this requires T1A.txt in the same directory as this file.

load_config(): loads PSG config file into Python dict
"""
import re
from collections import OrderedDict


def load_config(conf):
    """
    Loads a PSG configuration file into a dictionary

    Inputs
    ------
    conf: string.  Path to PSG config file.

    Outputs
    -------
    ret: dictionary.  Contains the keys and corresponding values from
                      the input PSG configuration file.
    """
    with open(conf, "r") as foo:
        conf_str = foo.read()
    psg_regex = r"<(.+?)>(.*)"
    matches = re.finditer(psg_regex, conf_str, re.MULTILINE)

    ret = OrderedDict()
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


def example(config="T1A.txt", fout="output_config.txt"):
    """
    Example use case of the load_config function.

    Inputs
    ------
    config: string.  Path to the configuration file.
    fout: string.  Path to the output file.

    Outputs
    -------
    Saves a file named `fout` containing the information from `config`
    but in a different format.
    """
    # Load the PSG config into a dictionary
    dictionary = load_config(config)
    # Write out the info to a text file
    with open(fout, "w") as foo:
        # NOTE: If you don't need all of the keys in the PSG config,
        #       supply a list of strings of the desired keys,
        #       and replace dictionary.keys() with your list
        for key in dictionary.keys():
            foo.write(key + " = " + str(dictionary[key]) + "\n")


if __name__ == "__main__":
    example()
