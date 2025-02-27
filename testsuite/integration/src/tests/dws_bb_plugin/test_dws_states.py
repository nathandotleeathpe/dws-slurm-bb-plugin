#
# Copyright 2022 Hewlett Packard Enterprise Development LP
# Other additional copyright holders may be indicated within.
#
# The entirety of this work is licensed under the Apache License,
# Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.
#
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import time
from .workflow import Workflow
from pytest_bdd import (
    given,
    parsers,
    scenarios,
    then,
    when,
)

"""Data Workflow Services State Progression feature tests."""
scenarios("test_dws_states.feature")

@when('a Workflow is created for the job')
@then('the workflow still exists')
def _(k8s, jobId):
    """a Workflow is created for the job."""
    workflow = Workflow(k8s, jobId)
    assert workflow.data != None, "Workflow for Job: " + str(jobId) + " not found"
    
    yield

    # attempt to delete workflow if it still exists
    try:
        workflow.delete()
    except:
        pass

@when(parsers.parse('the Workflow status becomes {status:l}'))
def _(slurmctld, jobId, status):
    """the Workflow status becomes <status>"""
    workflowStatus = slurmctld.get_workflow_status(jobId)
    assert workflowStatus["status"] == status

@when('the job is canceled')
def _(slurmctld, jobId):
    """the job is canceled"""
    time.sleep(2) # Sleep long enough for bb plugin to poll workflow once or twice
    slurmctld.cancel_job(jobId, False)

def verify_job_status(slurmctld, jobId, state, status):
    jobStatus = slurmctld.get_workflow_status(jobId)
    assert jobStatus["desiredState"] == state, "Incorrect desired state: " + str(jobStatus)
    assert jobStatus["currentState"] == state, "Incorrect current state: " + str(jobStatus)
    assert jobStatus["status"] == status, "Incorrect status: " + str(jobStatus)

@then(parsers.parse('the Workflow and job progress to the {state:l} state'))
def _(k8s, slurmctld, jobId, state):
    """the Workflow and job progress to the <state> state."""

    expectedStatus = "DriverWait"

    workflow = Workflow(k8s, jobId)
    workflow.wait_until(
        "the state the workflow is transitioning to",
        lambda wf: wf.data["status"]["state"] == state and wf.data["status"]["status"] == expectedStatus
    )
    print("job %s progressed to state %s" % (str(jobId),state))

    verify_job_status(slurmctld, jobId, state, expectedStatus)

    # Set driver status to completed so the workflow can progress to the next state
    foundPendingDriverStatus = False
    for driverStatus in workflow.data["status"]["drivers"]:
        if driverStatus["driverID"] == "tester" and state in driverStatus["watchState"] and driverStatus["status"] == "Pending":
            print("updating job %s to complete state %s" % (str(jobId), state))
            driverStatus["completed"] = True
            driverStatus["status"] = "Completed"
            foundPendingDriverStatus = True

    assert foundPendingDriverStatus, "Driver not found with \"Pending\" status" 
    workflow.save_driver_statuses()

@when(parsers.parse('the Workflow and job report errors at the {state:l} state'))
def _(k8s, slurmctld, jobId, state):
    """the Workflow and job report errors at the <state> state."""

    expectedStatus = "Error"

    workflow = Workflow(k8s, jobId)
    workflow.wait_until(
        "the state the workflow is transitioning to",
        lambda wf: wf.data["status"]["state"] == state and wf.data["status"]["status"] == expectedStatus
    )
    print("job %s progressed to state %s" % (str(jobId),state))

    verify_job_status(slurmctld, jobId, state, expectedStatus)

@then(parsers.parse("the job's system comment contains the following:\n{message}"))
def _(slurmctld, jobId, message):
    _,out = slurmctld.get_final_job_state(jobId)
    assert message in out
