# -*- coding: utf-8 -*-
"""Utilities to work with MALBEC data."""
from pathlib import Path
from typing import Optional

import f90nml
import iris
import iris.cube.Cube
import iris.pandas
import iris.util
import mule
import pandas as pd
from aeolus.const import init_const
from aeolus.meta import update_metadata
from dump_modifiers import set_fields_to_real


__all__ = (
    "MalbecContainer",
    "malbec_series_to_cube",
    "read_malbec_profiles",
)


def malbec_series_to_cube(
    df: pd.DataFrame, column_name: str, cube_name: str, si_units: str, z_name: str
) -> iris.cube.Cube:
    """Convert MALBEC data to an iris cube with appropriate units."""
    units = {
        "P": "bar",
        "T": "K",
        "MMW": "g/mol",
    }
    cube = iris.pandas.as_cube(df[column_name])
    cube.rename(cube_name)
    cube.units = units.get(column_name, "mol/mol")
    cube.convert_units(si_units)
    cube.coord("index").rename(z_name)
    cube.coord(z_name).units = "km"
    cube.coord(z_name).convert_units("m")
    return cube


def read_malbec_profiles(filepath: str) -> pd.DataFrame:
    """
    Read atmospheric profiles from a MALBEC text file.

    Parameters
    ----------
    filepath: Path-like
        Path to the `*_malbec.txt` file.

    Returns
    -------
    malbec_df: pandas.DataFrame
        Pandas dataframe containing the data.
    """
    line_label = "# Atmosphere-columns: "
    with filepath.open("r") as opened_file:
        raw_text = opened_file.read()
        column_names = None
        for line in raw_text.split("\n"):
            if line.startswith(line_label):
                column_names = line.lstrip(line_label).split(" ")
            elif not line.startswith("#"):
                ncol = len([i for i in line.split(" ") if i])
        if column_names is None:
            column_names = [f"col{i:02d}" for i in range(ncol)]
    df = pd.read_csv(
        filepath,
        sep=r"\s+",
        comment="#",
        names=column_names,
        index_col=column_names[3],
    )
    return df


class MalbecContainer(object):
    """Container for MALBEC data."""

    z_name = "level_height"

    def __init__(self, sim_case: str, const_dir: Path, data_dir: Path) -> None:
        """
        Initialise the container for MALBEC atmospheric profiles.

        Parameters
        ----------
        sim_case: str
            MALBEC case.
        """
        self.sim_case = sim_case
        self.data_dir = data_dir

        # Set planetary and atmospheric constants
        self.const = init_const(self.sim_case, directory=const_dir)
        self.const.kappa = (
            self.const.dry_air_gas_constant / self.const.dry_air_spec_heat_press
        )

        # Define variables
        self._height = None
        self._temperature = None
        self._pressure = None
        self._humidity_mixing_ratio = None
        self._exner = None
        self._potential_temperature = None

        self._load_data()

    def _load_data(self):
        """Load data from the malbec.txt file."""
        self.malbec_data = read_malbec_profiles(
            self.data_dir / self.sim_case / f"{self.sim_case}_malbec.txt"
        )

    @property
    def height(self):
        if self._height is None:
            self._height = malbec_series_to_cube(
                self.malbec_data.reset_index(),
                "Alt",
                self.z_name,
                "m",
                z_name=self.z_name,
            )
        return self._height

    @property
    def temperature(self):
        if self._temperature is None:
            self._temperature = malbec_series_to_cube(
                self.malbec_data, "T", "air_temperature", "K", z_name=self.z_name
            )
        return self._temperature

    @property
    def pressure(self):
        if self._pressure is None:
            self._pressure = malbec_series_to_cube(
                self.malbec_data, "P", "air_pressure", "Pa", z_name=self.z_name
            )
        return self._pressure

    @property
    def humidity_mixing_ratio(self):
        if self._humidity_mixing_ratio is None:
            self._humidity_mixing_ratio = malbec_series_to_cube(
                self.malbec_data,
                "H2O",
                "humidity_mixing_ratio",
                "kg kg-1",
                z_name=self.z_name,
            )
        return self._humidity_mixing_ratio

    # Derived variables
    @property
    @update_metadata(name="dimensionless_exner_function", units="1")
    def exner(self):
        if self._exner is None:
            self._exner = (
                self.pressure / self.const.reference_surface_pressure
            ) ** float(self.const.kappa.data)
        return self._exner

    @property
    @update_metadata(name="air_potential_temperature", units="K")
    def potential_temperature(self):
        if self._potential_temperature is None:
            self._potential_temperature = self.temperature / self.exner
        return self._potential_temperature

    def save_p_t_profile(self, outdir: Optional[Path] = None) -> None:
        """Save the P-T profile in netCDF format for the idealised reconfiguration in the UM."""
        if (_outdir := outdir) is None:
            _outdir = self.data_dir / self.sim_case
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

    def mk_vert_lev_file(
        self,
        first_constant_r_rho_level: Optional[int] = 1,
        outdir: Optional[Path] = None,
    ) -> None:
        """Make a file with vertical levels for the UM."""
        if (_outdir := outdir) is None:
            _outdir = self.data_dir / self.sim_case
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
        self,
        path_to_dump: Path,
        stash_item: str,
        malbec_variable: str,
        inplace: Optional[bool] = True,
    ) -> Optional[Path]:
        """Set a field in the dump to a horizontally uniform value."""
        ff_dump = mule.DumpFile.from_file(str(path_to_dump))
        set_fields_to_real(ff_dump, getattr(self, malbec_variable), stash_item)
        new_name = f"{path_to_dump.name}_mod_{stash_item:>03d}_{malbec_variable}"
        new_name_full = path_to_dump.with_name(new_name)
        ff_dump.to_file(str(new_name_full))
        if inplace:
            new_name_full.replace(path_to_dump)
        else:
            return new_name_full
