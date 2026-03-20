"""Trigger materialization of Meta assets via Dagster GraphQL API."""
import requests
import json
import time
import sys

GRAPHQL = "http://127.0.0.1:3000/graphql"

mutation = """
mutation {
  launchPipelineExecution(
    executionParams: {
      selector: {
        repositoryLocationName: "definitions.py"
        repositoryName: "__repository__"
        pipelineName: "raw_meta_sync"
      }
    }
  ) {
    __typename
    ... on LaunchRunSuccess {
      run { runId status }
    }
    ... on PythonError {
      message
    }
  }
}
"""

print("Launching materialization for raw_meta_sync job...")
try:
    resp = requests.post(GRAPHQL, json={"query": mutation}, timeout=300)
    result = resp.json()
    print(json.dumps(result, indent=2))
except requests.exceptions.Timeout:
    print("Launch request timed out (300s). Checking for active runs...")
    runs_query = """{ runsOrError(filter: {pipelineName: "raw_meta_sync", statuses: [STARTED, STARTING, QUEUED]}, limit: 1) { ... on Runs { results { runId status } } } }"""
    resp = requests.post(GRAPHQL, json={"query": runs_query}, timeout=30)
    result = resp.json()
    runs = result.get("data", {}).get("runsOrError", {}).get("results", [])
    if runs:
        run_id = runs[0]["runId"]
        print(f"Found active run: {run_id}")
    else:
        print("No active runs found.")
        sys.exit(1)

launch_data = result.get("data", {}).get("launchPipelineExecution", {})
if launch_data and launch_data.get("__typename") == "LaunchRunSuccess":
    run_id = launch_data["run"]["runId"]
elif "run_id" not in dir():
    print(f"Failed to launch: {result}")
    sys.exit(1)

print(f"\nRun ID: {run_id}")

run_query = """
query RunStatus($runId: ID!) {
  runOrError(runId: $runId) {
    ... on Run {
      runId
      status
      stats {
        ... on RunStatsSnapshot {
          stepsSucceeded
          stepsFailed
          startTime
          endTime
        }
      }
    }
  }
}
"""
for i in range(120):
    time.sleep(10)
    try:
        resp = requests.post(GRAPHQL, json={"query": run_query, "variables": {"runId": run_id}}, timeout=15)
        run_data = resp.json()["data"]["runOrError"]
        status = run_data["status"]
        print(f"  [{(i+1)*10}s] Status: {status}")
        if status in ("SUCCESS", "FAILURE", "CANCELED"):
            print(json.dumps(run_data, indent=2))
            if status == "SUCCESS":
                print("\nMaterialization SUCCEEDED!")
            else:
                print(f"\nMaterialization {status}")
            break
    except Exception as e:
        print(f"  [{(i+1)*10}s] Poll error: {e}")
else:
    print("\nTimed out waiting for run completion (1200s)")
