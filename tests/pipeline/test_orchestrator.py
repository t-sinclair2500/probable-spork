#!/usr/bin/env python3
"""
Test script for the orchestrator state machine
"""

import asyncio
import json
import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from fastapi_app.models import Job, JobStatus, Stage, ConfigSnapshot, Brief
from fastapi_app.orchestrator import orchestrator
from fastapi_app.db import db


async def test_orchestrator():
    """Test the orchestrator state machine"""
    print("Testing orchestrator state machine...")
    
    # Create a test job
    job = Job(
        id="test-job-001",
        slug="test-orchestrator",
        intent="Test the orchestrator state machine",
        status=JobStatus.QUEUED,
        stage=Stage.OUTLINE,
        cfg=ConfigSnapshot(
            brief=Brief(
                slug="test",
                intent="Test orchestrator",
                tone="informative",
                target_len_sec=60
            ),
            render={},
            models={},
            modules={}
        )
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
    await asyncio.sleep(2)
    
    # Check job status
    job_status = await orchestrator.get_job_status(job.id)
    print(f"   Job status: {job_status.status.value}")
    print(f"   Current stage: {job_status.stage.value}")
    
    # Test 2: Wait for first gate (script stage)
    print("\n2. Waiting for script gate...")
    max_wait = 30  # seconds
    waited = 0
    
    while waited < max_wait:
        job_status = await orchestrator.get_job_status(job.id)
        if job_status.status == JobStatus.NEEDS_APPROVAL:
            print(f"   ✓ Job paused at {job_status.stage.value} gate")
            break
        await asyncio.sleep(1)
        waited += 1
        print(f"   Waiting... ({waited}s)")
    
    if waited >= max_wait:
        print("   ✗ Timeout waiting for gate")
        return
    
    # Test 3: Approve gate
    print(f"\n3. Approving {job_status.stage.value} gate...")
    success = await orchestrator.approve_gate(job.id, job_status.stage, "test-operator", "Test approval")
    
    if success:
        print("   ✓ Gate approved")
    else:
        print("   ✗ Gate approval failed")
        return
    
    # Test 4: Wait for next gate or completion
    print("\n4. Waiting for next gate or completion...")
    max_wait = 60  # seconds
    waited = 0
    
    while waited < max_wait:
        job_status = await orchestrator.get_job_status(job.id)
        if job_status.status == JobStatus.COMPLETED:
            print(f"   ✓ Job completed successfully!")
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
    
    # Test 5: Check artifacts
    print("\n5. Checking job artifacts...")
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
    
    print(f"\n✓ Orchestrator test completed successfully!")
    print(f"  Final job status: {job_status.status.value}")
    print(f"  Final stage: {job_status.stage.value}")


if __name__ == "__main__":
    asyncio.run(test_orchestrator())
