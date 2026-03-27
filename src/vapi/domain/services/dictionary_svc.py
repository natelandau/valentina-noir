"""Dictionary services."""

from __future__ import annotations

from beanie import PydanticObjectId  # noqa: TC002
from beanie.operators import Or

from vapi.db.models import Company, DictionaryTerm
from vapi.lib.exceptions import ValidationError


class DictionaryService:
    """Dictionary service."""

    def __init__(self) -> None:
        """Initialize the dictionary service."""

    def verify_term_is_editable(
        self, dictionary_term: DictionaryTerm, company_id: PydanticObjectId
    ) -> bool:
        """Check if the dictionary term is editable by the company."""
        if dictionary_term.company_id != company_id or dictionary_term.source_type is not None:
            raise ValidationError(
                detail="You may not update dictionary terms that are not owned by your company."
            )

        return True

    async def list_all_dictionary_terms(
        self, *, company: Company, limit: int, offset: int, term: str | None = None
    ) -> tuple[int, list[DictionaryTerm]]:
        """List all dictionary terms for a company. Also includes global dictionary terms.

        Args:
            company: The company to filter dictionary terms for.
            limit: The limit of dictionary terms to return.
            offset: The offset of dictionary terms to return.
            term: The term to search for.

        Returns:
            A tuple containing the count of dictionary terms and the list of dictionary terms.
        """
        query = [
            DictionaryTerm.is_archived == False,
            Or(DictionaryTerm.company_id == company.id, DictionaryTerm.source_type != None),
        ]
        if term:
            query.append(
                Or(
                    DictionaryTerm.term == term.strip().lower(),
                    DictionaryTerm.synonyms == term.strip().lower(),
                )
            )

        count = await DictionaryTerm.find(*query).count()  # type: ignore [call-overload]
        dictionary_terms = (
            await DictionaryTerm.find(*query)  # type: ignore [call-overload]
            .sort("term")
            .skip(offset)
            .limit(limit)
            .to_list()
        )

        return count, dictionary_terms
