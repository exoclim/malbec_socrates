# -*- coding: utf-8 -*-
"""Utilities to work with PSG data."""
import re
from io import StringIO
from pathlib import Path

import f90nml
import iris
import iris.pandas
import iris.util
import mule
import pandas as pd
from aeolus.const import init_const
from aeolus.meta import update_metadata

from dump_modifiers import set_fields_to_real

__all__ = (
    "PSGContainer",
    "psg_series_to_cube",
    "read_psg_lyr_atm_prof",
    "read_psg_cfg",
)

PSG_REGEX = r"<(.+?)>(.*)"

SCRIPT_DIR = Path(__file__).parent


def psg_series_to_cube(psg_df, column_name, cube_name, si_units, z_name):
    """Convert PSG data to an iris cube with appropriate units."""

    if match := re.search(r"\[(.*?)\]", column_name):
        units = match.group(1)
    else:
        units = "1"

    cube = iris.pandas.as_cube(psg_df[column_name])
    cube.rename(cube_name)
    cube.units = units
    cube.convert_units(si_units)
    cube.coord("index").rename(z_name)
    cube.coord(z_name).units = "km"
    cube.coord(z_name).convert_units("m")
    return cube


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
        index_col="Alt[km]",
    )
    # If the data contains cloud MMR columns, rename them accordingly
    # psg_lyr_df = psg_lyr_df.rename(
    #     {"Cloud": "liquid_water [kg kg-1]", "size[m]": "ice [kg kg-1]"}, axis=1
    # )
    return psg_lyr_df


class PSGContainer(object):
    """Container for PSG data."""

    z_name = "level_height"

    def __init__(self, sim_case, const_dir, psg_data_dir):
        """
        Initialise the container for PSG data, as part of the MALBEC project.

        Parameters
        ----------
        sim_case: str
            MALBEC case.
        """
        self.sim_case = sim_case
        self.const = init_const(self.sim_case, directory=const_dir)
        self.kappa = (
            self.const.dry_air_gas_constant / self.const.dry_air_spec_heat_press
        )
        self.psg_data_dir = psg_data_dir
        self._height = None
        self._temperature = None
        self._pressure = None
        self._humidity_mixing_ratio = None
        self._cloud_liquid_water_mixing_ratio = None
        self._cloud_ice_mixing_ratio = None
        self._exner = None
        self._potential_temperature = None

        self._load_lyr()

    def _load_lyr(self):
        """Load PSG data from the `lyr` file."""
        self.lyr_data = read_psg_lyr_atm_prof(
            self.psg_data_dir / self.sim_case / "PSG" / "psg_lyr.txt"
        )

    @property
    def height(self):
        if self._height is None:
            self._height = psg_series_to_cube(
                self.lyr_data.reset_index(),
                "Alt[km]",
                self.z_name,
                "m",
                z_name=self.z_name,
            )
        return self._height

    @property
    def temperature(self):
        if self._temperature is None:
            self._temperature = psg_series_to_cube(
                self.lyr_data, "Temp[K]", "air_temperature", "K", z_name=self.z_name
            )
        return self._temperature

    @property
    def pressure(self):
        if self._pressure is None:
            self._pressure = psg_series_to_cube(
                self.lyr_data, "Pressure[bar]", "air_pressure", "Pa", z_name=self.z_name
            )
        return self._pressure

    @property
    def humidity_mixing_ratio(self):
        if self._humidity_mixing_ratio is None:
            self._humidity_mixing_ratio = psg_series_to_cube(
                self.lyr_data,
                "H2O",
                "humidity_mixing_ratio",
                "kg kg-1",
                z_name=self.z_name,
            )
        return self._humidity_mixing_ratio

    # @property
    # def cloud_liquid_water_mixing_ratio(self):
    #     if self._cloud_liquid_water_mixing_ratio is None:
    #         self._cloud_liquid_water_mixing_ratio = psg_series_to_cube(
    #             self.lyr_data,
    #             "liquid_water [kg kg-1]",
    #             "cloud_liquid_water_mixing_ratio",
    #             "kg kg-1",
    #             z_name=self.z_name,
    #         )
    #     return self._cloud_liquid_water_mixing_ratio

    # @property
    # def cloud_ice_mixing_ratio(self):
    #     if self._cloud_ice_mixing_ratio is None:
    #         self._cloud_ice_mixing_ratio = psg_series_to_cube(
    #             self.lyr_data,
    #             "ice [kg kg-1]",
    #             "cloud_ice_mixing_ratio",
    #             "kg kg-1",
    #             z_name=self.z_name,
    #         )
    #     return self._cloud_ice_mixing_ratio

    @property
    @update_metadata(name="dimensionless_exner_function", units="1")
    def exner(self):
        if self._exner is None:
            self._exner = (
                self.pressure / self.const.reference_surface_pressure
            ) ** float(self.kappa.data)
        return self._exner

    @property
    @update_metadata(name="air_potential_temperature", units="K")
    def potential_temperature(self):
        if self._potential_temperature is None:
            self._potential_temperature = self.temperature / self.exner
        return self._potential_temperature

    def save_p_t_profile(self, outdir=None):
        """Save the P-T profile in netCDF format for the idealised reconfiguration in the UM."""
        if (_outdir := outdir) is None:
            _outdir = self.psg_data_dir / self.sim_case
        cubelist_out = []
        for attr, new_name in zip(
            ["temperature", "pressure"], ["temperature", "pressure_si"]
        ):
            cube_out = iris.util.reverse(getattr(self, attr), self.z_name)
            cube_out.rename(new_name)
            cube_out.coord(self.z_name).rename("altitude")
            cubelist_out.append(cube_out)
        iris.save(
            cubelist_out,
            _outdir / f"{self.sim_case}_p_t_profile.nc",
        )

    def mk_vert_lev_file(self, first_constant_r_rho_level=1, outdir=None):
        """Make a file with vertical levels for the UM."""
        if (_outdir := outdir) is None:
            _outdir = self.psg_data_dir / self.sim_case
        theta_lev_m = self.height.data
        z_top = theta_lev_m[-1]
        theta_lev = theta_lev_m / z_top
        rho_lev = 0.5 * (theta_lev[:-1] + theta_lev[1:])
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
        nml.write(_outdir / f"vertlevs_{self.sim_case}", force=True, sort=True)

    def replace_profile_in_dump(
        self, path_to_dump, stash_item, psg_variable, inplace=True
    ):
        """Set a field in the dump to a horizontally uniform value."""
        ff_dump = mule.DumpFile.from_file(str(path_to_dump))
        set_fields_to_real(ff_dump, getattr(self, psg_variable), stash_item)
        new_name = f"{path_to_dump.name}_mod_{stash_item:>03d}_{psg_variable}"
        new_name_full = path_to_dump.with_name(new_name)
        ff_dump.to_file(str(new_name_full))
        if inplace:
            new_name_full.replace(path_to_dump)
        else:
            return new_name_full
