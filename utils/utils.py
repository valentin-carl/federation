import typing, json, shutil
from os import path

import yaml
from google.oauth2 import service_account


def generateYaml(data: typing.Dict) -> str:
    try:
        return yaml.dump(data, default_flow_style=False)
    except Exception as e:
        print(e)
        print(f"couldn't convert {data} to yaml")

def loadCredentials(path: str) -> typing.Dict[str, typing.Any]:
    with open(path) as f:
        return json.load(f)["credentials"]

def copyChoreographyPackage(choreoDst: str) -> None:
    choreoSrc = path.abspath("choreography")
    print(f"choreoSrc {choreoSrc}")
    assert path.exists(choreoSrc)
    shutil.copytree(
        src=choreoSrc,
        dst=choreoDst
    )
