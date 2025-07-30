from functools import cached_property

import xarray as xr

from r2r_ctd.breakout import BBox, DTRange
from r2r_ctd.checks import (
    check_dt,
    check_lat_lon,
    check_lat_lon_valid,
    check_three_files,
    check_time_valid,
)
from r2r_ctd.derived import (
    get_latitude,
    get_longitude,
    get_time,
    make_cnvs,
    make_con_report,
)
from r2r_ctd.state import get_or_write_check, get_or_write_derived_file


@xr.register_dataset_accessor("r2r")
class R2RAccessor:
    def __init__(self, xarray_obj: xr.Dataset):
        self._obj = xarray_obj

    @cached_property
    def latitude(self):
        return get_latitude(self._obj)

    @cached_property
    def longitude(self):
        return get_longitude(self._obj)

    @cached_property
    def lat_lon_valid(self):
        return get_or_write_check(self._obj, "lat_lon_valid", check_lat_lon_valid)

    @cached_property
    def time(self):
        return get_time(self._obj)

    @cached_property
    def time_valid(self):
        return get_or_write_check(self._obj, "date_valid", check_time_valid)

    @cached_property
    def all_three_files(self):
        return get_or_write_check(self._obj, "three_files", check_three_files)

    def time_in(self, dt_range: DTRange) -> bool:
        return get_or_write_check(self._obj, "date_range", check_dt, dtrange=dt_range)

    def lon_lat_in(self, bbox: BBox) -> bool:
        return get_or_write_check(self._obj, "lat_lon_range", check_lat_lon, bbox=bbox)

    @cached_property
    def con_report(self) -> str | None:
        con_report = get_or_write_derived_file(self._obj, "con_report", make_con_report)
        if con_report:
            return con_report.item()

        return None

    @cached_property
    def cnv_24hz(self) -> str | None:
        if self.con_report is None:
            return None

        cnv_24hz = get_or_write_derived_file(self._obj, "cnv_24hz", make_cnvs)
        if cnv_24hz:
            return cnv_24hz.item()

        return None

    @cached_property
    def cnv_1db(self) -> str | None:
        if self.con_report is None:
            return None

        cnv_1db = get_or_write_derived_file(self._obj, "cnv_1db", make_cnvs)
        if cnv_1db:
            return cnv_1db.item()

        return None

    @cached_property
    def bottles_fired(self) -> bool:
        """This cast as bottle trip records

        A trip record has 5 components:

        * sequence (int)
        * carrousel position (int)
        * timestamp (time string)
        * scan start (int)
        * scan end (int)

        this works by checking each line to see if any of the 4 "int" components parse as ints
        and returning true if any of them can.

        The bl file records every attempt to close a bottle and does not necessarily reflect how many bottles actually closed
        """
        COMPONENTS = 5
        if "bl" in self._obj:
            for line in self._obj.bl.item().splitlines():
                parts = line.split(",")
                if len(parts) != COMPONENTS:
                    continue

                try:
                    int(parts[0].strip())
                    int(parts[1].strip())
                    int(parts[-2].strip())
                    int(parts[-1].strip())
                    return True
                except ValueError:
                    continue

        return False
