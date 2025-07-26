from functools import cached_property

import xarray as xr

from r2r_ctd.checks import check_lat_lon_valid, check_three_files
from r2r_ctd.derived import get_latitude, get_longitude, get_time
from r2r_ctd.state import get_or_write_check


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
    def time(self):
        return get_time(self._obj)

    @cached_property
    def all_three_files(self):
        return get_or_write_check(self._obj, "three_files", check_three_files)

    @cached_property
    def lat_lon_valid(self):
        return (get_or_write_check(self._obj, "lat_lon_valid", check_lat_lon_valid),)
