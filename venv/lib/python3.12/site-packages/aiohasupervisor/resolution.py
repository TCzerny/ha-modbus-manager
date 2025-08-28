"""Resolution center client for supervisor."""

from uuid import UUID

from .client import _SupervisorComponentClient
from .models.resolution import (
    CheckOptions,
    CheckType,
    ResolutionInfo,
    Suggestion,
    SuggestionsList,
)


class ResolutionClient(_SupervisorComponentClient):
    """Handles resolution center access in supervisor."""

    async def info(self) -> ResolutionInfo:
        """Get resolution center info."""
        result = await self._client.get("resolution/info")
        return ResolutionInfo.from_dict(result.data)

    async def check_options(
        self, check: CheckType | str, options: CheckOptions
    ) -> None:
        """Set options for a check."""
        await self._client.post(
            f"resolution/check/{check}/options", json=options.to_dict()
        )

    async def run_check(self, check: CheckType | str) -> None:
        """Run a check."""
        await self._client.post(f"resolution/check/{check}/run")

    async def apply_suggestion(self, suggestion: UUID) -> None:
        """Apply a suggestion."""
        await self._client.post(f"resolution/suggestion/{suggestion.hex}", timeout=None)

    async def dismiss_suggestion(self, suggestion: UUID) -> None:
        """Dismiss a suggestion."""
        await self._client.delete(f"resolution/suggestion/{suggestion.hex}")

    async def dismiss_issue(self, issue: UUID) -> None:
        """Dismiss an issue."""
        await self._client.delete(f"resolution/issue/{issue.hex}")

    async def suggestions_for_issue(self, issue: UUID) -> list[Suggestion]:
        """Get suggestions for issue."""
        result = await self._client.get(f"resolution/issue/{issue.hex}/suggestions")
        return SuggestionsList.from_dict(result.data).suggestions

    async def healthcheck(self) -> None:
        """Run a healthcheck."""
        await self._client.post("resolution/healthcheck")
