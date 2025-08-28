"""Convenience classes for interacting with a single breakout directory.

Has one main class: :py:class:`Breakout`.
The other two classes: :py:class:`BBox` and :py:class:`Interval` are in here because they are properties of the cruise of that breakout.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum, auto
from functools import cached_property
from hashlib import file_digest
from logging import getLogger
from pathlib import Path
from typing import NamedTuple

from lxml import etree

from r2r_ctd.checks import is_deck_test
from r2r_ctd.state import initialize_or_get_state

logger = getLogger(__name__)

FLEX_FILES_OK = """.DS_Store
thumbs.db"""
"""Filenames that, when in --bag flex validation mode, will not cause a fail"""
# kept as a string so it prints in the documentation nicely


class BBox(NamedTuple):
    """namedtuple to represent a geo bounding box

    The coordinates are in Westernmost, Southernmost, Easternmost, Northernmost order (see the geojson spec).
    The zonal coordinates are assumed to be [-180, 180] i.e. there a discontinuity that would cause a bounding box crossing
    the antimeridian to have a westernmost coordinate that is larger than the easternmost.

    No actual bounds checks are done when instantiating.
    """

    w: float
    s: float
    e: float
    n: float

    @property
    def __geo_interface__(self):
        if self.w > self.e:
            return {
                "type": "MultiPolygon",
                "coordinates": (
                    (
                        (
                            (self.w, self.s),
                            (180, self.s),
                            (180, self.n),
                            (self.w, self.n),
                            (self.w, self.s),
                        ),
                    ),
                    (
                        (
                            (-180, self.s),
                            (self.e, self.s),
                            (self.e, self.n),
                            (-180, self.n),
                            (-180, self.s),
                        ),
                    ),
                ),
            }

        return {
            "type": "Polygon",
            "coordinates": (
                (
                    (self.w, self.s),
                    (self.e, self.s),
                    (self.e, self.n),
                    (self.w, self.n),
                    (self.w, self.s),
                ),
            ),
        }

    def contains(self, lon: float, lat: float) -> bool:
        """given a lon/lat pair, determine if it is inside the bounding box represented by this instance"""
        if lat < self.s:
            return False
        if lat > self.n:
            return False
        if self.w > self.e:  # case of crossing the "date line"
            if self.e < lon < self.w:
                return False
        else:
            if lon > self.e:
                return False
            if lon < self.w:
                return False

        return True


class Interval(NamedTuple):
    """namedtuple to represent a temporal interval"""

    dtstart: datetime
    dtend: datetime

    def contains(self, dt: datetime) -> bool:
        """Given a datetime object, determine if it is inside the interval represented by this instance"""
        logger.info(f"Checking if {dt} is between {self.dtstart} and {self.dtend}")
        return self.dtstart <= dt < self.dtend


class BagStrictness(StrEnum):
    """Strictness of how to validate the payload against the manifest

    * "strict": Exactly follow BagIt spec, any files in the payload directory and not in the manifest cause the test to fail.
    * "flex": a reasonable set of files in the payload directory and not in the manifest are ignored (.DS_Store files).
    * "manifest": only files in the manifest are checked and others are ignored.
    """

    STRICT = auto()
    FLEX = auto()
    MANIFEST = auto()


@dataclass
class Breakout:
    """Convenience wrapper for manipulating the various Paths of the r2r breakout

    This class is also responsible for some of the more basic checks/functions:

    * Is the manifest-md5.txt ok
    * Filtering out the "deck test" looking paths
    * Getting the qa xml template
    * Extracting some information from said template

    This class also keeps track of the various state netCDF files and the open Dataset objects.
    Access to files in the breakout (not proc dir) should always go through an instance of this class.
    """

    path: Path
    """Path to the breakout itself, this set on instantiating a Breakout"""

    bag_strictness: BagStrictness = BagStrictness.FLEX
    """How strictly should the payload directory be validated"""

    @property
    def manifest_path(self) -> Path:
        """The Path of the manifest-md5.txt file in this breakout"""
        return self.path / "manifest-md5.txt"

    @property
    def manifest(self) -> str:
        """Reads the manifest file as returns its contents as a string"""
        return self.manifest_path.read_text()

    @property
    def payload_path(self) -> Path:
        """The path to the "data" directory assuming this is a BagIt bag"""
        return self.path / "data"

    @cached_property
    def manifest_dict(self) -> dict[Path, str]:
        """Transforms the manifest file into a dict containing file path to file hash mappings"""
        di = {}
        for line in self.manifest.splitlines():
            if line.strip() == "":
                continue

            manifest_hash, path = line.split(maxsplit=1)
            file_path = self.path / path
            di[file_path] = manifest_hash
        return di

    @cached_property
    def manifest_ok(self) -> bool:
        """Iterate over the manifest and check all the file hashes against the files in the breakout

        See :py:class:`PayloadStrictness` for how to control behavior.

        This returns True if both all the files in the manifest are present and their md5 hashes match.

        This is one of the checks that goes into the stoplight report.
        """
        flex_files_ok = set(FLEX_FILES_OK.split("\n"))
        logger.info(f"Bag validation mode: {self.bag_strictness}")
        err_message = "Files are in payload directory and not in manifest, breakout is likely invalid or corrupted"
        for root, _, files in self.payload_path.walk():
            paths = {root / file for file in files}
            diff = paths - self.manifest_dict.keys()
            if self.bag_strictness == "strict" and any(diff):
                logger.critical(err_message)
                return False

            if self.bag_strictness == "flex" and not all(
                d.name in flex_files_ok for d in diff
            ):
                logger.critical(err_message)
                return False

        for file_path, manifest_hash in self.manifest_dict.items():
            if not file_path.exists():
                return False
            with file_path.open("rb") as fo:
                file_hash = file_digest(fo, "md5").hexdigest()
            if manifest_hash != file_hash:
                return False
        return True

    @property
    def hex_paths(self) -> list[Path]:
        """Get all the paths that look like raw hex files

        This is roughly equivalent to the create_stations_from_raw in the orig
        processing scripts. Instead of walking the dir, we will just check the
        paths generated by the manifest.

        .. admonition:: WHOI Divergence
            :class: warning

            The original would also try to load/open .hex.gz and .dat.gz files, this is not supported by the underlying odf.sbe reader yet.
            The underlying odf.sbe reader also probably cannot read .dat files, but I've never seen one.
        """
        # TODO: orig had support for .gz but not sure what to do with that
        stems = {".hex", ".dat"}

        return list(
            filter(lambda path: path.suffix.lower() in stems, self.manifest_dict)
        )

    @cached_property
    def deck_test_paths(self) -> list[Path]:
        """Returns a list of path that match the :py:func:`.is_deck_test` check"""
        return list(filter(is_deck_test, self.hex_paths))

    @property
    def stations_hex_paths(self) -> list[Path]:
        """Return a list of hex paths that are not deck tests, i.e. :py:func:`.is_deck_test` is False for these paths.

        For the purposes of QC, these are the set of stations to operate on.
        """
        return [path for path in self.hex_paths if path not in self.deck_test_paths]

    @property
    def qa_template_path(self) -> Path:
        """Get the file named <cruise_id>_<fileset_id>_qc.2.0.xmlt from the breakout and return its path"""
        qa_path = self.path / "qa"
        candidates = list(qa_path.glob("*_qa.2.0.xmlt"))
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise ValueError(f"Multiple qa xml templates found {candidates}")

        raise ValueError(f"No qa xml template found in {qa_path}")

    @property
    def qa_template_xml(self) -> etree._ElementTree:
        """Parse the XML document located at :py:obj:`Breakout.qa_template_path`

        This template is where we will get the temporal and spatial bounds for the cruise.
        It is also the template that gets modified with the results of the QA routines.
        """
        return etree.parse(
            self.qa_template_path,
            etree.XMLParser(remove_blank_text=True),
        )

    @cached_property
    def namespaces(self) -> dict[str, str]:
        """Get the XML namespaces from the XML document located at :py:obj:`Breakout.qa_template_path`

        These namespaces are then filtered to omit the default (None) namespace.
        R2R uses an r2r namespace in its XML documents, to make working with this easier, the r2r namespace is extracted from the template.
        This namespace needs to be added to the various xpath or find methods of the lxml.etree._ElementTree.
        """
        root = self.qa_template_xml.getroot()
        return {k: v for k, v in root.nsmap.items() if k is not None}

    @property
    def cruise_id(self) -> str | None:
        """Extracts the cruise id from the XML document located at :py:obj:`Breakout.qa_template_path`

        The cruise id is the string that looks like RR1806 or TN336
        """
        if (
            cruise_id := self.qa_template_xml.find(
                ".//r2r:cruise_id", namespaces=self.namespaces
            )
        ) is not None:
            return cruise_id.text
        return None

    @property
    def fileset_id(self) -> str | None:
        """Extracts the fileset id from the XML document located at :py:obj:`Breakout.qa_template_path`

        The fileset id appears to only be numeric and appears as part of the doi for this breakout.
        """
        if (
            fileset_id := self.qa_template_xml.find(
                ".//r2r:fileset_id", namespaces=self.namespaces
            )
        ) is not None:
            return fileset_id.text
        return None

    @cached_property
    def bbox(self) -> BBox | None:
        """The bounding of the cruise in geojson bbox format/order: w, s, e, n

        This extracts the bounding box from the qa templates qareport/filesetinfo/cruise/extent nodes.

        .. admonition:: WHOI Divergence
            :class: warning

            The original code expanded the breakout bounding box by 0.0002 in each direction to
            "avoid a rounding problem"

        :returns: a BBox instance if a bounding box could be extracted from the XML, else None
        """
        root = self.qa_template_xml.getroot()
        prefix = "/r2r:qareport/r2r:filesetinfo/r2r:cruise/r2r:extent"
        w = root.xpath(f"{prefix}/r2r:westernmost/text()", namespaces=self.namespaces)
        s = root.xpath(f"{prefix}/r2r:southernmost/text()", namespaces=self.namespaces)
        e = root.xpath(f"{prefix}/r2r:easternmost/text()", namespaces=self.namespaces)
        n = root.xpath(f"{prefix}/r2r:northernmost/text()", namespaces=self.namespaces)
        result = []
        for elm in (w, s, e, n):
            if len(elm) != 1:
                logger.error("Breakout XML has invalid cruise bounding box")
                return None
            try:
                result.append(float(elm[0]))
            except ValueError:
                logger.error(
                    "Breakout XML bounding box has values that could not be parsed as float: {elm[0]}"
                )
                return None

        return BBox(*result)

    @cached_property
    def temporal_bounds(self) -> Interval | None:
        """The temporal bounds of the cruise in start, stop order.

        This extracts the temporal bounds from the qa templates qareport/filesetinfo/cruise depart_date and arrive_date nodes.
        For the end date, because this uses a time away datetime object, a day is added to ensure any bounds checks includes the entire end day.

        .. admonition:: WHOI Divergence
            :class: warning

            The original WHOI code would also pad the start with a day.

        :returns: a DTRange instance if a temporal bounds could be extracted from the XML, else None
        """
        root = self.qa_template_xml.getroot()
        prefix = "/r2r:qareport/r2r:filesetinfo/r2r:cruise"
        start = root.xpath(
            f"{prefix}/r2r:depart_date/text()", namespaces=self.namespaces
        )
        stop = root.xpath(
            f"{prefix}/r2r:arrive_date/text()", namespaces=self.namespaces
        )

        result = []
        for name, elm in zip(("start", "stop"), (start, stop), strict=True):
            if len(elm) != 1:
                logger.error("Zero or more than one temporal bound in breakout xml")
                return None
            try:
                dt = datetime.strptime(elm[0], "%Y-%m-%d")
                if name == "stop":
                    dt = dt + timedelta(days=1)
                result.append(dt)
            except ValueError:
                logger.error(f"Could not parse date in breakout as date: {elm[0]}")
                return None

        return Interval(*result)

    def __getitem__(self, key):
        try:
            return self.__cache[key]
        except AttributeError:
            self.__cache = {key: initialize_or_get_state(self, key)}
            return self.__cache[key]
        except KeyError:
            self.__cache[key] = initialize_or_get_state(self, key)
            return self.__cache[key]

    def __iter__(self):
        for path in self.stations_hex_paths:
            yield self[path]
