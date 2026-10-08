"""A reduced-complexity weekly bucket model of soil moisture."""

from ._version import __version__ as __version__
from .model import SoilWaterOutput as SoilWaterOutput
from .model import simulate as simulate
from .params import ModelConstants as ModelConstants
from .params import SoilWaterParams as SoilWaterParams
from .processes import SoilProperties as SoilProperties
