#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
from pathlib import Path

import numpy as np

FMT = ">16.7e"
VALUES_PER_LINE = 5
LINE_LENGTH = 85
SCRIPT = Path(__file__).name


def write_1d_data_to_namelist_format(
    arr_1d, decl_line, values_per_line=VALUES_PER_LINE, line_length=LINE_LENGTH, fmt=FMT
):
    """Write 1D data with a given precision to a list of strings in a Fortran namelist format."""
    nvals = len(arr_1d)
    lines = []
    values = []

    lines.append(decl_line)
    for idx, value in enumerate(arr_1d):
        # Loop each value of
        values.append(f"{value:{fmt}}")
        # Condition A:
        # if there are already `values_per_line` values appended to the current line
        cond_a = (idx + 1) % values_per_line == 0
        # Condition B:
        # It's the last element
        cond_b = idx == nvals - 1
        if cond_a or cond_b:
            # If either condition is satisfied, convert the list of values into a string
            line = ",".join(values)
            if len(line) > line_length:
                raise ValueError(
                    f"Line is too long ({len(line)=}>{line_length=}). "
                    "Reduce precision or the number of values per line."
                )
            line = f" {line + ',':<{line_length-1}}"
            lines.append(line)
            values = []
    return lines


def parse_args(args=None):
    """Argument parser."""
    ap = argparse.ArgumentParser(
        SCRIPT,
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=f"""Usage:
./{SCRIPT} -o vertlevs_L42_85km -t uniform -n 42 -r 1 -z 85000
./{SCRIPT} -o vertlevs_L58_99km -t malbec -c T1A -r 1
""",
    )

    ap.add_argument("-o", "--outfile", type=str, help="Output file", required=True)
    ap.add_argument(
        "-t",
        "--type",
        type=str,
        help="Type of vertical levels",
        choices=["uniform", "malbec"],
        required=True,
    )
    ap.add_argument("-c", "--case", type=str, help="MALBEC case", required=True)
    ap.add_argument(
        "-n",
        "--nlevs",
        type=int,
        help="Number of levels",
    )
    ap.add_argument(
        "-r",
        "--first_const_r_rho_lev",
        type=int,
        help="First constant R rho level",
    )
    ap.add_argument(
        "-z",
        "--z_top_of_model",
        type=float,
        help="Model lid height in metres",
    )

    return ap.parse_args(args)


def main(args=None):
    """Standalone script entry."""
    # Parse command-line arguments
    args = parse_args(args)

    vert_lev_file_out = Path(args.outfile)
    lev_type = args.type
    first_constant_r_rho_level = args.first_const_r_rho_lev
    if lev_type == "uniform":
        nlevs = args.nlevs
        z_top = args.z_top_of_model
        theta_lev = np.linspace(0, 1, nlevs)
        rho_lev = 0.5 * (theta_lev[:-1] + theta_lev[1:])
    elif lev_type == "malbec":
        import mypaths
        from malbec_util import read_malbec_profiles

        df = read_malbec_profiles(
            mypaths.data_dir / args.case / f"{args.case}_malbec.txt"
        )
        theta_lev_km = df.index.values
        z_top = theta_lev_km[-1] * 1e3
        theta_lev = theta_lev_km / theta_lev_km[-1]
        rho_lev = 0.5 * (theta_lev[:-1] + theta_lev[1:])

    # Output
    try:
        import f90nml

        nml = f90nml.Namelist(
            {
                "VERTLEVS": {
                    "z_top_of_model": z_top,
                    "first_constant_r_rho_level": first_constant_r_rho_level,
                    "eta_theta": list(theta_lev),
                    "eta_rho": list(rho_lev),
                }
            }
        )
        nml.write(vert_lev_file_out, force=True, sort=True)
    except ImportError:
        vert_lev_content = []
        vert_lev_content.append("&VERTLEVS")
        vert_lev_content.append(f" z_top_of_model             = {z_top:{FMT}},")
        vert_lev_content.append(
            f" first_constant_r_rho_level = {first_constant_r_rho_level},"
        )
        vert_lev_content += write_1d_data_to_namelist_format(theta_lev, " eta_theta = ")
        vert_lev_content += write_1d_data_to_namelist_format(rho_lev, " eta_rho = ")
        vert_lev_content.append("/")
        vert_lev_content = "\n".join(vert_lev_content)
        with vert_lev_file_out.open("w") as fout:
            fout.write(vert_lev_content)


if __name__ == "__main__":
    main()
