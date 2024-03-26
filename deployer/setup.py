import deployer.serverless
import utils.utils

import shutil, os, subprocess, sys
from os import path
from typing import Any, Dict, List, Optional

import boto3


def createDeployment(deployment: Dict[str, Any], src: str, dst: str) -> None:
    # setup all files in a new directory to be deployed
    # -> also create all serverless.yaml files + serverless compose
    # assume the dst directory already exists and was created earlier
    # -> to create a unique deployment name, call it `deployment-<unix-ts>`
    # assume that the dir directory is empty

    assert path.exists(dst)

    compose = deployer.serverless.generateSlsCompose(deployment)
    assert compose is not None

    functions = deployment["functions"]
    for name in functions.keys():
        fn = functions[name]
        # create new subdirectory for the function
        try:
            functionDir = path.join(dst, name)
            print(f"functionDir {functionDir}")
            os.mkdir(functionDir)
        except Exception as e:
            print(e)
            print(f"could not create subdirectory for function {name}, skipping ...")
            continue
        # create provider specific deployment
        provider = fn["provider"].lower()
        if provider == "aws":
            createAwsDeployment(deployment, name, fn, functionDir, src)
        elif provider == "google":
            createGcpDeployment(deployment, name, fn, functionDir, src)
        elif provider == "tinyfaas":
            createTinyFaaSDeployment(deployment, name, fn, functionDir, src)
        else:
            raise Exception(f"unknown provider {provider}")
    # create sls compose
    # - [x] test
    slsCompose = deployer.serverless.generateSlsCompose(deployment)
    slsComposePath = path.join(dst, "serverless-compose.yml")
    with open(slsComposePath, "w") as f:
        try:
            f.write(slsCompose)
        except Exception as e:
            print(e)
            print(f"error while to create serverless compose at {slsComposePath}")

def createBucket(s3: Any, bucketName: str) -> None:
    # create a bucket while deploying to pass args around during the workflows
    s3.create_bucket(Bucket=bucketName, ObjectOwnership='BucketOwnerPreferred')
    s3.put_public_access_block(
        Bucket=bucketName,
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': False,
            'IgnorePublicAcls': False,
            'BlockPublicPolicy': False,
            'RestrictPublicBuckets': False
        }
    )
    s3.put_bucket_acl(Bucket=bucketName, ACL='public-read-write')

def createAwsDeployment(deployment: Dict[str, Any], name: str, fn: Dict[str, str], functionDir: str, src: str) -> None:
    # - [x] test

    # copy the choreography code to the new function subdirectory
    choreoDst = path.join(functionDir, "choreography")
    print(f"choreoDst {choreoDst}")
    try:
        utils.utils.copyChoreographyPackage(choreoDst)
    except Exception as e:
        print(e)
        print(f"could not copy choreography package into function direction for {name}, skipping ...")
        return

    # copy the function code (main.py & requirements.txt)
    mainSrc = path.join(src, name, "main.py")
    mainDst = path.join(functionDir, "main.py")
    print(f"mainSrc, mainDst = {mainSrc, mainDst}")
    shutil.copyfile(mainSrc, mainDst)
    requirementsSrc = path.join(src, f"{name}", "requirements.txt")
    requirementsDst = path.join(functionDir, "requirements.txt")
    print(f"requirementsSrc, requirementsDst = {requirementsSrc, requirementsDst}")
    shutil.copyfile(requirementsSrc, requirementsDst)

    # copy the aws wrapper
    try:
        wrapperSrc = path.join(path.abspath("wrapper"), "wrapper_aws.py")
        wrapperDst = path.join(functionDir, "wrapper_aws.py")
        print(f"wrapperSrc, wrapperDst = {wrapperSrc, wrapperDst}")
        shutil.copyfile(wrapperSrc, wrapperDst)
    except Exception as e:
        print(e)
        print(f"error while trying to copy wrapper_tinyfaas.py for function {name}, skipping ...")
        return

    # 5) generate the serverless.yml
    sls = deployer.serverless.generateAWS(deployment, name)
    assert sls is not None
    with open(path.join(functionDir, "serverless.yml"), "w") as f:
        try:
            f.write(sls)
        except ExceptionfunctionDir as e:
            print(e)
            print(f"error occurred while trying to write serverless.yml for aws lambda function {name}, skipping ...")
            return

    # 6) add packages used by the choreography middleware to the requirements
    requirementsPath = path.abspath("requirements.txt")
    requirements = getRequirements(requirementsPath)
    addRequirements(requirementsDst, requirements)

    # 7) handle AWS requirements
    handleAwsRequirements(requirementsDst, functionDir)
    print(f"successfully created AWS deployment for {name}")

def createGcpDeployment(deployment: Dict[str, Any], name: str, fn: Dict[str, str], functionDir: str, src: str) -> None:
    # - [x] test

    # copy choreo code
    choreoDst = path.join(functionDir, "choreography")
    print(f"choreoDst {choreoDst}")
    try:
        utils.utils.copyChoreographyPackage(choreoDst)
    except Exception as e:
        print(e)
        print(f"could not copy choreography package into function direction for {name}, skipping ...")
        return

    # main.py & requirements.txt
    # google want the file with the entrypoint called `main.py` -> that has to be the wrapper -> call main.py user_main.py
    mainSrc = path.join(src, name, "main.py")
    mainDst = path.join(functionDir, "user_main.py")
    print(f"mainSrc, mainDst = {mainSrc, mainDst}")
    shutil.copyfile(mainSrc, mainDst)
    requirementsSrc = path.join(src, f"{name}", "requirements.txt")
    requirementsDst = path.join(functionDir, "requirements.txt")
    print(f"requirementsSrc, requirementsDst = {requirementsSrc, requirementsDst}")
    shutil.copyfile(requirementsSrc, requirementsDst)

    # add packages used by the choreography middleware to the requirements
    requirementsPath = path.abspath("requirements.txt")
    requirements = getRequirements(requirementsPath)
    addRequirements(requirementsDst, requirements)

    # gcp wrapper (call it main.py)
    try:
        wrapperSrc = path.join(path.abspath("wrapper"), "wrapper_gcp.py")
        wrapperDst = path.join(functionDir, "main.py")
        print(f"wrapperSrc, wrapperDst = {wrapperSrc, wrapperDst}")
        shutil.copyfile(wrapperSrc, wrapperDst)
    except Exception as e:
        print(e)
        print(f"error while trying to copy wrapper_tinyfaas.py for function {name}, skipping ... ")
        return

    # generate serverless.yml
    sls = deployer.serverless.generateGCP(deployment, name)
    assert sls is not None
    with open(path.join(functionDir, "serverless.yml"), "w") as f:
        try:
            f.write(sls)
        except ExceptionfunctionDir as e:
            print(e)
            print(f"error occurred while trying to write serverless.yml for google cloud function {name}, skipping ...")
            return

def createTinyFaaSDeployment(deployment: Dict[str, Any], name: str, fn: Dict[str, str], functionDir: str, src: str) -> None:
    # - [x] test
    # tinyfaas wants different dir structure

    # create tinyfaas specific directory structure
    assert path.exists(functionDir)
    try:
        functionsSubdir = path.join(functionDir, "functions")
        print(f"functionsSubdir {functionsSubdir}")
        os.mkdir(functionsSubdir)
        functionTarget = path.join(functionsSubdir, name)
        print(f"functionTarget {functionTarget}")
    except Exception as e:
        print(e)
        print(f"error trying to create subdirectories for tinyfaas function {name}")
        return

    # copy choreo code
    choreoDst = path.join(functionTarget, "choreography")
    print(f"choreoDst {choreoDst}")
    try:
        utils.utils.copyChoreographyPackage(choreoDst)
    except Exception as e:
        print(e)
        print(f"could not copy choreography package into function direction for {name}, skipping ...")
        return

    # copy main.py & requirements.txt
    mainSrc = path.join(src, name, "main.py")
    mainDst = path.join(functionTarget, "main.py")
    print(f"mainSrc, mainDst = {mainSrc, mainDst}")
    shutil.copyfile(mainSrc, mainDst)
    requirementsSrc = path.join(src, f"{name}", "requirements.txt")
    requirementsDst = path.join(functionTarget, "requirements.txt")
    print(f"requirementsSrc, requirementsDst = {requirementsSrc, requirementsDst}")
    shutil.copyfile(requirementsSrc, requirementsDst)

    # add packages used by the choreography middleware to the requirements
    requirementsPath = path.abspath("requirements.txt")
    requirements = getRequirements(requirementsPath)
    addRequirements(requirementsDst, requirements)

    # tinyfaas wrapper
    try:
        wrapperSrc = path.join(path.abspath("wrapper"), "wrapper_tinyfaas.py")
        wrapperDst = path.join(functionTarget, "fn.py")
        print(f"wrapperSrc, wrapperDst = {wrapperSrc, wrapperDst}")
        shutil.copyfile(wrapperSrc, wrapperDst)
    except Exception as e:
        print(e)
        print(f"error while trying to copy wrapper_tinyfaas.py for function {name}, skipping ... ")
        return

    # generate serverless.yml
    sls = deployer.serverless.generateTinyFaas(deployment, name)
    assert sls is not None
    with open(path.join(functionDir, "serverless.yml"), "w") as f:
        try:
            f.write(sls)
        except ExceptionfunctionDir as e:
            print(e)
            print(
                f"error occurred while trying to write serverless.yml for tinyfaas function {name}, skipping ...")
            return

def handleAwsRequirements(requirementsPath: str, functionDir: str) -> None:
    # - [x] test
    assert path.exists(functionDir)
    cmd = f"pip install -t {functionDir} -r {requirementsPath}"
    try:
        print(f"installing requirements for aws lambda function")
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"result of requirements installation: {result.stdout}")
        err = result.stderr
        if err != None and err != "":
            print(f"error: {err}")
    except subprocess.CalledProcessError as e:
        print(f"couldn't install requirements {requirementsPath} for lambda function")
        print(f"Error: {e.with_traceback(e.__traceback__)}")
        sys.exit(1)


def getRequirements(requirementsPath: str) -> List[str]:
    # - [x] test
    assert path.exists(requirementsPath)
    with open(requirementsPath, "r") as f:
        return f.readlines()

def addRequirements(requirementsPath: str, requirements: List[str]) -> None:
    # - [x] test
    assert path.exists(requirementsPath)
    with open(requirementsPath, "a") as f:
        try:
            f.writelines(["\n"]+requirements)
        except Exception as e:
            print(e)
            print(f"error while trying to add requirements to {requirementsPath}")

def deploy(dst: str) -> None:
    # TODO test
    # - [ ] test
    assert path.exists(dst)
    cmd = f"cd {dst} && sls deploy"
    try:
        result = subprocess.run(cmd, shell=True, check=True)
    except Exception as e:
        print(e)
        print(f"error while trying to use subprocess to deploy serverless compose at {dst}")
