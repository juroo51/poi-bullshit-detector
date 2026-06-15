from app.models.schemas import ValidationRequest, Verdict, LoadResult
from app.modules import bullshit_detector, crowd_tester, report_generator


async def validate(req: ValidationRequest) -> Verdict:
    # Stage 1: data + schema gate
    schema, sanity, _body = await bullshit_detector.run(
        req.endpoint, req.method, req.auth, req.sample_payload, req.response_schema
    )

    # Stage 2: only load-test endpoints that return sane, valid data
    if schema.passed and sanity.passed:
        load = await crowd_tester.run(
            req.endpoint, req.method, req.auth, req.sample_payload
        )
    else:
        load = LoadResult(ran=False)

    # Stage 3: assemble the verdict
    return report_generator.build(schema, sanity, load)
