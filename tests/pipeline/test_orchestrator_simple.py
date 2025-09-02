#!/usr/bin/env python3
"""
Simple test script for the orchestrator state machine
Tests core functionality without requiring full pipeline modules
"""

import asyncio
import sys

from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from fastapi_app.db import db
from fastapi_app.models import Brief, ConfigSnapshot, Job, JobStatus, Stage
from fastapi_app.orchestrator import orchestrator


async def test_orchestrator_simple():
    """Test the orchestrator state machine with minimal dependencies"""
    print("Testing orchestrator state machine (simple mode)...")

    # Create a test job
    job = Job(
        id="test-simple-001",
        slug="test-simple",
        intent="Test the orchestrator state machine",
        status=JobStatus.QUEUED,
        stage=Stage.OUTLINE,
        cfg=ConfigSnapshot(
            brief=Brief(
                slug="test",
                intent="Test orchestrator",
                tone="informative",
                target_len_sec=60,
            ),
            render={},
            models={},
            modules={},
        ),
    )

    # Save job to database
    if db.create_job(job):
        print(f"✓ Created test job: {job.id}")
    else:
        print("✗ Failed to create test job")
        return

    # Test 1: Start job
    print("\n1. Starting job...")
    await orchestrator.start_job(job)

    # Wait a bit for execution to start
    await asyncio.sleep(3)

    # Check job status
    job_status = await orchestrator.get_job_status(job.id)
    print(f"   Job status: {job_status.status.value}")
    print(f"   Current stage: {job_status.stage.value}")

    # Test 2: Check if job is running or paused
    if job_status.status == JobStatus.RUNNING:
        print("   ✓ Job is running - waiting for completion or gate...")

        # Wait for job to either complete or hit a gate
        max_wait = 45  # seconds
        waited = 0

        while waited < max_wait:
            job_status = await orchestrator.get_job_status(job.id)

            if job_status.status == JobStatus.COMPLETED:
                print("   ✓ Job completed successfully!")
                break
            elif job_status.status == JobStatus.NEEDS_APPROVAL:
                print(f"   ✓ Job paused at {job_status.stage.value} gate")
                break
            elif job_status.status == JobStatus.FAILED:
                print(f"   ✗ Job failed at {job_status.stage.value}")
                # Check what artifacts were created
                artifacts = db.get_job_artifacts(job.id)
                print(f"   Created {len(artifacts)} artifacts before failure")
                for artifact in artifacts:
                    print(
                        f"     - {artifact.kind} ({artifact.stage.value}): {artifact.path}"
                    )
                return
            elif job_status.status == JobStatus.CANCELED:
                print("   ✗ Job was cancelled")
                return

            await asyncio.sleep(1)
            waited += 1
            print(f"   Waiting... ({waited}s) - Stage: {job_status.stage.value}")

        if waited >= max_wait:
            print("   ✗ Timeout waiting for completion")
            return

    elif job_status.status == JobStatus.NEEDS_APPROVAL:
        print(f"   ✓ Job paused at {job_status.stage.value} gate")

        # Test 3: Approve gate
        print(f"\n3. Approving {job_status.stage.value} gate...")
        success = await orchestrator.approve_gate(
            job.id, job_status.stage, "test-operator", "Test approval"
        )

        if success:
            print("   ✓ Gate approved")

            # Wait for next stage or completion
            print("\n4. Waiting for next stage or completion...")
            max_wait = 60  # seconds
            waited = 0

            while waited < max_wait:
                job_status = await orchestrator.get_job_status(job.id)
                if job_status.status == JobStatus.COMPLETED:
                    print("   ✓ Job completed successfully!")
                    break
                elif job_status.status == JobStatus.NEEDS_APPROVAL:
                    print(f"   ✓ Job paused at {job_status.stage.value} gate")
                    break
                elif job_status.status == JobStatus.FAILED:
                    print(f"   ✗ Job failed: {job_status.stage.value}")
                    return

                await asyncio.sleep(1)
                waited += 1
                print(f"   Waiting... ({waited}s) - Stage: {job_status.stage.value}")

            if waited >= max_wait:
                print("   ✗ Timeout waiting for completion")
                return
        else:
            print("   ✗ Gate approval failed")
            return

    elif job_status.status == JobStatus.FAILED:
        print("   ✗ Job failed immediately")
        # Check what artifacts were created
        artifacts = db.get_job_artifacts(job.id)
        print(f"   Created {len(artifacts)} artifacts before failure")
        for artifact in artifacts:
            print(f"     - {artifact.kind} ({artifact.stage.value}): {artifact.path}")
        return

    # Test 5: Check final artifacts
    print("\n5. Checking final job artifacts...")
    artifacts = db.get_job_artifacts(job.id)
    print(f"   Found {len(artifacts)} artifacts:")

    for artifact in artifacts:
        print(f"     - {artifact.kind} ({artifact.stage.value}): {artifact.path}")

    # Test 6: Check events
    print("\n6. Checking job events...")
    events = db.get_job_events(job.id)
    print(f"   Found {len(events)} events:")

    for event in events[:5]:  # Show first 5 events
        print(f"     - {event.event_type}: {event.message}")

    print("\n✓ Orchestrator test completed successfully!")
    print(f"  Final job status: {job_status.status.value}")
    print(f"  Final stage: {job_status.stage.value}")

    # Test 7: Check run directory
    print("\n7. Checking run directory...")
    run_dir = Path("runs") / job.id
    if run_dir.exists():
        print(f"   ✓ Run directory created: {run_dir}")

        # List files in run directory
        files = list(run_dir.rglob("*"))
        print(f"   Found {len(files)} files/directories:")
        for file in files:
            if file.is_file():
                print(f"     - {file.name} ({file.stat().st_size} bytes)")
            else:
                print(f"     - {file.name}/ (directory)")
    else:
        print("   ✗ Run directory not created")


if __name__ == "__main__":
    asyncio.run(test_orchestrator_simple())
