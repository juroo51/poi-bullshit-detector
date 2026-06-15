from app.models.schemas import (
    SchemaResult, SanityResult, LoadResult, Verdict, Status,
)


def build(
    schema: SchemaResult,
    sanity: SanityResult,
    load: LoadResult,
) -> Verdict:
    reasons: list[str] = []
    if not schema.passed:
        reasons += [f"schema: {e}" for e in schema.errors]
    if not sanity.passed:
        reasons += [f"sanity: {i}" for i in sanity.issues]
    if load.ran and not load.passed:
        reasons += [f"load: {r}" for r in load.reasons]
    if not load.ran:
        reasons.append("load test skipped (data validation gate failed)")

    status = Status.approved if not reasons else Status.rejected
    return Verdict(
        status=status,
        failure_reasons=reasons,
        schema_check=schema,
        sanity_check=sanity,
        load_test=load,
    )
