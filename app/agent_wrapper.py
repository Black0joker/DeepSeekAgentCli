import sys
import os
import json
import asyncio
import threading,traceback
from pathlib import Path
from typing import Callable, Dict, Any, Optional

AgentSystemMd = os.path.join(os.path.dirname(__file__), "agent", "system.md")

# Import agent modules
from app.agent.module import DeepSeekClient, full_parse_sse, execute_tool, create_client, load_system_prompt
from app.agent.logger import Logger
from app.agent.config import Config

class AgentWrapper:
    """
    Wraps the autonomous agent for integration with the Textual UI.
    
    The agent runs in a separate thread and communicates with the UI via callbacks.
    """
    
    def __init__(self, app):
        self.app = app
        self.client = None
        self.session_id = None
        self.parent_message_id = None
        self.system_prompt = None
        self.running = False
        self.thread = None
        self.callbacks = {}
        self.pending_response = None
        self.response_event = threading.Event()
        self.pending_permission_response = None
        self.permission_response_event = threading.Event()
        self.session_allowed_tools = set()
        self.system_prompt_sent = threading.Event()
        
    def initialize(self):
        """Initialize the agent client and session. Does NOT send the system prompt."""
        try:
            Config.load()
            self.client = create_client()
            self.system_prompt = load_system_prompt(AgentSystemMd)
            
            self.session_id = self.client.create_chat()
            
            Logger.success(f"Agent initialized with session: {self.session_id}")
            return True
        except Exception as e:
            Logger.error(f"Agent initialization failed: {e}")
            return False
    
    def initialize_in_thread(self, callback):
        """Initialize the agent in a background thread.
        
        Args:
            callback: Called on the main thread with a boolean indicating success.
        """
        def run_init():
            success = self.initialize()
            self.app.call_from_thread(callback, success)
        thread = threading.Thread(target=run_init, daemon=True)
        thread.start()
    
    def register_callbacks(self, callbacks: Dict[str, Callable]):
        """
        Register callbacks for UI updates.
        
        Expected callbacks:
        - on_message: Called when agent sends a message
        - on_tool: Called when agent executes a tool
        - on_status: Called when agent status changes
        - on_question: Called when agent asks a question
        - on_finish: Called when agent finishes
        - on_error: Called on error
        """
        self.callbacks = callbacks
    
    def run(self, user_prompt: str):
        """Run the agent with the given prompt."""
        if self.running:
            Logger.warn("Agent is already running")
            return
        
        if not self.client:
            Logger.error("Agent not initialized")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_agent_thread, args=(user_prompt,), daemon=True)
        self.thread.start()
    
    def _run_agent_thread(self, user_prompt: str):
        """Run the agent in a separate thread."""
        try:
            # Send system prompt on first run
            if not self.system_prompt_sent.is_set():
                self._call_callback('on_status', 'Sending System Prompt')
                response = self.client.send_prompt(self.system_prompt, self.session_id)
                actions = full_parse_sse(response)
                for action in actions:
                    if action['type'] == 'message_id':
                        self.parent_message_id = action['value']
                        self._call_callback('on_status', 'System Prompt has been sent')
                self.system_prompt_sent.set()
                Logger.success("System prompt sent")
            
            # Update status
            self._call_callback('on_status', 'Sending the prompt')
            
            # Run the agent loop
            self._run_agent_loop(user_prompt)
            
        except Exception as e:
            Logger.exception(f"Agent thread error: {e}")
            self._call_callback('on_error', str(e))
        finally:
            self.running = False
            self._call_callback('on_status', 'finished')
    
    def _run_agent_loop(self, prompt: str, max_iterations: int = 50):
        """Main agent loop - adapted from agent/main.py"""
        first=False
        iteration = 0
        while True:
            try:
                # Send prompt to DeepSeek API
                response = self.client.send_prompt(
                    prompt,
                    self.session_id,
                    parent_message_id=self.parent_message_id,
                )

                if first==False:
                    self._call_callback('on_status', 'running')
                    first=True

            except Exception as e:
                self._call_callback('on_error', f"Failed to send prompt: {e}")
                Logger.exception(f"Failed to send prompt: {e}")
                return
            
            Status = None
            actions = full_parse_sse(response)
            results = []
            
            for action in actions:
                if action['type'] == 'message_id':
                    self.parent_message_id = action['value']
                    continue
                
                elif action['type'] == 'status':
                    Status = action['value']
                    if Status not in ['finished','waiting']:
                        
                        self._call_callback('on_status', Status)
                    continue
                
                elif Status == 'finished':
                    desc = action['value']['arguments'].get('description', '')
                    self._call_callback('on_status', Status)
                    self._call_callback('on_finish', desc)
                    return
                
                elif action['type'] == 'action':
                    if Status == 'running' and action['value']['tool'] == 'user_response':
                        user_response = action['value']['arguments'].get('description', '')
                        self._call_callback('on_message', user_response)
                        continue
                    
                    elif Status == 'running':
                        tool = action['value']['tool']
                        args = action['value']['arguments']
                        
                        self._call_callback('on_tool', {'tool': tool, 'arguments': args})
                        
                        # Check mode and permission
                        mode = self.app.state.mode if hasattr(self.app, 'state') else "permission"
                        read_only_tools = ['read_file', 'list_directory', 'current_path', 'search_file', 'glob', 'grep_search', 'list_background_processes', 'read_background_output', 'enter_plan_mode']
                        if mode == "permission" and tool not in read_only_tools:
                            # Check if tool is in session allowed set
                            if tool in self.session_allowed_tools:
                                # Already allowed for this session
                                pass
                            else:
                                decision = self._request_permission(tool, args)
                                if decision == "reject":
                                    results.append({"status": "error", "tool": tool, "result": {"error_msg": "Tool execution rejected by user."}})
                                    prompt = f"Tool output:\n{json.dumps(results)}"
                                    continue
                                elif decision == "allow_session":
                                    self.session_allowed_tools.add(tool)
                                # else allow_once, proceed
                        
                        # Execute the tool with current workspace
                        workspace = self.app.state.workspace if hasattr(self.app, 'state') else None
                        result = execute_tool(tool, args, workspace=workspace)
                        results.append(result)
                        
                        # Prepare the next prompt with tool output
                        prompt = f"Tool output:\n{json.dumps(results)}"
                        continue
                    
                    elif Status == 'waiting':
                        if action['value']['tool'] == 'ask_user':
                            question = action['value']['arguments'].get('question', '')
                            
                            self._call_callback('on_status', 'finished')
                            self._call_callback('on_finish', question)
                            return

                            
                        continue
                else:
                    Logger.error(f"Unexpected status: {Status}")
                    # prompt="You must respond in json format"
                    # self._call_callback('on_status', 'There is an error. it respond in normal text not json')
                    return

            iteration += 1
            if iteration > max_iterations:
                self._call_callback('on_error', f'Agent exceeded maximum iterations ({max_iterations}). Stopping to prevent infinite loop.')
                return

    def _wait_for_response(self) -> Optional[str]:
        """Wait for the user to provide a response to the agent's question."""
        self.response_event.clear()
        self.pending_response = None
        
        # Wait for response (with timeout)
        if not self.response_event.wait(timeout=600):  # 10 minute timeout
            self._call_callback('on_error', 'Timeout waiting for user response')
            return None
        
        return self.pending_response

    def _request_permission(self, tool: str, args: dict) -> str:
        """Request user permission to execute a tool."""
        self.permission_response_event.clear()
        self.pending_permission_response = None
        self._call_callback('on_permission_request', {'tool': tool, 'args': args})
        # Wait for response (with timeout)
        if not self.permission_response_event.wait(timeout=600):
            self._call_callback('on_error', 'Timeout waiting for permission response')
            return "reject"
        decision = self.pending_permission_response
        if decision is None:
            return "reject"
        # Expect 'allow_once', 'allow_session', or 'reject' from the selector
        if decision in ("allow_once", "allow_session", "reject"):
            return decision
        # Fallback
        return "reject"
    
    def provide_response(self, response: str):
        """Provide a response to the agent's question from the UI."""
        self.pending_response = response
        self.response_event.set()

    def provide_permission_response(self, decision: str):
        """Provide a permission decision from the UI."""
        self.pending_permission_response = decision
        self.permission_response_event.set()
    
    def _call_callback(self, name: str, data: Any):
        """Call a registered callback safely from the thread."""
        if name in self.callbacks:
            callback = self.callbacks[name]
            try:
                # Use call_from_thread to safely update UI from another thread
                self.app.call_from_thread(callback, data)
            except Exception as e:
                Logger.error(f"Callback error '{name}': {e}")
    
    def fetch_chats_in_thread(self, callback):
        """Fetch chat sessions in a background thread.
        
        Args:
            callback: Called on the main thread with (success: bool, data: list or str).
        """
        def run_fetch():
            try:
                chats = self.client.fetch_chats()
                self.app.call_from_thread(callback, True, chats)
            except Exception as e:
                Logger.error(f"Failed to fetch chats: {e}")
                self.app.call_from_thread(callback, False, str(e))
        thread = threading.Thread(target=run_fetch, daemon=True)
        thread.start()
    
    def change_chat_in_thread(self, chat_id: str, callback):
        """Run change_chat in a background thread to avoid blocking the UI.
        
        Args:
            chat_id: The new chat session ID.
            callback: Called on the main thread with (success: bool, message: str).
        """
        def run_change():
            success = self.change_chat(chat_id)
            if success:
                msg = f"Switched to chat session: {chat_id}"
            else:
                msg = f"Failed to switch to chat session: {chat_id}. Check logs."
            self.app.call_from_thread(callback, success, msg)
        thread = threading.Thread(target=run_change, daemon=True)
        thread.start()
    
    def change_chat(self, chat_id: str) -> bool:
        """Switch to a different chat session.
        
        Args:
            chat_id: The new chat session ID.
            
        Returns:
            True if successful, False otherwise.
        """
        if not self.client:
            Logger.error("Agent not initialized")
            return False
        try:
            self.session_id = chat_id
            self.parent_message_id = self.client.get_last_message_id(chat_id)
            self.system_prompt_sent.set()  # Assume system prompt already sent in existing chat
            Logger.success(f"Switched to chat session: {chat_id}, parent_message_id: {self.parent_message_id}")
            return True
        except Exception as e:
            Logger.error(f"Failed to change chat session: {e}")
            return False
    
    def cancel(self):
        """Cancel the running agent."""
        if self.running:
            # Signal cancellation by providing a None response
            self.pending_response = None
            self.response_event.set()
            self.running = False
            Logger.info("Agent cancelled")
