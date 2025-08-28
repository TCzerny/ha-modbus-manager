"""Backups client for supervisor."""

from collections.abc import AsyncIterator

from aiohttp import MultipartWriter
from multidict import MultiDict

from .client import _SupervisorComponentClient
from .const import ResponseType
from .models.backups import (
    Backup,
    BackupComplete,
    BackupJob,
    BackupList,
    BackupsInfo,
    BackupsOptions,
    DownloadBackupOptions,
    FreezeOptions,
    FullBackupOptions,
    FullRestoreOptions,
    NewBackup,
    PartialBackupOptions,
    PartialRestoreOptions,
    RemoveBackupOptions,
    UploadBackupOptions,
    UploadedBackup,
)


class BackupsClient(_SupervisorComponentClient):
    """Handles backups access in Supervisor."""

    async def list(self) -> list[Backup]:
        """List backups."""
        result = await self._client.get("backups")
        return BackupList.from_dict(result.data).backups

    async def info(self) -> BackupsInfo:
        """Get backups info."""
        result = await self._client.get("backups/info")
        return BackupsInfo.from_dict(result.data)

    async def set_options(self, options: BackupsOptions) -> None:
        """Set options for backups."""
        await self._client.post("backups/options", json=options.to_dict())

    async def reload(self) -> None:
        """Reload backups cache."""
        await self._client.post("backups/reload")

    async def freeze(self, options: FreezeOptions | None = None) -> None:
        """Start a freeze for external snapshot process."""
        await self._client.post(
            "backups/freeze", json=options.to_dict() if options else None
        )

    async def thaw(self) -> None:
        """Thaw an active freeze when external snapshot process ends."""
        await self._client.post("backups/thaw")

    async def full_backup(self, options: FullBackupOptions | None = None) -> NewBackup:
        """Create a new full backup."""
        result = await self._client.post(
            "backups/new/full",
            json=options.to_dict() if options else None,
            response_type=ResponseType.JSON,
            timeout=None,
        )
        return NewBackup.from_dict(result.data)

    async def partial_backup(self, options: PartialBackupOptions) -> NewBackup:
        """Create a new partial backup."""
        result = await self._client.post(
            "backups/new/partial",
            json=options.to_dict(),
            response_type=ResponseType.JSON,
            timeout=None,
        )
        return NewBackup.from_dict(result.data)

    async def backup_info(self, backup: str) -> BackupComplete:
        """Get backup details."""
        result = await self._client.get(f"backups/{backup}/info")
        return BackupComplete.from_dict(result.data)

    async def remove_backup(
        self, backup: str, options: RemoveBackupOptions | None = None
    ) -> None:
        """Remove a backup."""
        await self._client.delete(
            f"backups/{backup}", json=options.to_dict() if options else None
        )

    async def full_restore(
        self, backup: str, options: FullRestoreOptions | None = None
    ) -> BackupJob:
        """Start full restore from backup."""
        result = await self._client.post(
            f"backups/{backup}/restore/full",
            json=options.to_dict() if options else None,
            response_type=ResponseType.JSON,
            timeout=None,
        )
        return BackupJob.from_dict(result.data)

    async def partial_restore(
        self, backup: str, options: PartialRestoreOptions
    ) -> BackupJob:
        """Start partial restore from backup."""
        result = await self._client.post(
            f"backups/{backup}/restore/partial",
            json=options.to_dict(),
            response_type=ResponseType.JSON,
            timeout=None,
        )
        return BackupJob.from_dict(result.data)

    async def upload_backup(
        self, stream: AsyncIterator[bytes], options: UploadBackupOptions | None = None
    ) -> str:
        """Upload backup by stream and return slug."""
        params = MultiDict()
        if options and options.location:
            for location in options.location:
                params.add("location", location or "")

        with MultipartWriter("form-data") as mp:
            mp.append(stream)
            result = await self._client.post(
                "backups/new/upload",
                params=params,
                data=mp,
                response_type=ResponseType.JSON,
                timeout=None,
            )

        return UploadedBackup.from_dict(result.data).slug

    async def download_backup(
        self, backup: str, options: DownloadBackupOptions | None = None
    ) -> AsyncIterator[bytes]:
        """Download backup and return stream."""
        params = MultiDict()
        if options and options.location:
            params.add("location", options.location or "")

        result = await self._client.get(
            f"backups/{backup}/download",
            params=params,
            response_type=ResponseType.STREAM,
            timeout=None,
        )
        return result.data
