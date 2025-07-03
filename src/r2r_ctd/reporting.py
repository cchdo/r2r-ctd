from lxml.builder import ElementMaker

E = ElementMaker(
    namespace="https://service.rvdata.us/schema/r2r-2.0",
    nsmap={"r2r": "https://service.rvdata.us/schema/r2r-2.0"},
)

Rating = E.rating
Tests = E.tests
Test = E.test
TestResult = E.test_result
Bounds = E.bounds
Bound = E.bound

Infos = E.infos
Info = E.info


rating = {
    "description": (
        "GREEN (G) if all tests GREEN, "
        "RED (R) if at least one test RED, "
        "else YELLOW (Y); "
        "Gray(N) if no navigation was included in the distribution; "
        "X if one or more tests could not be run."
    )
}
