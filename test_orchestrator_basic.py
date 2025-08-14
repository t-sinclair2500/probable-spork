#!/usr/bin/env python3
"""
Basic test script for the orchestrator
Tests core job management functionality without running pipeline stages
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


async def test_orchestrator_basic():
    """Test basic orchestrator functionality"""
    print("Testing basic orchestrator functionality...")
    
    # Test 1: Create and save job
    print("\n1. Creating test job...")
    job = Job(
        id="test-basic-004",
        slug="test-basic-4",
        intent="Test basic orchestrator functionality",
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
    
    # Test 2: Check job retrieval
    print("\n2. Testing job retrieval...")
    retrieved_job = db.get_job(job.id)
    if retrieved_job:
        print(f"   ✓ Retrieved job: {retrieved_job.slug}")
        print(f"   Status: {retrieved_job.status.value}")
        print(f"   Stage: {retrieved_job.stage.value}")
    else:
        print("   ✗ Failed to retrieve job")
        return
    
    # Test 3: Test job status update
    print("\n3. Testing job status update...")
    if db.update_job_status(job.id, JobStatus.RUNNING, Stage.RESEARCH):
        print("   ✓ Updated job status to running")
        
        # Verify update
        updated_job = db.get_job(job.id)
        if updated_job.status == JobStatus.RUNNING and updated_job.stage == Stage.RESEARCH:
            print("   ✓ Status update verified")
        else:
            print("   ✗ Status update verification failed")
            return
    else:
        print("   ✗ Failed to update job status")
        return
    
    # Test 4: Test event logging
    print("\n4. Testing event logging...")
    from fastapi_app.models import Event
    
    test_event = Event(
        event_type="test_event",
        message="Test event message",
        metadata={"test": True}
    )
    
    if db.add_event(job.id, test_event):
        print("   ✓ Added test event")
        
        # Verify event
        events = db.get_job_events(job.id)
        if events:
            print(f"   ✓ Retrieved {len(events)} events")
            latest_event = events[0]  # Most recent first
            print(f"   Latest event: {latest_event.event_type} - {latest_event.message}")
        else:
            print("   ✗ No events retrieved")
            return
    else:
        print("   ✗ Failed to add event")
        return
    
    # Test 5: Test gate management
    print("\n5. Testing gate management...")
    
    # First, let's check if there are any existing gates
    updated_job = db.get_job(job.id)
    print(f"   Current gates: {len(updated_job.gates)}")
    
    # Try to create/update gate decision
    if db.create_or_update_gate(job.id, Stage.SCRIPT, True, "test-operator", "Test approval"):
        print("   ✓ Updated gate decision")
        
        # Verify gate
        updated_job = db.get_job(job.id)
        gate_found = False
        for gate in updated_job.gates:
            if gate.stage == Stage.SCRIPT and gate.approved:
                gate_found = True
                print(f"   ✓ Gate {gate.stage.value} approved by {gate.by}")
                break
        
        if not gate_found:
            print("   ✗ Gate not found in job")
            print("   Available gates:")
            for gate in updated_job.gates:
                print(f"     - {gate.stage.value}: approved={gate.approved}, by={gate.by}")
            return
    else:
        print("   ✗ Failed to update gate decision")
        return
    
    # Test 6: Test artifact management
    print("\n6. Testing artifact management...")
    from fastapi_app.models import Artifact
    
    test_artifact = Artifact(
        stage=Stage.OUTLINE,
        kind="test",
        path="/tmp/test.txt",
        meta={"test": True, "size": 100}
    )
    
    if db.add_artifact(job.id, test_artifact):
        print("   ✓ Added test artifact")
        
        # Verify artifact
        artifacts = db.get_job_artifacts(job.id)
        if artifacts:
            print(f"   ✓ Retrieved {len(artifacts)} artifacts")
            for artifact in artifacts:
                print(f"     - {artifact.kind} ({artifact.stage.value}): {artifact.path}")
        else:
            print("   ✗ No artifacts retrieved")
            return
    else:
        print("   ✗ Failed to add artifact")
        return
    
    # Test 7: Test job listing
    print("\n7. Testing job listing...")
    all_jobs = db.list_jobs()
    if all_jobs:
        print(f"   ✓ Retrieved {len(all_jobs)} jobs")
        for job_item in all_jobs:
            print(f"     - {job_item.id}: {job_item.slug} ({job_item.status.value})")
    else:
        print("   ✗ No jobs retrieved")
        return
    
    # Test 8: Test orchestrator instance
    print("\n8. Testing orchestrator instance...")
    if orchestrator:
        print("   ✓ Orchestrator instance exists")
        print(f"   Active jobs: {len(await orchestrator.list_active_jobs())}")
        
        # Test job status retrieval
        job_status = await orchestrator.get_job_status(job.id)
        if job_status:
            print(f"   ✓ Retrieved job status via orchestrator: {job_status.status.value}")
        else:
            print("   ✗ Failed to retrieve job status via orchestrator")
            return
    else:
        print("   ✗ Orchestrator instance not found")
        return
    
    print(f"\n✓ Basic orchestrator test completed successfully!")
    print(f"  Test job ID: {job.id}")
    print(f"  Final status: {job.status.value}")
    print(f"  Final stage: {job.stage.value}")


if __name__ == "__main__":
    asyncio.run(test_orchestrator_basic())
