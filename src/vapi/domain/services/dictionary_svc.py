"""Dictionary services."""

import asyncio
from uuid import UUID

from tortoise.expressions import Q

from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.lib.exceptions import ValidationError


class DictionaryService:
    """Dictionary service."""

    def verify_term_is_editable(self, dictionary_term: DictionaryTerm, company_id: UUID) -> bool:
        """Check if the dictionary term is editable by the company.

        A term is editable only if it is owned by the requesting company
        and has no source_type (not auto-generated).

        Raises:
            ValidationError: If the term is not editable.
        """
        if dictionary_term.company_id != company_id or dictionary_term.source_type is not None:  # type: ignore[attr-defined]
            raise ValidationError(
                detail="You may not update dictionary terms that are not owned by your company."
            )

        return True

    async def list_all_dictionary_terms(
        self, *, company_id: UUID, limit: int, offset: int, term: str | None = None
    ) -> tuple[int, list[DictionaryTerm]]:
        """List dictionary terms visible to a company.

        Returns company-owned terms and global terms (company_id IS NULL).
        Optionally filter by term name or synonym match.

        Args:
            company_id: The company ID to scope results.
            limit: Maximum number of results to return.
            offset: Number of results to skip.
            term: Optional search string to match against term or synonyms.

        Returns:
            A tuple of (total_count, page_of_results).
        """
        base_q = Q(is_archived=False) & (Q(company_id=company_id) | Q(company_id__isnull=True))

        if term:
            normalized = term.strip().lower()
            base_q &= Q(term=normalized) | Q(synonyms__contains=[normalized])

        qs = DictionaryTerm.filter(base_q)

        count, terms = await asyncio.gather(
            qs.count(),
            qs.order_by("term").offset(offset).limit(limit),
        )

        return count, list(terms)
