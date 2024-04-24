import typing, json
import tinyfaas_prefetching_request
import tinyfaas_invocation_request


def fn(input: typing.Optional[str]) -> typing.Optional[str]:

    assert input
    inputDict = json.loads(input)

    if inputDict.get("pf-request") and inputDict.get("pf-request") is True:
        print("got pre-fetching request")
        preFetchedDataPath = tinyfaas_prefetching_request.handlePreFetchingRequest(inputDict)
    else:
        print("assuming invocation request")
        status_code = tinyfaas_invocation_request.handleInvocationRequest(inputDict)
        return str(status_code)

    return preFetchedDataPath
