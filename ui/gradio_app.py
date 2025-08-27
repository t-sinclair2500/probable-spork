"""
Gradio UI for Operator Console
Provides a web interface for job management and HITL gate decisions.
"""

import gradio as gr
import logging
import requests
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import threading
import queue

logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://127.0.0.1:8008/api/v1"
DEFAULT_HEADERS = {"Content-Type": "application/json"}

class APIClient:
    """Client for communicating with FastAPI backend"""
    
    def __init__(self, admin_token: str):
        self.admin_token = admin_token
        self.headers = {
            **DEFAULT_HEADERS,
            "Authorization": f"Bearer {admin_token}"
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to API"""
        url = f"{API_BASE_URL}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return {"error": str(e)}
    
    def get_config(self) -> Dict:
        """Get operator configuration"""
        return self._make_request("GET", "/config/operator")
    
    def validate_config(self) -> Dict:
        """Validate configuration"""
        return self._make_request("POST", "/config/validate")
    
    def list_jobs(self) -> List[Dict]:
        """List all jobs"""
        result = self._make_request("GET", "/jobs")
        return result if isinstance(result, list) else []
    
    def get_job(self, job_id: str) -> Dict:
        """Get specific job"""
        return self._make_request("GET", f"/jobs/{job_id}")
    
    def create_job(self, job_data: Dict) -> Dict:
        """Create new job"""
        return self._make_request("POST", "/jobs", job_data)
    
    def approve_gate(self, job_id: str, stage: str, notes: str = "", patch: Optional[Dict] = None) -> Dict:
        """Approve gate for job stage"""
        data = {
            "decision": "approved",
            "stage": stage,
            "notes": notes,
            "operator": "gradio_ui",
            "patch": patch
        }
        return self._make_request("POST", f"/jobs/{job_id}/approve", data)
    
    def reject_gate(self, job_id: str, stage: str, notes: str = "", patch: Optional[Dict] = None) -> Dict:
        """Reject gate for job stage"""
        data = {
            "decision": "rejected",
            "stage": stage,
            "notes": notes,
            "operator": "gradio_ui",
            "patch": patch
        }
        return self._make_request("POST", f"/jobs/{job_id}/reject", data)
    
    def resume_job(self, job_id: str) -> Dict:
        """Resume paused job"""
        return self._make_request("POST", f"/jobs/{job_id}/resume")
    
    def get_job_events(self, job_id: str, limit: int = 50) -> List[Dict]:
        """Get job events (polling fallback)"""
        result = self._make_request("GET", f"/jobs/{job_id}/events?limit={limit}")
        return result.get("events", []) if isinstance(result, dict) else []
    
    def compile_brief(self, free_text: str, preset: str, testing_mode: str, seed: int) -> Dict:
        """Compile a free-text brief into structured format"""
        try:
            data = {
                "free_text_brief": free_text,
                "preset": preset,
                "testing_mode": testing_mode,
                "seed": seed
            }
            return self._make_request("POST", "/compile-brief", data)
        except Exception as e:
            logger.error(f"Failed to compile brief: {e}")
            return {"error": str(e)}
    
    def create_job_with_brief(self, slug: str, intent: str, brief: Dict, preset: str, testing_mode: str, seed: int) -> Dict:
        """Create a new job with the compiled brief"""
        try:
            # Add metadata to the brief
            brief["meta"] = {
                "preset": preset,
                "testing_mode": testing_mode,
                "seed": seed
            }
            
            job_data = {
                "slug": slug,
                "intent": intent,
                "brief": brief,
                "meta": {
                    "free_text_brief": brief.get("notes", ""),
                    "preset": preset,
                    "testing_mode": testing_mode,
                    "seed": seed
                }
            }
            return self._make_request("POST", "/jobs", job_data)
        except Exception as e:
            logger.error(f"Failed to create job with brief: {e}")
            return {"error": str(e)}

class EventStreamer:
    """Manages real-time event streaming with polling fallback"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        self.active_streams = {}
        self.stop_event = threading.Event()
    
    def start_streaming(self, job_id: str, callback):
        """Start streaming events for a job"""
        if job_id in self.active_streams:
            return
        
        self.active_streams[job_id] = callback
        thread = threading.Thread(target=self._stream_events, args=(job_id, callback))
        thread.daemon = True
        thread.start()
    
    def stop_streaming(self, job_id: str):
        """Stop streaming events for a job"""
        if job_id in self.active_streams:
            del self.active_streams[job_id]
    
    def _stream_events(self, job_id: str, callback):
        """Stream events with polling fallback"""
        last_event_time = None
        
        while not self.stop_event.is_set() and job_id in self.active_streams:
            try:
                # Get events since last check
                events = self.api_client.get_job_events(job_id, limit=100)
                
                if events:
                    # Find new events
                    new_events = []
                    for event in events:
                        event_time = event.get("ts", event.get("timestamp"))
                        if not last_event_time or event_time > last_event_time:
                            new_events.append(event)
                            last_event_time = event_time
                    
                    if new_events:
                        callback(new_events)
                
                time.sleep(2)  # Poll every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in event stream for job {job_id}: {e}")
                time.sleep(5)  # Wait longer on error
    
    def stop_all(self):
        """Stop all event streams"""
        self.stop_event.set()
        self.active_streams.clear()

def create_config_launch_page(api_client: APIClient = None, event_streamer: EventStreamer = None):
    """Create the Config & Launch page"""
    
    def load_current_config():
        """Load current configuration from API"""
        client = get_api_client()
        if not client:
            return "Please initialize API client first"
        
        try:
            config = client.get_config()
            if "error" not in config:
                return json.dumps(config, indent=2)
            else:
                return f"Error loading config: {config['error']}"
        except Exception as e:
            return f"Failed to load config: {str(e)}"
    
    def validate_config():
        """Validate configuration via API"""
        client = get_api_client()
        if not client:
            return "Please initialize API client first", "error"
        
        try:
            result = client.validate_config()
            if "error" not in result:
                return "Configuration is valid", "success"
            else:
                return f"Configuration validation failed: {result['error']}", "error"
        except Exception as e:
            return f"Validation error: {str(e)}", "error"
    
    def create_job(slug, intent, target_len_sec, tone, testing_mode, notes):
        """Create a new job"""
        client = get_api_client()
        if not client:
            return "Please initialize API client first", "error"
        
        try:
            if not slug or not intent:
                return "Slug and intent are required", "error"
            
            # Prepare job data
            job_data = {
                "slug": slug,
                "intent": intent,
                "brief_config": {
                    "slug": slug,
                    "intent": intent,
                    "target_len_sec": int(target_len_sec) if target_len_sec else 90,
                    "tone": tone or "informative",
                    "testing_mode": testing_mode or "reuse"
                }
            }
            
            # Create job via API
            result = client.create_job(job_data)
            
            if "error" not in result:
                job_id = result.get("id", "unknown")
                return f"Job created successfully! ID: {job_id}", "success"
            else:
                return f"Failed to create job: {result['error']}", "error"
                
        except Exception as e:
            return f"Job creation error: {str(e)}", "error"
    
    with gr.Blocks(title="Config & Launch") as page:
        gr.Markdown("# Configuration & Job Launch")
        gr.Markdown("Configure pipeline settings and launch new jobs")
        
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("## Current Configuration")
                config_display = gr.Code(
                    label="Current Config",
                    language="json",
                    lines=20,
                    interactive=False
                )
                gr.Button("Refresh Config", value="Refresh").click(
                    fn=load_current_config,
                    outputs=config_display
                )
                
                gr.Markdown("## Configuration Validation")
                validate_btn = gr.Button("Validate Config", variant="secondary")
                validation_result = gr.Textbox(
                    label="Validation Result",
                    interactive=False,
                    lines=2
                )
                
            with gr.Column(scale=1):
                gr.Markdown("## Create New Job")
                
                slug_input = gr.Textbox(
                    label="Topic Slug",
                    placeholder="e.g., design-history, tech-review, how-to-guide",
                    info="Unique identifier for this job"
                )
                
                intent_input = gr.Textbox(
                    label="Intent",
                    placeholder="e.g., narrative_history",
                    info="Content intent/purpose"
                )
                
                target_len_input = gr.Number(
                    label="Target Length (seconds)",
                    value=90,
                    minimum=30,
                    maximum=600,
                    step=15
                )
                
                tone_input = gr.Dropdown(
                    label="Tone",
                    choices=["informative", "curious", "authoritative", "conversational", "professional"],
                    value="informative"
                )
                
                testing_mode_input = gr.Radio(
                    label="Testing Mode",
                    choices=["reuse", "live"],
                    value="reuse",
                    info="reuse: use cached assets, live: download new assets"
                )
                
                notes_input = gr.Textbox(
                    label="Notes",
                    placeholder="Optional notes for this job",
                    lines=3
                )
                
                create_btn = gr.Button("Create Job", variant="primary")
                job_result = gr.Textbox(
                    label="Job Creation Result",
                    interactive=False,
                    lines=2
                )
        
        # Load initial config
        page.load(load_current_config, outputs=config_display)
        
        # Wire up events
        validate_btn.click(
            fn=validate_config,
            outputs=[validation_result, validation_result]
        )
        
        create_btn.click(
            fn=create_job,
            inputs=[slug_input, intent_input, target_len_input, tone_input, testing_mode_input, notes_input],
            outputs=[job_result, job_result]
        )
        
        # Quick Brief Panel
        gr.Markdown("---")
        gr.Markdown("## Quick Brief")
        gr.Markdown("Enter a natural language brief and let the system parse it automatically")
        
        with gr.Row():
            with gr.Column(scale=2):
                brief_text_input = gr.Textbox(
                    label="Free-Text Brief",
                    placeholder="e.g., 3-4 min explainer on baby sleep regression, comforting tone, linen texture, CTA off",
                    lines=3,
                    info="Describe your content needs in plain English"
                )
                
                with gr.Row():
                    preset_input = gr.Dropdown(
                        label="Style Preset",
                        choices=["(none)", "print_soft", "print_strong", "flat_noise", "halftone_classic", "vintage_paper", "minimal", "modern_flat", "off"],
                        value="(none)",
                        info="Optional texture/style preset"
                    )
                    
                    testing_mode_quick = gr.Radio(
                        label="Testing Mode",
                        choices=["reuse", "live"],
                        value="reuse",
                        info="reuse: use cached assets, live: download new assets"
                    )
                    
                    seed_input = gr.Number(
                        label="Seed",
                        value=42,
                        minimum=1,
                        maximum=9999,
                        step=1,
                        info="Random seed for consistent generation"
                    )
                
                with gr.Row():
                    preview_btn = gr.Button("Preview Brief", variant="secondary")
                    run_btn = gr.Button("Run Job", variant="primary", visible=False)
                
                brief_preview = gr.Code(
                    label="Compiled Brief Preview",
                    language="json",
                    lines=15,
                    interactive=False,
                    visible=False
                )
                
                # Hidden state to store the compiled brief object
                compiled_brief_state = gr.State()
                
                assumptions_display = gr.Markdown(
                    label="Assumptions Made",
                    visible=False
                )
                
                quick_brief_result = gr.Textbox(
                    label="Quick Brief Result",
                    interactive=False,
                    lines=2,
                    visible=False
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### Quick Brief Examples")
                gr.Markdown("""
                **Duration & Type:**
                - "3-4 min explainer on baby sleep regression"
                - "90 second history of modern design principles"
                - "2 minute tutorial on Python decorators"
                
                **Tone & Style:**
                - "comforting tone, linen texture"
                - "authoritative, modern flat style"
                - "conversational, vintage paper feel"
                
                **CTA & Monetization:**
                - "CTA off, no monetization"
                - "include lead magnet, CTA on"
                """)
        
        # Quick Brief functionality
        def preview_brief(free_text, preset, testing_mode, seed):
            """Preview the compiled brief"""
            if not free_text.strip():
                return None, None, None, None, gr.Row(visible=False), gr.Button(visible=False)
            
            client = get_api_client()
            if not client:
                return "Please initialize API client first", None, None, None, gr.Row(visible=False), gr.Button(visible=False)
            
            try:
                result = client.compile_brief(free_text, preset, testing_mode, seed)
                if "error" in result:
                    return f"Error: {result['error']}", None, None, None, gr.Row(visible=False), gr.Button(visible=False)
                
                compiled_brief = result.get("compiled_brief", {})
                assumptions = result.get("assumptions", [])
                
                # Format assumptions
                assumptions_text = "### Assumptions Made:\n"
                if assumptions:
                    for assumption in assumptions:
                        assumptions_text += f"- {assumption}\n"
                else:
                    assumptions_text += "- No assumptions made, all fields specified\n"
                
                return (
                    json.dumps(compiled_brief, indent=2),
                    assumptions_text,
                    compiled_brief,
                    gr.Row(visible=True),
                    gr.Button(visible=True)
                )
                
            except Exception as e:
                return f"Error: {str(e)}", None, None, None, gr.Row(visible=False), gr.Button(visible=False)
        
        def run_quick_brief_job(free_text, preset, testing_mode, seed, compiled_brief_json):
            """Run a job with the compiled brief"""
            if not compiled_brief_json:
                return "No compiled brief available", "error"
            
            client = get_api_client()
            if not client:
                return "Please initialize API client first", "error"
            
            try:
                # Parse the compiled brief JSON back to dict
                if isinstance(compiled_brief_json, str):
                    compiled_brief = json.loads(compiled_brief_json)
                else:
                    compiled_brief = compiled_brief_json
                
                # Generate slug from title or use timestamp
                import time
                slug = compiled_brief.get("title", "").lower().replace(" ", "-").replace("guide-on-", "").replace(" ", "-")
                if not slug or slug == "guide-on":
                    slug = f"quick-brief-{int(time.time())}"
                
                # Create job with compiled brief
                result = client.create_job_with_brief(slug, "narrative_history", compiled_brief, preset, testing_mode, seed)
                
                if "error" not in result:
                    job_id = result.get("id", "unknown")
                    return f"Job created successfully! ID: {job_id}", "success"
                else:
                    return f"Failed to create job: {result['error']}", "error"
                    
            except Exception as e:
                return f"Job creation error: {str(e)}", "error"
        
        # Wire up Quick Brief events
        preview_btn.click(
            fn=preview_brief,
            inputs=[brief_text_input, preset_input, testing_mode_quick, seed_input],
            outputs=[brief_preview, assumptions_display, compiled_brief_state, run_btn, run_btn]
        ).then(
            fn=lambda: gr.Code(visible=True),
            outputs=[brief_preview]
        ).then(
            fn=lambda: gr.Markdown(visible=True),
            outputs=[assumptions_display]
        ).then(
            fn=lambda: gr.Textbox(visible=True),
            outputs=[quick_brief_result]
        )
        
        run_btn.click(
            fn=run_quick_brief_job,
            inputs=[brief_text_input, preset_input, testing_mode_quick, seed_input, compiled_brief_state],
            outputs=[quick_brief_result, quick_brief_result]
        )
    
    return page

def create_job_console_page(api_client: APIClient = None, event_streamer: EventStreamer = None):
    """Create the Job Console page"""
    
    def load_jobs():
        """Load list of jobs"""
        client = get_api_client()
        if not client:
            return gr.Dropdown(choices=["Please initialize API client first"], value=None)
        
        try:
            jobs = client.list_jobs()
            if jobs:
                choices = [f"{job['slug']} ({job['status']})" for job in jobs]
                values = [job['id'] for job in jobs]
                return gr.Dropdown(choices=choices, value=values[0] if values else None)
            else:
                return gr.Dropdown(choices=["No jobs found"], value=None)
        except Exception as e:
            return gr.Dropdown(choices=[f"Error: {str(e)}"], value=None)
    
    def select_job(job_id):
        """Select a job and load its details"""
        if not job_id:
            return "Please select a job", None, None, None, None, None, None, None
        
        client = get_api_client()
        if not client:
            return "Please initialize API client first", None, None, None, None, None, None, None
        
        try:
            job = client.get_job(job_id)
            if "error" in job:
                return f"Error loading job: {job['error']}", None, None, None, None, None, None, None
            
            # Extract job info
            status = job.get("status", "unknown")
            stage = job.get("stage", "unknown")
            created_at = job.get("created_at", "unknown")
            updated_at = job.get("updated_at", "unknown")
            
            # Build stage cards
            stage_cards = build_stage_cards(job)
            
            # Build gate controls
            gate_controls = build_gate_controls(job)
            
            # Build artifacts list
            artifacts_list = build_artifacts_list(job)
            
            return (
                f"**Job:** {job.get('slug', 'Unknown')}\n**Status:** {status}\n**Stage:** {stage}\n**Created:** {created_at}\n**Updated:** {updated_at}",
                stage_cards,
                gate_controls,
                artifacts_list,
                status,
                stage,
                job_id,
                "Job loaded successfully"
            )
            
        except Exception as e:
            return f"Error: {str(e)}", None, None, None, None, None, None, None
    
    def build_stage_cards(job):
        """Build stage progress cards"""
        stages = ["outline", "research", "script", "storyboard", "assets", "animatics", "audio", "assemble", "acceptance"]
        current_stage = job.get("stage", "unknown")
        status = job.get("status", "unknown")
        
        cards = []
        for stage in stages:
            stage_status = "pending"
            if stage == current_stage:
                stage_status = "active" if status == "running" else "paused"
            elif stages.index(stage) < stages.index(current_stage):
                stage_status = "completed"
            
            # Find gate info
            gate_info = ""
            for gate in job.get("gates", []):
                if gate.get("stage") == stage:
                    if gate.get("approved") is True:
                        stage_status = "completed"
                        gate_info = f"Approved by {gate.get('by', 'unknown')}"
                    elif gate.get("approved") is False:
                        stage_status = "rejected"
                        gate_info = f"Rejected by {gate.get('by', 'unknown')}"
                    elif gate.get("required", True):
                        stage_status = "waiting"
                        gate_info = "Waiting for approval"
            
            cards.append(f"### {stage.title()}\n**Status:** {stage_status}\n{gate_info}")
        
        return "\n\n".join(cards)
    
    def build_gate_controls(job):
        """Build gate approval controls"""
        current_stage = job.get("stage", "unknown")
        gates = job.get("gates", [])
        
        controls = []
        for gate in gates:
            if gate.get("stage") == current_stage and gate.get("approved") is None and gate.get("required", True):
                controls.append(f"### Gate: {gate.get('stage', 'unknown').title()}\n**Required:** {gate.get('required', True)}\n**Status:** Waiting for decision")
        
        if not controls:
            controls.append("### No gates requiring approval at this stage")
        
        return "\n\n".join(controls)
    
    def build_artifacts_list(job):
        """Build artifacts list"""
        artifacts = job.get("artifacts", [])
        
        if not artifacts:
            return "No artifacts generated yet"
        
        artifact_list = []
        for artifact in artifacts:
            stage = artifact.get("stage", "unknown")
            kind = artifact.get("kind", "unknown")
            path = artifact.get("path", "unknown")
            meta = artifact.get("meta", {})
            
            artifact_list.append(f"**{stage.title()} - {kind}:** {path}")
            if meta:
                meta_str = ", ".join([f"{k}: {v}" for k, v in meta.items()])
                artifact_list.append(f"  *{meta_str}*")
        
        return "\n\n".join(artifact_list)
    
    def approve_gate(job_id, stage, notes, patch_json):
        """Approve a gate"""
        if not job_id or not stage:
            return "Job ID and stage are required", "error"
        
        client = get_api_client()
        if not client:
            return "API client not initialized", "error"
        
        try:
            # Parse patch if provided
            patch = None
            if patch_json and patch_json.strip():
                try:
                    patch = json.loads(patch_json)
                except json.JSONDecodeError:
                    return "Invalid JSON patch format", "error"
            
            result = client.approve_gate(job_id, stage, notes, patch)
            if "error" not in result:
                return f"Gate {stage} approved successfully!", "success"
            else:
                return f"Failed to approve gate: {result['error']}", "error"
        except Exception as e:
            return f"Approval error: {str(e)}", "error"
    
    def reject_gate(job_id, stage, notes, patch_json):
        """Reject a gate"""
        if not job_id or not stage:
            return "Job ID and stage are required", "error"
        
        client = get_api_client()
        if not client:
            return "API client not initialized", "error"
        
        try:
            # Parse patch if provided
            patch = None
            if patch_json and patch_json.strip():
                try:
                    patch = json.loads(patch_json)
                except json.JSONDecodeError:
                    return "Invalid JSON patch format", "error"
            
            result = client.reject_gate(job_id, stage, notes, patch)
            if "error" not in result:
                return f"Gate {stage} rejected successfully!", "success"
            else:
                return f"Failed to reject gate: {result['error']}", "error"
        except Exception as e:
            return f"Rejection error: {str(e)}", "error"
    
    def resume_job(job_id):
        """Resume a paused job"""
        if not job_id:
            return "Job ID is required", "error"
        
        client = get_api_client()
        if not client:
            return "API client not initialized", "error"
        
        try:
            result = client.resume_job(job_id)
            if "error" not in result:
                return f"Job resumed successfully!", "success"
            else:
                return f"Failed to resume job: {result['error']}", "error"
        except Exception as e:
            return f"Resume error: {str(e)}", "error"
    
    def update_events(events):
        """Update events display (called by event streamer)"""
        if events:
            event_text = "\n\n".join([
                f"**{event.get('ts', 'unknown')}** - {event.get('type', 'unknown')}: {event.get('message', '')}"
                for event in events
            ])
            return event_text
        return "No new events"
    
    with gr.Blocks(title="Job Console") as page:
        gr.Markdown("# Job Console")
        gr.Markdown("Monitor job progress and manage HITL gates")
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## Job Selection")
                refresh_jobs_btn = gr.Button("Refresh Jobs", variant="secondary")
                job_dropdown = gr.Dropdown(
                    label="Select Job",
                    choices=["Please initialize API client first"],
                    value=None
                )
                select_job_btn = gr.Button("Load Job Details", variant="primary")
                
                gr.Markdown("## Job Info")
                job_info = gr.Markdown("Select a job to view details")
                
                gr.Markdown("## Gate Actions")
                gate_stage_input = gr.Dropdown(
                    label="Gate Stage",
                    choices=["script", "storyboard", "assets", "audio"],
                    value="script"
                )
                gate_notes_input = gr.Textbox(
                    label="Notes",
                    placeholder="Optional notes for gate decision",
                    lines=2
                )
                gate_patch_input = gr.Code(
                    label="JSON Patch (optional)",
                    language="json",
                    lines=5
                )
                
                with gr.Row():
                    approve_btn = gr.Button("Approve", variant="success")
                    reject_btn = gr.Button("Reject", variant="stop")
                
                resume_btn = gr.Button("Resume Job", variant="secondary")
                gate_result = gr.Textbox(
                    label="Gate Action Result",
                    interactive=False,
                    lines=2
                )
            
            with gr.Column(scale=2):
                gr.Markdown("## Stage Progress")
                stage_cards = gr.Markdown("Select a job to view stage progress")
                
                gr.Markdown("## Gate Controls")
                gate_controls = gr.Markdown("Select a job to view gate controls")
                
                gr.Markdown("## Artifacts")
                artifacts_list = gr.Markdown("Select a job to view artifacts")
                
                gr.Markdown("## Live Events")
                events_display = gr.Textbox(
                    label="Event Stream",
                    lines=10,
                    interactive=False
                )
        
        # Hidden inputs for job context
        current_job_id = gr.State(None)
        current_status = gr.State(None)
        current_stage = gr.State(None)
        event_status = gr.State("No events")
        
        # Wire up events
        refresh_jobs_btn.click(
            fn=load_jobs,
            outputs=job_dropdown
        )
        
        select_job_btn.click(
            fn=select_job,
            inputs=[job_dropdown],
            outputs=[job_info, stage_cards, gate_controls, artifacts_list, current_status, current_stage, current_job_id, event_status]
        )
        
        approve_btn.click(
            fn=approve_gate,
            inputs=[current_job_id, gate_stage_input, gate_notes_input, gate_patch_input],
            outputs=[gate_result, gate_result]
        )
        
        reject_btn.click(
            fn=reject_gate,
            inputs=[current_job_id, gate_stage_input, gate_notes_input, gate_patch_input],
            outputs=[gate_result, gate_result]
        )
        
        resume_btn.click(
            fn=resume_job,
            inputs=[current_job_id],
            outputs=[gate_result, gate_result]
        )
        
        # Load jobs on page load
        page.load(load_jobs, outputs=job_dropdown)
    
    return page

def create_ui() -> gr.Blocks:
    """Create the complete Gradio interface"""
    logger.info("Creating Gradio UI")
    
    with gr.Blocks(title="Probable Spork Operator Console") as interface:
        gr.Markdown("# Probable Spork Operator Console")
        gr.Markdown("Pipeline orchestration and HITL gate management")
        
        # Authentication
        with gr.Row():
            admin_token_input = gr.Textbox(
                label="Admin Token",
                placeholder="Enter admin token",
                type="password",
                info="Set ADMIN_TOKEN env var or use default: default-admin-token-change-me"
            )
            init_btn = gr.Button("Initialize", variant="primary")
            auth_status = gr.Textbox(
                label="Authentication Status",
                value="Enter admin token and click Initialize",
                interactive=False
            )
        
        # Main interface (only visible after auth)
        with gr.Row(visible=False) as main_interface:
            with gr.Tabs():
                with gr.TabItem("Config & Launch"):
                    config_page = create_config_launch_page()
                
                with gr.TabItem("Job Console"):
                    console_page = create_job_console_page()
        
        # Wire up authentication
        def on_auth_success():
            return gr.Row(visible=True)
        
        def init_api_client(token):
            """Initialize API client with admin token"""
            if token:
                # Create API client and store in global state
                global api_client_instance, event_streamer_instance
                api_client_instance = APIClient(token)
                event_streamer_instance = EventStreamer(api_client_instance)
                return "API client initialized"
            else:
                return "Admin token required"
        
        init_btn.click(
            fn=init_api_client,
            inputs=[admin_token_input],
            outputs=[auth_status]
        ).then(
            fn=on_auth_success,
            outputs=[main_interface]
        )
        
        # Set default token
        interface.load(lambda: "default-admin-token-change-me", outputs=admin_token_input)
    
    return interface

# Global instances for API client and event streamer
api_client_instance = None
event_streamer_instance = None

def get_api_client():
    """Get the current API client instance"""
    global api_client_instance
    return api_client_instance

def get_event_streamer():
    """Get the current event streamer instance"""
    global event_streamer_instance
    return event_streamer_instance

def launch_ui(port: int = 7860, share: bool = False, debug: bool = False):
    """Launch the Gradio interface"""
    logger.info(f"Launching Gradio UI on port {port}")
    
    try:
        interface = create_ui()
        interface.launch(
            server_port=port,
            share=share,
            debug=debug,
            show_error=True
        )
    except Exception as e:
        logger.error(f"Failed to launch Gradio UI: {e}")
        raise

if __name__ == "__main__":
    launch_ui()
