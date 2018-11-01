__all__ = "Snmp"

from typing import Any, List, Optional, Tuple, Union

from .connection import SnmpConnection
from .exceptions import SnmpUnsupportedValueType
from .message import (
    GetBulkRequest,
    GetNextRequest,
    GetRequest,
    SetRequest,
    SnmpMessage,
    SnmpVarbind,
    SnmpVersion,
)


class Snmp(SnmpConnection):
    __slots__ = ("version", "community", "non_repeaters", "max_repetitions")

    def __init__(
        self,
        *,
        version: SnmpVersion = SnmpVersion.v2c,
        community: str = "public",
        non_repeaters: int = 0,
        max_repetitions: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.version: SnmpVersion = version
        self.community: str = community
        self.non_repeaters: int = non_repeaters
        self.max_repetitions: int = max_repetitions

    async def _send(self, message: SnmpMessage) -> List[SnmpVarbind]:
        if self._protocol is None:
            await self._connect()
        assert self._protocol
        return await self._protocol._send(message, self.host, self.port)

    async def get(self, oids: Union[str, List[str]]) -> List[SnmpVarbind]:
        if isinstance(oids, str):
            oids = [oids]
        message = SnmpMessage(
            self.version, self.community, GetRequest([SnmpVarbind(oid) for oid in oids])
        )
        return await self._send(message)

    async def get_next(self, oids: Union[str, List[str]]) -> List[SnmpVarbind]:
        if isinstance(oids, str):
            oids = [oids]
        message = SnmpMessage(
            self.version,
            self.community,
            GetNextRequest([SnmpVarbind(oid) for oid in oids]),
        )
        return await self._send(message)

    async def get_bulk(
        self,
        oids: Union[str, List[str]],
        *,
        non_repeaters: Optional[int] = None,
        max_repetitions: Optional[int] = None,
    ) -> List[SnmpVarbind]:
        if isinstance(oids, str):
            oids = [oids]
        nr: int = self.non_repeaters if non_repeaters is None else non_repeaters
        mr: int = self.max_repetitions if max_repetitions is None else max_repetitions
        message = SnmpMessage(
            self.version,
            self.community,
            GetBulkRequest([SnmpVarbind(oid) for oid in oids], nr, mr),
        )
        return await self._send(message)

    async def walk(self, oid: str) -> List[SnmpVarbind]:
        varbinds: List[SnmpVarbind] = []
        message = SnmpMessage(
            self.version, self.community, GetNextRequest([SnmpVarbind(oid)])
        )
        vbs = await self._send(message)
        next_oid = vbs[0].oid
        if not next_oid.startswith(f"{oid}."):
            message = SnmpMessage(
                self.version, self.community, GetRequest([SnmpVarbind(oid)])
            )
            return await self._send(message)

        varbinds.append(vbs[0])
        while True:
            message = SnmpMessage(
                self.version, self.community, GetNextRequest([SnmpVarbind(next_oid)])
            )
            vbs = await self._send(message)
            next_oid = vbs[0].oid
            if not next_oid.startswith(f"{oid}."):
                break
            varbinds.append(vbs[0])
        return varbinds

    async def set(
        self, varbinds: List[Tuple[str, Union[int, str, bytes]]]
    ) -> List[SnmpVarbind]:
        for varbind in varbinds:
            if not isinstance(varbind[1], (int, str, bytes)):
                raise SnmpUnsupportedValueType(
                    f"Only int, str and bytes supported, got {type(varbind[1])}"
                )
        message = SnmpMessage(
            self.version,
            self.community,
            SetRequest([SnmpVarbind(oid, value) for oid, value in varbinds]),
        )
        return await self._send(message)

    async def bulk_walk(
        self,
        oid: str,
        *,
        non_repeaters: Optional[int] = None,
        max_repetitions: Optional[int] = None,
    ) -> List[SnmpVarbind]:
        nr: int = self.non_repeaters if non_repeaters is None else non_repeaters
        mr: int = self.max_repetitions if max_repetitions is None else max_repetitions
        base_oid: str = oid
        varbinds: List[SnmpVarbind] = []
        message = SnmpMessage(
            self.version,
            self.community,
            GetBulkRequest([SnmpVarbind(base_oid)], nr, mr),
        )
        vbs: List[SnmpVarbind] = await self._send(message)
        next_oid: str = ""
        for i, vb in enumerate(vbs):
            if not vb.oid.startswith(f"{base_oid}.") or vb.value is None:
                if i == 0:
                    message = SnmpMessage(
                        self.version,
                        self.community,
                        GetRequest([SnmpVarbind(base_oid)]),
                    )
                    return await self._send(message)
                return varbinds
            varbinds.append(vb)
            next_oid = vb.oid
        while next_oid:
            message = SnmpMessage(
                self.version,
                self.community,
                GetBulkRequest([SnmpVarbind(next_oid)], nr, mr),
            )
            vbs = await self._send(message)
            for vb in vbs:
                if not vb.oid.startswith(f"{base_oid}.") or vb.value is None:
                    next_oid = ""
                    break
                varbinds.append(vb)
                next_oid = vb.oid
        return varbinds
