"""Adds an .r2r accessor to the xarray.Dataset objects in use within this software.

Mostly these are wrappers around functions in :py:mod:`r2r_ctd.derived` for nice syntax.
Instead of writing::

    get_longitude(ds)

I could write::

    ds.r2r.longitude

While that example isn't very short, some of the more involved derived products benefit nicely from this e.g.::

    get_or_write_derived_file(ds, "con_report", make_con_report)

Makes the configuration report, with the accessor pattern, this becomes as simple as getting the longitude::

    d2.r2r.con_report

All that complexity is hidden from me.
Does it need to be that complex? Probably, since that function checks the cache, and if missed, runs a while routing within the companion container to get the results.
"""

from datetime import datetime
from functools import cached_property
from logging import getLogger
from typing import Literal

import xarray as xr

from r2r_ctd.breakout import BBox, Breakout, Interval
from r2r_ctd.checks import (
    check_dt,
    check_lon_lat,
    check_lon_lat_valid,
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
from r2r_ctd.state import (
    get_config_path,
    get_filename,
    get_or_write_check,
    get_or_write_derived_file,
    get_product_path,
)

logger = getLogger(__name__)


@xr.register_dataset_accessor("r2r")
class R2RAccessor:
    def __init__(self, xarray_obj: xr.Dataset):
        self._obj = xarray_obj

    @property
    def __geo_interface__(self):
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": (self.longitude, self.latitude),
            },
            "properties": {
                "name": self.name,
                "time": f"{self.time:%Y-%m-%d %H:%M:%S}" if self.time else "None",
                "all_three_files": f"<span style='color: {'green' if self.all_three_files else 'red'}'>{self.all_three_files}</span>",
                "lon_lat_valid": f"<span style='color: {'green' if self.lon_lat_valid else 'red'}'>{self.lon_lat_valid}</span>",
                "time_valid": f"<span style='color: {'green' if self.time_valid else 'red'}'>{self.time_valid}</span>",
                "bottles_fired": f"<span style='color: {'green' if self.bottles_fired else 'red'}'>{self.bottles_fired}</span>",
            },
        }

    def get_marker_color(self, bbox: BBox | None, interval: Interval | None):
        # warning, duplicated logic?
        if bbox is None or interval is None:
            return "black"
        if not self.lon_lat_valid or not self.time_valid:
            return "grey"
        if not self.all_three_files:
            return "red"
        if not self.lon_lat_in(bbox):
            return "red"
        if not self.time_in(interval):
            return "red"
        return "green"

    @property
    def name(self):
        return get_filename(self._obj.hex).removesuffix(".hex")

    @cached_property
    def latitude(self) -> float | None:
        """Simple wrapper around :py:func:`~r2r_ctd.derived.get_latitude`"""
        return get_latitude(self._obj)

    @cached_property
    def longitude(self) -> float | None:
        """Simple wrapper around :py:func:`~r2r_ctd.derived.get_longitude`"""
        return get_longitude(self._obj)

    @cached_property
    def lon_lat_valid(self) -> bool:
        """Caching wrapper around :py:func:`~r2r_ctd.checks.check_lon_lat_valid`"""
        return get_or_write_check(self._obj, "lon_lat_valid", check_lon_lat_valid)

    @cached_property
    def time(self) -> datetime | None:
        """Simple wrapper around :py:func:`~r2r_ctd.derived.get_time`"""
        return get_time(self._obj)

    @cached_property
    def time_valid(self) -> bool:
        """Caching wrapper around :py:func:`~r2r_ctd.checks.check_time_valid`"""
        return get_or_write_check(self._obj, "date_valid", check_time_valid)

    @cached_property
    def all_three_files(self) -> bool:
        """Caching wrapper around :py:func:`~r2r_ctd.checks.check_three_files`"""
        return get_or_write_check(self._obj, "three_files", check_three_files)

    def time_in(self, dt_range: Interval) -> bool:
        """Caching wrapper around :py:func:`~r2r_ctd.checks.check_dt`"""
        return get_or_write_check(self._obj, "date_range", check_dt, dtrange=dt_range)

    def lon_lat_in(self, bbox: BBox) -> bool:
        """Caching wrapper around :py:func:`~r2r_ctd.checks.check_lon_lat`"""
        return get_or_write_check(self._obj, "lon_lat_range", check_lon_lat, bbox=bbox)

    @cached_property
    def con_report(self) -> str | None:
        """Caching wrapper around :py:func:`~r2r_ctd.derived.make_con_report`"""
        con_report = get_or_write_derived_file(self._obj, "con_report", make_con_report)
        if con_report:
            return con_report.item()

        return None

    @cached_property
    def cnv_24hz(self) -> str | None:
        """Caching wrapper around :py:func:`~r2r_ctd.derived.make_cnvs`

        Will generate the :py:meth:`cnv_1db` as a side effect if not already done.
        """
        if self.con_report is None:
            return None

        if self.all_three_files is False:
            return None

        cnv_24hz = get_or_write_derived_file(self._obj, "cnv_24hz", make_cnvs)
        if cnv_24hz:
            return cnv_24hz.item()

        return None

    @cached_property
    def cnv_1db(self) -> str | None:
        """Caching wrapper around :py:func:`~r2r_ctd.derived.make_cnvs`

        Will generate the :py:meth:`cnv_24hz` as a side effect if not already done.
        """
        if self.con_report is None:
            return None

        if self.all_three_files is False:
            return None

        cnv_1db = get_or_write_derived_file(self._obj, "cnv_1db", make_cnvs)
        if cnv_1db:
            return cnv_1db.item()

        return None

    @cached_property
    def bottles_fired(self) -> bool:
        """This cast has bottle trip records in its bl file.

        A trip record has 5 components:

        * sequence (int)
        * carrousel position (int)
        * timestamp (time string)
        * scan start (int)
        * scan end (int)

        This works by checking each line to see if any of the 4 "int" components parse as ints
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

    def write_con_report(self, breakout: "Breakout") -> None:
        """Actually write the configuration report files to disk."""
        if self.con_report is None:
            return None

        fname = get_filename(self._obj.con_report)
        con_path = get_config_path(breakout) / fname
        con_path.write_text(self.con_report)
        logger.info(f"Conreport written to {con_path}")

    def write_cnv(
        self, breakout: "Breakout", cnv: Literal["cnv_24hz", "cnv_1db"]
    ) -> None:
        """Actually write the derived cnv files to disk."""
        cnv_contents = getattr(self, cnv)
        if cnv_contents is None:
            return None

        da = getattr(self._obj, cnv)
        fname = get_filename(da)
        write_path = get_product_path(breakout) / fname
        write_path.write_text(cnv_contents)
        logger.info(f"{cnv} written to {write_path}")
