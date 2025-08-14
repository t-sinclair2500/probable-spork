"""
Storage Management
Handles artifact storage, file operations, and runs directory management.
"""

import os
import shutil
import logging
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from .models import Artifact, Stage

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages file storage and artifact organization"""
    
    def __init__(self, runs_dir: str = "runs", artifacts_dir: str = "artifacts"):
        self.runs_dir = Path(runs_dir)
        self.artifacts_dir = Path(artifacts_dir)
        self._ensure_directories()
        logger.info("Storage manager initialized")
    
    def _ensure_directories(self) -> None:
        """Ensure required directories exist"""
        self.runs_dir.mkdir(exist_ok=True)
        self.artifacts_dir.mkdir(exist_ok=True)
    
    def create_job_directory(self, job_id: str) -> Path:
        """Create directory structure for a new job"""
        job_dir = self.runs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (job_dir / "artifacts").mkdir(exist_ok=True)
        (job_dir / "logs").mkdir(exist_ok=True)
        
        logger.info(f"Created job directory: {job_dir}")
        return job_dir
    
    def store_artifact(self, job_id: str, artifact: Artifact) -> bool:
        """Store an artifact in the job's directory"""
        try:
            job_dir = self.runs_dir / job_id
            artifacts_dir = job_dir / "artifacts"
            
            # Ensure artifacts directory exists
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # Create stage subdirectory
            stage_dir = artifacts_dir / artifact.stage.value
            stage_dir.mkdir(exist_ok=True)
            
            # Determine artifact filename
            if artifact.kind == "file":
                # For file artifacts, use the basename of the path
                filename = Path(artifact.path).name
            else:
                # For other types, create a descriptive filename
                filename = f"{artifact.stage.value}_{artifact.kind}.json"
            
            artifact_path = stage_dir / filename
            
            # Copy or symlink the artifact
            if os.path.exists(artifact.path):
                if os.path.islink(artifact.path):
                    # If it's already a symlink, copy the target
                    shutil.copy2(artifact.path, artifact_path)
                else:
                    # Create symlink to avoid duplication
                    try:
                        os.symlink(artifact.path, artifact_path)
                    except OSError:
                        # Fallback to copy if symlink fails
                        shutil.copy2(artifact.path, artifact_path)
                
                # Update artifact path to the stored location
                artifact.path = str(artifact_path)
                
                logger.info(f"Stored artifact {artifact.kind} for {job_id} at {artifact_path}")
                return True
            else:
                logger.warning(f"Source artifact not found: {artifact.path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to store artifact {artifact.kind} for {job_id}: {e}")
            return False
    
    def get_artifact_path(self, job_id: str, stage: Stage, kind: str) -> Optional[Path]:
        """Get the path to a specific artifact"""
        try:
            job_dir = self.runs_dir / job_id
            artifacts_dir = job_dir / "artifacts"
            stage_dir = artifacts_dir / stage.value
            
            # Look for artifacts in the stage directory
            if stage_dir.exists():
                for artifact_file in stage_dir.iterdir():
                    if artifact_file.is_file() and kind in artifact_file.name:
                        return artifact_file
            
            return None
        except Exception as e:
            logger.error(f"Failed to get artifact path for {job_id} - {stage} - {kind}: {e}")
            return None
    
    def list_job_artifacts(self, job_id: str) -> List[Artifact]:
        """List all artifacts for a specific job"""
        try:
            artifacts = []
            job_dir = self.runs_dir / job_id
            artifacts_dir = job_dir / "artifacts"
            
            if not artifacts_dir.exists():
                return []
            
            for stage_dir in artifacts_dir.iterdir():
                if stage_dir.is_dir():
                    stage = Stage(stage_dir.name)
                    for artifact_file in stage_dir.iterdir():
                        if artifact_file.is_file():
                            # Determine artifact kind from filename
                            if artifact_file.suffix == '.json':
                                kind = 'json'
                            elif artifact_file.suffix == '.mp4':
                                kind = 'video'
                            elif artifact_file.suffix == '.mp3':
                                kind = 'audio'
                            elif artifact_file.suffix == '.srt':
                                kind = 'captions'
                            elif artifact_file.suffix == '.txt':
                                kind = 'text'
                            else:
                                kind = 'file'
                            
                            artifact = Artifact(
                                stage=stage,
                                kind=kind,
                                path=str(artifact_file),
                                meta={
                                    "size": artifact_file.stat().st_size,
                                    "modified": artifact_file.stat().st_mtime
                                }
                            )
                            artifacts.append(artifact)
            
            return artifacts
        except Exception as e:
            logger.error(f"Failed to list artifacts for {job_id}: {e}")
            return []
    
    def cleanup_job(self, job_id: str) -> bool:
        """Clean up all artifacts for a completed/failed job"""
        try:
            job_dir = self.runs_dir / job_id
            if job_dir.exists():
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up job directory: {job_dir}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cleanup job {job_id}: {e}")
            return False
    
    def resolve_pipeline_paths(self, job_id: str, stage: Stage) -> Dict[str, Path]:
        """Resolve paths for pipeline artifacts based on stage"""
        job_dir = self.runs_dir / job_id
        artifacts_dir = job_dir / "artifacts"
        
        paths = {
            "job_dir": job_dir,
            "artifacts_dir": artifacts_dir,
            "stage_dir": artifacts_dir / stage.value,
            "logs_dir": job_dir / "logs"
        }
        
        # Create directories if they don't exist
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        
        return paths
    
    def copy_pipeline_artifact(self, source_path: str, job_id: str, stage: Stage, filename: str) -> Optional[Path]:
        """Copy a pipeline artifact to the job's artifacts directory"""
        try:
            if not os.path.exists(source_path):
                logger.warning(f"Source artifact not found: {source_path}")
                return None
            
            paths = self.resolve_pipeline_paths(job_id, stage)
            target_path = paths["stage_dir"] / filename
            
            # Copy the artifact
            shutil.copy2(source_path, target_path)
            logger.info(f"Copied artifact {source_path} to {target_path}")
            
            return target_path
        except Exception as e:
            logger.error(f"Failed to copy artifact {source_path}: {e}")
            return None


# Global storage manager instance
storage_manager = StorageManager()
