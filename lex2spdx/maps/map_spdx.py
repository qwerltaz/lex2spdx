from abc import ABC, abstractmethod

from . import load_spdx_licenses

class IMap(ABC):
    @abstractmethod
    def map(self, license: str) -> str | None:
        """
        Map a license string to an SPDX license using exact match.
        :param license: The license string to map.
        :return: The mapped SPDX license or None if no match is found.
        """

class MapExactMatch(IMap):
    def map(self, license: str) -> str | None:
        raise NotImplementedError

